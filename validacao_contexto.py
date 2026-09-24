#!/usr/bin/env python3
"""
VALIDACAO_CONTEXTO.PY - porteiro dos CSVs do poller de contexto.

Os CSVs do museu tinham validador desde o primeiro dia. Os do poller
nao tinham nenhum, e foi assim que 36 linhas num mesmo minuto ficaram
em disco sem ninguem notar — duas instancias colidindo durante o
conserto do lancador, em 23/09/2026.

  python validacao_contexto.py            # todos os dias
  python validacao_contexto.py 2026-09-23 # um dia

Criterios:
  1. cabecalho conhecido (14 colunas, ou 12 no esquema anterior)
  2. ZERO pares (ts, symbol) repetidos       <- invariante 11
  3. mesmo numero de simbolos em todo minuto
  4. simbolos fora do universo declarado
  5. minutos faltando dentro do intervalo do arquivo, cruzados com o
     contexto_falhas do mesmo dia

O criterio 5 nao reprova sozinho: buraco DECLARADO no arquivo de
falhas e buraco honesto. Buraco nao declarado e que e defeito.
"""
import collections
import csv
import glob
import os
import sys
from datetime import datetime, timezone

from config import DIR_EXECUCAO, MAJORS
from invariante10 import SerieDuplicada, exigir_serie_integra

MS_POR_MINUTO = 60_000

CABECALHO_14 = ["ts", "symbol", "open_interest", "funding", "mark_px",
                "oracle_px", "mid_px", "premium", "impact_bid",
                "impact_ask", "day_ntl_vlm", "prev_day_px",
                "is_delisted", "max_leverage"]
CABECALHO_12 = CABECALHO_14[:12]


def ler(caminho):
    linhas = list(csv.reader(open(caminho, encoding="utf-8")))
    if not linhas:
        return None, [], ["arquivo vazio"]
    cab, dados = linhas[0], linhas[1:]
    problemas = []
    if cab == CABECALHO_14:
        esquema = 14
    elif cab == CABECALHO_12:
        esquema = 12
    else:
        return None, [], [f"cabecalho desconhecido ({len(cab)} colunas)"]
    for i, r in enumerate(dados, start=2):
        if len(r) != len(cab):
            problemas.append(f"linha {i}: {len(r)} campos, esperado {len(cab)}")
    return esquema, dados, problemas


