#!/usr/bin/env python3
"""
PODER.PY - efeito detectavel, com os pressupostos impressos no resultado.

  python poder.py                 # tabela do desenho do Adendo 2
  python poder.py --autoteste     # prova que ele consegue reprovar

--------------------------------------------------------------------
POR QUE ESTE ARQUIVO EXISTE
--------------------------------------------------------------------
Em 2026-09-25 tres numeros deste projeto foram transportados de um
contexto para outro sem recalculo:

  - "188 dias" era o calendario de 100 EVENTOS, citado como se fosse o
    de 23 DIAS qualificados
  - "1,3 pp detectavel" vinha de um calculo NAO pareado, citado dentro
    de um desenho pareado
  - "alfa 0,0167" era o limiar de uma familia de TRES celulas, citado
    depois que a familia ja tinha virado QUATRO

Nenhum dos tres foi erro de conta. Os tres foram numero certo no lugar
errado - a mesma familia do `blood_toll_pct` da V1, que nao quebrou
nada em execucao e enterrou uma estrategia dentro de um custo que nao
existia, por meses.

Numero que vai para decisao sai de funcao medida, com os pressupostos
impressos junto. Enquanto o calculo de poder morou em uma linha de
terminal, o pressuposto morou na cabeca de quem digitou.

--------------------------------------------------------------------
O QUE ELE RECUSA
--------------------------------------------------------------------
Como a `Medida` da invariante 10, ele nao calcula sem:

  - sigma declarado, E a janela de onde ele foi medido
  - alfa DA FAMILIA e o numero de celulas - ele mesmo divide, porque
    Bonferroni contado a mao foi exatamente o que produziu o 0,0167
  - unidade de agrupamento declarada por extenso
  - esquema de controle declarado (pareado ou nao pareado)

E imprime, dentro do proprio resultado, o alfa e o valor critico que
usou. Transporte entre limiares fica visivel no output em vez de
depender de alguem lembrar de conferir.

--------------------------------------------------------------------
NORMAL x t
--------------------------------------------------------------------
A formula (z_crit + z_poder) * sigma / raiz(n) supoe sigma CONHECIDO.
Com n = 15 ele nao e: o valor critico vem da t com 14 graus de
liberdade, nao da normal, e nesse tamanho a diferenca nao e decorativa.

Os dois metodos estao aqui de proposito, e o autoteste exige que o
exato seja MAIOR que a aproximacao e que os dois convirjam quando n
cresce. Reportar a aproximacao sabendo que ela e otimista seria o mesmo
defeito com o sinal trocado.
"""
import math
import sys
from dataclasses import dataclass, replace

try:
    from scipy import stats as _st
except ImportError:
    _st = None


class PoderIndeclarado(Exception):
    """Faltou pressuposto. Nao existe calculo de poder sem ele."""


class ParametroInvalido(Exception):
    """Pressuposto declarado, mas impossivel."""


