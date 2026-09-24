#!/usr/bin/env python3
"""
VALIDACAO.PY - Fase 0, porteiro.

Validacao obrigatoria antes de qualquer analise. Um simbolo que falha
qualquer criterio e REBAIXADO e excluido da analise, com o motivo por
extenso. Nunca remendado: preencher buraco com interpolacao inventa
evento que nao houve, e o museu inteiro existe para nao inventar nada.

  python validacao.py bin_fut
  python validacao.py bin_spot
  python validacao.py hl

Criterios:
  1. cobertura > 99% contra o PERIODO SOLICITADO (nunca contra o
     intervalo do proprio arquivo)
  2. zero timestamps duplicados
  3. zero precos nao positivos
  4. high >= max(open,close) e low <= min(open,close) em TODA linha
  5. contrato do CSV: cabecalho exato, 6 campos, sem espaco em branco

Escreve <pasta>/manifesto.json com fonte, defaultType, periodo
solicitado, cobertura medida e veredito por simbolo. O analisador le
esse manifesto e se recusa a julgar se a fonte declarada nao bater com
a superficie pedida (Gate 2).
"""
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np

from config import (COBERTURA_MINIMA, MAJORS, MUSEU_INICIO_MS, SUPERFICIES)

MS_POR_MINUTO = 60_000
CABECALHO = ["time", "open", "high", "low", "close", "vol"]


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M")


def caminho_manifesto(chave):
    return os.path.join(SUPERFICIES[chave]["dir"], "manifesto.json")


def caminho_csv(chave, sym):
    return os.path.join(SUPERFICIES[chave]["dir"], f"{sym}.csv")


def ler_csv(caminho):
    """
    Le o CSV cru e devolve (arrays, problemas_de_contrato).

    Valida o contrato de formato enquanto le: cabecalho exato, seis
    campos por linha, sem espaco em branco nas bordas. A V1 gerou CSV
    com espaco a esquerda em toda linha - este e o ponto em que isso
    passa a ser detectado em vez de sobreviver ate a analise.
    """
    problemas = []
    t, o, h, l, c, v = [], [], [], [], [], []

    with open(caminho, "r", encoding="utf-8", newline="") as f:
        primeira = f.readline().rstrip("\n")
        if primeira.split(",") != CABECALHO:
            problemas.append(f"cabecalho invalido: {primeira!r}")
            return None, problemas
        for num, linha in enumerate(f, start=2):
            linha = linha.rstrip("\n")
            if not linha:
                continue
            campos = linha.split(",")
            if len(campos) != 6:
                problemas.append(f"linha {num}: {len(campos)} campos")
                continue
            if any(campo != campo.strip() for campo in campos):
                problemas.append(f"linha {num}: espaco em branco no campo")
                continue
            try:
                t.append(int(campos[0]))
                o.append(float(campos[1]))
                h.append(float(campos[2]))
                l.append(float(campos[3]))
                c.append(float(campos[4]))
                v.append(float(campos[5]))
            except ValueError as e:
                problemas.append(f"linha {num}: {e}")

    arrays = {"time": np.array(t, dtype=np.int64),
              "open": np.array(o), "high": np.array(h),
              "low": np.array(l), "close": np.array(c),
              "vol": np.array(v)}
    return arrays, problemas


