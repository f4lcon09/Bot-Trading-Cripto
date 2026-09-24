#!/usr/bin/env python3
"""
COLETOR_EXECUCAO.PY - Fase 1.

NAO ENVIA ORDEM. Nao assina nada, nao le chave, nao toca em carteira.
Le o livro e mede quanto custaria executar. Essa e a unica pergunta
que nenhum dado historico responde e que nenhuma fonte publica
publicou.

  python coletor_execucao.py

Arquitetura: processo unico, WebSocket, sem polling REST em loop.
  1. conecta em wss://api.hyperliquid.xyz/ws
  2. assina candle(1m) e l2Book para os 18 majors
  3. buffer circular dos ultimos 90 fechamentos por simbolo
  4. vela fecha com retorno em [-3.0%, -1.5%] -> registra evento e
     congela o snapshot do livro naquele instante
  5. caminha o livro: preco medio de preenchimento de US$ 20/50/200
  6. 60 minutos depois, marca a saida e caminha o lado da venda
  7. grava sigma local, lev diagnostica, MAE e MFE da janela

Silencio tatico: o terminal imprime apenas eventos detectados e erros
definitivos de API. Todo o resto vai para arquivo.

O gatilho vem de sinal.py, o MESMO modulo que a analise historica usa.
Isso e o que faz o Gate 2 (paridade de sinal) ser estrutural em vez de
uma coincidencia que se torce para dar certo.
"""
import asyncio
import csv
import json
import os
import signal
import sys
import time
from collections import deque
from datetime import datetime, timezone

import websockets

from config import (DIR_EXECUCAO, HORIZONTE_MIN, JANELA_SIGMA, MAJORS,
                    NIVEIS_LIVRO, NOCIONAIS_TESTE, OFFSETS_LIVRO_MS,
                    PING_INTERVALO_S, WS_URL)
from fisica_v2 import max_safe_leverage
from relogio import duracao, humano, offset_local
from sinal import (MS_POR_MINUTO, eh_gatilho, minutos_contiguos, ret_1m,
                   sigma_pre_gatilho)

TAM_BUFFER = 90
RECONEXAO_INICIAL_S = 2.0
RECONEXAO_MAX_S = 60.0

# --------------------------------------------------------------------
# CONTRATO DO CSV - ordem exata da especificacao. Nao reordenar, nao
# acrescentar coluna. Analise a jusante depende desta ordem.
#
# UNIDADES (a especificacao mistura as duas, entao fica explicito):
#   ret_1m       PERCENTO   (-2.1 = queda de 2,1%)
#   sigma_30m    FRACAO por minuto (0.0015 = 0,15%/min), igual ao
#                fisica_v2. Para comparar com a tabela de quartis da
#                especificacao, multiplique por 100.
#   slip_*       PERCENTO, sempre positivo = custo
#   mae/mfe/ret  PERCENTO
# --------------------------------------------------------------------
COLUNAS_BASE = [
    "ts_evento", "symbol", "ret_1m", "sigma_30m", "lev_sugerida",
    "mid_evento",
    "fill_compra_20", "fill_compra_50", "fill_compra_200",
    "slip_compra_20", "slip_compra_50", "slip_compra_200",
    "prof_bid_10n", "prof_ask_10n",
    "ts_saida", "mid_saida",
    "slip_venda_20", "slip_venda_50", "slip_venda_200",
    "mae_pct", "mfe_pct", "ret_60m_pct",
]


def _rot(ms):
    """Sufixo de coluna para um offset: 200 -> t200, 1000 -> t1s."""
    return f"t{ms}" if ms < 1000 else f"t{ms // 1000}s"


# Snapshots escalonados: mid e slippage de compra em cada instante.
# A degradacao contra o snapshot do gatilho e a medida do vies.
COLUNAS_ESCALONADAS = []
for _o in OFFSETS_LIVRO_MS:
    COLUNAS_ESCALONADAS.append(f"mid_{_rot(_o)}")
    for _n in NOCIONAIS_TESTE:
        COLUNAS_ESCALONADAS.append(f"slip_compra_{int(_n)}_{_rot(_o)}")

