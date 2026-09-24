#!/usr/bin/env python3
"""
COLETOR_CONTEXTO.PY - poll do metaAndAssetCtxs, uma vez por minuto.

PRIORIDADE MAXIMA entre os coletores. Open interest, funding e mark
price NAO tem historico em fonte nenhuma: a Binance retem 1 mes a 5
minutos de granularidade, e a Hyperliquid so expoe o snapshot atual.
Velas da para comprar depois; isto nao. Cada minuto sem rodar e
perdido para sempre.

  python coletor_contexto.py

NAO envia ordem, nao le credencial. `POST /info` com
{"type":"metaAndAssetCtxs"} e publico.

--------------------------------------------------------------------
O QUE ISTO FECHA
--------------------------------------------------------------------
  openInterest   o instrumento para separar queda-por-liquidacao de
                 queda-por-reprecificacao. Requisito de coleta, nao
                 analise retrospectiva: so produz evidencia depois de
                 meses de acumulo.
  funding        estava subavaliado por uma fonte hedgeada
  markPx/oraclePx/midPx
                 qual preco dispara o stop, com a divergencia medida
                 em vez de assumida
  impactPxs      preco de impacto dos dois lados, gratis no mesmo
                 payload

Alinhado ao minuto UTC para casar com as velas de 1m sem interpolar.
--------------------------------------------------------------------
"""
import csv
import os
import signal
import sys
import time
from datetime import datetime, timezone

import requests

from config import API_INFO, DIR_EXECUCAO, MAJORS
from relogio import duracao, humano, offset_local

MS_POR_MINUTO = 60_000
BACKOFF_INICIAL_S = 2.0
BACKOFF_MAX_S = 60.0

# --------------------------------------------------------------------
# is_delisted vem do `universe`, nao do contexto, e e DECLARADO pela
# corretora. Acrescentado em 23/09/2026, depois de o TON aparecer com
# openInterest=0, midPx vazio e markPx congelado em 1,8014 por 22 polls
# seguidos.
#
# A tentacao era inferir morte de mercado a partir dos zeros. Errado
# pelo mesmo motivo de sempre: e reconstruir com heuristica uma
# informacao que a fonte ja entrega explicita. O `universe` diz
# isDelisted=True para o TON e False para os outros 17.
#
# Os zeros continuam sendo checados, como segunda linha: um simbolo
# pode estar morrendo sem ainda ter sido marcado.
# --------------------------------------------------------------------
COLUNAS = [
    "ts", "symbol", "open_interest", "funding", "mark_px", "oracle_px",
    "mid_px", "premium", "impact_bid", "impact_ask", "day_ntl_vlm",
    "prev_day_px", "is_delisted", "max_leverage",
]

COLUNAS_FALHA = ["ts_inicio", "ts_fim", "minutos_perdidos", "motivo"]


# --------------------------------------------------------------------
# INSTANCIA UNICA
#
# O lancador .vbs usa Run(cmd, 0, False): o wscript retorna na hora e a
# tarefa do Agendador TERMINA, deixando o python orfao dela. Isso quebra
# o MultipleInstancesPolicy=IgnoreNew, que olha a tarefa e nao o
# processo — e o gatilho de 10 minutos passaria a empilhar um poller
# novo a cada disparo, todos gravando no mesmo CSV.
#
# Dois pollers escrevendo o mesmo arquivo produzem timestamp duplicado
# por simbolo, que e justamente o criterio que o validador usa para
# rebaixar uma serie. O dado ficaria corrompido em silencio.
#
# O lock e um arquivo travado com msvcrt. O sistema operacional o
# libera quando o processo morre, de qualquer jeito que morra — kill
# incluido. Nao ha PID obsoleto para limpar.
# --------------------------------------------------------------------
_TRAVA = None


def caminho_log():
    """
    Resolvido A CADA CHAMADA, nunca no import.

    A versao anterior era `CAMINHO_LOG = os.path.join(DIR_EXECUCAO,
    ...)` no topo do modulo. Um teste que remenda DIR_EXECUCAO para um
    diretorio temporario NAO mudava CAMINHO_LOG, entao a linha do CSV
    ia para o temp e a linha do LOG ia para producao.

    O resultado foram quatro lacunas fantasma de 2h57 no poller.log de
    23/09, cada uma afirmando "Registrada em contexto_falhas_X.csv"
    sobre uma linha que nunca existiu naquele arquivo. O log declarava
    uma gravacao que nao aconteceu.

    Pior: o vazamento foi conferido e declarado limpo, porque so o CSV
    foi contado. Duas saidas, uma verificada.
    """
    return os.path.join(DIR_EXECUCAO, "poller.log")