def validar(chave, sym, fim_ms):
    """
    Veredito de um simbolo numa superficie.

    O periodo solicitado depende da superficie:

      binance  [MUSEU_INICIO_MS, agora] - janela fixa, pedida de fato
      hl       [primeira vela, agora]   - acumulo prospectivo: o museu
               da HL e "o que conseguimos guardar", entao o inicio e
               livre; o que NAO e livre e o fim. Um simbolo cuja serie
               para meses atras nao esta acumulando, esta parado.

    Essa segunda regra existe por causa do TON: as ultimas 5.000 velas
    de 1m dele na HL sao de junho/2026. Medido contra o proprio
    intervalo, esse arquivo da 100% de cobertura e passa. Medido ate
    agora, da ~2% e e rebaixado - que e o certo.
    """
    caminho = caminho_csv(chave, sym)
    r = {"symbol": sym, "aprovado": False, "motivos": []}

    if not os.path.exists(caminho):
        r["motivos"].append("arquivo ausente")
        return r

    arrays, problemas = ler_csv(caminho)
    if arrays is None or len(arrays["time"]) == 0:
        r["motivos"].append("arquivo ilegivel ou vazio")
        r["motivos"].extend(problemas[:5])
        return r
    if problemas:
        r["motivos"].append(
            f"{len(problemas)} violacoes de contrato do CSV "
            f"(ex.: {problemas[0]})")

    t = arrays["time"]
    o, h, l, c = arrays["open"], arrays["high"], arrays["low"], arrays["close"]
    n = len(t)

    r["n_velas"] = int(n)
    r["inicio"] = iso(int(t.min()))
    r["fim"] = iso(int(t.max()))

    # 1. cobertura contra o periodo solicitado
    if SUPERFICIES[chave]["fonte"] == "hyperliquid":
        inicio_pedido = int(t.min())
    else:
        inicio_pedido = MUSEU_INICIO_MS
    minutos_periodo = (fim_ms - inicio_pedido) // MS_POR_MINUTO + 1
    dentro = int(np.sum((t >= inicio_pedido) & (t <= fim_ms)))
    cobertura = dentro / minutos_periodo if minutos_periodo > 0 else 0.0

    r["periodo_inicio"] = iso(inicio_pedido)
    r["periodo_fim"] = iso(fim_ms)
    r["cobertura"] = round(float(cobertura), 5)
    r["minutos_periodo"] = int(minutos_periodo)
    r["velas_no_periodo"] = int(dentro)
    if cobertura < COBERTURA_MINIMA:
        r["motivos"].append(
            f"cobertura {cobertura:.3%} < {COBERTURA_MINIMA:.0%} "
            f"({dentro} velas em {minutos_periodo} minutos de periodo)")

    if dentro == 0:
        r["motivos"].append(
            f"nenhuma vela dentro do periodo pedido; a serie termina em "
            f"{r['fim']}")

    # 2. duplicatas
    n_dup = int(n - len(np.unique(t)))
    r["duplicatas"] = n_dup
    if n_dup > 0:
        r["motivos"].append(f"{n_dup} timestamps duplicados")

    # ordenacao: nao e criterio da especificacao, mas serie fora de
    # ordem quebra toda a varredura de gatilho em silencio
    if not np.all(np.diff(t) > 0):
        r["motivos"].append("timestamps fora de ordem crescente")

    # 3. precos nao positivos
    n_nao_pos = int(np.sum((o <= 0) | (h <= 0) | (l <= 0) | (c <= 0)))
    r["nao_positivos"] = n_nao_pos
    if n_nao_pos > 0:
        r["motivos"].append(f"{n_nao_pos} precos nao positivos")

    # 4. coerencia OHLC
    n_incoer = int(np.sum((h < np.maximum(o, c)) | (l > np.minimum(o, c))))
    r["ohlc_incoerente"] = n_incoer
    if n_incoer > 0:
        r["motivos"].append(f"{n_incoer} linhas com OHLC incoerente")

    r["aprovado"] = len(r["motivos"]) == 0
    return r


def main(argv):
    if not argv or argv[0] not in SUPERFICIES:
        print("Uso: python validacao.py bin_fut|bin_spot|hl [SYM ...]")
        return 2

    chave = argv[0]
    sup = SUPERFICIES[chave]
    alvos = [a.upper() for a in argv[1:]] or list(MAJORS)

    if not os.path.isdir(sup["dir"]):
        print(f"ERRO: {sup['dir']} nao existe. Rode o minerador antes.")
        return 2

    fim_ms = (int(time.time() * 1000) // MS_POR_MINUTO) * MS_POR_MINUTO

    print(f"VALIDACAO {chave}  ({sup['fonte']}, "
          f"defaultType={sup['default_type']})")
    print(f"  cobertura minima {COBERTURA_MINIMA:.0%}, contra o periodo "
          f"solicitado\n")
    print(f"{'sym':<6}{'velas':>9}{'cobertura':>11}{'dup':>6}{'ohlc':>6}"
          f"  {'periodo do arquivo':<37}veredito")
    print("-" * 88)

    vereditos = []
    for sym in alvos:
        r = validar(chave, sym, fim_ms)
        vereditos.append(r)
        if "n_velas" in r:
            periodo = f"{r['inicio']} a {r['fim']}"
            print(f"{sym:<6}{r['n_velas']:>9}{r['cobertura']:>10.2%}"
                  f"{r['duplicatas']:>6}{r['ohlc_incoerente']:>6}"
                  f"  {periodo:<37}"
                  f"{'APROVADO' if r['aprovado'] else 'REBAIXADO'}")
        else:
            print(f"{sym:<6}{'-':>9}{'-':>11}{'-':>6}{'-':>6}"
                  f"  {'-':<37}REBAIXADO")
        for m in r["motivos"]:
            print(f"        ! {m}")

    aprovados = [r["symbol"] for r in vereditos if r["aprovado"]]
    rebaixados = [r["symbol"] for r in vereditos if not r["aprovado"]]

    print("-" * 88)
    print(f"aprovados: {len(aprovados)}/{len(alvos)}  {aprovados}")
    if rebaixados:
        print(f"rebaixados (excluidos da analise): {rebaixados}")

    manifesto = {
        "superficie": chave,
        "fonte": sup["fonte"],
        "default_type": sup["default_type"],
        "sufixo": sup["sufixo"],
        "serve": sup["serve"],
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cobertura_minima": COBERTURA_MINIMA,
        "periodo_fim": iso(fim_ms),
        "aprovados": aprovados,
        "rebaixados": rebaixados,
        "vereditos": vereditos,
    }
    with open(caminho_manifesto(chave), "w", encoding="utf-8") as f:
        json.dump(manifesto, f, indent=1, ensure_ascii=False)
    print(f"\nmanifesto: {caminho_manifesto(chave)}")

    if len(aprovados) < 12:
        print(f"\nAVISO: so {len(aprovados)} simbolos aprovados. Os gates "
              f"exigem 12 de 18 positivos - com menos de 12 series validas "
              f"o criterio nem e avaliavel.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
