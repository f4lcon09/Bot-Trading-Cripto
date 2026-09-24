#!/usr/bin/env python3
"""
CONFIG.PY - constantes do Sniper V2.

Lista estatica. Sem auto-descoberta, sem scanner, sem leitura de
universo em runtime. Se um simbolo precisa entrar ou sair, edita-se
aqui e o diff aparece no historico.
"""
import os

RAIZ = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------
# UNIVERSO - 18 majors. Estatico por decisao, nao por preguica:
# o mesmo sinal nas iliquidas da 51% de acerto (ruido), e o limiar de
# 100.000 USDC da liquidacao parcial da Hyperliquid nem e alcancado
# nesses livros.
# --------------------------------------------------------------------
MAJORS = [
    "BTC", "ETH", "SOL", "DOGE", "ADA", "AVAX",
    "LINK", "DOT", "ARB", "OP", "APT", "SUI",
    "NEAR", "ATOM", "UNI", "AAVE", "TON", "TRX",
]
assert len(MAJORS) == 18, f"universo deve ter 18 majors, tem {len(MAJORS)}"
assert len(set(MAJORS)) == 18, "simbolo duplicado no universo"

# --------------------------------------------------------------------
# GATILHO - retorno de 1 minuto na faixa [-3.0%, -1.5%].
# Fracoes, nao percentos. GATILHO_MAX e o menos negativo.
# --------------------------------------------------------------------
GATILHO_MIN = -0.030
GATILHO_MAX = -0.015
assert GATILHO_MIN < GATILHO_MAX < 0, "faixa de gatilho invertida"

HORIZONTE_MIN = 60        # saida por tempo
JANELA_SIGMA = 30         # velas para o desvio-padrao local
PASSO_BENCHMARK = 37      # amostragem de instantes de benchmark

# --------------------------------------------------------------------
# SUPERFICIES - uma pasta por superficie, NUNCA misturadas.
#
# A tese foi medida em Binance SPOT. O bot operaria perpetuo. Essa
# transferencia de superficie nunca foi verificada, e e o que o Gate 0a
# testa. Por isso as tres ficam separadas em disco, cada uma com seu
# manifesto declarando a fonte: o analisador se recusa a julgar se o
# manifesto indicar fonte diferente da declarada (Gate 2).
# --------------------------------------------------------------------
SUPERFICIES = {
    "bin_fut": {
        "dir": os.path.join(RAIZ, "museu_bin_fut"),
        "fonte": "binance",
        "default_type": "future",
        "mercado": "futures/um",     # caminho no data.binance.vision
        "sufixo": "USDT",
        "serve": "Gate 0a e Gate 0",
    },
    "bin_spot": {
        "dir": os.path.join(RAIZ, "museu_bin_spot"),
        "fonte": "binance",
        "default_type": "spot",
        "mercado": "spot",
        "sufixo": "USDT",
        "serve": "controle do Gate 0a",
    },
    "hl": {
        "dir": os.path.join(RAIZ, "museu_hl"),
        "fonte": "hyperliquid",
        "default_type": "swap",
        "mercado": None,
        "sufixo": "USDC",
        "serve": "Gate 0b e acumulo diario",
    },
}

# --------------------------------------------------------------------
# JANELAS - decididas antes de ver qualquer resultado.
# --------------------------------------------------------------------
MUSEU_INICIO_MS = 1754006400000     # 2025-08-01T00:00:00Z, inicio da coleta

# Gate 0a: a MESMA janela da tese (09/ago/2025 a 02/abr/2026),
# reaplicada em futures. E o teste de transferencia de superficie.
GATE0A_INICIO_MS = 1754697600000    # 2025-08-09T00:00:00Z
GATE0A_FIM_MS = 1775088000000       # 2026-04-02T00:00:00Z

# Gate 0: holdout. De 02/abr/2026 ate agora.
GATE0_INICIO_MS = 1775088000000     # 2026-04-02T00:00:00Z

# --------------------------------------------------------------------
# FONTES
# --------------------------------------------------------------------
DATA_VISION = "https://data.binance.vision/data"
BIN_REST_FUT = "https://fapi.binance.com/fapi/v1/klines"
BIN_REST_SPOT = "https://api.binance.com/api/v3/klines"

API_INFO = "https://api.hyperliquid.xyz/info"
MAX_VELAS_RESPOSTA = 5000
PAUSA_REQUISICAO_S = 1.1   # HL: teto de 60 req/min (peso 20, limite 1200)

# Validacao: qualquer simbolo que falhe e rebaixado e excluido da
# analise. Nunca remendado.
COBERTURA_MINIMA = 0.99

# --------------------------------------------------------------------
# FASE 1 - coletor de execucao
# --------------------------------------------------------------------
WS_URL = "wss://api.hyperliquid.xyz/ws"
DIR_EXECUCAO = os.path.join(RAIZ, "dados_execucao")
NIVEIS_LIVRO = 10                      # profundidade capturada por lado
NOCIONAIS_TESTE = (20.0, 50.0, 200.0)  # US$ para caminhar o livro
PING_INTERVALO_S = 50                  # keepalive do WebSocket

# Snapshots escalonados do livro apos o gatilho.
#
# O caminhamento do livro assume que o livro nao se moveu entre o
# snapshot e a chegada da ordem. Durante uma cascata e exatamente o que
# falha: o livro visto 300 ms atras ja nao existe, e o slippage
# simulado sai sistematicamente melhor que o real, com vies maximo
# justo quando o gatilho dispara.
#
# A degradacao entre estes instantes mede a velocidade com que o livro
# foge. Nao exige ordem nenhuma, e converte coleta passiva em
# experimento com resposta.
OFFSETS_LIVRO_MS = (200, 500, 1000, 5000)

# --------------------------------------------------------------------
# CREDENCIAIS - vazias no fonte, por invariante 7. Nenhuma das fases
# autorizadas envia ordem, entao nada aqui e usado ainda. As klines
# publicas da Binance nao exigem chave nem conta.
# --------------------------------------------------------------------
HL_ACCOUNT_ADDRESS = os.environ.get("HL_ACCOUNT_ADDRESS", "")
HL_SECRET_KEY = os.environ.get("HL_SECRET_KEY", "")
