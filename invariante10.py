#!/usr/bin/env python3
"""
INVARIANTE10.PY - a decima invariante, como codigo.

As nove primeiras invariantes de risco quebram sozinhas: uma ordem sem
preco levanta excecao, uma margem cross falha a chamada. A decima e
prosa, e prosa so funciona se alguem ler. Ela ja foi violada quatro
vezes neste projeto, duas delas DEPOIS de escrita, e uma dentro da
propria retratacao da anterior.

Este modulo a torna executavel. Nao ha caminho para imprimir um alpha
sem n, sigma, erro padrao e unidade de agrupamento declarada, nem para
julgar um gate sem familia de busca registrada.

  python invariante10.py     # autoteste

--------------------------------------------------------------------
O QUE A INVARIANTE EXIGE
--------------------------------------------------------------------
1. Toda medida de retorno carrega n, sigma medido NAQUELA amostra,
   erro padrao e t. Transportar sigma de outra amostra foi o primeiro
   erro desta analise.

2. Eventos correlacionados sao agrupados pela unidade independente
   antes de qualquer contagem, e o design effect e recalculado a cada
   analise, nunca herdado. O DE medido aqui variou de 3,51 a 7,45
   entre janelas do mesmo sinal.

3. A familia de busca e declarada ANTES da varredura, e o limiar
   corrigido por ela. Fundir celulas adjacentes depois de ver o
   resultado conta como busca.

4. Quando existir mais de uma estrategia de controle defensavel,
   rodar todas e reportar a amplitude. Um alpha que muda de sinal
   conforme o controle nao e medida, e escolha.
--------------------------------------------------------------------
"""
import math
import sys

import numpy as np


class ViolacaoInvariante10(Exception):
    """Levantada quando uma medida tenta ser reportada sem o exigido."""


# ====================================================================
# 1 e 2 - medida com agrupamento declarado
# ====================================================================
class Medida:
    """
    Um alpha reportavel. Construir esta classe e a UNICA forma
    sancionada de produzir um numero para relatorio.

    `valores` sao as observacoes JA agrupadas pela unidade
    independente. `unidade` e o nome dessa unidade, obrigatorio e
    livre — mas tem de ser escrito, porque escrever obriga a pensar.
    `n_bruto` e a contagem antes do agrupamento, usada para o design
    effect.
    """

    def __init__(self, valores, unidade, n_bruto=None, rotulo=""):
        v = np.asarray(valores, dtype=float)
        v = v[np.isfinite(v)]
        if not unidade or not isinstance(unidade, str):
            raise ViolacaoInvariante10(
                "unidade de agrupamento nao declarada. Escreva qual e a "
                "observacao independente ('dia', 'evento', 'semana') — "
                "nao ha default, de proposito.")
        if len(v) < 2:
            raise ViolacaoInvariante10(
                f"amostra de {len(v)} unidades nao permite erro padrao.")
        self.rotulo = rotulo
        self.unidade = unidade
        self.valores = v
        self.n = len(v)
        self.n_bruto = int(n_bruto) if n_bruto else len(v)
        self.media = float(v.mean())
        self.sigma = float(v.std(ddof=1))
        self.ep = self.sigma / math.sqrt(self.n)
        self.t = self.media / self.ep if self.ep > 0 else float("nan")
        self.design_effect = self.n_bruto / self.n if self.n else float("nan")

    @property
    def ic95(self):
        return (self.media - 1.96 * self.ep, self.media + 1.96 * self.ep)

    def linha(self):
        """
        Uma linha de relatorio. Carrega tudo o que a invariante exige,
        e nao ha versao curta.
        """
        lo, hi = self.ic95
        return (f"{self.rotulo:<28} n={self.n:>4} {self.unidade:<8} "
                f"media={self.media*100:+.3f}% sigma={self.sigma*100:.2f}% "
                f"EP={self.ep*100:.3f}% t={self.t:+.2f} "
                f"IC95=[{lo*100:+.3f}%, {hi*100:+.3f}%] "
                f"DE={self.design_effect:.2f}")


def exigir_medida(obj):
    """Guarda para qualquer funcao que va imprimir um alpha."""
    if not isinstance(obj, Medida):
        raise ViolacaoInvariante10(
            f"tentativa de reportar alpha a partir de {type(obj).__name__}. "
            "Construa uma Medida: ela obriga n, sigma, EP e unidade.")
    return obj


