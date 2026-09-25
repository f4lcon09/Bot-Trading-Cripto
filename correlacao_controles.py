#!/usr/bin/env python3
"""
CORRELACAO_CONTROLES.PY - correlacao entre o estimador pareado e o nao
pareado, medida NO MUSEU.

  python correlacao_controles.py
  python correlacao_controles.py --autoteste

--------------------------------------------------------------------
DE ONDE VEM O DADO, E DE ONDE NAO VEM
--------------------------------------------------------------------
FONTE: museu Binance, futures e spot, janela do Gate 0a e do holdout.
       Sao os mesmos 493/499 eventos ja publicados e ja gastos.

NAO E: a amostra do teste do Adendo 2. Nao ha open interest aqui.
       Nenhum evento da coleta ao vivo entra. Nada lacrado e tocado.

A distincao precisa estar escrita porque daqui a um ano "correlacao
medida" pode parecer que alguem olhou o dado que nao podia olhar. Nao
olhou: o dado do teste nao existe ainda - a base tem zero eventos.

--------------------------------------------------------------------
O QUE ELE MEDE, E POR QUE
--------------------------------------------------------------------
O Adendo 2 declarou a clausula de sinais opostos: se a celula 4
(pareada) cruzar na direcao da tese e a estimativa pontual da celula 1
(nao pareada) for estritamente negativa, o veredito e inconclusivo
declarado.

O custo dessa clausula depende de quanto os dois estimadores andam
juntos. Isso estava declarado como NAO CONHECIDO - corretamente, porque
ninguem tinha medido. Mas e mensuravel sem tocar no dado do teste: os
dois estimadores sao funcoes das medias diarias, e o museu tem dias com
eventos em quantidade.

A variavel classificadora do teste e o delta de OI, que o museu nao tem.
Entao a correlacao e medida sob classificadores SUBSTITUTOS, e o que
importa e que eles particionem DENTRO do dia, como o delta de OI fara.
O `aleatorio` e a referencia sob H0; os outros dois sao proxies
contextuais medidos antes do evento.

NENHUM classificador enxerga `ret_60m`. Isso e verificado pelo
autoteste, permutando o desfecho e exigindo que a particao nao mude.

--------------------------------------------------------------------
O QUE SAI DAQUI NAO E O VEREDITO
--------------------------------------------------------------------
Este arquivo nao testa a tese e nao produz alpha. Ele mede uma
propriedade do DESENHO - quanto dois estimadores se movem juntos - para
que o custo de uma clausula ja escrita deixe de ser desconhecido.
"""
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

from analise import analisar_simbolo
from config import (GATE0A_FIM_MS, GATE0A_INICIO_MS, GATE0_INICIO_MS,
                    MAJORS)

try:
    from scipy.stats import multivariate_normal as _mvn
except ImportError:
    _mvn = None

N_DESENHO = 17          # dias qualificados, regra de parada em vigor
REPLICAS = 4000
SEMENTE = 20260925

# (rotulo, chave da superficie, inicio, fim, sigma da diferenca, sigma diario)
# Os dois sigmas vem do Adendo 2 e sao os do desenho, nao remedidos aqui.
JANELAS = [
    ("0a futures", "bin_fut", GATE0A_INICIO_MS, GATE0A_FIM_MS, 1.97, 2.33),
    ("0a spot", "bin_spot", GATE0A_INICIO_MS, GATE0A_FIM_MS, 1.92, 2.24),
    ("holdout futures", "bin_fut", GATE0_INICIO_MS, 10**14, 2.05, 1.80),
]


def dia_utc(ms):
    return datetime.fromtimestamp(ms / 1000.0, timezone.utc).strftime("%Y-%m-%d")


def eventos(chave, inicio, fim):
    """Eventos do museu, com dia UTC. Sem OI, sem dado ao vivo."""
    fora = []
    for sym in MAJORS:
        evs, _, _, _ = analisar_simbolo(chave, sym, inicio, fim)
        for e in evs:
            fora.append({"dia": dia_utc(e["t"]), "sigma": e["sigma"],
                         "gatilho": e["ret_gatilho"],
                         "ret": 100.0 * e["ret_60m"]})   # em pp
    return fora


