#!/usr/bin/env python3
"""
MINERADOR_BINANCE.PY - Fase 0, coleta historica.

Baixa velas de 1 minuto dos 18 majors, de 2025-08-01 ate hoje, em duas
superficies separadas: futures (perpetuo USDT) e spot. Nao envia ordem,
nao le chave, nao cria conta - klines publicas sao abertas.

  python minerador_binance.py futures      # PRIMEIRO. Serve o Gate 0a.
  python minerador_binance.py spot         # controle do Gate 0a
  python minerador_binance.py futures BTC ETH

--------------------------------------------------------------------
METODO: arquivo mensal, nao paginacao REST
--------------------------------------------------------------------
A especificacao sugere `klines` com limit=1000 paginando por startTime.
Sao 417 dias x 18 simbolos x 2 superficies = ~21.600 requisicoes. O
data.binance.vision publica os mesmos dados em ZIP mensal: ~500
arquivos para o mesmo conteudo, e e o caminho que atende melhor o
"baixe e arquive tudo em disco antes de rodar qualquer analise".

REST entra so no rabo: os dias do mes corrente que o arquivo ainda nao
publicou. O arquivo diario sai com ~1 dia de atraso, entao o REST cobre
a ponta.

Cada vela vem de exatamente uma fonte. Nunca se mistura arquivo e REST
para o mesmo minuto, e duplicata por timestamp e eliminada mantendo a
primeira ocorrencia (a do arquivo, que e a canonica).
--------------------------------------------------------------------

Saida: museu_bin_fut/<SYM>.csv ou museu_bin_spot/<SYM>.csv
       time,open,high,low,close,vol   (time em ms epoch UTC)
"""
import csv
import io
import os
import sys
import time
import zipfile
from datetime import datetime, timedelta, timezone

import requests

from config import (BIN_REST_FUT, BIN_REST_SPOT, DATA_VISION, MAJORS,
                    MUSEU_INICIO_MS, SUPERFICIES)

MS_POR_MINUTO = 60_000
MS_POR_DIA = 86_400_000
CABECALHO = ["time", "open", "high", "low", "close", "vol"]

BACKOFF_INICIAL_S = 2.0
BACKOFF_MAX_S = 120.0
TENTATIVAS_MAX = 5
PAUSA_ARQUIVO_S = 0.15
PAUSA_REST_S = 0.35


def agora_ms():
    return int(time.time() * 1000)


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M")