# ====================================================================
# INTEGRIDADE DA SERIE - invariante 11, na direcao oposta
#
# A invariante 11 nasceu de ausencia de medicao virando medicao de
# zero. Este guarda cobre o inverso: DUAS medicoes apresentadas como
# uma serie.
#
# Em 23/09/2026 duas instancias do poller coexistiram por um minuto
# durante o conserto do lancador. O resultado foram 36 linhas no
# minuto 03:46 — os 18 simbolos, duas vezes, com valores DIFERENTES em
# 17 dos 18 pares, porque foram duas consultas a API com segundos de
# diferenca.
#
# A trava de instancia unica impede que se repita. Impedir nao e
# detectar: se a trava falhar por qualquer motivo, o sintoma some no
# meio de milhares de linhas. Aquele so apareceu porque alguem foi
# contar.
# ====================================================================
class SerieDuplicada(ViolacaoInvariante10):
    """Levantada quando a mesma chave aparece mais de uma vez."""


def exigir_serie_integra(chaves, rotulo="serie", limite_exemplos=5):
    """
    Recusa uma serie com chave repetida. `chaves` e um iteravel de
    tuplas — (ts, symbol) para o contexto, (ts,) para uma serie de um
    simbolo so.

    Nao tenta escolher qual leitura fica. Duas leituras tiradas com
    segundos de diferenca sao igualmente validas, e escolher e
    inventar. O minuto inteiro e descartado e o descarte e declarado.
    Um minuto perdido e declarado vale mais que um minuto ambiguo e
    escondido.
    """
    vistos = {}
    for k in chaves:
        k = tuple(k)
        vistos[k] = vistos.get(k, 0) + 1
    dup = {k: n for k, n in vistos.items() if n > 1}
    if not dup:
        return len(vistos)
    exemplos = list(dup.items())[:limite_exemplos]
    detalhe = "; ".join(f"{k} x{n}" for k, n in exemplos)
    mais = "" if len(dup) <= limite_exemplos else f" (+{len(dup)-limite_exemplos})"
    raise SerieDuplicada(
        f"{rotulo}: {len(dup)} chave(s) repetida(s) — {detalhe}{mais}. "
        f"Duas medicoes nao sao uma serie. Descarte o periodo inteiro e "
        f"registre o descarte; nao escolha qual leitura fica.")


# ====================================================================
# 3 - familia de busca declarada ANTES
# ====================================================================
class FamiliaDeBusca:
    """
    Registro do que sera varrido, aberto antes de ver qualquer numero.

    `fechar()` sela a familia. Tentar acrescentar celula depois de
    selada levanta excecao — que e exatamente o caso da fusao pos-hoc
    de (-3,0, -1,5] a partir de duas celulas adjacentes, o grau de
    liberdade que nenhuma correcao formal captura.
    """

    def __init__(self, nome):
        self.nome = nome
        self.celulas = []
        self.selada = False

    def declarar(self, *descricoes):
        if self.selada:
            raise ViolacaoInvariante10(
                f"familia '{self.nome}' ja selada com {len(self.celulas)} "
                f"celulas. Acrescentar agora e busca pos-hoc: declare tudo "
                f"antes de rodar, ou abra uma familia nova e assuma o custo.")
        self.celulas.extend(descricoes)
        return self

    def fechar(self):
        if not self.celulas:
            raise ViolacaoInvariante10(
                f"familia '{self.nome}' selada vazia.")
        self.selada = True
        return self

    @property
    def n(self):
        return len(self.celulas)

    def limiar(self, alfa=0.05):
        """Bonferroni. Cru de proposito: e o piso, nao o teto."""
        if not self.selada:
            raise ViolacaoInvariante10(
                f"familia '{self.nome}' nao foi selada. Chame fechar() "
                f"antes de olhar qualquer resultado.")
        return alfa / self.n

    def resumo(self):
        return (f"familia '{self.nome}': {self.n} celulas, "
                f"limiar Bonferroni a 5% = {self.limiar():.5f}")


def exigir_familia(fam):
    """Guarda para julgamento de gate."""
    if not isinstance(fam, FamiliaDeBusca) or not fam.selada:
        raise ViolacaoInvariante10(
            "julgamento de gate sem familia de busca registrada e selada. "
            "Quantas faixas, horizontes e variantes foram varridas? Se a "
            "resposta for 'uma', declare uma — mas declare.")
    return fam