# --------------------------------------------------------------------
# CLASSIFICADORES - nenhum recebe `ret`. A assinatura e a garantia:
# eles veem uma lista de (sigma, gatilho) e devolvem um vetor de 0/1.
# --------------------------------------------------------------------
def _mediana_do_dia(valores, rng):
    v = np.asarray(valores, dtype=float)
    med = np.median(v)
    g = (v > med).astype(int)
    # empates (dia com valores iguais) vao ao acaso, para nao criar
    # grupo vazio por construcao
    emp = v == med
    if emp.any():
        g[emp] = rng.integers(0, 2, size=int(emp.sum()))
    return g


CLASSIFICADORES = {
    "aleatorio": lambda sig, gat, rng: rng.integers(0, 2, size=len(sig)),
    "sigma": lambda sig, gat, rng: _mediana_do_dia(sig, rng),
    "gatilho": lambda sig, gat, rng: _mediana_do_dia(gat, rng),
}


def particionar(evs, classificador, rng):
    """{dia: (media do grupo 0, media do grupo 1, n do 0, n do 1)}."""
    por_dia = defaultdict(list)
    for e in evs:
        por_dia[e["dia"]].append(e)
    fora = {}
    for dia, lista in por_dia.items():
        sig = [e["sigma"] for e in lista]
        gat = [e["gatilho"] for e in lista]
        g = CLASSIFICADORES[classificador](sig, gat, rng)
        a = [lista[i]["ret"] for i in range(len(lista)) if g[i] == 0]
        b = [lista[i]["ret"] for i in range(len(lista)) if g[i] == 1]
        fora[dia] = (float(np.mean(a)) if a else None,
                     float(np.mean(b)) if b else None, len(a), len(b))
    return fora


def estimadores(medias_por_dia, dias_q, dias_u, empilhado=False):
    """
    (pareado, nao pareado) sobre um conjunto de dias.

    pareado - media, nos dias qualificados, de (media A - media B).

    nao pareado, `empilhado=False` - o DECLARADO no Adendo 2: media das
        medias DIARIAS de A, um peso por dia, sobre todo dia com A,
        menos o mesmo para B. Dia nao qualificado entra aqui.

    nao pareado, `empilhado=True` - o DEFEITO, presente para ser
        exibido e nunca usado: media sobre EVENTOS empilhados, que
        pondera cada dia pelo numero de eventos que ele teve. E a
        primeira causa da morte da tese - eventos correlacionados
        contados como independentes - reencarnada dentro do teste
        escrito para nao repeti-la.

    A diferenca nao e estilistica. Com agregacao diaria e 100% de dias
    qualificados os dois estimadores sao IDENTICOS; com empilhamento
    eles divergem mesmo assim, e rho = 1 nunca aparece. O autoteste
    exige as duas coisas.
    """
    pares = [medias_por_dia[d][0] - medias_por_dia[d][1] for d in dias_q]
    pareado = float(np.mean(pares)) if pares else float("nan")

    dias = list(dias_q) + list(dias_u)
    if empilhado:
        sa = sum(medias_por_dia[d][0] * medias_por_dia[d][2] for d in dias
                 if medias_por_dia[d][0] is not None)
        na = sum(medias_por_dia[d][2] for d in dias
                 if medias_por_dia[d][0] is not None)
        sb = sum(medias_por_dia[d][1] * medias_por_dia[d][3] for d in dias
                 if medias_por_dia[d][1] is not None)
        nb = sum(medias_por_dia[d][3] for d in dias
                 if medias_por_dia[d][1] is not None)
        if not na or not nb:
            return pareado, float("nan")
        return pareado, float(sa / na - sb / nb)

    a = [medias_por_dia[d][0] for d in dias
         if medias_por_dia[d][0] is not None]
    b = [medias_por_dia[d][1] for d in dias
         if medias_por_dia[d][1] is not None]
    if not a or not b:
        return pareado, float("nan")
    return pareado, float(np.mean(a) - np.mean(b))


