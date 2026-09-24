#!/usr/bin/env python3
"""
FISICA_V2.PY — modulo de dimensionamento do Sniper V2

Derivado do fisica.py da V1, amputado. Sobraram cinco funcoes; as
outras seis (variance_ratio, hurst_from_vr, jump_ratio,
critical_slowing, physics_features, elasticity_gate) foram removidas
porque foram testadas contra 493 eventos e nao preveem nada — o que
pareciam separar era sigma disfarcado.

A fisica aqui NAO decide SE entrar. Isso e o gatilho de preco.
A fisica decide QUANTO, depois que o gatilho ja disparou.

--------------------------------------------------------------------
CONTRATO DE UNIDADES — leia antes de usar
--------------------------------------------------------------------
sigma e devolvido como FRACAO de log-retorno por minuto.
  sigma = 0.0015  significa 0.15% por minuto.

Se voce esta comparando com a tabela de quartis da especificacao
(0.15 / 0.26 / 0.54 / 2.53), aqueles valores estao em PERCENTO de
retorno simples. Para converter: sigma_pct = sigma * 100.

Confundir os dois e um erro de fator 100 que nao levanta excecao —
ele so faz a alavancagem sair 100x errada. Por isso existe
sigma_pct() e por isso max_safe_leverage() tem assert.
--------------------------------------------------------------------
"""
import numpy as np

# Parametros da V2. Nao sao sugestoes.
HORIZON_MIN = 60      # saida por tempo
K_SIGMA = 2.0         # largura da barreira, em desvios
TARGET_STOP_ROE = -15.0
LEV_CAP = 2           # teto rigido; a 3x o retorno geometrico ja e -1.02%
BARS = 30             # janela de sigma


# ====================================================================
# DIFUSAO — a base de tudo
# ====================================================================
def realized_sigma(closes, bars=BARS):
    """
    Desvio-padrao dos log-retornos de 1 minuto nas ultimas `bars` velas.

    Recebe um array/lista de precos de fechamento, mais recente por
    ultimo. Devolve FRACAO por minuto (0.0015 = 0.15%/min).
    Devolve 0.0 quando nao ha dados suficientes — quem chama decide
    o que fazer com isso, esta funcao nao inventa numero.
    """
    c = np.asarray(closes, dtype=float)
    c = c[-(bars + 1):]
    if len(c) < 5 or np.any(c <= 0):
        return 0.0
    r = np.diff(np.log(c))
    r = r[np.isfinite(r)]
    if len(r) < 3:
        return 0.0
    return float(np.std(r, ddof=1))


def sigma_pct(sigma):
    """sigma em percento por minuto. Use so para log e comparacao."""
    return sigma * 100.0


def expected_excursion(sigma, horizon_min=HORIZON_MIN, k_sigma=K_SIGMA):
    """
    Excursao adversa esperada em `horizon_min` minutos, como fracao
    de preco:  k * sigma * sqrt(t)

    Este e o numero que matou a V1. Com sigma de 0.15%/min e janela
    de 60 min, 2 sigma da 2.32% de preco — a 10x isso e -23% de ROE,
    e o stop de -15% e atingido antes do sinal se realizar.
    """
    if sigma <= 0 or horizon_min <= 0:
        return 0.0
    return float(k_sigma * sigma * np.sqrt(horizon_min))


def diffusion_stop(sigma, lev, horizon_min=HORIZON_MIN, k_sigma=K_SIGMA):
    """
    Stop em PRECO (fracao, negativa), escalado pela volatilidade real.

    Devolve (stop_preco_frac, stop_roe_pct).

    O stop vive em preco, nao em ROE. Um stop escrito em ROE muda de
    lugar quando a alavancagem muda, que e exatamente o bug que fazia
    o stop da V1 cair dentro do ruido a 10x.
    """
    exc = expected_excursion(sigma, horizon_min, k_sigma)
    if exc <= 0:
        return 0.0, 0.0
    return float(-exc), float(-exc * lev * 100.0)