# ====================================================================
# 4 - amplitude entre estrategias de controle
# ====================================================================
def amplitude_de_controle(medidas, rotulo="amplitude"):
    """
    Recebe as Medidas produzidas por CADA estrategia de controle
    defensavel e devolve o relatorio da amplitude.

    Esta funcao existe por causa de 22/09/2026: um achado — "60% do
    alpha era premio de volatilidade" — foi reportado a partir de um
    unico esquema de casamento. Outro esquema, igualmente defensavel,
    deu o oposto. A invariante cobria familia de busca e unidade de
    agrupamento; nao cobria escolha de estrategia de controle.

    Reportar so a melhor estrategia e a mesma familia de erro que
    escolher o bucket vencedor de uma varredura.
    """
    if len(medidas) < 2:
        raise ViolacaoInvariante10(
            "amplitude exige ao menos duas estrategias de controle. Se so "
            "existe uma defensavel, diga por que as outras nao sao — por "
            "escrito, nao por omissao.")
    for m in medidas:
        exigir_medida(m)
    ts = np.array([m.t for m in medidas])
    ms = np.array([m.media for m in medidas])
    atravessa = bool(ts.min() < 0 < ts.max())
    cruza_sig = bool(abs(ts).max() > 1.96 >= abs(ts).min())

    linhas = [f"{rotulo}: {len(medidas)} estrategias de controle"]
    for m in medidas:
        linhas.append("  " + m.linha())
    linhas.append(f"  t de {ts.min():+.2f} a {ts.max():+.2f}   "
                  f"media de {ms.min()*100:+.3f}% a {ms.max()*100:+.3f}%")
    if atravessa:
        linhas.append("  ATRAVESSA ZERO: o sinal do efeito depende do "
                      "controle escolhido. Isto nao e medida, e escolha.")
    elif cruza_sig:
        linhas.append("  ATRAVESSA A LINHA DE SIGNIFICANCIA: significativo "
                      "sob alguns controles e nao sob outros. Reportar o "
                      "maior e selecao.")
    else:
        linhas.append("  conclusao estavel entre os controles testados.")
    return "\n".join(linhas), atravessa or cruza_sig


# ====================================================================
# AUTOTESTE
# ====================================================================
if __name__ == "__main__":
    rng = np.random.default_rng(10)
    falhas = 0

    def esperar_violacao(desc, fn):
        global falhas
        try:
            fn()
            print(f"  FALHOU (nao levantou): {desc}")
            falhas += 1
        except ViolacaoInvariante10 as e:
            print(f"  ok  {desc}\n      -> {str(e)[:66]}...")

    print("GUARDAS DA MEDIDA")
    esperar_violacao("alpha sem unidade de agrupamento declarada",
                     lambda: Medida([0.01, 0.02, 0.03], ""))
    esperar_violacao("amostra de uma unidade so",
                     lambda: Medida([0.01], "dia"))
    esperar_violacao("reportar a partir de lista crua",
                     lambda: exigir_medida([0.01, 0.02]))

    print("\nGUARDAS DA FAMILIA DE BUSCA")
    fam = FamiliaDeBusca("varredura original")
    fam.declarar(*[f"faixa{i}" for i in range(78)]).fechar()
    print(f"  ok  {fam.resumo()}")
    esperar_violacao("acrescentar celula depois de selar (fusao pos-hoc)",
                     lambda: fam.declarar("(-3,0, -1,5] fundida"))
    esperar_violacao("julgar gate sem familia",
                     lambda: exigir_familia(None))
    esperar_violacao("olhar limiar de familia nao selada",
                     lambda: FamiliaDeBusca("aberta").declarar("x").limiar())

    print("\nMEDIDA COMPLETA")
    m = Medida(rng.normal(0.005, 0.02, 67), "dia", n_bruto=499,
               rotulo="in-sample, benchmark ingenuo")
    print("  " + m.linha())

    print("\nAMPLITUDE ENTRE CONTROLES - caso estavel")
    # efeito grande contra ruido pequeno: os tres controles concordam
    ms = [Medida(rng.normal(0.020, 0.010, 67), "dia", 499, f"controle {i}")
          for i in range(3)]
    txt, alerta = amplitude_de_controle(ms)
    print("\n".join("  " + l for l in txt.split("\n")))
    print(f"  alerta={alerta}")

    print("\nAMPLITUDE ENTRE CONTROLES - caso instavel (o de 22/09)")
    ms = [Medida(rng.normal(0.0005, 0.02, 67), "dia", 499, "casado por sigma"),
          Medida(rng.normal(0.0090, 0.02, 67), "dia", 499, "pareado por dia")]
    txt, alerta = amplitude_de_controle(ms)
    print("\n".join("  " + l for l in txt.split("\n")))
    print(f"  alerta={alerta}")

    esperar_violacao("\n  amplitude com uma estrategia so",
                     lambda: amplitude_de_controle([m]))

    print(f"\n{'TODOS OS GUARDAS PASSARAM' if not falhas else f'{falhas} FALHAS'}")
    sys.exit(1 if falhas else 0)