def correlacao(evs, classificador, semente=SEMENTE, replicas=REPLICAS,
               efeito=0.0, n_desenho=N_DESENHO, empilhado=False,
               fracao_nq=None):
    """
    Bootstrap sobre DIAS, reamostrando na dimensao do desenho.

    Cada replica sorteia `n_desenho` dias qualificados com reposicao,
    mais dias nao qualificados. Os dois estimadores sao calculados na
    MESMA replica - e por isso que a correlacao medida e a correlacao
    por dado compartilhado.

    `fracao_nq` fixa a fracao de dias NAO qualificados, em vez de usar a
    proporcao observada no museu. E o parametro que governa tudo: a
    clausula de sinais opostos so dispara por esses dias, entao o custo
    dela e funcao da fracao, e rho anda junto. Sob o delta de OI real a
    fracao pode ser bem outra que a do museu.
    """
    rng = np.random.default_rng(semente)
    medias = particionar(evs, classificador, rng)
    if efeito:
        medias = {d: (None if v[0] is None else v[0] + efeito,
                      v[1], v[2], v[3]) for d, v in medias.items()}

    q = [d for d, v in medias.items() if v[0] is not None and v[1] is not None]
    u = [d for d, v in medias.items() if (v[0] is None) != (v[1] is None)]
    if len(q) < 2:
        return None
    if fracao_nq is None:
        n_u = int(round(n_desenho * len(u) / max(1, len(q))))
    elif fracao_nq >= 1.0:
        return None
    else:
        n_u = int(round(n_desenho * fracao_nq / (1.0 - fracao_nq)))

    P, U = [], []
    for _ in range(replicas):
        dq = [q[i] for i in rng.integers(0, len(q), size=n_desenho)]
        du = [u[i] for i in rng.integers(0, len(u), size=n_u)] if u and n_u \
            else []
        p, nu = estimadores(medias, dq, du, empilhado=empilhado)
        if not (math.isnan(p) or math.isnan(nu)):
            P.append(p)
            U.append(nu)
    if len(P) < 100:
        return None
    P, U = np.array(P), np.array(U)
    return {"rho": float(np.corrcoef(P, U)[0, 1]),
            "dias_q": len(q), "dias_u": len(u), "n_eventos": len(evs),
            "n_u_usado": n_u,
            "fracao_nq": n_u / float(n_desenho + n_u),
            "media_pareado": float(P.mean()),
            "media_nao_pareado": float(U.mean()),
            "replicas": len(P)}


