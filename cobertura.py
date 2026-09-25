#!/usr/bin/env python3
"""
COBERTURA.PY - contabilidade de cobertura do poller de contexto.

  python cobertura.py              # todos os dias
  python cobertura.py 2026-09-25   # um dia

Existe por causa do Adendo 2 do PRE_REGISTRO_OI.md: a coleta roda em
maquina pessoal, a cobertura e parcial, e o pre-registro passa a exigir
que todo resultado reporte a cobertura por hora UTC da janela usada,
junto com n e erro padrao.

--------------------------------------------------------------------
POR QUE POR HORA, E NAO SO O TOTAL DIARIO
--------------------------------------------------------------------
Perder 25% do dia e perda de poder — resolve-se com mais tempo.
Perder SEMPRE as mesmas horas e ponto cego estrutural — nao se resolve
com tempo nenhum.

Um total diario de 60% nao distingue os dois casos. A tabela por hora
distingue: cobertura espalhada e ruido, cobertura com uma faixa em
zero e vies de horario.
--------------------------------------------------------------------
"""
import collections
import csv
import glob
import os
import sys
from datetime import datetime, timezone

from config import DIR_EXECUCAO, MAJORS

MIN_POR_DIA = 1440


def minutos_por_dia():
    """{dia: set(minuto_utc)} a partir dos CSVs de contexto."""
    fora = collections.defaultdict(set)
    for p in sorted(glob.glob(os.path.join(DIR_EXECUCAO, "contexto_*.csv"))):
        if "falhas" in p:
            continue
        with open(p, encoding="utf-8") as f:
            leitor = csv.reader(f)
            next(leitor, None)
            for r in leitor:
                if not r:
                    continue
                try:
                    t = datetime.fromisoformat(r[0]).astimezone(timezone.utc)
                except (ValueError, IndexError):
                    continue
                fora[t.strftime("%Y-%m-%d")].add(t.hour * 60 + t.minute)
    return fora


def por_hora(minutos):
    """[(hora, presentes, 60)] para um conjunto de minutos do dia."""
    c = collections.Counter(m // 60 for m in minutos)
    return [(h, c.get(h, 0), 60) for h in range(24)]


def barra(frac, largura=24):
    cheio = int(round(frac * largura))
    return "#" * cheio + "." * (largura - cheio)


def main(argv):
    dias = minutos_por_dia()
    if not dias:
        print("nenhum contexto_*.csv em", DIR_EXECUCAO)
        return 2
    alvos = [d for d in sorted(dias) if not argv or d in argv]
    if not alvos:
        print("nenhum dia corresponde a", argv)
        return 2

    print("COBERTURA DO POLLER DE CONTEXTO")
    print("(minutos com pelo menos um registro, por hora UTC)\n")

    total_h = collections.Counter()
    total_possivel = collections.Counter()

    print(f"{'dia':<12}{'minutos':>9}{'cobertura':>11}  perfil por hora UTC "
          f"(0 -> 23)")
    print("-" * 78)
    for d in alvos:
        m = dias[d]
        linha = ""
        for h, presentes, _ in por_hora(m):
            total_h[h] += presentes
            total_possivel[h] += 60
            linha += " .:-=+*#@"[min(8, presentes * 8 // 60)]
        print(f"{d:<12}{len(m):>9}{len(m)/MIN_POR_DIA:>10.0%}  {linha}")

    print("-" * 78)
    print(f"{'legenda':<12}{'':>9}{'':>11}  espaco=0%  @=100%\n")

    print("POR HORA UTC, AGREGADO")
    print(f"{'hora':<6}{'minutos':>9}{'possivel':>10}{'cobertura':>11}  ")
    print("-" * 60)
    zeradas = []
    for h in range(24):
        pres, poss = total_h[h], total_possivel[h]
        frac = pres / poss if poss else 0.0
        if pres == 0:
            zeradas.append(h)
        print(f"{h:02d}:00{pres:>9}{poss:>10}{frac:>10.0%}  {barra(frac)}")

    print("-" * 60)
    tot_p = sum(total_h.values())
    tot_q = sum(total_possivel.values())
    print(f"{'TOTAL':<6}{tot_p:>9}{tot_q:>10}{tot_p/tot_q:>10.0%}")

    if zeradas:
        faixas = []
        ini = zeradas[0]
        ant = ini
        for h in zeradas[1:] + [None]:
            if h is None or h != ant + 1:
                faixas.append((ini, ant))
                if h is not None:
                    ini = h
            if h is not None:
                ant = h
        txt = ", ".join(f"{a:02d}:00-{b:02d}:59" for a, b in faixas)
        print(f"\nHORAS COM COBERTURA ZERO EM TODOS OS DIAS: {txt}")
        print("Isto e ponto cego estrutural, nao perda de poder. Mais dias")
        print("nao corrigem: o teste nunca observa cascata nesse horario.")
    else:
        print("\nNenhuma hora com cobertura zero em todos os dias.")
    return 0


if __name__ == "__main__":
    sys.exit(main([a for a in sys.argv[1:] if not a.startswith("-")]))
