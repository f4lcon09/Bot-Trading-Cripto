#!/usr/bin/env python3
"""
CALENDARIO.PY - quantos dias corridos para juntar N dias qualificados.

  python calendario.py             # tabela contra cobertura
  python calendario.py --autoteste # prova que ele consegue reprovar

--------------------------------------------------------------------
POR QUE NAO DA PARA INTERPOLAR
--------------------------------------------------------------------
O Adendo 2 tabulou calendario a 37%, 60% e 100% de cobertura. E tentador
ler 72% como "entre 60% e 100%, mais perto do 60%". Errado, e nao por
incerteza de medicao: por estrutura.

Um dia QUALIFICADO exige DOIS eventos no mesmo dia caindo em baldes
opostos de delta de OI. Perder metade dos minutos nao corta a
probabilidade pela metade - corta por algo proximo do quadrado, porque
os dois eventos tem de sobreviver. Interpolar linearmente SUBESTIMA o
ganho de melhorar cobertura, e subestimar esse ganho e o que faz um
Wake on RTC parecer opcional.

--------------------------------------------------------------------
A CONTA
--------------------------------------------------------------------
Num dia com k eventos, cada evento e observado com probabilidade c (a
cobertura) e cai no balde A com prob pA, no B com pB. O dia qualifica
se sobrar pelo menos um A E pelo menos um B:

  P(qualifica | k) = 1 - (1-c*pA)^k - (1-c*pB)^k + (1-c*pA-c*pB)^k

Note que k = 1 da SEMPRE zero: um evento nao pode estar nos dois baldes.
E por isso que a relacao e curva e nao reta.

O k vem da distribuicao REAL de eventos por dia do museu - nao de uma
media, porque a media esconde que dias de muitos eventos carregam quase
toda a probabilidade de qualificar.

--------------------------------------------------------------------
O QUE E MEDIDO E O QUE E SUPOSTO
--------------------------------------------------------------------
MEDIDO   a distribuicao de eventos por dia, no museu Binance.
SUPOSTO  pA e pB - as fracoes de eventos em cada balde de delta de OI.
         NAO HA COMO MEDIR: o museu nao tem open interest, e a coleta ao
         vivo tem zero eventos da tese de OI. A tabela e reportada numa
         FAIXA de pA=pB, nunca num valor, e o resultado imprime qual
         suposicao usou.

Pressuposto adicional, e ele importa: a conta supoe cobertura ALEATORIA
no tempo. Hoje ela nao e - 08:49-11:50 UTC falta em todos os dias, o que
e ausencia SISTEMATICA. Com cobertura sistematica, um evento que cai na
faixa cega nunca e observado, e o calendario real e PIOR que o desta
tabela. A tabela vale como teto otimista enquanto o ponto cego existir.
"""
import sys
from collections import Counter
from datetime import datetime, timezone

try:
    from analise import analisar_simbolo
    from config import GATE0_INICIO_MS, MAJORS
except ImportError:  # pragma: no cover
    analisar_simbolo = None

N_ALVO = 17          # dias qualificados, regra de parada em vigor
COBERTURAS = (0.20, 0.37, 0.50, 0.60, 0.72, 0.85, 1.00)
FRACOES_BALDE = (0.25, 0.3333, 0.40)


class PressupostoNaoDeclarado(Exception):
    """Faltou cobertura, fracao de balde, N ou a distribuicao de eventos."""


def p_qualifica(k, c, pa, pb):
    """P(dia com k eventos qualificar), cobertura c, baldes pa e pb."""
    if k < 2:
        return 0.0            # um evento nao ocupa dois baldes
    ca, cb = c * pa, c * pb
    if ca + cb > 1.0:
        raise PressupostoNaoDeclarado(
            f"c*(pa+pb) = {ca + cb:.3f} > 1: probabilidades incoerentes")
    return (1.0 - (1.0 - ca) ** k - (1.0 - cb) ** k
            + (1.0 - ca - cb) ** k)


def taxa_por_dia_corrido(dist, c, pa, pb):
    """
    Fracao de dias CORRIDOS que qualificam.

    `dist` e {k: quantos dias tiveram k eventos}, incluindo k = 0. Os
    dias sem evento entram no denominador: eles fazem parte do
    calendario mesmo sem contribuir.
    """
    if not dist:
        raise PressupostoNaoDeclarado("distribuicao de eventos por dia vazia")
    total = sum(dist.values())
    return sum(n * p_qualifica(k, c, pa, pb) for k, n in dist.items()) / total


def calendario(dist, c, pa, pb, n_alvo=N_ALVO):
    """(dias corridos, meses) para juntar n_alvo dias qualificados."""
    taxa = taxa_por_dia_corrido(dist, c, pa, pb)
    if taxa <= 0:
        return float("inf"), float("inf")
    dias = n_alvo / taxa
    return dias, dias / 30.44