# Cadeia de latencia. `ack_ts` e `fill_ts` ficam VAZIOS enquanto nao
# houver envio de ordem - reservados de proposito, para que o contrato
# do CSV nao mude no dia em que houver dinheiro.
COLUNAS_LATENCIA = [
    "candle_close_ts", "signal_detected_ts", "decision_ts",
    "order_ready_ts", "ack_ts", "fill_ts",
    "lat_deteccao_ms", "lat_decisao_ms", "lat_pronta_ms",
]

COLUNAS = COLUNAS_BASE + COLUNAS_ESCALONADAS + COLUNAS_LATENCIA
COLUNAS_DESCONEXAO = ["ts_inicio", "ts_fim", "duracao_seg", "motivo"]


def agora_ms():
    return int(time.time() * 1000)


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(
        timespec="seconds")


def dia(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d")


def anexar(caminho, colunas, linha):
    """
    Uma linha no contrato: UTF-8, cabecalho presente, sem espaco apos
    a virgula, contagem de campos fixa. Escreve e fecha - o processo
    roda duas semanas e nao pode perder dado num kill.
    """
    novo = not os.path.exists(caminho)
    with open(caminho, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        if novo:
            w.writerow(colunas)
        w.writerow(linha)


def caminhar_livro(niveis, nocional_usd):
    """
    Preco medio de preenchimento de uma ordem a mercado de
    `nocional_usd`, caminhando os niveis na ordem em que vem.

    `niveis` e a lista de {"px","sz"} do lado que SERA CONSUMIDO:
    asks para uma compra, bids para uma venda.

    Devolve None se o livro visivel nao cobre o nocional - livro raso
    e um resultado, nao um erro, e inventar preco ai seria mentir
    sobre o custo exato que a Fase 1 existe para medir.
    """
    restante = float(nocional_usd)
    custo = 0.0
    qtd = 0.0
    for nivel in niveis:
        try:
            px = float(nivel["px"])
            sz = float(nivel["sz"])
        except (KeyError, TypeError, ValueError):
            continue
        if px <= 0 or sz <= 0:
            continue
        disponivel = px * sz
        usar = min(disponivel, restante)
        qtd += usar / px
        custo += usar
        restante -= usar
        if restante <= 1e-9:
            break
    if restante > 1e-9 or qtd <= 0:
        return None
    return custo / qtd


def profundidade(niveis, n=NIVEIS_LIVRO):
    """Nocional somado nos primeiros n niveis."""
    total = 0.0
    for nivel in niveis[:n]:
        try:
            total += float(nivel["px"]) * float(nivel["sz"])
        except (KeyError, TypeError, ValueError):
            continue
    return total


def mid_do_livro(bids, asks):
    if not bids or not asks:
        return None
    try:
        return (float(bids[0]["px"]) + float(asks[0]["px"])) / 2.0
    except (KeyError, TypeError, ValueError):
        return None


def fmt(x, casas=6):
    return "" if x is None else f"{x:.{casas}f}"


class Coletor:
    def __init__(self):
        self.closes = {s: deque(maxlen=TAM_BUFFER) for s in MAJORS}
        self.times = {s: deque(maxlen=TAM_BUFFER) for s in MAJORS}
        self.vela_aberta = {s: None for s in MAJORS}   # ultima vela em curso
        self.livro = {s: None for s in MAJORS}         # snapshot mais recente
        self.pendentes = []                            # eventos aguardando saida
        self.desconectado_desde = None
        self.parar = False
        os.makedirs(DIR_EXECUCAO, exist_ok=True)
        self.caminho_pendentes = os.path.join(DIR_EXECUCAO, "pendentes.json")
        self.caminho_pulso = os.path.join(DIR_EXECUCAO, "pulso_execucao.txt")
        self._carregar_pendentes()
        self._registrar_lacuna_de_subida()

    # ---------------- pulso e lacuna de processo ausente ------------
    def _bater_pulso(self):
        """
        Marca em disco que o processo estava vivo neste minuto.

        Sem isto, um kill de fora nao passa pelo handler de sinal e a
        janela em que o coletor esteve ausente NAO aparece no CSV de
        desconexoes — a analise leria ausencia de evento como ausencia
        de sinal. Aconteceu com o coletor de contexto em 22/09/2026:
        8h37 sumiram sem deixar linha.

        O coletor de execucao e ainda mais exposto, porque so escreve
        quando ha evento (~2 por dia): sem pulso, nao existe marca
        nenhuma de que ele esteve de pe.
        """
        try:
            with open(self.caminho_pulso, "w", encoding="utf-8") as f:
                f.write(str(agora_ms()))
        except OSError:
            pass

    def _registrar_lacuna_de_subida(self):
        """Compara o ultimo pulso com agora e grava a janela ausente."""
        try:
            with open(self.caminho_pulso, "r", encoding="utf-8") as f:
                ultimo = int(f.read().strip())
        except (OSError, ValueError):
            self._bater_pulso()
            return
        agora = agora_ms()
        if agora - ultimo < 2 * MS_POR_MINUTO:
            self._bater_pulso()
            return
        dur = (agora - ultimo) / 1000.0
        anexar(os.path.join(DIR_EXECUCAO, f"desconexoes_{dia(agora)}.csv"),
               COLUNAS_DESCONEXAO,
               [iso(ultimo), iso(agora), f"{dur:.1f}",
                "processo ausente (lacuna detectada na subida)"])
        print(f"LACUNA: {duracao(dur)} sem coletor, de "
              f"{humano(ultimo)} a {humano(agora)}. Registrada em "
              f"desconexoes.", flush=True)
        self._bater_pulso()

    # ---------------- persistencia de eventos em voo ----------------
    def _carregar_pendentes(self):
        """
        Um evento espera 60 minutos pela saida. Se o processo morre
        nesse intervalo, o evento se perde - e a Fase 1 inteira tem
        uns 30 eventos. Por isso eles vao para disco na deteccao.
        """
        if os.path.exists(self.caminho_pendentes):
            try:
                with open(self.caminho_pendentes, "r", encoding="utf-8") as f:
                    self.pendentes = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.pendentes = []

    def _salvar_pendentes(self):
        try:
            with open(self.caminho_pendentes, "w", encoding="utf-8") as f:
                json.dump(self.pendentes, f, indent=1)
        except OSError:
            pass

    # ---------------- registro de desconexao ----------------
    def marcar_queda(self):
        if self.desconectado_desde is None:
            self.desconectado_desde = agora_ms()

    def marcar_volta(self, motivo):
        if self.desconectado_desde is None:
            return
        fim = agora_ms()
        dur = (fim - self.desconectado_desde) / 1000.0
        caminho = os.path.join(DIR_EXECUCAO, f"desconexoes_{dia(fim)}.csv")
        anexar(caminho, COLUNAS_DESCONEXAO,
               [iso(self.desconectado_desde), iso(fim), f"{dur:.1f}", motivo])
        self.desconectado_desde = None

    # ---------------- ingestao ----------------
    def _finalizar_vela(self, sym, vela):
        """
        Uma vela de 1m fechou. Atualiza buffers, testa o gatilho e
        alimenta MAE/MFE dos eventos em voo daquele simbolo.
        """
        try:
            t = int(vela["t"])
            c = float(vela["c"])
            h = float(vela["h"])
            l = float(vela["l"])
        except (KeyError, TypeError, ValueError):
            return
        if c <= 0 or h <= 0 or l <= 0:
            return

        if self.times[sym] and int(self.times[sym][-1]) == t:
            return   # ja contabilizada

        anterior_t = self.times[sym][-1] if self.times[sym] else None
        anterior_c = self.closes[sym][-1] if self.closes[sym] else None

        # excursao dos eventos em voo, antes de o buffer avancar
        self._atualizar_excursoes(sym, h, l, t)

        self.times[sym].append(t)
        self.closes[sym].append(c)

        if anterior_t is None or anterior_c is None:
            return
        if not minutos_contiguos(int(anterior_t), t):
            return   # buraco na serie: nao e retorno de 1 minuto

        r = ret_1m(float(anterior_c), c)
        if not eh_gatilho(r):
            return
        if len(self.closes[sym]) < JANELA_SIGMA + 2:
            return   # sem historico para o sigma; nao inventa numero

        self._registrar_evento(sym, t, r)

    def _atualizar_excursoes(self, sym, high, low, t):
        for p in self.pendentes:
            if p["symbol"] != sym or p["entrada"] <= 0:
                continue
            if t <= p["t_evento"] or t > p["t_saida"]:
                continue
            p["mae"] = min(p["mae"], low / p["entrada"] - 1.0)
            p["mfe"] = max(p["mfe"], high / p["entrada"] - 1.0)

    def _registrar_evento(self, sym, t, r):
        # Cadeia de latencia local. Medida agora, nao reconstruida
        # depois: a diferenca entre o fechamento da vela e o instante
        # em que o sinal foi visto e o unico pedaco de latencia que
        # este processo controla, e e o que some se nao for cravado
        # no momento.
        ts_detectado = agora_ms()
        livro = self.livro[sym]
        if livro is None:
            print(f"[{iso(t)}] {sym} gatilho {r*100:+.2f}% - SEM LIVRO, "
                  f"evento perdido", flush=True)
            return

        bids, asks = livro["bids"], livro["asks"]
        mid = mid_do_livro(bids, asks)
        if mid is None:
            print(f"[{iso(t)}] {sym} gatilho {r*100:+.2f}% - LIVRO VAZIO, "
                  f"evento perdido", flush=True)
            return

        # sigma das 30 velas ANTERIORES ao gatilho (exclusive): o
        # buffer ja contem a vela-gatilho, entao corta-se o ultimo
        closes_antes = list(self.closes[sym])[:-1]
        sigma = sigma_pre_gatilho(closes_antes)
        lev = max_safe_leverage(sigma) if sigma > 0 else 0

        ts_decisao = agora_ms()
        fills = {n: caminhar_livro(asks, n) for n in NOCIONAIS_TESTE}
        entrada = float(self.closes[sym][-1])

        evento = {
            "symbol": sym,
            "t_evento": t,
            "t_saida": t + HORIZONTE_MIN * MS_POR_MINUTO,
            "ret_1m": r * 100.0,
            "sigma": sigma,
            "lev": int(lev),
            "mid_evento": mid,
            "fills": {str(n): fills[n] for n in NOCIONAIS_TESTE},
            "prof_bid": profundidade(bids),
            "prof_ask": profundidade(asks),
            "entrada": entrada,
            "mae": 0.0,
            "mfe": 0.0,
            # snapshots escalonados, preenchidos pela tarefa assincrona
            "escalonados": {},
            # cadeia de latencia; ack e fill ficam vazios sem envio
            "candle_close_ms": t + MS_POR_MINUTO,
            "detectado_ms": ts_detectado,
            "decisao_ms": ts_decisao,
            "pronta_ms": agora_ms(),
        }
        self.pendentes.append(evento)
        self._salvar_pendentes()

        # Agenda as capturas escalonadas. Se nao houver laco rodando
        # (teste sincrono), o evento simplesmente fica sem elas.
        try:
            asyncio.get_running_loop()
            asyncio.create_task(self._capturar_escalonado(evento))
        except RuntimeError:
            pass

        f50 = fills[50.0]
        slip50 = (f50 / mid - 1.0) * 100.0 if f50 else None
        print(f"[{humano(t)}] {sym:<5} ret {r*100:+.2f}%  "
              f"sigma {sigma*100:.2f}%/min  lev_diag {lev}x  "
              f"mid {mid:.6g}  slip$50 "
              f"{'n/d' if slip50 is None else f'{slip50:+.3f}%'}  "
              f"-> saida {humano(evento['t_saida'])}", flush=True)

    async def _capturar_escalonado(self, evento):
        """
        Re-fotografa o livro em +200 ms, +500 ms, +1 s e +5 s depois do
        gatilho, e recalcula o preenchimento de cada tamanho.

        A degradacao contra o snapshot do instante zero e a medida
        direta da velocidade com que o livro foge — o componente
        dominante do slippage sob estresse, e a unica parte do vies do
        caminhamento que da para quantificar sem enviar ordem.
        """
        sym = evento["symbol"]
        t0 = agora_ms()
        for off in OFFSETS_LIVRO_MS:
            alvo = t0 + off
            atraso = (alvo - agora_ms()) / 1000.0
            if atraso > 0:
                await asyncio.sleep(atraso)
            livro = self.livro[sym]
            if livro is None:
                continue
            bids, asks = livro["bids"], livro["asks"]
            mid = mid_do_livro(bids, asks)
            if mid is None:
                continue
            registro = {"mid": mid, "slip": {}}
            for n in NOCIONAIS_TESTE:
                f = caminhar_livro(asks, n)
                registro["slip"][str(n)] = (
                    (f / mid - 1.0) * 100.0 if f else None)
            evento["escalonados"][str(off)] = registro
        self._salvar_pendentes()

    def _fechar_vencidos(self):
        """Eventos cujo horizonte de 60 minutos expirou."""
        agora = agora_ms()
        vencidos = [p for p in self.pendentes if agora >= p["t_saida"]]
        for p in vencidos:
            self._gravar_saida(p)
            self.pendentes.remove(p)
        if vencidos:
            self._salvar_pendentes()

    def _gravar_saida(self, p):
        sym = p["symbol"]
        livro = self.livro[sym]
        bids = livro["bids"] if livro else []
        asks = livro["asks"] if livro else []
        mid_saida = mid_do_livro(bids, asks)

        # venda consome os bids; slippage positivo = custo
        slips_venda = {}
        for n in NOCIONAIS_TESTE:
            f = caminhar_livro(bids, n)
            slips_venda[n] = ((1.0 - f / mid_saida) * 100.0
                              if (f and mid_saida) else None)

        slips_compra = {}
        for n in NOCIONAIS_TESTE:
            f = p["fills"].get(str(n))
            slips_compra[n] = ((f / p["mid_evento"] - 1.0) * 100.0
                               if f else None)

        # retorno de preco usa mid a mid: o fill ja esta nas colunas de
        # slippage, e misturar os dois esconde exatamente o custo que
        # este coletor existe para isolar
        ret60 = ((mid_saida / p["mid_evento"] - 1.0) * 100.0
                 if mid_saida else None)

        linha = [
            iso(p["t_evento"]), sym, f"{p['ret_1m']:.4f}",
            f"{p['sigma']:.8f}", p["lev"], fmt(p["mid_evento"]),
            fmt(p["fills"].get("20.0")), fmt(p["fills"].get("50.0")),
            fmt(p["fills"].get("200.0")),
            fmt(slips_compra[20.0], 4), fmt(slips_compra[50.0], 4),
            fmt(slips_compra[200.0], 4),
            f"{p['prof_bid']:.2f}", f"{p['prof_ask']:.2f}",
            iso(p["t_saida"]), fmt(mid_saida),
            fmt(slips_venda[20.0], 4), fmt(slips_venda[50.0], 4),
            fmt(slips_venda[200.0], 4),
            f"{p['mae']*100:.4f}", f"{p['mfe']*100:.4f}", fmt(ret60, 4),
        ]

        # snapshots escalonados; vazio onde o livro nao estava
        # disponivel naquele instante
        esc = p.get("escalonados") or {}
        for off in OFFSETS_LIVRO_MS:
            reg = esc.get(str(off))
            if not reg:
                linha.extend([""] * (1 + len(NOCIONAIS_TESTE)))
                continue
            linha.append(fmt(reg.get("mid")))
            for n in NOCIONAIS_TESTE:
                linha.append(fmt((reg.get("slip") or {}).get(str(n)), 4))

        # cadeia de latencia; ack_ts e fill_ts reservados vazios
        cc = p.get("candle_close_ms")
        det = p.get("detectado_ms")
        dec = p.get("decisao_ms")
        pr = p.get("pronta_ms")
        linha.extend([
            iso(cc) if cc else "", iso(det) if det else "",
            iso(dec) if dec else "", iso(pr) if pr else "",
            "", "",
            str(det - cc) if (det and cc) else "",
            str(dec - det) if (dec and det) else "",
            str(pr - dec) if (pr and dec) else "",
        ])

        caminho = os.path.join(DIR_EXECUCAO,
                               f"execucao_{dia(p['t_evento'])}.csv")
        anexar(caminho, COLUNAS, linha)

        ida_volta = None
        if slips_compra[50.0] is not None and slips_venda[50.0] is not None:
            ida_volta = slips_compra[50.0] + slips_venda[50.0]
        print(f"[{humano(p['t_saida'])}] {sym:<5} SAIDA  "
              f"ret {'n/d' if ret60 is None else f'{ret60:+.2f}%'}  "
              f"MAE {p['mae']*100:+.2f}%  MFE {p['mfe']*100:+.2f}%  "
              f"ida+volta$50 "
              f"{'n/d' if ida_volta is None else f'{ida_volta:.3f}%'}",
              flush=True)

    # ---------------- mensagens ----------------
    def _tratar(self, msg):
        canal = msg.get("channel")
        if canal == "candle":
            d = msg.get("data")
            velas = d if isinstance(d, list) else [d]
            for vela in velas:
                if not isinstance(vela, dict):
                    continue
                sym = vela.get("s")
                if sym not in self.closes:
                    continue
                try:
                    t_vela = int(vela["t"])
                except (KeyError, TypeError, ValueError):
                    continue   # vela malformada nao derruba a conexao
                aberta = self.vela_aberta[sym]
                # a HL republica a vela em curso; ela so esta fechada
                # quando aparece uma com timestamp de abertura maior
                if aberta is not None and t_vela > int(aberta["t"]):
                    self._finalizar_vela(sym, aberta)
                self.vela_aberta[sym] = vela
        elif canal == "l2Book":
            d = msg.get("data") or {}
            sym = d.get("coin")
            niveis = d.get("levels")
            if sym in self.livro and isinstance(niveis, list) and len(niveis) == 2:
                self.livro[sym] = {"bids": niveis[0] or [],
                                   "asks": niveis[1] or [],
                                   "time": d.get("time")}
        elif canal == "error":
            print(f"ERRO DA API: {msg.get('data')}", file=sys.stderr,
                  flush=True)

    # ---------------- laco principal ----------------
    async def _assinar(self, ws):
        for sym in MAJORS:
            await ws.send(json.dumps({
                "method": "subscribe",
                "subscription": {"type": "candle", "coin": sym,
                                 "interval": "1m"}}))
            await ws.send(json.dumps({
                "method": "subscribe",
                "subscription": {"type": "l2Book", "coin": sym}}))

    async def _ping(self, ws):
        while True:
            await asyncio.sleep(PING_INTERVALO_S)
            await ws.send(json.dumps({"method": "ping"}))

    async def _relogio(self):
        """Fecha eventos vencidos mesmo se o simbolo estiver quieto."""
        while not self.parar:
            await asyncio.sleep(5)
            self._fechar_vencidos()
            self._bater_pulso()

    async def rodar(self):
        espera = RECONEXAO_INICIAL_S
        asyncio.create_task(self._relogio())

        while not self.parar:
            try:
                async with websockets.connect(
                        WS_URL, ping_interval=None, max_size=None) as ws:
                    self.marcar_volta("reconectado")
                    await self._assinar(ws)
                    espera = RECONEXAO_INICIAL_S
                    tarefa_ping = asyncio.create_task(self._ping(ws))
                    try:
                        async for bruto in ws:
                            if self.parar:
                                break
                            try:
                                self._tratar(json.loads(bruto))
                            except json.JSONDecodeError:
                                continue
                    finally:
                        tarefa_ping.cancel()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if self.parar:
                    break
                self.marcar_queda()
                print(f"WS caiu ({type(e).__name__}: {e}), reconectando em "
                      f"{espera:.0f}s", file=sys.stderr, flush=True)
                await asyncio.sleep(espera)
                espera = min(espera * 2, RECONEXAO_MAX_S)
            else:
                if not self.parar:
                    self.marcar_queda()
                    await asyncio.sleep(espera)
                    espera = min(espera * 2, RECONEXAO_MAX_S)

        self.marcar_volta("encerrado")
        self._salvar_pendentes()


def main():
    col = Coletor()

    def encerrar(*_):
        col.parar = True

    try:
        signal.signal(signal.SIGINT, encerrar)
        signal.signal(signal.SIGTERM, encerrar)
    except (ValueError, AttributeError):
        pass

    print(f"COLETOR DE EXECUCAO  {len(MAJORS)} majors  "
          f"gatilho [-3.0%, -1.5%] 1m  saida {HORIZONTE_MIN} min")
    print(f"horarios: seu fuso ({offset_local()}) primeiro, UTC entre "
          f"parenteses. O CSV grava UTC puro.")
    print(f"destino: {DIR_EXECUCAO}")
    print("NAO ENVIA ORDEM. Silencio tatico: so eventos e erros de API.\n",
          flush=True)
    if col.pendentes:
        print(f"{len(col.pendentes)} evento(s) em voo recuperados do disco\n",
              flush=True)

    try:
        asyncio.run(col.rodar())
    except KeyboardInterrupt:
        pass
    print("\nencerrado.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
