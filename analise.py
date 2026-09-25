#!/usr/bin/env python3
"""
ANALISE.PY - Fase 0, veredito.

Reaplica o procedimento da tese SEM ALTERAR UM PARAMETRO. Nao ha flag
de tuning neste arquivo, e isso e deliberado.

  python analise.py 0a     # Gate 0a: futures na janela da tese
  python analise.py 0      # Gate 0: futures no holdout abr/2026 -> hoje

Procedimento (identico ao in-sample):
  gatilho   retorno de 1m em [-3.0%, -1.5%], fecha-a-fecha, majors
  saida     tempo, 60 minutos, SEM STOP
  benchmark instantes a cada 37 minutos, mesmo horizonte
  alpha     retorno medio do evento - retorno medio do benchmark

GATE 2 (paridade de fonte): cada gate declara de que superficie precisa
ser julgado. Se o manifesto da pasta indicar fonte ou defaultType
diferente do declarado, o analisador RECUSA julgar. Asserção, nao
inspecao manual.

O julgamento vale uma vez. Se o edge sumir, o projeto termina - nao se
ajusta a faixa do gatilho e tenta de novo.
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

from config import (GATE0A_FIM_MS, GATE0A_INICIO_MS, GATE0_INICIO_MS,
                    HORIZONTE_MIN, JANELA_SIGMA, MAJORS, PASSO_BENCHMARK,
                    SUPERFICIES)
from invariante10 import FamiliaDeBusca, Medida, exigir_familia
from sinal import (MS_POR_MINUTO, excursoes, indices_de_gatilho,
                   sigma_pre_gatilho)
from validacao import caminho_csv, caminho_manifesto, iso, ler_csv

# --------------------------------------------------------------------
# FAMILIA DE BUSCA - declarada antes de qualquer resultado.
#
# A varredura que produziu o bucket vencedor: 6 faixas de queda x 4
# horizontes x 2 direcoes = 48, mais 5 faixas x 3 horizontes x 2 grupos
# de liquidez = 30. Total 78 celulas. A faixa (-3,0, -1,5] nao aparece
# em nenhuma delas: foi criada fundindo duas adjacentes depois de ver o
# resultado, e a fusao pos-hoc conta como busca — por isso ela entra
# aqui como a 79a celula, em vez de ser esquecida.
# --------------------------------------------------------------------
FAMILIA_TESE = FamiliaDeBusca("varredura original da tese")
FAMILIA_TESE.declarar(
    *[f"queda{i}_horizonte{j}_direcao{k}"
      for i in range(6) for j in range(4) for k in range(2)],
    *[f"queda{i}_horizonte{j}_liquidez{k}"
      for i in range(5) for j in range(3) for k in range(2)],
    "(-3,0, -1,5] fundida pos-hoc de duas celulas adjacentes",
).fechar()

# --------------------------------------------------------------------
# CRITERIOS - decididos antes de ver o resultado. Mover um limiar
# depois de olhar os dados invalida o teste.
# --------------------------------------------------------------------
GATES = {
    "0a": {
        "nome": "Gate 0a - replicacao em futures, mesma janela da tese",
        "superficie": "bin_fut",
        "fonte": "binance",
        "default_type": "future",
        "inicio": GATE0A_INICIO_MS,
        "fim": GATE0A_FIM_MS,
        "alpha_passa": 0.007,
        "alpha_reprova": 0.003,
        "wr_passa": 0.65,
        "wr_reprova": 0.58,
        "simbolos_min": None,
        "zona_intermediaria": None,   # a especificacao nao define
    },
    "0": {
        "nome": "Gate 0 - holdout em futures",
        "superficie": "bin_fut",
        "fonte": "binance",
        "default_type": "future",
        "inicio": GATE0_INICIO_MS,
        "fim": None,                  # ate o fim da serie
        "alpha_passa": 0.005,
        "alpha_reprova": 0.0,
        "wr_passa": 0.60,
        "wr_reprova": 0.55,
        "simbolos_min": 12,
        "zona_intermediaria": "reprova",
    },
}

# Referencia da tese, medida em Binance SPOT. Nao e criterio; serve
# para a tabela de comparacao do Gate 0a.
TESE_SPOT = {"n": 493, "alpha": 0.01397, "win_rate": 0.734,
             "positivos": 17, "total": 18}


def checar_fonte(chave, gate):
    """
    Gate 2. Devolve (aprovados, erro).

    Recusa julgar se o manifesto nao existir, se a fonte declarada nao
    bater, ou se o defaultType nao bater. Julgar futures com arquivo de
    spot e exatamente o erro que o Gate 0a existe para detectar - seria
    absurdo que o proprio analisador o cometesse.
    """
    caminho = caminho_manifesto(chave)
    if not os.path.exists(caminho):
        return None, (f"manifesto ausente em {caminho}. Rode "
                      f"'python validacao.py {chave}' antes da analise.")
    with open(caminho, "r", encoding="utf-8") as f:
        man = json.load(f)

    if man.get("fonte") != gate["fonte"]:
        return None, (f"RECUSA: o manifesto declara fonte "
                      f"'{man.get('fonte')}', o {gate['nome']} exige "
                      f"'{gate['fonte']}'.")
    if man.get("default_type") != gate["default_type"]:
        return None, (f"RECUSA: o manifesto declara defaultType "
                      f"'{man.get('default_type')}', o {gate['nome']} exige "
                      f"'{gate['default_type']}'.")
    aprovados = man.get("aprovados", [])
    if not aprovados:
        return None, "nenhum simbolo aprovado no manifesto."
    return aprovados, None


def analisar_simbolo(chave, sym, inicio_ms, fim_ms):
    """
    (eventos, retornos_benchmark, descartados) de um simbolo, restrito
    a janela [inicio_ms, fim_ms].

    Exige contiguidade estrita entre entrada e saida: se faltam velas
    dentro da janela, "60 minutos depois" nao e 60 minutos depois, e o
    evento e descartado em vez de contabilizado errado.
    """
    arrays, _ = ler_csv(caminho_csv(chave, sym))
    if arrays is None:
        return [], np.array([]), 0

    t_all = arrays["time"]
    mask = (t_all >= inicio_ms) & (t_all <= fim_ms)
    t = t_all[mask]
    c = arrays["close"][mask]
    h = arrays["high"][mask]
    l = arrays["low"][mask]

    if len(t) < HORIZONTE_MIN + JANELA_SIGMA + 2:
        return [], np.array([]), 0

    eventos = []
    descartados = 0
    for i in indices_de_gatilho(t, c):
        j = i + HORIZONTE_MIN
        if int(t[j]) - int(t[i]) != HORIZONTE_MIN * MS_POR_MINUTO:
            descartados += 1
            continue
        entrada = float(c[i])
        saida = float(c[j])
        mae, mfe = excursoes(entrada, h[i + 1:j + 1], l[i + 1:j + 1])
        if mae is None:
            descartados += 1
            continue
        eventos.append({
            "symbol": sym,
            "t": int(t[i]),
            "ret_gatilho": float(c[i] / c[i - 1] - 1.0),
            "sigma": float(sigma_pre_gatilho(c[:i])),
            "ret_60m": float(saida / entrada - 1.0),
            "mae": mae,
            "mfe": mfe,
        })

    bench, bench_t = [], []
    n = len(c)
    for k in range(0, n - HORIZONTE_MIN, PASSO_BENCHMARK):
        j = k + HORIZONTE_MIN
        if int(t[j]) - int(t[k]) != HORIZONTE_MIN * MS_POR_MINUTO:
            continue
        if c[k] > 0:
            bench.append(float(c[j] / c[k] - 1.0))
            bench_t.append(int(t[k]))

    # O 4o valor existe para que o benchmark possa ser agrupado por dia
    # junto com os eventos. Sem carimbo de tempo, `agregacao="dia"` teria
    # que comparar media diaria de evento contra media empilhada de
    # benchmark - duas unidades diferentes dentro do mesmo alpha.
    return eventos, np.array(bench), descartados, np.array(bench_t)


AGREGACOES = ("evento", "dia")


class AgregacaoNaoDeclarada(Exception):
    """
    `medir()` foi chamada sem dizer o que ela esta contando.

    Nao ha valor padrao de proposito. Um padrao aqui e a forma canonica
    de defeito silencioso deste projeto: o padrao certo para reaplicar a
    tese e o padrao ERRADO para qualquer teste novo, e quem escrever o
    proximo arquivo herdaria a escolha errada por omissao - sem erro,
    sem aviso, com numero plausivel.

    Contar eventos correlacionados como independentes foi a primeira
    causa da morte da tese (design effect medido de 3,51 a 7,45). O
    Adendo 2 do PRE_REGISTRO_OI declara que o teste de OI agrega POR
    DIA, nas quatro celulas. Declaracao em documento nao segura: isto
    aqui segura.

    Escreva `agregacao="evento"` e assuma, ou `agregacao="dia"` e esteja
    certo. Ninguem herda por omissao.
    """


def _dia_utc(ms):
    return datetime.fromtimestamp(ms / 1000.0, timezone.utc).strftime("%Y%m%d")


def _medias_diarias(ts, vals):
    """[(ts_ms, valor)] -> array com uma media por dia UTC."""
    por_dia = defaultdict(list)
    for t, v in zip(ts, vals):
        por_dia[_dia_utc(int(t))].append(float(v))
    return np.array([float(np.mean(v)) for v in por_dia.values()])


def medir(chave, aprovados, inicio_ms, fim_ms, rotulo, agregacao=None):
    """
    Resumo agregado de uma superficie.

    `agregacao` e OBRIGATORIA e nao tem padrao (ver AgregacaoNaoDeclarada):

      "evento" - cada evento vale um. Correto para REAPLICAR a tese, que
                 foi medida assim; errado para qualquer coisa nova,
                 porque conta eventos correlacionados como independentes.
      "dia"    - cada dia UTC vale um, evento e benchmark agrupados na
                 mesma unidade. E o que o Adendo 2 exige do teste de OI.

    MAE e MFE continuam em nivel de EVENTO nas duas agregacoes: sao
    estatisticas de distribuicao de excursao, e "mediana das medianas
    diarias" nao e uma medida de drawdown.
    """
    if agregacao is None:
        raise AgregacaoNaoDeclarada(
            "medir() exige agregacao=%s, sem padrao. "
            "Veja AgregacaoNaoDeclarada." % (" ou ".join(map(repr,
                                                             AGREGACOES)),))
    if agregacao not in AGREGACOES:
        raise AgregacaoNaoDeclarada(
            "agregacao=%r desconhecida; use %s"
            % (agregacao, " ou ".join(map(repr, AGREGACOES))))

    todos, benches, bench_ts, descartados = [], [], [], 0
    por_simbolo = {}

    for sym in aprovados:
        ev, bench, desc, bts = analisar_simbolo(chave, sym, inicio_ms, fim_ms)
        descartados += desc
        todos.extend(ev)
        if len(bench):
            benches.append(bench)
            bench_ts.append(bts)
        if ev:
            r_ev = np.array([e["ret_60m"] for e in ev])
            if agregacao == "dia":
                r_ev = _medias_diarias([e["t"] for e in ev], r_ev)
        else:
            r_ev = np.array([])
        por_simbolo[sym] = {
            "n": len(ev),
            "n_unidades": int(len(r_ev)),
            "ret_medio": float(r_ev.mean()) if len(r_ev) else 0.0,
            "win_rate": float((r_ev > 0).mean()) if len(r_ev) else 0.0,
            "bench": float(bench.mean()) if len(bench) else 0.0,
        }

    if not todos:
        return None

    maes = np.array([e["mae"] for e in todos])
    mfes = np.array([e["mfe"] for e in todos])
    b_vals = np.concatenate(benches) if benches else np.array([0.0])
    b_ts = np.concatenate(bench_ts) if bench_ts else np.array([0])

    if agregacao == "evento":
        rets = np.array([e["ret_60m"] for e in todos])
        bench_u = b_vals
    else:
        rets = _medias_diarias([e["t"] for e in todos],
                               [e["ret_60m"] for e in todos])
        bench_u = _medias_diarias(b_ts, b_vals)

    positivos = [s for s, d in por_simbolo.items()
                 if d["n"] > 0 and d["ret_medio"] > 0]
    com_eventos = [s for s, d in por_simbolo.items() if d["n"] > 0]

    return {
        "rotulo": rotulo,
        "superficie": chave,
        "agregacao": agregacao,
        "n": len(rets),
        "n_eventos": len(todos),
        "n_bench": len(bench_u),
        "descartados": descartados,
        "ret_medio": float(rets.mean()),
        "benchmark": float(bench_u.mean()),
        "alpha": float(rets.mean() - bench_u.mean()),
        "win_rate": float((rets > 0).mean()),
        "mae_mediano": float(np.median(maes)),
        "mae_p25": float(np.percentile(maes, 25)),
        "mae_p10": float(np.percentile(maes, 10)),
        "mfe_mediano": float(np.median(mfes)),
        "positivos": len(positivos),
        "com_eventos": len(com_eventos),
        "por_simbolo": por_simbolo,
    }


def imprimir_por_simbolo(res, aprovados):
    print("\nPOR SIMBOLO")
    print(f"{'sym':<6}{'n':>6}{'ret medio':>12}{'win rate':>11}"
          f"{'benchmark':>12}")
    print("-" * 47)
    for sym in aprovados:
        d = res["por_simbolo"].get(sym)
        if not d or d["n"] == 0:
            print(f"{sym:<6}{0:>6}{'-':>12}{'-':>11}{'-':>12}")
            continue
        print(f"{sym:<6}{d['n']:>6}{d['ret_medio']:>11.3%}"
              f"{d['win_rate']:>11.1%}{d['bench']:>12.3%}")


def imprimir_agregado(res):
    print("\nAGREGADO")
    print(f"  eventos (n)              {res['n']}")
    print(f"  benchmark (n)            {res['n_bench']}")
    if res["descartados"]:
        print(f"  descartados por buraco   {res['descartados']}")
    print(f"  retorno de preco 60 min  {res['ret_medio']:+.3%}")
    print(f"  benchmark                {res['benchmark']:+.3%}")
    print(f"  ALPHA                    {res['alpha']:+.3%}")
    print(f"  win rate                 {res['win_rate']:.1%}")
    print(f"  MAE mediano              {res['mae_mediano']:+.2%}")
    print(f"  MAE p25                  {res['mae_p25']:+.2%}")
    print(f"  MAE p10                  {res['mae_p10']:+.2%}")
    print(f"  MFE mediano              {res['mfe_mediano']:+.2%}")
    print(f"  simbolos positivos       {res['positivos']}/"
          f"{res['com_eventos']}")


def julgar(gate, res, familia=None):
    """
    Devolve (veredito, linhas) sem mover nenhum limiar.

    Invariante 10, aplicada: nao ha julgamento sem familia de busca
    registrada e selada. `exigir_familia` levanta excecao — isto e
    asserção, nao comentario.
    """
    exigir_familia(familia if familia is not None else FAMILIA_TESE)
    linhas = []
    c_alpha_p = res["alpha"] > gate["alpha_passa"]
    c_wr_p = res["win_rate"] > gate["wr_passa"]
    c_alpha_r = res["alpha"] < gate["alpha_reprova"]
    c_wr_r = res["win_rate"] < gate["wr_reprova"]

    linhas.append(f"  alpha > {gate['alpha_passa']:+.1%}            "
                  f"{res['alpha']:+.3%}   {'ok' if c_alpha_p else 'nao'}")
    linhas.append(f"  win rate > {gate['wr_passa']:.0%}           "
                  f"{res['win_rate']:.1%}   {'ok' if c_wr_p else 'nao'}")

    c_sym = True
    if gate["simbolos_min"]:
        c_sym = res["positivos"] >= gate["simbolos_min"]
        linhas.append(f"  >= {gate['simbolos_min']} simbolos positivos  "
                      f"{res['positivos']}      {'ok' if c_sym else 'nao'}")

    if c_alpha_p and c_wr_p and c_sym:
        return "APROVADO", linhas
    if c_alpha_r or c_wr_r:
        return "REPROVADO", linhas
    if gate["zona_intermediaria"] == "reprova":
        return "REPROVADO", linhas
    return "INCONCLUSIVO", linhas


def main(argv):
    if not argv or argv[0] not in GATES:
        print("Uso: python analise.py 0a|0")
        return 2

    chave_gate = argv[0]
    gate = GATES[chave_gate]
    chave = gate["superficie"]

    aprovados, erro = checar_fonte(chave, gate)
    if erro:
        print(erro)
        return 2

    inicio = gate["inicio"]
    fim = gate["fim"] if gate["fim"] else (1 << 62)

    print(gate["nome"])
    print(f"  superficie {chave} ({gate['fonte']}, "
          f"defaultType={gate['default_type']})  - fonte conferida")
    print(f"  janela {iso(inicio)} a "
          f"{iso(fim) if gate['fim'] else 'fim da serie'} UTC")
    print(f"  {len(aprovados)} simbolos aprovados na validacao")
    rebaixados = [s for s in MAJORS if s not in aprovados]
    if rebaixados:
        print(f"  excluidos: {rebaixados}")
    print(f"  gatilho [-3.0%, -1.5%] 1m | saida {HORIZONTE_MIN} min | "
          f"sem stop | benchmark a cada {PASSO_BENCHMARK} min")

    # agregacao="evento" e DELIBERADA aqui: este arquivo reaplica o
    # procedimento da tese sem alterar um parametro, e a tese foi
    # medida empilhando eventos. E tambem o defeito que a matou - o
    # design effect de 3,51 a 7,45 mora exatamente nesta escolha.
    # Reproduzir o erro para poder exibi-lo e o proposito do Gate 0a.
    # Qualquer analise NOVA usa agregacao="dia".
    res = medir(chave, aprovados, inicio, fim, chave_gate,
                agregacao="evento")
    if res is None:
        print("\nERRO: zero eventos na janela.")
        return 2

    imprimir_por_simbolo(res, aprovados)
    imprimir_agregado(res)

    # ---- controle em spot, so no Gate 0a ----
    controle = None
    if chave_gate == "0a":
        apr_spot, err_spot = checar_fonte("bin_spot", {
            "nome": "controle spot", "fonte": "binance",
            "default_type": "spot"})
        comuns = None
        fut_comuns = None
        if err_spot:
            print(f"\nCONTROLE SPOT indisponivel: {err_spot}")
        else:
            # O controle roda sobre a INTERSECAO dos aprovados das duas
            # superficies. Comparar futures-sobre-18 com spot-sobre-17
            # confundiria efeito de superficie com efeito de universo -
            # e a pergunta do Gate 0a e exatamente sobre superficie.
            # O VEREDITO continua sobre os aprovados de futures; o que
            # roda na intersecao e so a tabela de comparacao.
            comuns = [s for s in aprovados if s in apr_spot]
            # idem: o controle de encanamento tem que ser medido do
            # MESMO jeito que a tese, ou nao e controle.
            controle = medir("bin_spot", comuns, inicio, fim, "spot",
                             agregacao="evento")
            if len(comuns) != len(aprovados):
                fut_comuns = medir("bin_fut", comuns, inicio, fim,
                                   "futures_intersecao",
                                   agregacao="evento")
                fora = [s for s in aprovados if s not in apr_spot]
                print(f"\n  Intersecao de {len(comuns)} simbolos para a "
                      f"comparacao; fora do spot: {fora}.")
                print(f"  O veredito continua sobre os {len(aprovados)} "
                      f"aprovados em futures.")

        comp = fut_comuns if fut_comuns else res
        print("\nGATE 0a - SPOT versus FUTURES (mesma janela, mesmo "
              "conjunto de simbolos)")
        print(f"{'':<20}{'spot (tese)':>14}{'spot (remedido)':>18}"
              f"{'futures':>14}")
        print("-" * 66)

        def linha(rotulo, tese, chave_res, fmt):
            c = (format(controle[chave_res], fmt) if controle else "n/d")
            f_ = format(comp[chave_res], fmt)
            print(f"{rotulo:<20}{tese:>14}{c:>18}{f_:>14}")

        linha("n", TESE_SPOT["n"], "n", "d")
        linha("alpha", f"{TESE_SPOT['alpha']:.3%}", "alpha", ".3%")
        linha("win rate", f"{TESE_SPOT['win_rate']:.1%}", "win_rate", ".1%")
        pos_t = f"{TESE_SPOT['positivos']}/{TESE_SPOT['total']}"
        pos_c = (f"{controle['positivos']}/{controle['com_eventos']}"
                 if controle else "n/d")
        pos_f = f"{comp['positivos']}/{comp['com_eventos']}"
        print(f"{'majors positivos':<20}{pos_t:>14}{pos_c:>18}{pos_f:>14}")

        if controle:
            print("\n  O spot remedido e o controle do encanamento. Se ele")
            print("  nao reproduzir a tese, a divergencia esta no metodo e")
            print("  nao na superficie - e o Gate 0a nao pode ser lido.")

    # ---- veredito ----
    print(f"\n{FAMILIA_TESE.resumo()}")
    print("  O criterio do gate foi fixado antes de ver o dado e NAO e o "
          "limiar corrigido.")
    print("  Os dois convivem: o gate decide capital, a correcao decide "
          "se ha evidencia.")
    veredito, linhas = julgar(gate, res, FAMILIA_TESE)
    print(f"\n{gate['nome'].split(' - ')[0].upper()}")
    for ln in linhas:
        print(ln)
    print()
    print(f"  VEREDITO: {veredito}")

    if veredito == "REPROVADO" and chave_gate == "0a":
        print("  O edge era artefato de spot. O bot operaria perpetuo, e")
        print("  nenhum holdout conserta isso. O projeto termina aqui.")
    elif veredito == "INCONCLUSIVO":
        print(f"  Zona intermediaria: alpha entre "
              f"{gate['alpha_reprova']:+.1%} e {gate['alpha_passa']:+.1%}, "
              f"ou win rate entre {gate['wr_reprova']:.0%} e "
              f"{gate['wr_passa']:.0%}.")
        print("  A especificacao NAO define o que fazer nesta faixa para")
        print("  este gate. Nao inventei uma regra: a decisao e sua, e")
        print("  deveria ter sido escrita antes de ver este numero.")
    if veredito != "APROVADO":
        print("  Nao ajuste parametro e rode de novo.")

    saida = os.path.join(SUPERFICIES[chave]["dir"],
                         f"resultado_gate{chave_gate}.json")
    with open(saida, "w", encoding="utf-8") as f:
        json.dump({"gate": chave_gate, "veredito": veredito,
                   "futures": res, "controle_spot": controle}, f,
                  indent=1, ensure_ascii=False)
    print(f"\nresultado: {saida}")
    return {"APROVADO": 0, "REPROVADO": 1, "INCONCLUSIVO": 3}[veredito]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