def distribuicao_do_museu(chave="bin_fut", inicio=None, fim=None):
    """{k: dias com k eventos}, a partir do museu. Inclui dias com zero."""
    if analisar_simbolo is None:
        raise PressupostoNaoDeclarado("museu/analise indisponivel")
    inicio = GATE0_INICIO_MS if inicio is None else inicio
    fim = 10 ** 14 if fim is None else fim
    por_dia = Counter()
    minimo = maximo = None
    for sym in MAJORS:
        evs, _, _, _ = analisar_simbolo(chave, sym, inicio, fim)
        for e in evs:
            t = e["t"]
            minimo = t if minimo is None else min(minimo, t)
            maximo = t if maximo is None else max(maximo, t)
            d = datetime.fromtimestamp(t / 1000.0, timezone.utc)
            por_dia[d.strftime("%Y-%m-%d")] += 1
    if not por_dia:
        raise PressupostoNaoDeclarado("zero eventos no museu nesta janela")
    corridos = int((maximo - minimo) / 86400000.0) + 1
    dist = Counter(por_dia.values())
    dist[0] = max(0, corridos - len(por_dia))
    return dist, corridos, sum(por_dia.values())


def _ok(cond, rotulo, detalhe=""):
    print("  %s %s%s" % ("OK   " if cond else "FALHA", rotulo,
                         ("   " + detalhe) if detalhe else ""))
    return bool(cond)


def autoteste():
    r = []

    print(chr(10) + "1. CASOS FECHADOS, VERIFICAVEIS A MAO")
    # k=2, c=1, pa=pb=0.5: 1 - 0.5^2 - 0.5^2 + 0 = 0.5
    r.append(_ok(abs(p_qualifica(2, 1.0, 0.5, 0.5) - 0.5) < 1e-12,
                 "k=2, c=1, baldes 50/50 -> 0,5",
                 "%.6f" % p_qualifica(2, 1.0, 0.5, 0.5)))
    # k=1 nunca qualifica, seja qual for a cobertura
    r.append(_ok(all(p_qualifica(1, c, 0.5, 0.5) == 0.0
                     for c in (0.1, 0.5, 1.0)),
                 "k=1 nunca qualifica"))
    r.append(_ok(p_qualifica(0, 1.0, 0.5, 0.5) == 0.0, "k=0 nunca qualifica"))
    # c=0 nunca qualifica
    r.append(_ok(p_qualifica(10, 0.0, 0.5, 0.5) == 0.0,
                 "cobertura zero nunca qualifica"))
    # k=3, c=1, 50/50: 1 - 0.125 - 0.125 + 0 = 0.75
    r.append(_ok(abs(p_qualifica(3, 1.0, 0.5, 0.5) - 0.75) < 1e-12,
                 "k=3, c=1, baldes 50/50 -> 0,75"))

    print(chr(10) + "2. A RELACAO E CURVA, NAO RETA")
    dist = Counter({0: 40, 2: 20, 3: 15, 5: 10, 8: 5})
    t100 = taxa_por_dia_corrido(dist, 1.00, 1 / 3, 1 / 3)
    t50 = taxa_por_dia_corrido(dist, 0.50, 1 / 3, 1 / 3)
    t25 = taxa_por_dia_corrido(dist, 0.25, 1 / 3, 1 / 3)
    r.append(_ok(t50 < 0.5 * t100,
                 "metade da cobertura rende MENOS da metade dos dias",
                 "%.4f < %.4f" % (t50, 0.5 * t100)))
    r.append(_ok(t25 < 0.5 * t50,
                 "e cai de novo mais que a metade",
                 "%.4f < %.4f" % (t25, 0.5 * t50)))
    r.append(_ok(t25 / t100 < 0.25,
                 "um quarto da cobertura rende menos de um quarto",
                 "razao %.3f" % (t25 / t100)))
    lin = t100 * 0.5
    r.append(_ok(lin / t50 > 1.2,
                 "interpolar linear SUPERESTIMA a taxa em >20%",
                 "fator %.2fx" % (lin / t50)))

    print(chr(10) + "3. MONOTONIA E COERENCIA")
    r.append(_ok(all(taxa_por_dia_corrido(dist, a, 1 / 3, 1 / 3)
                     < taxa_por_dia_corrido(dist, b, 1 / 3, 1 / 3)
                     for a, b in zip(COBERTURAS, COBERTURAS[1:])),
                 "mais cobertura, mais dias qualificados"))
    d1, _ = calendario(dist, 1.00, 1 / 3, 1 / 3)
    d2, _ = calendario(dist, 0.50, 1 / 3, 1 / 3)
    r.append(_ok(d2 > d1, "menos cobertura, calendario mais longo",
                 "%.0f > %.0f dias" % (d2, d1)))
    r.append(_ok(abs(calendario(dist, 1.0, 1 / 3, 1 / 3, 34)[0]
                     - 2 * d1) < 1e-6,
                 "dobrar N dobra o calendario"))

    print(chr(10) + "4. RECUSA PRESSUPOSTO INCOERENTE OU AUSENTE")
    for fn, rotulo in (
            (lambda: taxa_por_dia_corrido({}, 1.0, 0.5, 0.5),
             "distribuicao vazia"),
            (lambda: p_qualifica(3, 1.0, 0.7, 0.7),
             "c*(pa+pb) maior que 1")):
        try:
            fn()
            r.append(_ok(False, rotulo, "-> NAO recusou"))
        except PressupostoNaoDeclarado:
            r.append(_ok(True, rotulo, "-> PressupostoNaoDeclarado"))

    print(chr(10) + "=" * 62)
    print("%d/%d verificacoes passaram" % (sum(r), len(r)))
    print("=" * 62)
    return 0 if all(r) else 1