# --------------------------------------------------------------------
# Normal padrao sem dependencia externa, para que o caso fechado do
# autoteste seja verificavel a mao mesmo sem scipy instalado.
# --------------------------------------------------------------------
def _phi(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def probit(p):
    """Inversa da normal padrao, por bissecao sobre erfc."""
    if not 0.0 < p < 1.0:
        raise ParametroInvalido("probit(%r) fora de (0,1)" % (p,))
    lo, hi = -40.0, 40.0
    for _ in range(300):
        m = 0.5 * (lo + hi)
        if _phi(m) < p:
            lo = m
        else:
            hi = m
    return 0.5 * (lo + hi)


# rotulo -> (graus de liberdade, fator do erro padrao em unidades de sigma)
#
# pareado     - n e o numero de PARES (dias qualificados) e sigma e o da
#               DIFERENCA intradiaria: ep = sigma/raiz(n), gl = n-1
# nao_pareado - n e o numero de dias POR GRUPO e sigma e o do dia dentro
#               do grupo: ep = sigma*raiz(2/n), gl = 2n-2
ESQUEMAS = {
    "pareado": (lambda n: n - 1, lambda n: 1.0 / math.sqrt(n)),
    "nao_pareado": (lambda n: 2 * n - 2, lambda n: math.sqrt(2.0 / n)),
}


@dataclass(frozen=True)
class Desenho:
    """Os pressupostos. Nenhum deles tem default silencioso."""

    sigma: float = None
    n: int = None
    alfa_familia: float = None
    celulas: int = None
    unidade: str = None
    esquema: str = None
    janela_do_sigma: str = None
    poder: float = 0.80
    rotulo: str = ""

    def __post_init__(self):
        faltando = [k for k in ("sigma", "n", "alfa_familia", "celulas",
                                "unidade", "esquema", "janela_do_sigma")
                    if getattr(self, k) in (None, "")]
        if faltando:
            raise PoderIndeclarado(
                "calculo de poder sem pressuposto declarado: "
                + ", ".join(faltando)
                + ". Nao existe efeito detectavel 'em geral'.")
        if self.sigma <= 0:
            raise ParametroInvalido("sigma=%r nao e dispersao" % (self.sigma,))
        if self.n < 2:
            raise ParametroInvalido("n=%r: sem graus de liberdade" % (self.n,))
        if not 0.0 < self.alfa_familia < 1.0:
            raise ParametroInvalido("alfa_familia=%r" % (self.alfa_familia,))
        if self.celulas < 1:
            raise ParametroInvalido("celulas=%r" % (self.celulas,))
        if not 0.0 < self.poder < 1.0:
            raise ParametroInvalido("poder=%r" % (self.poder,))
        if self.esquema not in ESQUEMAS:
            raise ParametroInvalido(
                "esquema %r nao declarado; use %s"
                % (self.esquema, " ou ".join(repr(k) for k in ESQUEMAS)))

    @property
    def alfa(self):
        """Bonferroni feito AQUI. Contado a mao foi o que deu 0,0167."""
        return self.alfa_familia / self.celulas

    @property
    def gl(self):
        return ESQUEMAS[self.esquema][0](self.n)

    @property
    def erro_padrao(self):
        return self.sigma * ESQUEMAS[self.esquema][1](self.n)


@dataclass(frozen=True)
class ResultadoPoder:
    desenho: Desenho
    efeito: float
    critico: float
    metodo: str

    def __str__(self):
        d = self.desenho
        linhas = [
            "PODER - " + d.rotulo if d.rotulo else "PODER",
            "  efeito detectavel   %.4f   (mesma unidade de sigma)"
            % self.efeito,
            "  sigma               %.4f   medido em: %s"
            % (d.sigma, d.janela_do_sigma),
            "  n                   %d   %s" % (d.n, d.unidade),
            "  esquema             %s   gl = %d" % (d.esquema, d.gl),
            "  erro padrao         %.4f" % d.erro_padrao,
            "  alfa                %.6f   (= %s / %d celulas, bicaudal)"
            % (d.alfa, d.alfa_familia, d.celulas),
            "  poder alvo          %.0f%%" % (100 * d.poder),
            "  metodo              %s" % self.metodo,
            "  valor critico       %.4f" % self.critico,
        ]
        return chr(10).join(linhas)


def _poder_exato(delta, d):
    """Poder real de um teste t bicaudal, pela t nao central."""
    if _st is None:
        raise ParametroInvalido("metodo 't' exige scipy; use 'normal'")
    tc = _st.t.ppf(1.0 - d.alfa / 2.0, d.gl)
    nc = delta / d.erro_padrao
    return _st.nct.sf(tc, d.gl, nc) + _st.nct.cdf(-tc, d.gl, nc)


def detectavel(desenho, metodo="t"):
    """Menor efeito que este desenho enxerga com o poder alvo."""
    d = desenho
    if metodo == "normal":
        crit = probit(1.0 - d.alfa / 2.0)
        efeito = (crit + probit(d.poder)) * d.erro_padrao
        return ResultadoPoder(d, efeito, crit, "normal (sigma conhecido)")
    if metodo != "t":
        raise ParametroInvalido("metodo %r: use 't' ou 'normal'" % (metodo,))
    if _st is None:
        raise ParametroInvalido("metodo 't' exige scipy; use 'normal'")
    lo, hi = 0.0, 100.0 * d.erro_padrao
    for _ in range(200):
        m = 0.5 * (lo + hi)
        if _poder_exato(m, d) < d.poder:
            lo = m
        else:
            hi = m
    crit = _st.t.ppf(1.0 - d.alfa / 2.0, d.gl)
    return ResultadoPoder(d, 0.5 * (lo + hi), crit, "t exata (gl=%d)" % d.gl)


def n_necessario(desenho, efeito, metodo="t", teto=100000):
    """Menor n que enxerga `efeito`. Recalcula o desenho inteiro a cada n."""
    for n in range(2, teto + 1):
        if detectavel(replace(desenho, n=n), metodo).efeito <= efeito:
            return n
    raise ParametroInvalido("nem n=%d enxerga %r" % (teto, efeito))


# --------------------------------------------------------------------
# AUTOTESTE - a exigencia do Gate 1b: nao basta calcular certo, ele
# precisa conseguir REPROVAR. Cada bloco abaixo tem alguma forma de
# falhar que nao depende de eu ter escrito a formula direito.
# --------------------------------------------------------------------
def _ok(cond, rotulo, detalhe=""):
    marca = "OK   " if cond else "FALHA"
    print("  %s %s%s" % (marca, rotulo, ("   " + detalhe) if detalhe else ""))
    return bool(cond)


def _recusa(fn, excecao, rotulo):
    try:
        fn()
    except excecao as e:
        return _ok(True, rotulo, "-> " + type(e).__name__)
    except Exception as e:  # noqa: BLE001
        return _ok(False, rotulo, "-> excecao errada: " + type(e).__name__)
    return _ok(False, rotulo, "-> NAO recusou")


def _base(**kw):
    p = dict(sigma=2.05, n=15, alfa_familia=0.05, celulas=4,
             unidade="dia qualificado", esquema="pareado",
             janela_do_sigma="holdout futures, split aleatorio intradiario")
    p.update(kw)
    return Desenho(**p)


def autoteste():
    r = []

    print(chr(10) + "1. RECUSA SEM PRESSUPOSTO DECLARADO")
    for campo in ("sigma", "n", "alfa_familia", "celulas", "unidade",
                  "esquema", "janela_do_sigma"):
        r.append(_recusa(lambda c=campo: _base(**{c: None}),
                         PoderIndeclarado, "sem " + campo))

    print(chr(10) + "2. RECUSA PRESSUPOSTO IMPOSSIVEL")
    for campo, val in (("sigma", 0.0), ("sigma", -1.0), ("n", 1),
                       ("alfa_familia", 0.0), ("alfa_familia", 1.0),
                       ("celulas", 0), ("poder", 1.0),
                       ("esquema", "pareadissimo")):
        r.append(_recusa(lambda c=campo, v=val: _base(**{c: v}),
                         ParametroInvalido, "%s=%r" % (campo, val)))

    print(chr(10) + "3. O RESULTADO IMPRIME O ALFA E O CRITICO QUE USOU")
    s = str(detectavel(_base(), "normal"))
    r.append(_ok("0.012500" in s, "alfa impresso no resultado"))
    r.append(_ok("0.05 / 4 celulas" in s, "origem do alfa impressa"))
    r.append(_ok("valor critico" in s, "valor critico impresso"))
    r.append(_ok("dia qualificado" in s, "unidade impressa"))
    r.append(_ok("split aleatorio" in s, "janela do sigma impressa"))
    r.append(_ok(abs(_base().alfa - 0.0125) < 1e-12,
                 "Bonferroni feito pelo codigo", "0,05/4 = 0,0125"))
    r.append(_ok(abs(_base(celulas=3).alfa - 0.05 / 3) < 1e-12,
                 "familia de 3 daria outro alfa", "0,0167"))

    print(chr(10) + "4. CASO FECHADO, VERIFICAVEL A MAO")
    # sigma=10, n=25 pares, alfa=0,05 sem familia, poder 80%, normal:
    #   (1,9599640 + 0,8416212) * 10 / raiz(25) = 5,6031704
    caso = _base(sigma=10.0, n=25, alfa_familia=0.05, celulas=1,
                 janela_do_sigma="caso sintetico de referencia")
    got = detectavel(caso, "normal").efeito
    r.append(_ok(abs(got - 5.6031704) < 1e-6,
                 "(z0,975 + z0,80) * 10 / 5",
                 "%.7f vs 5,6031704" % got))
    r.append(_ok(abs(probit(0.975) - 1.9599640) < 1e-6, "probit(0,975)"))
    r.append(_ok(abs(probit(0.80) - 0.8416212) < 1e-6, "probit(0,80)"))

    print(chr(10) + "5. IDENTIDADE EXATA: PODER EM EFEITO ZERO = ALFA")
    if _st is None:
        r.append(_ok(False, "scipy ausente - metodo t indisponivel"))
    else:
        d = _base()
        r.append(_ok(abs(_poder_exato(0.0, d) - d.alfa) < 1e-9,
                     "poder(0) == alfa", "%.8f" % _poder_exato(0.0, d)))

    print(chr(10) + "6. IDA E VOLTA")
    if _st is not None:
        d = _base()
        e = detectavel(d, "t").efeito
        r.append(_ok(abs(_poder_exato(e, d) - d.poder) < 1e-6,
                     "poder(efeito detectavel) == poder alvo",
                     "%.6f" % _poder_exato(e, d)))
        r.append(_ok(n_necessario(d, e, "t") == d.n,
                     "n_necessario devolve o proprio n"))

    print(chr(10) + "7. t EXATA x APROXIMACAO NORMAL")
    if _st is not None:
        d = _base()
        et = detectavel(d, "t").efeito
        en = detectavel(d, "normal").efeito
        r.append(_ok(et > en, "com n=15 a exata e MAIOR",
                     "%.4f > %.4f  (+%.1f%%)" % (et, en, 100 * (et / en - 1))))
        g = _base(n=20000)
        et2 = detectavel(g, "t").efeito
        en2 = detectavel(g, "normal").efeito
        r.append(_ok(abs(et2 / en2 - 1.0) < 0.001,
                     "com n=20000 elas convergem",
                     "diferenca %.4f%%" % (100 * abs(et2 / en2 - 1))))

    print(chr(10) + "8. MONOTONIA")
    e15 = detectavel(_base(), "normal").efeito
    e30 = detectavel(_base(n=30), "normal").efeito
    r.append(_ok(e30 < e15, "mais n enxerga menos",
                 "%.4f < %.4f" % (e30, e15)))
    e8 = detectavel(_base(celulas=8), "normal").efeito
    r.append(_ok(e8 > e15, "familia maior exige efeito maior",
                 "%.4f > %.4f" % (e8, e15)))
    ep = detectavel(_base(esquema="nao_pareado"), "normal").efeito
    r.append(_ok(ep > e15, "nao pareado exige mais com o mesmo n e sigma",
                 "%.4f > %.4f" % (ep, e15)))

    print(chr(10) + "9. REPRODUZ O NUMERO PUBLICADO NO PRE-REGISTRO")
    for sig, alvo, jan in ((2.05, 1.77, "holdout futures"),
                           (1.92, 1.66, "0a spot"),
                           (1.97, 1.70, "0a futures")):
        v = detectavel(_base(sigma=sig, janela_do_sigma=jan), "normal").efeito
        r.append(_ok(abs(round(v, 2) - alvo) < 1e-9,
                     "%s: %s pp" % (jan, alvo), "%.4f" % v))

    print(chr(10) + "=" * 62)
    print("%d/%d verificacoes passaram" % (sum(r), len(r)))
    print("=" * 62)
    return 0 if all(r) else 1


def tabela():
    print("EFEITO DETECTAVEL - DESENHO DO ADENDO 2")
    print("familia de 4 celulas, alfa 0,05, poder 80%, unidade = dia")
    print("n = 15 dias qualificados" + chr(10))

    # Cada esquema tem o SEU sigma. O pareado consome o sigma da
    # diferenca intradiaria; o nao pareado consome o sigma diario dentro
    # do grupo. Trocar um pelo outro e o transporte que este arquivo
    # existe para impedir - e foi cometido aqui na primeira versao.
    SIGMAS = {
        # janela: (sigma da diferenca, sigma diario)
        "holdout futures": (2.05, 1.80),
        "0a spot": (1.92, 2.24),
        "0a futures": (1.97, 2.33),
    }
    for esq, rot, idx, nome in (
            ("pareado", "celula 4 - pareado no dia", 0,
             "sigma da diferenca intradiaria"),
            ("nao_pareado", "celula 1 - nao pareado", 1,
             "sigma diario dentro do grupo")):
        print("=" * 62)
        for jan in ("holdout futures", "0a spot", "0a futures"):
            sig = SIGMAS[jan][idx]
            d = _base(sigma=sig, esquema=esq,
                      janela_do_sigma="%s, %s" % (jan, nome),
                      rotulo="%s | %s" % (rot, jan))
            for met in ("normal", "t"):
                try:
                    print(detectavel(d, met))
                except ParametroInvalido as e:
                    print("  %s: %s" % (met, e))
            print("")
    return 0


if __name__ == "__main__":
    sys.exit(autoteste() if "--autoteste" in sys.argv else tabela())
