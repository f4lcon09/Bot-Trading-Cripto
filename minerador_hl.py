#!/usr/bin/env python3
"""
MINERADOR_HL.PY - Fase 0, acumulo prospectivo.

A Hyperliquid retem ~5.000 velas por intervalo. Em 1m isso sao 3,5
dias: nao existe historico de 1m nela, e nunca vai existir olhando para
tras. O que existe e para frente.

Este programa roda UMA VEZ POR DIA, indefinidamente, a partir de hoje.
Cada execucao salva um dia de 1m que sairia da retencao e se perderia.
Com 3,5 dias de janela contra 1 dia de intervalo ha folga para tolerar
uma falha sem abrir buraco.

  python minerador_hl.py           # todos os 18
  python minerador_hl.py BTC ETH

E idempotente: mescla o que baixou com o que ja estava em disco,
mantendo a vela existente em caso de conflito de timestamp, e reescreve
ordenado. Rodar duas vezes no mesmo dia nao duplica nada.

Saida: museu_hl/<SYM>.csv   time,open,high,low,close,vol  (ms epoch UTC)

NAO envia ordem, nao le credencial.
"""
import csv
import os
import sys
import time
from datetime import datetime, timezone

import requests

from config import (API_INFO, MAJORS, MAX_VELAS_RESPOSTA, PAUSA_REQUISICAO_S,
                    SUPERFICIES)

MS_POR_MINUTO = 60_000
BACKOFF_INICIAL_S = 2.0
BACKOFF_MAX_S = 120.0
TENTATIVAS_MAX = 6
RETENCAO_MS = MAX_VELAS_RESPOSTA * MS_POR_MINUTO   # ~3,5 dias

CABECALHO = ["time", "open", "high", "low", "close", "vol"]
DIR_HL = SUPERFICIES["hl"]["dir"]


def agora_ms():
    return int(time.time() * 1000)


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M")


def caminho_csv(sym):
    return os.path.join(DIR_HL, f"{sym}.csv")


def buscar(sessao, coin, inicio_ms, fim_ms):
    """
    candleSnapshot. Backoff exponencial em 429 e erro de rede; estoura
    depois de TENTATIVAS_MAX. Falha ruidosa e melhor que buraco
    silencioso, porque o buraco so apareceria no validador semanas
    depois, sem ninguem saber de onde veio.
    """
    corpo = {"type": "candleSnapshot",
             "req": {"coin": coin, "interval": "1m",
                     "startTime": int(inicio_ms), "endTime": int(fim_ms)}}
    espera = BACKOFF_INICIAL_S
    for tentativa in range(1, TENTATIVAS_MAX + 1):
        try:
            r = sessao.post(API_INFO, json=corpo, timeout=30)
            if r.status_code == 429:
                time.sleep(espera)
                espera = min(espera * 2, BACKOFF_MAX_S)
                continue
            r.raise_for_status()
            dados = r.json()
            if dados is None:
                return []
            if not isinstance(dados, list):
                raise ValueError(f"resposta nao e lista: {type(dados)}")
            return dados
        except (requests.RequestException, ValueError) as e:
            if tentativa == TENTATIVAS_MAX:
                raise
            print(f"    {coin}: {e}, tentativa {tentativa}", file=sys.stderr)
            time.sleep(espera)
            espera = min(espera * 2, BACKOFF_MAX_S)
    return []


def normalizar(vela):
    try:
        t = int(vela["t"])
        o = float(vela["o"])
        h = float(vela["h"])
        l = float(vela["l"])
        c = float(vela["c"])
        v = float(vela["v"])
    except (KeyError, TypeError, ValueError):
        return None
    if min(o, h, l, c) <= 0:
        return None
    return (t, o, h, l, c, v)