# ====================================================================
# DIMENSIONAMENTO — o que os dados dizem, nao o que a formula dizia
# ====================================================================
# CORRECAO (medida sobre os 493 eventos, 21/09/2026):
#
# A ideia original era alavancagem dinamica via max_safe_leverage.
# Testada de frente contra a alternativa simples, ela PERDE:
#
#   alavancagem fixa 2x + stop escalado por sigma  -> +1.631%/trade
#   alavancagem dinamica (cap 2)                   -> +0.506%/trade
#   alavancagem fixa 2x + stop fixo de -10% preco  -> +0.883%/trade
#
# A dinamica recusa 17% dos eventos e reduz a alavancagem em muitos
# outros, e o que ela evita nao compensa o que ela deixa de ganhar.
#
# O que sobrevive: alavancagem FIXA, stop ESCALADO por sigma.
# O sigma nao serve para prever o MAE (explica so 17% da variancia
# dele, com expoente 0.617 em vez de 1.0) — serve para colocar o
# stop fora do piso de ruido daquela moeda naquele momento.
#
# O platô de k e largo e chato entre 0.25 e 1.5 (+1.554 a +1.651 a
# 2x), o que e sinal de robustez e nao de agulha. k=1.0 por ser
# redondo, nao por ser otimo.
#
# Tudo isto e in-sample sobre a mesma amostra que desenhou o sinal.
# O Gate 0 e quem decide se sobrevive.

LEV = 2                # fixa. Nao e parametro de tuning.
K_STOP = 1.0           # stop = K_STOP * sigma * sqrt(60)
STOP_FLOOR = 0.03      # nunca mais apertado que 3% de preco
STOP_CEIL = 0.15       # nunca mais largo que 15% de preco


def position_stop(sigma, k=K_STOP, horizon_min=HORIZON_MIN,
                  floor=STOP_FLOOR, ceil=STOP_CEIL):
    """
    Stop em PRECO (fracao positiva), escalado pela volatilidade local
    e limitado nos dois extremos.

    O piso existe porque um stop abaixo de 3% de preco cai dentro do
    spread e do slippage. O teto existe porque acima de 15% a 2x o
    prejuizo por operacao passa de 30% de ROE, que nenhuma banca
    pequena aguenta repetidas vezes.

    Devolve 0.0 se sigma for invalido — quem chama NAO opera.
    """
    if sigma <= 0:
        return 0.0
    raw = k * sigma * np.sqrt(horizon_min)
    return float(np.clip(raw, floor, ceil))


def survivable(stop_px, lev=LEV, margem_seguranca=0.80):
    """
    Guarda de liquidacao. A posicao morre quando a excursao adversa
    chega a 100%/lev de preco. O stop precisa disparar bem antes.

    Devolve True se o stop cabe com folga dentro da margem.
    """
    if stop_px <= 0 or lev <= 0:
        return False
    return bool(stop_px * lev < margem_seguranca)


def size_position(sigma, banca_usd, risco_frac=0.02, lev=LEV):
    """
    Devolve (lev, stop_px, notional_usd, margem_usd) ou None.

    Risco por operacao fixo em `risco_frac` da banca NO STOP:
        perda_no_stop = notional * stop_px = banca * risco_frac
    """
    stop_px = position_stop(sigma)
    if stop_px <= 0 or not survivable(stop_px, lev):
        return None
    notional = (banca_usd * risco_frac) / stop_px
    margem = notional / lev
    if margem > banca_usd:
        notional = banca_usd * lev
        margem = banca_usd
    return lev, float(stop_px), float(notional), float(margem)


def max_safe_leverage(sigma, target_stop_roe=TARGET_STOP_ROE,
                      horizon_min=HORIZON_MIN, k_sigma=K_SIGMA,
                      cap=LEV_CAP):
    """
    MANTIDA APENAS COMO DIAGNOSTICO. Nao use para decidir alavancagem
    em producao — ela perde para a alavancagem fixa (ver a correcao no
    topo desta secao). Serve para inspecionar um evento e perguntar
    "quao violento era este?", nada mais.
    """
    assert sigma >= 0.0, f"sigma negativo: {sigma}"
    assert sigma < 0.5, (
        f"sigma={sigma} — alto demais para fracao por minuto. "
        "Voce passou percento? Use sigma/100."
    )
    if sigma <= 0:
        return 0
    exc = expected_excursion(sigma, horizon_min, k_sigma)
    if exc <= 0:
        return 0
    return int(np.clip(np.floor(abs(target_stop_roe) / (exc * 100.0)), 0, cap))



# ====================================================================
# ELASTICIDADE — estimadores de slippage, A VALIDAR na Fase 1
# ====================================================================
# Estes dois entram como ESTIMADORES, nao como filtros. A Fase 1 mede
# slippage de verdade caminhando o livro; estes dois sao a tentativa de
# prever esse numero so com OHLCV. Se a correlacao com o slippage
# medido for fraca, amputa-se os dois tambem.

