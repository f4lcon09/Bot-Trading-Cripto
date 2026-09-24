#!/usr/bin/env python3
"""
SINAL.PY — definicao unica do gatilho e das medidas do evento.

Este modulo existe por causa do Gate 2. O criterio de paridade exige
que os eventos detectados ao vivo batam com os que o backtest acharia
sobre as mesmas velas, com tolerancia de 1 em 10. A forma barata de
falhar esse gate e ter duas implementacoes do gatilho — uma no
analisador e outra no coletor — que divergem num detalhe de borda.

Aqui ha uma so. O analisador (Fase 0) e o coletor (Fase 1) importam
destas funcoes. A paridade passa a ser estrutural, nao um teste que
se torce para passar.

--------------------------------------------------------------------
DEFINICOES — explicitas porque a especificacao e ambigua
--------------------------------------------------------------------
retorno de 1 minuto : close[i] / close[i-1] - 1   (fecha-a-fecha)

  A especificacao diz "queda de 1,5% a 3,0% em uma vela de 1 minuto".
  Isso admite duas leituras: fecha-a-fecha, ou (close-open)/open.
  Adotamos fecha-a-fecha porque e a mesma serie de retornos que
  alimenta o sigma (realized_sigma diffa os closes), e usar duas
  definicoes diferentes de "retorno de 1 minuto" no mesmo sistema e
  como o erro de fator 100 do fisica_v2: nao levanta excecao, so
  envenena o numero.

  A vela anterior precisa ser o minuto imediatamente anterior. Se
  houver buraco na serie, o retorno atravessa o buraco e nao e um
  retorno de 1 minuto — o evento e descartado.

preco de entrada   : close da vela-gatilho
  Nao e preco de preenchimento. E exatamente essa a lacuna que a
  Fase 1 existe para medir.

sigma              : desvio-padrao dos log-retornos das 30 velas
                     ANTERIORES ao gatilho, exclusive.
  A vela-gatilho nao entra no proprio sigma. Incluir a queda de -2%
  no desvio-padrao que dimensiona a resposta aquela queda e
  circularidade.

MAE / MFE          : excursao maxima em preco contra / a favor,
                     medida sobre low/high das velas da janela,
                     relativa ao preco de entrada.
--------------------------------------------------------------------
"""
import numpy as np

from config import (GATILHO_MIN, GATILHO_MAX, HORIZONTE_MIN,
                    JANELA_SIGMA, MAJORS)
from fisica_v2 import realized_sigma

MS_POR_MINUTO = 60_000


def ret_1m(close_anterior, close_atual):
    """Retorno fecha-a-fecha, em FRACAO. 0.015 = 1.5%."""
    if close_anterior is None or close_anterior <= 0:
        return None
    if close_atual is None or close_atual <= 0:
        return None
    return close_atual / close_anterior - 1.0


def eh_gatilho(ret):
    """
    True se o retorno cai na faixa [-3.0%, -1.5%].
    Bordas inclusivas nos dois lados — uma unica convencao, usada
    igual nos dois lados do Gate 2.
    """
    if ret is None:
        return False
    return GATILHO_MIN <= ret <= GATILHO_MAX


def eh_major(symbol):
    return symbol in MAJORS


def minutos_contiguos(t_anterior_ms, t_atual_ms):
    """As duas velas sao minutos consecutivos, sem buraco na serie?"""
    return (t_atual_ms - t_anterior_ms) == MS_POR_MINUTO


def sigma_pre_gatilho(closes_ate_anterior, bars=JANELA_SIGMA):
    """
    Sigma das `bars` velas anteriores ao gatilho.

    `closes_ate_anterior` termina na vela IMEDIATAMENTE ANTERIOR ao
    gatilho — a vela-gatilho nao entra. Devolve fracao por minuto, ou
    0.0 se nao houver historico suficiente (quem chama decide; este
    modulo nao inventa numero).
    """
    return realized_sigma(closes_ate_anterior, bars=bars)


def excursoes(entrada, highs, lows):
    """
    (mae_frac, mfe_frac) sobre a janela, relativos ao preco de entrada.
    mae e negativo ou zero, mfe e positivo ou zero.
    """
    if entrada is None or entrada <= 0:
        return None, None
    h = np.asarray(highs, dtype=float)
    l = np.asarray(lows, dtype=float)
    h = h[np.isfinite(h) & (h > 0)]
    l = l[np.isfinite(l) & (l > 0)]
    if len(h) == 0 or len(l) == 0:
        return None, None
    mae = float(l.min() / entrada - 1.0)
    mfe = float(h.max() / entrada - 1.0)
    return min(mae, 0.0), max(mfe, 0.0)


def indices_de_gatilho(times_ms, closes, horizonte=HORIZONTE_MIN,
                       janela_sigma=JANELA_SIGMA):
    """
    Varre uma serie e devolve os indices das velas-gatilho.

    Um indice `i` so entra se:
      - ha `janela_sigma` velas antes dele para o sigma;
      - ha `horizonte` velas depois dele para a saida por tempo;
      - a vela i-1 e o minuto imediatamente anterior;
      - o retorno fecha-a-fecha cai na faixa.

    Esta e a mesma peneira que o coletor aplica ao vivo, so que em
    lote. Se esta funcao e o coletor divergirem, o Gate 2 reprova — e
    o objetivo de estarem no mesmo arquivo e que divirjam por edicao
    deliberada, nunca por descuido.
    """
    t = np.asarray(times_ms, dtype=np.int64)
    c = np.asarray(closes, dtype=float)
    n = len(c)
    fora = []
    inicio = max(janela_sigma + 1, 1)
    for i in range(inicio, n - horizonte):
        if c[i - 1] <= 0 or c[i] <= 0:
            continue
        if not minutos_contiguos(int(t[i - 1]), int(t[i])):
            continue
        if eh_gatilho(ret_1m(float(c[i - 1]), float(c[i]))):
            fora.append(i)
    return fora
