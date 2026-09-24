#!/usr/bin/env python3
"""
PARIDADE_VENUE.PY - Gate 0b.

Os gates 0a e 0 sao julgados em Binance futures. O bot opera na
Hyperliquid. Este programa mede o quanto essas duas coisas sao a mesma
coisa, sobre os poucos dias de 1m que a HL retem.

  python paridade_venue.py

Passa com sobreposicao acima de 70% e defasagem mediana de ate 1
minuto. Amostra pequena, valor confirmatorio - roda depois do 0a.

--------------------------------------------------------------------
DEFINICAO DE SOBREPOSICAO
--------------------------------------------------------------------
A especificacao pede "sobreposicao de gatilhos HL x Binance futures"
sem definir a formula. Escolhi a conservadora:

    sobreposicao = casados / max(n_hl, n_bin)

Ela pune gatilho sobrando dos DOIS lados. As alternativas
(casados/n_hl, casados/n_bin, Jaccard) sao todas recomputaveis a
partir dos numeros brutos, que ficam impressos e no JSON - nao
escondi a escolha atras de um numero so.

Um gatilho da HL casa com um da Binance se ocorrem no mesmo simbolo
dentro de TOLERANCIA_MIN minutos. Cada gatilho casa no maximo uma vez,
com o mais proximo no tempo.
--------------------------------------------------------------------
"""
import json
import os
import sys

import numpy as np

from config import HORIZONTE_MIN, MAJORS, SUPERFICIES
from sinal import MS_POR_MINUTO, indices_de_gatilho
from validacao import caminho_csv, caminho_manifesto, iso, ler_csv

TOLERANCIA_MIN = 5
SOBREPOSICAO_PASSA = 0.70
DEFASAGEM_MAX_MIN = 1.0


def carregar_aprovados(chave):
    caminho = caminho_manifesto(chave)
    if not os.path.exists(caminho):
        return None, f"manifesto ausente em {caminho}"
    with open(caminho, "r", encoding="utf-8") as f:
        man = json.load(f)
    esperado = SUPERFICIES[chave]
    if man.get("fonte") != esperado["fonte"]:
        return None, (f"manifesto de {chave} declara fonte "
                      f"'{man.get('fonte')}', esperado "
                      f"'{esperado['fonte']}'")
    return man.get("aprovados", []), None


def gatilhos(chave, sym, inicio_ms, fim_ms):
    """[(t_ms, ret_60m)] dos gatilhos de um simbolo na janela."""
    arrays, _ = ler_csv(caminho_csv(chave, sym))
    if arrays is None:
        return []
    t_all = arrays["time"]
    mask = (t_all >= inicio_ms) & (t_all <= fim_ms)
    t = t_all[mask]
    c = arrays["close"][mask]
    if len(t) < HORIZONTE_MIN + 40:
        return []
    fora = []
    for i in indices_de_gatilho(t, c):
        j = i + HORIZONTE_MIN
        if int(t[j]) - int(t[i]) != HORIZONTE_MIN * MS_POR_MINUTO:
            continue
        fora.append((int(t[i]), float(c[j] / c[i] - 1.0)))
    return fora


def casar(hl, bin_fut, tolerancia_min=TOLERANCIA_MIN):
    """
    Casamento guloso pelo vizinho mais proximo, cada gatilho usado no
    maximo uma vez. Devolve [(t_hl, t_bin, defasagem_min, d_ret)].
    """
    livres = list(range(len(bin_fut)))
    pares = []
    for t_hl, ret_hl in hl:
        melhor, melhor_d = None, None
        for idx in livres:
            d = abs(bin_fut[idx][0] - t_hl) / MS_POR_MINUTO
            if d <= tolerancia_min and (melhor_d is None or d < melhor_d):
                melhor, melhor_d = idx, d
        if melhor is not None:
            t_bin, ret_bin = bin_fut[melhor]
            livres.remove(melhor)
            pares.append((t_hl, t_bin,
                          (t_bin - t_hl) / MS_POR_MINUTO,
                          ret_bin - ret_hl))
    return pares