def amihud_illiquidity(closes, vols, bars=BARS):
    """
    ILLIQ = media(|retorno| / volume em dolar)
    Quanto o preco se move por dolar negociado. Escalado por 1e6.
    BAIXO = livro fundo. ALTO = livro fino.
    """
    c = np.asarray(closes, dtype=float)[-(bars + 1):]
    v = np.asarray(vols, dtype=float)[-(bars + 1):]
    if len(c) < 5 or len(v) != len(c):
        return 0.0
    ret = np.abs(np.diff(c) / c[:-1])
    dollar = v[1:] * c[1:]
    mask = np.isfinite(ret) & np.isfinite(dollar) & (dollar > 0)
    if mask.sum() < 3:
        return 0.0
    return float(np.mean(ret[mask] / dollar[mask]) * 1e6)


def kyle_lambda(opens, closes, vols, bars=BARS):
    """
    Impacto de mercado por unidade de fluxo. Escalado por 1e9.

    Sem tick data nao ha volume assinado de verdade; assina-se pela
    direcao da vela. Cru — e a razao de isto ser estimador e nao
    filtro.
    """
    o = np.asarray(opens, dtype=float)[-(bars + 1):]
    c = np.asarray(closes, dtype=float)[-(bars + 1):]
    v = np.asarray(vols, dtype=float)[-(bars + 1):]
    if len(c) < 10 or len(o) != len(c) or len(v) != len(c):
        return 0.0
    dp = np.diff(c) / c[:-1]
    signed = np.sign(c[1:] - o[1:]) * v[1:] * c[1:]
    mask = np.isfinite(dp) & np.isfinite(signed) & (signed != 0)
    if mask.sum() < 8:
        return 0.0
    x, y = signed[mask], dp[mask]
    denom = float(np.dot(x, x))
    if denom <= 0:
        return 0.0
    return float(np.dot(x, y) / denom * 1e9)


# ====================================================================
# AUTOTESTE — python fisica_v2.py
# ====================================================================
if __name__ == "__main__":
    rng = np.random.default_rng(42)

    print("CONTRATO DE UNIDADES")
    for nome, s_pct in [("calmo   (Q1)", 0.15),
                        ("medio   (Q2)", 0.26),
                        ("agitado (Q3)", 0.54),
                        ("violento(Q4)", 2.53)]:
        s = s_pct / 100.0
        exc = expected_excursion(s)
        L = max_safe_leverage(s)
        sp, sr = diffusion_stop(s, max(L, 1))
        print(f"  {nome}  sigma={sigma_pct(s):5.2f}%/min  "
              f"excursao 60m={exc*100:6.2f}%  lev_max={L}x  "
              f"stop={sp*100:+6.2f}% preco ({sr:+6.1f}% ROE a {max(L,1)}x)")

    print("\nDIMENSIONAMENTO (banca de $100, risco 2%)")
    for nome, s_pct in [("calmo", 0.15), ("medio", 0.26), ("agitado", 0.54), ("violento", 2.53)]:
        r = size_position(s_pct/100.0, 100.0)
        if r is None:
            print(f"  {nome:9} NAO OPERA")
        else:
            L, sp, nt, mg = r
            print(f"  {nome:9} lev={L}x stop={sp*100:5.2f}% preco "
                  f"({sp*L*100:5.1f}% ROE)  notional=${nt:6.2f}  margem=${mg:6.2f}")

    print("\nGUARDAS")
    try:
        max_safe_leverage(2.53)          # percento passado como fracao
        print("  FALHOU: assert nao disparou")
    except AssertionError as e:
        print(f"  ok: {str(e)[:60]}...")

    print(f"  sigma=0      -> lev {max_safe_leverage(0.0)} (nao opere)")
    print(f"  sigma=0.05   -> lev {max_safe_leverage(0.05)} (nao opere)")

    print("\nSANIDADE DO SIGMA")
    for alvo in [0.0015, 0.0050]:
        c = 100 * np.exp(np.cumsum(rng.normal(0, alvo, 500)))
        est = realized_sigma(c, 200)
        print(f"  alvo {alvo:.4f} -> estimado {est:.4f} "
              f"(erro {100*abs(est-alvo)/alvo:.1f}%)")