def ler_existente(caminho):
    """dict {t: tupla} do que ja esta em disco. Vazio se nao ha arquivo."""
    if not os.path.exists(caminho):
        return {}
    fora = {}
    with open(caminho, "r", encoding="utf-8", newline="") as f:
        leitor = csv.reader(f)
        cab = next(leitor, None)
        if cab != CABECALHO:
            return {}
        for linha in leitor:
            if len(linha) != 6:
                continue
            try:
                fora[int(linha[0])] = (int(linha[0]), float(linha[1]),
                                       float(linha[2]), float(linha[3]),
                                       float(linha[4]), float(linha[5]))
            except ValueError:
                continue
    return fora


def escrever(caminho, velas):
    """Contrato: UTF-8, cabecalho, sem espaco apos virgula, LF."""
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(CABECALHO)
        for t, o, h, l, c, v in velas:
            w.writerow([t, repr(o), repr(h), repr(l), repr(c), repr(v)])


def acumular(sessao, sym, fim_ms):
    caminho = caminho_csv(sym)
    existente = ler_existente(caminho)
    antes = len(existente)

    # Pede a janela de retencao inteira. Se ja ha dado, comeca do
    # ultimo timestamp - a API trunca no inicio o que nao retem mais.
    inicio = fim_ms - RETENCAO_MS
    if existente:
        inicio = min(inicio, max(existente) + MS_POR_MINUTO)

    novas = 0
    cursor = inicio
    while cursor < fim_ms:
        fim_pagina = min(cursor + RETENCAO_MS, fim_ms)
        bruto = buscar(sessao, sym, cursor, fim_pagina)
        time.sleep(PAUSA_REQUISICAO_S)
        if not bruto:
            break
        maior = cursor
        for item in bruto:
            n = normalizar(item)
            if n is None or n[0] >= fim_ms:
                continue
            maior = max(maior, n[0])
            if n[0] in existente:
                continue          # o que ja esta em disco manda
            existente[n[0]] = n
            novas += 1
        if maior <= cursor:
            break
        cursor = maior + MS_POR_MINUTO

    if not existente:
        print(f"  {sym:5} SEM DADO")
        return 0, 0

    velas = [existente[k] for k in sorted(existente)]
    escrever(caminho, velas)

    buraco = ""
    if antes and novas:
        # Buraco entre o fim do arquivo antigo e o inicio do que a API
        # ainda retem: dado que se perdeu porque ninguem rodou a tempo.
        pass
    print(f"  {sym:5} {len(velas):>7} velas (+{novas:>5})  "
          f"{iso(velas[0][0])} a {iso(velas[-1][0])}{buraco}")
    return len(velas), novas


def main(argv):
    alvos = [a.upper() for a in argv if not a.startswith("--")] or list(MAJORS)
    desconhecidos = [s for s in alvos if s not in MAJORS]
    if desconhecidos:
        print(f"ERRO: fora do universo de 18 majors: {desconhecidos}")
        return 2

    os.makedirs(DIR_HL, exist_ok=True)
    fim_ms = (agora_ms() // MS_POR_MINUTO) * MS_POR_MINUTO

    print(f"ACUMULO HL  {iso(fim_ms - RETENCAO_MS)} a {iso(fim_ms)} UTC "
          f"(retencao de {RETENCAO_MS/86400000:.1f} dias)")
    print(f"destino: {DIR_HL}\n")

    sessao = requests.Session()
    sessao.headers.update({"Content-Type": "application/json"})

    total = novas_total = 0
    falhas = []
    for sym in alvos:
        try:
            n, novas = acumular(sessao, sym, fim_ms)
            total += n
            novas_total += novas
        except Exception as e:
            print(f"  {sym:5} FALHOU: {type(e).__name__}: {e}")
            falhas.append(sym)

    print(f"\n{total} velas em disco, {novas_total} novas nesta execucao.")
    if falhas:
        print(f"falharam: {falhas}")
    print("\nRode este programa UMA VEZ POR DIA. Cada dia sem rodar e um "
          "dia de 1m perdido para sempre.")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