def main(argv):
    apr_hl, erro = carregar_aprovados("hl")
    if erro:
        print(f"ERRO: {erro}. Rode 'python validacao.py hl'.")
        return 2
    apr_bin, erro = carregar_aprovados("bin_fut")
    if erro:
        print(f"ERRO: {erro}. Rode 'python validacao.py bin_fut'.")
        return 2

    comuns = [s for s in MAJORS if s in apr_hl and s in apr_bin]
    if not comuns:
        print("ERRO: nenhum simbolo aprovado nas duas superficies.")
        print(f"  aprovados HL:      {apr_hl}")
        print(f"  aprovados futures: {apr_bin}")
        return 2

    print("GATE 0b - paridade de venue (HL x Binance futures)")
    print(f"  {len(comuns)} simbolos aprovados nas duas superficies")
    so_hl = [s for s in apr_hl if s not in apr_bin]
    so_bin = [s for s in apr_bin if s not in apr_hl]
    if so_hl:
        print(f"  so na HL:      {so_hl}")
    if so_bin:
        print(f"  so em futures: {so_bin}")
    print(f"  tolerancia de casamento: {TOLERANCIA_MIN} min\n")

    print(f"{'sym':<6}{'n_hl':>6}{'n_bin':>7}{'casados':>9}"
          f"{'sobrep.':>9}{'defas.med':>11}{'d_ret med':>11}")
    print("-" * 59)

    tot_hl = tot_bin = tot_casados = 0
    defasagens, dretornos = [], []
    por_simbolo = {}

    for sym in comuns:
        arrays, _ = ler_csv(caminho_csv("hl", sym))
        if arrays is None or len(arrays["time"]) == 0:
            continue
        # A janela e a da HL: e ela que tem o lado curto.
        inicio = int(arrays["time"].min())
        fim = int(arrays["time"].max())

        g_hl = gatilhos("hl", sym, inicio, fim)
        g_bin = gatilhos("bin_fut", sym, inicio, fim)
        pares = casar(g_hl, g_bin)

        tot_hl += len(g_hl)
        tot_bin += len(g_bin)
        tot_casados += len(pares)
        defasagens.extend([p[2] for p in pares])
        dretornos.extend([p[3] for p in pares])

        denom = max(len(g_hl), len(g_bin))
        sob = len(pares) / denom if denom else 0.0
        dm = np.median([abs(p[2]) for p in pares]) if pares else float("nan")
        dr = np.median([abs(p[3]) for p in pares]) if pares else float("nan")
        por_simbolo[sym] = {"n_hl": len(g_hl), "n_bin": len(g_bin),
                            "casados": len(pares), "sobreposicao": sob}

        print(f"{sym:<6}{len(g_hl):>6}{len(g_bin):>7}{len(pares):>9}"
              f"{sob:>8.0%}"
              f"{'      n/d' if pares == [] else f'{dm:>10.1f}m'}"
              f"{'      n/d' if pares == [] else f'{dr:>10.2%}'}")

    denom = max(tot_hl, tot_bin)
    sobreposicao = tot_casados / denom if denom else 0.0
    defas_med = float(np.median([abs(d) for d in defasagens])) if defasagens \
        else float("nan")
    dret_med = float(np.median([abs(d) for d in dretornos])) if dretornos \
        else float("nan")

    print("-" * 59)
    print(f"\nAGREGADO")
    print(f"  gatilhos na HL           {tot_hl}")
    print(f"  gatilhos em futures      {tot_bin}")
    print(f"  casados                  {tot_casados}")
    print(f"  sobreposicao             {sobreposicao:.1%} "
          f"(casados / max(n_hl, n_bin))")
    print(f"    casados / n_hl         "
          f"{tot_casados/tot_hl:.1%}" if tot_hl else "    n/d")
    print(f"    casados / n_bin        "
          f"{tot_casados/tot_bin:.1%}" if tot_bin else "    n/d")
    print(f"  defasagem mediana        {defas_med:.2f} min")
    print(f"  |d_retorno 60m| mediano  {dret_med:.3%}")

    c_sob = sobreposicao > SOBREPOSICAO_PASSA
    c_def = (not np.isnan(defas_med)) and defas_med <= DEFASAGEM_MAX_MIN

    print(f"\nGATE 0b")
    print(f"  sobreposicao > {SOBREPOSICAO_PASSA:.0%}        "
          f"{sobreposicao:.1%}   {'ok' if c_sob else 'FALHA'}")
    print(f"  defasagem <= {DEFASAGEM_MAX_MIN:.0f} min       "
          f"{defas_med:.2f}   {'ok' if c_def else 'FALHA'}")
    aprovado = c_sob and c_def
    print(f"\n  VEREDITO: {'APROVADO' if aprovado else 'REPROVADO'}")
    print(f"  Amostra pequena ({tot_hl} gatilhos na HL), valor "
          f"confirmatorio.")

    saida = os.path.join(SUPERFICIES["hl"]["dir"], "resultado_gate0b.json")
    with open(saida, "w", encoding="utf-8") as f:
        json.dump({"sobreposicao": sobreposicao, "n_hl": tot_hl,
                   "n_bin": tot_bin, "casados": tot_casados,
                   "defasagem_mediana_min": defas_med,
                   "d_retorno_mediano": dret_med,
                   "tolerancia_min": TOLERANCIA_MIN,
                   "por_simbolo": por_simbolo,
                   "aprovado": bool(aprovado)}, f, indent=1,
                  ensure_ascii=False)
    print(f"\nresultado: {saida}")
    return 0 if aprovado else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