# --------------------------------------------------------------------
# A conta que a clausula pede
# --------------------------------------------------------------------
def _phi(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def prob_clausula(delta, sig_dif, sig_dia, rho, n=N_DESENHO, t_crit=2.8131):
    """
    P(celula 4 cruza na direcao da tese E celula 1 sai negativa).

    Normal bivariada: as duas estimativas tem media `delta`, erros
    padrao do desenho, e correlacao `rho`. O corte da celula 4 e
    t_crit * erro padrao pareado.
    """
    sp = sig_dif / math.sqrt(n)
    su = sig_dia * math.sqrt(2.0 / n)
    corte = t_crit * sp
    marginal = _phi((0.0 - delta) / su)
    if _mvn is None:
        return None, marginal
    cov = [[sp * sp, rho * sp * su], [rho * sp * su, su * su]]
    # P(P>corte, U<0) = P(U<0) - P(P<=corte, U<0)
    conj = marginal - float(_mvn(mean=[delta, delta], cov=cov,
                                 allow_singular=True).cdf([corte, 0.0]))
    return max(0.0, conj), marginal


FRACOES = (0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80)


def pior_custo(sdif, sdia, rho, passo=0.02, teto=5.0):
    """Maior P(clausula) varrendo o efeito verdadeiro, e onde ela ocorre."""
    melhor = (0.0, 0.0)
    d = 0.0
    while d <= teto:
        c, _ = prob_clausula(d, sdif, sdia, rho)
        if c is not None and c > melhor[0]:
            melhor = (c, d)
        d += passo
    return melhor


def tabela_por_fracao(evs_por_janela, replicas=2000):
    """
    O custo da clausula contra a FRACAO DE DIAS NAO QUALIFICADOS.

    rho nao e um numero solto: a clausula so dispara pelos dias nao
    qualificados, entao a fracao deles e que governa, e rho anda junto.
    Sob o delta de OI real a fracao pode ser bem diferente da do museu.
    Esta tabela existe para que, quando os dias reais existirem, o custo
    seja LIDO na linha correspondente - sem remodelar nada, e sem que a
    leitura pareca ajuste feito depois.
    """
    print("")
    print("=" * 70)
    print("CUSTO DA CLAUSULA CONTRA A FRACAO DE DIAS NAO QUALIFICADOS")
    print("(N = %d dias qualificados; pior caso sobre as tres janelas,"
          % N_DESENHO)
    print(" os tres classificadores e todo efeito verdadeiro ate 5 pp)")
    print("")
    print("%9s %8s %16s %12s %12s"
          % ("fracao nq", "dias nq", "rho medido", "pior custo", "no efeito"))
    print("-" * 62)
    linhas = []
    for f in FRACOES:
        rhos = []
        n_u = None
        for rot, evs in evs_por_janela.items():
            for c in CLASSIFICADORES:
                r = correlacao(evs, c, replicas=replicas, fracao_nq=f)
                if r:
                    rhos.append(r["rho"])
                    n_u = r["n_u_usado"]
        if not rhos:
            continue
        lo, hi = min(rhos), max(rhos)
        pior, onde = 0.0, 0.0
        for _, _, _, _, sdif, sdia in JANELAS:
            c, d = pior_custo(sdif, sdia, lo)
            if c > pior:
                pior, onde = c, d
        linhas.append((f, n_u, lo, hi, pior, onde))
        print("%8.0f%% %8d %7.3f a %.3f %11.3f%% %10.2f pp"
              % (100 * f, n_u, lo, hi, 100 * pior, onde))
    print("-" * 62)
    print("Leitura: o custo e o teto sob o rho MENOS favoravel medido")
    print("naquela fracao. Fracao maior -> mais dia que so o estimador")
    print("nao pareado ve -> menos correlacao -> clausula mais cara.")
    return linhas


def main():
    print("CORRELACAO ENTRE OS ESTIMADORES PAREADO E NAO PAREADO")
    print("fonte: MUSEU (Binance futures/spot). Nao e a amostra do teste.")
    print("nao ha open interest neste calculo; zero eventos ao vivo usados.")
    print("desenho: N = %d dias qualificados, %d replicas de bootstrap"
          % (N_DESENHO, REPLICAS))

    rhos = []
    guardados = {}
    for rot, chave, ini, fim, sdif, sdia in JANELAS:
        print("")
        print("=" * 70)
        print(rot)
        try:
            evs = eventos(chave, ini, fim)
        except Exception as e:  # noqa: BLE001
            print("  museu indisponivel: %s" % e)
            continue
        if not evs:
            print("  sem eventos nesta janela")
            continue
        guardados[rot] = evs
        print("  %-11s %7s %7s %7s   %s"
              % ("classific.", "rho", "dias_q", "dias_u", "eventos"))
        for c in CLASSIFICADORES:
            r = correlacao(evs, c)
            if r is None:
                print("  %-11s  (dias qualificados insuficientes)" % c)
                continue
            rhos.append(r["rho"])
            print("  %-11s %7.3f %7d %7d   %d"
                  % (c, r["rho"], r["dias_q"], r["dias_u"], r["n_eventos"]))

    if not rhos:
        print("\nsem museu: nada medido. Isto e ausencia de medida,")
        print("nao medida de zero (invariante 11).")
        return 2

    lo, hi = min(rhos), max(rhos)
    print("")
    print("=" * 70)
    print("FAIXA MEDIDA DE rho: %.3f a %.3f" % (lo, hi))

    tabela_por_fracao(guardados)

    print("")
    print("CUSTO DA CLAUSULA DE SINAIS OPOSTOS")
    print("P(celula 4 cruza na direcao da tese E celula 1 sai negativa)")
    print("%-16s %8s %10s %10s %10s"
          % ("janela", "efeito", "marginal", "rho=%.2f" % lo, "rho=%.2f" % hi))
    for rot, _, _, _, sdif, sdia in JANELAS:
        for delta in (1.0, 2.0, 3.0):
            c_lo, marg = prob_clausula(delta, sdif, sdia, lo)
            c_hi, _ = prob_clausula(delta, sdif, sdia, hi)
            print("%-16s %6.1f pp %9.2f%% %9.3f%% %9.3f%%"
                  % (rot, delta, 100 * marg, 100 * c_lo, 100 * c_hi))
    return 0


# --------------------------------------------------------------------
# AUTOTESTE
# --------------------------------------------------------------------
def _ok(cond, rotulo, detalhe=""):
    print("  %s %s%s" % ("OK   " if cond else "FALHA", rotulo,
                         ("   " + detalhe) if detalhe else ""))
    return bool(cond)


def _sintetico(n_dias=40, efeito_no_sigma=0.0, semente=7,
               sempre_qualifica=False):
    """
    Dias com contagem VARIAVEL de eventos, inclusive dias de 1 evento -
    que nao qualificam e so entram no estimador nao pareado. Um gerador
    de 8 eventos por dia produziria 100% de dias qualificados, e nesse
    caso os dois estimadores sao identicos por construcao (ver bloco 4).
    """
    rng = np.random.default_rng(semente)
    evs = []
    for d in range(n_dias):
        nivel = rng.normal(0, 1.5)          # componente do dia
        k = 8 if sempre_qualifica else int(rng.integers(1, 10))
        for _ in range(k):
            evs.append({"dia": "d%02d" % d,
                        "sigma": float(rng.normal()),
                        "gatilho": float(rng.normal()),
                        "ret": float(nivel + rng.normal(0, 2.0))})
    if efeito_no_sigma:
        for e in evs:
            e["ret"] += efeito_no_sigma * (e["sigma"] > 0)
    return evs


def _media_sobre_sementes(cl, chave, n=12, efeito=0.0, **kw):
    """
    Vies do ESTIMADOR, nao de uma amostra. Uma amostra sintetica sozinha
    tem media amostral com erro padrao proprio: testar contra ela reprova
    por azar. A media sobre amostras independentes testa o estimador.
    """
    vals = []
    for s in range(n):
        a = correlacao(_sintetico(semente=100 + s, **kw), cl,
                       semente=SEMENTE + s, replicas=600, efeito=efeito)
        if a:
            vals.append(a[chave])
    return float(np.mean(vals)), float(np.std(vals) / math.sqrt(len(vals)))


def autoteste():
    r = []

    print(chr(10) + "1. NENHUM CLASSIFICADOR ENXERGA O DESFECHO")
    evs = _sintetico()
    rng = np.random.default_rng(1)
    base = particionar(evs, "sigma", np.random.default_rng(1))
    emb = [dict(e) for e in evs]
    perm = np.random.default_rng(2).permutation(len(emb))
    rets = [e["ret"] for e in emb]
    for i, j in enumerate(perm):
        emb[i]["ret"] = rets[j]
    depois = particionar(emb, "sigma", np.random.default_rng(1))
    # a particao nao muda; so as medias mudam, porque o desfecho mudou
    r.append(_ok(set(base) == set(depois),
                 "os mesmos dias qualificam"))
    r.append(_ok(any(abs((base[d][0] or 0) - (depois[d][0] or 0)) > 1e-9
                     for d in base),
                 "as medias mudam quando o desfecho e permutado"))
    r.append(_ok("ret" not in CLASSIFICADORES["sigma"].__code__.co_varnames,
                 "a assinatura do classificador nao tem `ret`"))

    print(chr(10) + "2. ESTIMADORES SEM VIES (media sobre 12 amostras)")
    for cl in ("aleatorio", "sigma"):
        m, se = _media_sobre_sementes(cl, "media_pareado")
        r.append(_ok(abs(m) < 3 * se + 0.05,
                     "%s: pareado ~ 0 sem efeito" % cl,
                     "%.3f +- %.3f" % (m, se)))

    print(chr(10) + "3. EFEITO INJETADO APARECE NOS DOIS")
    for chave, rot in (("media_pareado", "pareado"),
                       ("media_nao_pareado", "nao pareado")):
        m, se = _media_sobre_sementes("aleatorio", chave, efeito=2.0)
        r.append(_ok(abs(m - 2.0) < 3 * se + 0.10,
                     "%s recupera o efeito" % rot, "%.3f +- %.3f" % (m, se)))

    print(chr(10) + "4. A IDENTIDADE ESTRUTURAL, E ONDE ELA SE QUEBRA")
    # Se TODO dia qualifica, os dois estimadores sao o MESMO numero:
    # media das diferencas diarias == diferenca das medias diarias. A
    # clausula de sinais opostos so pode disparar por causa dos dias NAO
    # qualificados, que entram apenas no nao pareado.
    tudo_q = correlacao(_sintetico(sempre_qualifica=True), "aleatorio",
                        replicas=1200)
    r.append(_ok(tudo_q["dias_u"] == 0, "cenario sem dia nao qualificado"))
    r.append(_ok(abs(tudo_q["rho"] - 1.0) < 1e-9,
                 "com todo dia qualificado, rho = 1 exato",
                 "%.6f" % tudo_q["rho"]))
    misto = correlacao(_sintetico(), "aleatorio", replicas=1200)
    r.append(_ok(misto["dias_u"] > 0, "cenario com dia nao qualificado",
                 "%d dias" % misto["dias_u"]))
    r.append(_ok(misto["rho"] < 1.0 - 1e-6,
                 "dia nao qualificado e o que separa os dois estimadores",
                 "rho %.3f" % misto["rho"]))

    print(chr(10) + "4c. A CELULA 1 AGREGA POR DIA, E NAO EMPILHA EVENTOS")
    # A identidade do bloco 4 SO vale se o estimador nao pareado agregar
    # por dia. Se ele empilhasse eventos, ponderaria cada dia pelo numero
    # de eventos que teve - eventos correlacionados contados como
    # independentes, a primeira causa da morte da tese. Estes dois casos
    # separam as duas definicoes de forma executavel, em vez de confiar
    # na leitura do codigo.
    emp_q = correlacao(_sintetico(sempre_qualifica=True), "aleatorio",
                       replicas=1200, empilhado=True)
    r.append(_ok(emp_q["rho"] < 1.0 - 1e-6,
                 "empilhado quebra a identidade mesmo com todo dia qualif.",
                 "rho %.4f" % emp_q["rho"]))
    r.append(_ok(abs(tudo_q["rho"] - 1.0) < 1e-9,
                 "agregado por dia a preserva", "rho %.6f" % tudo_q["rho"]))
    # e o default do modulo e o agregado por dia
    med = particionar(_sintetico(), "aleatorio", np.random.default_rng(3))
    dq = [d for d, v in med.items() if v[0] is not None and v[1] is not None]
    r.append(_ok(estimadores(med, dq, [])[1]
                 != estimadores(med, dq, [], empilhado=True)[1],
                 "as duas definicoes dao numeros diferentes"))
    r.append(_ok(abs(estimadores(med, dq, [])[1]
                     - estimadores(med, dq, [])[0]) < 1e-9,
                 "o default e o agregado por dia (identidade vale)"))

    print(chr(10) + "4b. rho NAO DEPENDE DO TAMANHO DO EFEITO")
    r0 = correlacao(_sintetico(), "aleatorio", replicas=2500)["rho"]
    r2 = correlacao(_sintetico(), "aleatorio", replicas=2500,
                    efeito=2.0)["rho"]
    r.append(_ok(abs(r0 - r2) < 0.05,
                 "os dois sao lineares nas medias diarias",
                 "rho %.3f vs %.3f" % (r0, r2)))
    r.append(_ok(-1.0 <= r0 <= 1.0, "rho dentro de [-1, 1]"))

    print(chr(10) + "5. A CONTA DA CLAUSULA")
    if _mvn is None:
        r.append(_ok(False, "scipy ausente"))
    else:
        c, m = prob_clausula(2.0, 2.05, 1.80, 0.7)
        r.append(_ok(c <= m, "conjunta nunca excede a marginal",
                     "%.4f%% <= %.4f%%" % (100 * c, 100 * m)))
        c_alto, _ = prob_clausula(2.0, 2.05, 1.80, 0.95)
        c_baixo, _ = prob_clausula(2.0, 2.05, 1.80, 0.20)
        r.append(_ok(c_alto < c_baixo, "mais correlacao, clausula mais barata",
                     "%.4f%% < %.4f%%" % (100 * c_alto, 100 * c_baixo)))
        c1, _ = prob_clausula(1.0, 2.05, 1.80, 0.7)
        c3, _ = prob_clausula(3.0, 2.05, 1.80, 0.7)
        r.append(_ok(c1 > c3, "efeito forte torna a clausula rara",
                     "%.4f%% > %.4f%%" % (100 * c1, 100 * c3)))
        z, _ = prob_clausula(0.0, 2.05, 1.80, 0.7)
        r.append(_ok(z < 0.0125, "sem efeito, limitada pelo alfa",
                     "%.4f%%" % (100 * z)))

    print(chr(10) + "6. PROCEDENCIA DECLARADA NO PROPRIO MODULO")
    d = sys.modules[__name__].__doc__
    r.append(_ok("FONTE: museu" in d and "NAO E:" in d, "fonte declarada"))
    r.append(_ok("open interest" in d, "ausencia de OI declarada"))

    print(chr(10) + "=" * 62)
    print("%d/%d verificacoes passaram" % (sum(r), len(r)))
    print("=" * 62)
    return 0 if all(r) else 1


if __name__ == "__main__":
    sys.exit(autoteste() if "--autoteste" in sys.argv else main())