def dia_utc(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date()


def meses_entre(inicio_ms, fim_ms):
    """Lista de (ano, mes) cobrindo o periodo, inclusive nas bordas."""
    d = dia_utc(inicio_ms).replace(day=1)
    fim = dia_utc(fim_ms)
    saida = []
    while d <= fim:
        saida.append((d.year, d.month))
        d = (d.replace(day=28) + timedelta(days=5)).replace(day=1)
    return saida


def url_mensal(mercado, par, ano, mes):
    return (f"{DATA_VISION}/{mercado}/monthly/klines/{par}/1m/"
            f"{par}-1m-{ano:04d}-{mes:02d}.zip")


def url_diario(mercado, par, data):
    return (f"{DATA_VISION}/{mercado}/daily/klines/{par}/1m/"
            f"{par}-1m-{data.isoformat()}.zip")


def baixar_zip(sessao, url):
    """
    Devolve as linhas do CSV dentro do ZIP, ou None se o arquivo nao
    existe (404). Qualquer outro erro entra em backoff.

    404 nao e falha: significa que aquele mes/dia nao foi publicado
    para aquele simbolo - o par pode nem existir ainda naquela data.
    """
    espera = BACKOFF_INICIAL_S
    for tentativa in range(1, TENTATIVAS_MAX + 1):
        try:
            r = sessao.get(url, timeout=120)
            if r.status_code == 404:
                return None
            if r.status_code == 429:
                time.sleep(espera)
                espera = min(espera * 2, BACKOFF_MAX_S)
                continue
            r.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                nome = z.namelist()[0]
                with z.open(nome) as f:
                    texto = io.TextIOWrapper(f, encoding="utf-8")
                    return list(csv.reader(texto))
        except (requests.RequestException, zipfile.BadZipFile) as e:
            if tentativa == TENTATIVAS_MAX:
                print(f"    falha definitiva em {url}: {e}", file=sys.stderr)
                raise
            time.sleep(espera)
            espera = min(espera * 2, BACKOFF_MAX_S)
    return None


def normalizar_linha(campos):
    """
    Linha de kline da Binance -> (t, o, h, l, c, v) ou None.

    O layout e o mesmo no arquivo e no REST:
      0 open_time, 1 open, 2 high, 3 low, 4 close, 5 volume, ...

    Alguns arquivos recentes trazem uma linha de cabecalho textual;
    ela cai fora sozinha no ValueError.
    """
    if len(campos) < 6:
        return None
    try:
        t = int(float(campos[0]))
        o = float(campos[1])
        h = float(campos[2])
        l = float(campos[3])
        c = float(campos[4])
        v = float(campos[5])
    except (TypeError, ValueError):
        return None
    if min(o, h, l, c) <= 0:
        return None
    # Alguns meses vem com open_time em microssegundos.
    if t > 10 ** 14:
        t //= 1000
    return (t, o, h, l, c, v)


def buscar_rest(sessao, url, par, inicio_ms, fim_ms):
    """Rabo do periodo, paginando por startTime com limit=1000."""
    saida = []
    cursor = inicio_ms
    espera = BACKOFF_INICIAL_S
    while cursor < fim_ms:
        try:
            r = sessao.get(url, params={"symbol": par, "interval": "1m",
                                        "startTime": cursor,
                                        "endTime": fim_ms,
                                        "limit": 1000}, timeout=30)
            if r.status_code in (429, 418):
                time.sleep(espera)
                espera = min(espera * 2, BACKOFF_MAX_S)
                continue
            if r.status_code == 400:
                break   # par inexistente nesta superficie
            r.raise_for_status()
            lote = r.json()
        except requests.RequestException:
            time.sleep(espera)
            espera = min(espera * 2, BACKOFF_MAX_S)
            if espera >= BACKOFF_MAX_S:
                break
            continue
        if not lote:
            break
        for k in lote:
            n = normalizar_linha(k)
            if n and inicio_ms <= n[0] < fim_ms:
                saida.append(n)
        cursor = int(lote[-1][0]) + MS_POR_MINUTO
        espera = BACKOFF_INICIAL_S
        time.sleep(PAUSA_REST_S)
    return saida


def escrever(caminho, velas):
    """
    Contrato: UTF-8, cabecalho sempre presente, sem espaco apos a
    virgula, seis campos em toda linha, LF e nao CRLF.
    """
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(CABECALHO)
        for t, o, h, l, c, v in velas:
            w.writerow([t, repr(o), repr(h), repr(l), repr(c), repr(v)])


def baixar_simbolo(sessao, sym, sup, inicio_ms, fim_ms):
    par = f"{sym}{sup['sufixo']}"
    mercado = sup["mercado"]
    caminho = os.path.join(sup["dir"], f"{sym}.csv")

    if os.path.exists(caminho):
        print(f"  {sym:5} PULADO: {sym}.csv ja existe (apague para "
              f"rebaixar e rebaixar)")
        return 0, "ja existia"

    vistos = set()
    velas = []
    faltando_mes = []

    # ---- corpo: arquivos mensais ----
    for ano, mes in meses_entre(inicio_ms, fim_ms):
        linhas = baixar_zip(sessao, url_mensal(mercado, par, ano, mes))
        time.sleep(PAUSA_ARQUIVO_S)
        if linhas is None:
            faltando_mes.append(f"{ano:04d}-{mes:02d}")
            continue
        for campos in linhas:
            n = normalizar_linha(campos)
            if n is None or n[0] in vistos:
                continue
            if not (inicio_ms <= n[0] < fim_ms):
                continue
            vistos.add(n[0])
            velas.append(n)
        print(f"  {sym:5} {len(velas):>7} velas  ate {ano:04d}-{mes:02d}",
              end="\r")

    # ---- rabo: arquivos diarios do mes corrente ----
    ultimo = max(vistos) if vistos else inicio_ms - MS_POR_MINUTO
    d = dia_utc(ultimo + MS_POR_MINUTO)
    hoje = dia_utc(fim_ms)
    while d <= hoje:
        linhas = baixar_zip(sessao, url_diario(mercado, par, d))
        time.sleep(PAUSA_ARQUIVO_S)
        if linhas is not None:
            for campos in linhas:
                n = normalizar_linha(campos)
                if n is None or n[0] in vistos:
                    continue
                if not (inicio_ms <= n[0] < fim_ms):
                    continue
                vistos.add(n[0])
                velas.append(n)
        d += timedelta(days=1)

    # ---- ponta: REST para o que o arquivo ainda nao publicou ----
    ultimo = max(vistos) if vistos else inicio_ms - MS_POR_MINUTO
    if ultimo + MS_POR_MINUTO < fim_ms:
        url = BIN_REST_FUT if sup["default_type"] == "future" else BIN_REST_SPOT
        for n in buscar_rest(sessao, url, par, ultimo + MS_POR_MINUTO, fim_ms):
            if n[0] in vistos:
                continue
            vistos.add(n[0])
            velas.append(n)

    if not velas:
        print(f"  {sym:5} SEM DADO nesta superficie ({par})            ")
        return 0, f"sem dado ({par})"

    velas.sort(key=lambda x: x[0])
    escrever(caminho, velas)

    nota = ""
    if faltando_mes:
        nota = f"meses sem arquivo: {','.join(faltando_mes)}"
    print(f"  {sym:5} {len(velas):>7} velas  {iso(velas[0][0])} a "
          f"{iso(velas[-1][0])}  {nota}          ")
    return len(velas), nota


def main(argv):
    if not argv or argv[0] not in ("futures", "spot"):
        print(__doc__.strip().split("\n---")[0])
        print("\nUso: python minerador_binance.py futures|spot [SYM ...]")
        return 2

    chave = "bin_fut" if argv[0] == "futures" else "bin_spot"
    sup = SUPERFICIES[chave]

    alvos = [a.upper() for a in argv[1:] if not a.startswith("--")]
    if not alvos:
        alvos = list(MAJORS)
    desconhecidos = [s for s in alvos if s not in MAJORS]
    if desconhecidos:
        print(f"ERRO: fora do universo de 18 majors: {desconhecidos}")
        return 2

    os.makedirs(sup["dir"], exist_ok=True)
    fim_ms = (agora_ms() // MS_POR_MINUTO) * MS_POR_MINUTO
    inicio_ms = MUSEU_INICIO_MS
    dias = (fim_ms - inicio_ms) / MS_POR_DIA

    print(f"MUSEU {chave}  ({sup['fonte']}, defaultType={sup['default_type']})")
    print(f"  {iso(inicio_ms)} a {iso(fim_ms)} UTC  ({dias:.0f} dias, "
          f"{len(alvos)} simbolos)")
    print(f"  serve: {sup['serve']}")
    print(f"  destino: {sup['dir']}\n")

    sessao = requests.Session()
    total = 0
    notas = {}
    falhas = []
    t0 = time.time()

    for sym in alvos:
        try:
            n, nota = baixar_simbolo(sessao, sym, sup, inicio_ms, fim_ms)
            total += n
            if nota:
                notas[sym] = nota
        except Exception as e:
            print(f"  {sym:5} FALHOU: {type(e).__name__}: {e}            ")
            falhas.append(sym)

    print(f"\n{total} velas em {(time.time()-t0)/60:.1f} min.")
    if notas:
        print("notas:")
        for s, n in notas.items():
            print(f"  {s}: {n}")
    if falhas:
        print(f"falharam: {falhas}  (rode de novo; o que ja baixou e pulado)")

    print(f"\nProximo passo: python validacao.py {chave}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