def falhas_declaradas(dia):
    """Minutos cobertos por linha no contexto_falhas do mesmo dia."""
    caminho = os.path.join(DIR_EXECUCAO, f"contexto_falhas_{dia}.csv")
    cobertos = set()
    if not os.path.exists(caminho):
        return cobertos
    with open(caminho, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                ini = datetime.fromisoformat(r["ts_inicio"])
                fim = datetime.fromisoformat(r["ts_fim"])
            except (ValueError, KeyError, TypeError):
                continue
            t = ini
            while t <= fim:
                cobertos.add(t.astimezone(timezone.utc).isoformat(
                    timespec="seconds"))
                t = t.fromtimestamp(t.timestamp() + 60, tz=t.tzinfo)
    return cobertos


def sobreposicoes(dia):
    """
    Janelas do contexto_falhas que se sobrepoem entre si.

    Em 24/09 uma linha `01:06:18-01:07:01, 1, recuperado` sobrepunha
    `01:07-01:07, 1, minutos pulados`: o mesmo minuto contado duas
    vezes. O arquivo declarava 429 minutos perdidos e o validador
    encontrava 428 faltando.

    A soma da coluna `minutos_perdidos` tem de bater com o numero de
    minutos DISTINTOS cobertos. Se nao bate, alguma janela foi contada
    duas vezes — e um arquivo de lacunas que inflaciona a propria
    contagem e pior que nenhum, porque parece preciso.
    """
    caminho = os.path.join(DIR_EXECUCAO, f"contexto_falhas_{dia}.csv")
    if not os.path.exists(caminho):
        return None
    declarado = 0
    janelas = []
    with open(caminho, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                ini = datetime.fromisoformat(r["ts_inicio"])
                fim = datetime.fromisoformat(r["ts_fim"])
                declarado += int(r["minutos_perdidos"])
            except (ValueError, KeyError, TypeError):
                continue
            janelas.append((ini, fim, r.get("motivo", "")))
    distintos = len(falhas_declaradas(dia))
    pares = []
    for i in range(len(janelas)):
        for j in range(i + 1, len(janelas)):
            a, b = janelas[i], janelas[j]
            if a[0] <= b[1] and b[0] <= a[1]:
                pares.append((a[2], b[2]))
    return {"declarado": declarado, "distintos": distintos,
            "sobrepostas": pares}


def validar(caminho):
    dia = os.path.basename(caminho)[len("contexto_"):-len(".csv")]
    r = {"arquivo": os.path.basename(caminho), "aprovado": False,
         "motivos": []}

    esquema, dados, problemas = ler(caminho)
    if esquema is None:
        r["motivos"] = problemas
        return r
    r["esquema"] = esquema
    r["n_linhas"] = len(dados)
    r["notas"] = []
    if esquema == 12:
        # aviso, nao defeito: dado valido gravado antes de a coluna
        # existir. Reprovar aqui excluiria serie legitima, que e o
        # oposto do que o porteiro deve fazer.
        r["notas"].append("esquema anterior de 12 colunas: sem is_delisted; "
                          "a exclusao depende dos criterios inferidos")
    if problemas:
        r["motivos"].extend(problemas[:3])

    if not dados:
        r["motivos"].append("sem linhas de dados")
        return r

    # 2. duplicatas — o criterio que faltava
    try:
        exigir_serie_integra(((x[0], x[1]) for x in dados),
                             rotulo=r["arquivo"])
    except SerieDuplicada as e:
        r["motivos"].append(str(e))

    # 3. simbolos por minuto
    por_min = collections.Counter(x[0] for x in dados)
    tamanhos = collections.Counter(por_min.values())
    r["minutos"] = len(por_min)
    r["simbolos_por_minuto"] = dict(tamanhos)
    if len(tamanhos) > 1:
        fora = [t for t, _ in tamanhos.most_common()[1:]]
        r["motivos"].append(
            f"numero de simbolos varia entre minutos: {dict(tamanhos)} "
            f"(tamanhos anomalos: {fora})")

    # 4. universo
    simbolos = set(x[1] for x in dados)
    intrusos = sorted(simbolos - set(MAJORS))
    ausentes = sorted(set(MAJORS) - simbolos)
    if intrusos:
        r["motivos"].append(f"simbolos fora do universo: {intrusos}")
    if ausentes:
        r["motivos"].append(f"majors nunca vistos neste dia: {ausentes}")

    # 5. buracos nao declarados
    ts = sorted(por_min)
    marcas = [datetime.fromisoformat(t) for t in ts]
    esperados = int((marcas[-1] - marcas[0]).total_seconds() // 60) + 1
    faltando = esperados - len(marcas)
    r["minutos_faltando"] = faltando
    if faltando > 0:
        cobertos = falhas_declaradas(dia)
        t = marcas[0]
        nao_declarados = []
        presentes = set(ts)
        while t <= marcas[-1]:
            iso = t.isoformat(timespec="seconds")
            if iso not in presentes and iso not in cobertos:
                nao_declarados.append(iso)
            t = datetime.fromtimestamp(t.timestamp() + 60, tz=t.tzinfo)
        r["buracos_nao_declarados"] = len(nao_declarados)
        if nao_declarados:
            r["motivos"].append(
                f"{len(nao_declarados)} minuto(s) ausente(s) SEM linha no "
                f"contexto_falhas (ex.: {nao_declarados[0]})")

    # 6. coerencia do proprio arquivo de falhas
    sob = sobreposicoes(dia)
    if sob:
        r["falhas_declaradas"] = sob["declarado"]
        r["falhas_distintas"] = sob["distintos"]
        if sob["sobrepostas"]:
            r["motivos"].append(
                f"contexto_falhas tem {len(sob['sobrepostas'])} par(es) de "
                f"janelas sobrepostas (ex.: {sob['sobrepostas'][0]}) — o "
                f"mesmo minuto contado duas vezes")
        if sob["declarado"] != sob["distintos"]:
            r["motivos"].append(
                f"contexto_falhas declara {sob['declarado']} minutos mas "
                f"cobre {sob['distintos']} distintos")

    r["aprovado"] = not r["motivos"]
    return r


def main(argv):
    alvos = argv or None
    arquivos = sorted(p for p in glob.glob(
        os.path.join(DIR_EXECUCAO, "contexto_*.csv")) if "falhas" not in p)
    if alvos:
        arquivos = [p for p in arquivos
                    if any(a in os.path.basename(p) for a in alvos)]
    if not arquivos:
        print("nenhum contexto_*.csv encontrado em", DIR_EXECUCAO)
        return 2

    print("VALIDACAO DO CONTEXTO")
    print(f"{'arquivo':<34}{'linhas':>8}{'minutos':>9}{'esq':>5}"
          f"{'falta':>7}  veredito")
    print("-" * 78)
    reprovados = 0
    for p in arquivos:
        r = validar(p)
        print(f"{r['arquivo']:<34}{r.get('n_linhas','-'):>8}"
              f"{r.get('minutos','-'):>9}{r.get('esquema','-'):>5}"
              f"{r.get('minutos_faltando','-'):>7}  "
              f"{'APROVADO' if r['aprovado'] else 'REPROVADO'}")
        for m in r["motivos"]:
            print(f"    ! {m}")
        for n in r.get("notas", []):
            print(f"    - {n}")
        if not r["aprovado"]:
            reprovados += 1
    print("-" * 78)
    print(f"{len(arquivos) - reprovados}/{len(arquivos)} aprovados")
    return 1 if reprovados else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