def main():
    try:
        dist, corridos, n_ev = distribuicao_do_museu()
    except PressupostoNaoDeclarado as e:
        print("sem distribuicao medida: %s" % e)
        print("Isto e ausencia de medida, nao medida de zero.")
        return 2

    print("CALENDARIO PARA %d DIAS QUALIFICADOS" % N_ALVO)
    print("")
    print("MEDIDO   distribuicao de eventos por dia, museu bin_fut, holdout")
    print("         %d eventos em %d dias corridos; %d dias com evento"
          % (n_ev, corridos, corridos - dist.get(0, 0)))
    print("SUPOSTO  pA = pB, a fracao de eventos em cada balde de delta de")
    print("         OI. Nao ha como medir: o museu nao tem OI e a base da")
    print("         tese de OI tem zero eventos. Reportado em faixa.")
    print("SUPOSTO  cobertura ALEATORIA no tempo. Hoje ela e sistematica")
    print("         (08:49-11:50 UTC falta em todos os dias), entao a")
    print("         tabela e TETO OTIMISTA enquanto o ponto cego existir.")
    print("")
    print("%9s %28s %26s" % ("cobertura", "dias corridos (pA=pB)",
                             "meses (pA=pB)"))
    print("%9s %8s %9s %9s %8s %8s %8s"
          % ("", "0,25", "0,33", "0,40", "0,25", "0,33", "0,40"))
    print("-" * 66)
    for c in COBERTURAS:
        ds, ms = [], []
        for p in FRACOES_BALDE:
            d, m = calendario(dist, c, p, p)
            ds.append(d)
            ms.append(m)
        print("%8.0f%% %8.0f %9.0f %9.0f %8.1f %8.1f %8.1f"
              % (100 * c, ds[0], ds[1], ds[2], ms[0], ms[1], ms[2]))
    print("-" * 66)

    # ----------------------------------------------------------------
    # A DIRECAO DA CURVATURA, MEDIDA E NAO SUPOSTA
    #
    # A intuicao natural e que, como um dia qualificado precisa de DOIS
    # eventos, perder metade dos minutos custaria perto do quadrado. Isso
    # vale para dias de k=2, e a distribuicao REAL nao e feita deles: ela
    # e assimetrica, com dias de muitos eventos que ja qualificam mesmo
    # com cobertura parcial. Nesses dias P(qualifica) SATURA.
    #
    # Resultado: sobre a distribuicao medida a funcao e CONCAVA, nao
    # convexa - o oposto da intuicao. Medido em vez de suposto porque a
    # intuicao errada aponta na direcao confortavel.
    # ----------------------------------------------------------------
    t100 = taxa_por_dia_corrido(dist, 1.0, 1 / 3, 1 / 3)
    t50 = taxa_por_dia_corrido(dist, 0.5, 1 / 3, 1 / 3)
    print("CURVATURA, sobre a distribuicao medida (pA=pB=0,33):")
    print("  taxa a 100%% de cobertura            %.4f dia qualificado/dia"
          % t100)
    print("  taxa a 50%%, se fosse proporcional   %.4f" % (t100 * 0.5))
    print("  taxa a 50%%, medida                  %.4f" % t50)
    if t50 > t100 * 0.5:
        print("  -> a curva e CONCAVA: metade da cobertura rende %.0f%% da"
              % (100 * t50 / t100))
        print("     taxa, nao 50%. Dias de muitos eventos ja qualificam")
        print("     com cobertura parcial, e a saturacao domina o efeito")
        print("     quadratico dos dias de dois eventos.")
        print("  -> CONSEQUENCIA: cada hora recuperada vale MENOS do que")
        print("     um modelo quadratico sugere. O argumento do Wake on")
        print("     RTC NAO se sustenta pelo calendario.")
    else:
        print("  -> a curva e CONVEXA: cada hora recuperada vale mais do")
        print("     que a proporcao sugere.")
    print("")
    print("O que sustenta o Wake on RTC e outra coisa, e esta tabela nao")
    print("a mede: com 08:49-11:50 UTC ausente em TODOS os dias, os")
    print("eventos dessa faixa nunca sao observados. Isso nao e custo de")
    print("calendario, e custo de VALIDADE - o teste nao sabe nada sobre")
    print("aquele horario, e mais dias nao ensinam. Ver invariante 11 e a")
    print("secao de cobertura do PRE_REGISTRO_OI.")
    return 0


if __name__ == "__main__":
    sys.exit(autoteste() if "--autoteste" in sys.argv else main())