def aviso(msg):
    """
    Imprime e anexa ao poller.log, abrindo e fechando a cada linha.

    NAO use redirecionamento de shell (`>> log`) para isto. O primeiro
    processo manteria o arquivo aberto pela vida inteira, e qualquer
    outro lancamento falharia no PROPRIO redirecionamento — antes de
    chegar ao python, antes da trava, com o .bat saindo em erro e
    disparando RestartOnFailure em loop. Aconteceu em 23/09/2026, e so
    apareceu porque o teste contou as linhas do log e achou uma
    "subida" onde deveria haver quatro.

    Mesma disciplina de anexar() nos CSVs: abre, escreve, fecha.
    """
    print(msg, flush=True)
    try:
        os.makedirs(DIR_EXECUCAO, exist_ok=True)
        with open(caminho_log(), "a", encoding="utf-8") as f:
            f.write(msg + chr(10))
    except OSError:
        pass


def obter_trava():
    """
    True se esta instancia pegou a trava; False se ja ha outra de pe.

    A trava e um byte travado com msvcrt no poller.lock. O sistema
    operacional a libera quando o processo morre, de qualquer jeito
    que morra — kill incluido. Nao ha PID obsoleto para limpar.
    """
    global _TRAVA
    caminho = os.path.join(DIR_EXECUCAO, "poller.lock")
    try:
        _TRAVA = open(caminho, "a+")
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(_TRAVA.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(_TRAVA.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        if _TRAVA is not None:
            _TRAVA.close()
            _TRAVA = None
        return False
    return True


def agora_ms():
    return int(time.time() * 1000)


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(
        timespec="seconds")


def dia(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d")


def anexar(caminho, colunas, linhas):
    """Contrato: UTF-8, cabecalho presente, sem espaco apos virgula, LF."""
    novo = not os.path.exists(caminho)
    with open(caminho, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        if novo:
            w.writerow(colunas)
        for ln in linhas:
            w.writerow(ln)


def puxar(sessao):
    """
    Devolve {symbol: ctx} para os 18 majors, ou None em falha.

    `universe` e `ctxs` vem alinhados por indice - e o unico vinculo
    entre nome e contexto. Nao assumir ordem fixa entre chamadas: a
    HL lista novos ativos, e um indice decorado silenciosamente
    atribuiria o OI de um ativo a outro.
    """
    r = sessao.post(API_INFO, json={"type": "metaAndAssetCtxs"}, timeout=20)
    r.raise_for_status()
    d = r.json()
    if not isinstance(d, list) or len(d) != 2:
        raise ValueError(f"formato inesperado: {type(d)}")
    universo = d[0].get("universe") or []
    ctxs = d[1] or []
    if len(universo) != len(ctxs):
        raise ValueError(f"universe={len(universo)} != ctxs={len(ctxs)}")
    fora = {}
    for ativo, ctx in zip(universo, ctxs):
        nome = ativo.get("name")
        if nome in MAJORS and isinstance(ctx, dict):
            # o contexto nao carrega isDelisted; ele vem do universe,
            # e so o par (ativo, ctx) tem os dois
            fora[nome] = (ctx, ativo)
    return fora


def mercado_invalido(ctx, ativo):
    """
    (invalido, motivo) para um simbolo neste minuto.

    Ausencia de mercado NAO e medicao de mercado. Um openInterest de
    zero num simbolo deslistado nao e "OI baixo": e a ausencia do
    instrumento. Tratar os dois como o mesmo numero e a mesma familia
    de erro do poller que perdia 8h37 sem registrar — ausencia de
    observacao lida como observacao.

    Primeiro criterio declarado, depois os inferidos.
    """
    if ativo.get("isDelisted") is True:
        return True, "isDelisted"
    try:
        if float(ctx.get("openInterest") or 0) <= 0:
            return True, "openInterest<=0"
    except (TypeError, ValueError):
        return True, "openInterest ilegivel"
    if ctx.get("midPx") in (None, ""):
        return True, "midPx ausente"
    try:
        if float(ctx.get("dayNtlVlm") or 0) <= 0:
            return True, "dayNtlVlm<=0"
    except (TypeError, ValueError):
        return True, "dayNtlVlm ilegivel"
    return False, ""


def linha(ts, sym, ctx, ativo):
    imp = ctx.get("impactPxs") or [None, None]
    if not isinstance(imp, list) or len(imp) != 2:
        imp = [None, None]

    def g(k):
        v = ctx.get(k)
        return "" if v is None else v

    return [iso(ts), sym, g("openInterest"), g("funding"), g("markPx"),
            g("oraclePx"), g("midPx"), g("premium"),
            "" if imp[0] is None else imp[0],
            "" if imp[1] is None else imp[1],
            g("dayNtlVlm"), g("prevDayPx"),
            "1" if ativo.get("isDelisted") is True else "0",
            "" if ativo.get("maxLeverage") is None else ativo["maxLeverage"]]


def ultimo_registrado_ms():
    """
    Maior `ts` ja gravado, varrendo os CSVs de contexto mais recentes.

    Existe por causa de 22/09/2026: o processo foi morto de fora, nao
    passou pelo handler de sinal, e 8h37 de coleta sumiram SEM deixar
    linha no arquivo de falhas. A lacuna ficou invisivel no dado — que
    e precisamente o que o arquivo de falhas existe para impedir.

    Encerramento limpo registra a falha na saida. Kill nao registra
    nada. Entao a deteccao tem de acontecer tambem na SUBIDA, olhando
    o que esta em disco, nunca so o que aconteceu em memoria.
    """
    if not os.path.isdir(DIR_EXECUCAO):
        return None
    arquivos = sorted(f for f in os.listdir(DIR_EXECUCAO)
                      if f.startswith("contexto_") and f.endswith(".csv")
                      and "falhas" not in f)
    for nome in reversed(arquivos[-3:]):
        maior = None
        try:
            with open(os.path.join(DIR_EXECUCAO, nome), "r",
                      encoding="utf-8", newline="") as f:
                leitor = csv.reader(f)
                cab = next(leitor, None)
                # Basta a primeira coluna ser o timestamp. Exigir o
                # cabecalho inteiro faria uma mudanca de esquema cegar
                # o detector para todos os arquivos anteriores — e ele
                # devolveria None em silencio, que e precisamente o
                # modo de falha que ele existe para impedir. Aconteceu
                # em 23/09/2026 ao acrescentar is_delisted.
                if not cab or cab[0] != "ts":
                    continue
                for linha in leitor:
                    if not linha:
                        continue
                    try:
                        ms = int(datetime.fromisoformat(
                            linha[0]).timestamp() * 1000)
                    except (ValueError, IndexError):
                        continue
                    if maior is None or ms > maior:
                        maior = ms
        except OSError:
            continue
        if maior is not None:
            return maior
    return None


class Coletor:
    def __init__(self):
        self.parar = False
        self.ultimo_ok_ms = None
        self.falha_desde = None
        os.makedirs(DIR_EXECUCAO, exist_ok=True)
        self._registrar_lacuna_de_subida()

    def _registrar_lacuna_de_subida(self):
        """
        Compara o ultimo registro em disco com agora e grava a lacuna,
        se houver. Roda ANTES do primeiro poll, toda vez que o
        processo sobe.
        """
        ultimo = ultimo_registrado_ms()
        if ultimo is None:
            return
        agora = (agora_ms() // MS_POR_MINUTO) * MS_POR_MINUTO
        perdidos = (agora - ultimo) // MS_POR_MINUTO - 1
        if perdidos < 1:
            return
        inicio = ultimo + MS_POR_MINUTO
        fim = agora - MS_POR_MINUTO
        anexar(os.path.join(DIR_EXECUCAO, f"contexto_falhas_{dia(fim)}.csv"),
               COLUNAS_FALHA,
               [[iso(inicio), iso(fim), perdidos,
                 "lacuna detectada na subida (processo ausente)"]])
        horas = perdidos / 60.0
        aviso(f"LACUNA: {duracao(perdidos * 60)} sem coleta, de "
              f"{humano(inicio)} a {humano(fim)}. Registrada em "
              f"contexto_falhas_{dia(fim)}.csv.")

    def registrar_falha(self, motivo):
        """
        Registra no LOG por que a coleta falhou. NAO escreve no CSV.

        A divisao de trabalho e deliberada:

          contexto_falhas.csv   QUAIS minutos faltam
          poller.log            POR QUE faltaram

        A versao anterior escrevia nos dois, e isso produzia contagem
        dupla. Em 24/09 uma falha de API gerou a linha
        `01:06:18 - 01:07:01, 1, recuperado` enquanto o detector de
        minutos pulados ja tinha gravado `01:07 - 01:07, 1`. O mesmo
        minuto contado duas vezes: o arquivo declarava 429 minutos
        perdidos, o validador encontrava 428 faltando.

        Havia mais dois defeitos na mesma funcao. O motivo
        "recuperado" descreve a RECUPERACAO, nao a lacuna — um arquivo
        de lacunas nao registra recuperacoes. E `max(1, ...)` forcava
        um minuto perdido mesmo quando a falha durou 43 segundos e nao
        custou minuto nenhum: perda inventada.

        O detector de minutos pulados, que roda em um_ciclo() ANTES
        desta funcao, ja grava a janela exata e alinhada ao minuto.
        Duplicar ali nao acrescenta informacao, so ruido.
        """
        if self.falha_desde is None:
            return
        fim = agora_ms()
        dur = (fim - self.falha_desde) / 1000.0
        aviso(f"[{humano(fim)}] coleta restabelecida apos {duracao(dur)} "
              f"({motivo}). Os minutos perdidos, se houver, estao no "
              f"contexto_falhas do dia.")
        self.falha_desde = None

    def um_ciclo(self, sessao):
        ts = (agora_ms() // MS_POR_MINUTO) * MS_POR_MINUTO
        dados = puxar(sessao)
        if not dados:
            raise ValueError("nenhum major no universo retornado")

        faltando = [s for s in MAJORS if s not in dados]
        linhas = []
        invalidos = {}
        for s in MAJORS:
            if s not in dados:
                continue
            ctx, ativo = dados[s]
            inval, motivo = mercado_invalido(ctx, ativo)
            if inval:
                invalidos[s] = motivo
            # a linha e gravada de qualquer jeito: o dado bruto fica em
            # disco, e a exclusao acontece na analise, a partir das
            # colunas. Filtrar na coleta apagaria a evidencia de que o
            # simbolo estava morto naquele minuto.
            linhas.append(linha(ts, s, ctx, ativo))
        anexar(os.path.join(DIR_EXECUCAO, f"contexto_{dia(ts)}.csv"),
               COLUNAS, linhas)

        # buraco de calendario: o processo estava vivo mas perdeu minutos
        if self.ultimo_ok_ms is not None:
            pulados = (ts - self.ultimo_ok_ms) // MS_POR_MINUTO - 1
            if pulados > 0:
                anexar(os.path.join(DIR_EXECUCAO,
                                    f"contexto_falhas_{dia(ts)}.csv"),
                       COLUNAS_FALHA,
                       [[iso(self.ultimo_ok_ms + MS_POR_MINUTO),
                         iso(ts - MS_POR_MINUTO), pulados,
                         "minutos pulados (processo vivo)"]])
        self.ultimo_ok_ms = ts
        return len(linhas), faltando, invalidos

    def rodar(self):
        sessao = requests.Session()
        sessao.headers.update({"Content-Type": "application/json"})
        espera = BACKOFF_INICIAL_S
        avisou_faltando = set()
        avisou_invalido = {}

        while not self.parar:
            try:
                n, faltando, invalidos = self.um_ciclo(sessao)
                self.registrar_falha("falha de API")
                espera = BACKOFF_INICIAL_S
                # silencio tatico: so o que e anomalia, e so uma vez
                novos = set(faltando) - avisou_faltando
                if novos:
                    aviso(f"[{humano(agora_ms())}] ausentes do universo "
                          f"da HL: {sorted(novos)}")
                    avisou_faltando |= novos
                for s, motivo in invalidos.items():
                    if avisou_invalido.get(s) != motivo:
                        aviso(f"[{humano(agora_ms())}] {s}: mercado "
                              f"invalido ({motivo}). Gravado, mas excluido "
                              f"da analise.")
                        avisou_invalido[s] = motivo
            except Exception as e:
                if self.falha_desde is None:
                    self.falha_desde = agora_ms()
                    aviso(f"[{humano(agora_ms())}] falha: "
                          f"{type(e).__name__}: {e}")
                time.sleep(espera)
                espera = min(espera * 2, BACKOFF_MAX_S)
                continue

            # dorme ate a virada do proximo minuto
            alvo = ((agora_ms() // MS_POR_MINUTO) + 1) * MS_POR_MINUTO
            while not self.parar and agora_ms() < alvo:
                time.sleep(min(1.0, (alvo - agora_ms()) / 1000.0))

        self.registrar_falha("encerrado")


def main():
    os.makedirs(DIR_EXECUCAO, exist_ok=True)
    if not obter_trava():
        aviso(f"[{humano(agora_ms())}] ja existe um poller de contexto "
              f"rodando. Saindo sem fazer nada.")
        return 0

    col = Coletor()

    def encerrar(*_):
        col.parar = True

    try:
        signal.signal(signal.SIGINT, encerrar)
        signal.signal(signal.SIGTERM, encerrar)
    except (ValueError, AttributeError):
        pass

    aviso(f"==== subida em {humano(agora_ms())} ====")
    print(f"COLETOR DE CONTEXTO  {len(MAJORS)} majors  1 poll/minuto")
    print(f"horarios: seu fuso ({offset_local()}) primeiro, UTC entre "
          f"parenteses. O CSV grava UTC puro.")
    print(f"destino: {DIR_EXECUCAO}")
    print("openInterest, funding, mark/oracle/mid, premium, impactPxs")
    print("NAO ENVIA ORDEM. Silencio tatico: so anomalias e falhas.\n",
          flush=True)
    try:
        col.rodar()
    except KeyboardInterrupt:
        pass
    print("\nencerrado.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
