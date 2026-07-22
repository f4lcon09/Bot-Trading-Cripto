# Ecossistema Sniper — Pipeline de Trading Algorítmico

Conjunto de ferramentas para coleta de dados de mercado, treino de modelo
preditivo (ML), execução de estratégias de trading em Binance e Hyperliquid
(spot/futuros), e diagnóstico estatístico de performance (post-mortem de
trades).

O pipeline foi desenhado como um ciclo fechado: **minerar dados → treinar
modelo → validar em modo fantasma (Ghost/simulação) → operar ao vivo →
autopsiar resultados → retreinar**.

---

## ⚠️ Autoria e Processo de Validação

Este código foi **gerado com o apoio de IA (LLM)** como ferramenta de
implementação. Isso não significa geração automática sem supervisão — o
processo de trabalho foi:

- **Engenharia de prompt**: toda a arquitetura, regras de decisão, lógica de
  risco e critérios estatísticos foram especificados, iterados e corrigidos
  por mim; a IA funcionou como executor de implementação sob direção técnica
  constante ("Mesa de Guerra" — sessões de debugging e arquitetura linha a
  linha).
- **Revisão de segurança**: cada script que toca chaves de API, ordens reais
  ou dados sensíveis foi auditado manualmente por mim antes de operar com
  capital — incluindo verificação de que chaves/API secrets nunca são
  hardcoded no código (ficam vazias por default, carregadas via variável de
  ambiente/config externa) e que nenhum dado é enviado a terceiros além das
  exchanges (Binance/Hyperliquid via `ccxt`).
- **Verificação de vazamento de dados (data leakage)**: os modelos de ML
  (`forja_v5.py`, `kernel_v5.py`) foram construídos e validados com
  metodologia Walk-Forward com *purge embargo* especificamente para evitar
  contaminação temporal entre treino e teste — algo que precisou ser
  verificado e corrigido manualmente, não é um comportamento "de fábrica" de
  um modelo XGBoost genérico.
- **Testes em campo por mais de 2 meses**: os bots de execução (`sniper_*`)
  rodaram em modo *Ghost* (simulação com dados reais de mercado, sem ordens
  reais) e em operações reais com capital, em paralelo, para comparar ROE
  puro vs. ROE com fricção real (slippage, taxas, latência) antes de
  qualquer decisão de escalar exposição.
- **Avaliação de viabilidade para terceiros**: a documentação abaixo, os
  avisos de risco e as dependências externas foram revisados pensando em
  alguém além de mim rodando este código — mas isso **não elimina a
  necessidade de validação própria** por quem for usar (ver seção de Riscos).

Em suma: a IA acelerou a digitação e a implementação; o julgamento de
engenharia, risco e validação empírica foi feito por mim.

---

## Estrutura do Pipeline

```
minerador_ohlcv.py ──► database/*.csv (histórico OHLCV)
                              │
                              ▼
                   [Máquina do Tempo — não incluída neste pacote]
                              │
                              ▼
                     forja_dna_*.csv (dataset rotulado)
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
             forja_v5.py           autopsia.py
        (treino + validação      (diagnóstico estatístico
         Walk-Forward)            winners vs losers)
                    │
                    ▼
       modelo_sniper_v5.ubj + schema_features_v5.json
                    │
                    ▼
              kernel_v5.py (motor de inferência)
                    │
      ┌─────────────┼──────────────────┬──────────────────┐
      ▼             ▼                  ▼                   ▼
sniper_binance_  sniper_v152_hl.py  sniper_v152_bn.py  sniper_v15h_coletor.py
v9_4_1.py        (HL: live long +   (BN: ghost collector  (V15: grid search /
(BN: live +      ghost long/short)  long+short, sem       Monte Carlo, shadow
ghost, pedágio                      ordens reais)         book, read-only)
duplo no CSV)

futures_coletor.py — coletor multi-estratégia standalone (BN futures,
                      7 estratégias, alavancagem dinâmica)
```

---

## Descrição dos Módulos

### `minerador_ohlcv.py`
Minerador de dados históricos OHLCV (candles de 1 minuto) com roteamento
dual-exchange: Binance como fonte primária (anos de histórico), Hyperliquid
como fallback automático para tokens nativos que não existem na Binance.
Inclui reparo binário de CSVs corrompidos e retomada automática de
mineração interrompida. Gera o "museu" de dados usado para backtesting e
treino de modelo.

### `forja_v5.py`
Motor de treino do modelo preditivo (XGBoost) com validação **Walk-Forward
+ Purge Embargo** — metodologia anti-overfitting que impede vazamento de
informação futura para o passado durante a validação. Faz busca de
threshold ótimo por grid search e produz o par `modelo_sniper_v5.ubj` +
`schema_features_v5.json` consumido pelo Kernel.

### `kernel_v5.py`
Motor de inferência ML standalone (`KernelV5`). Carrega o modelo treinado e
o schema de features, calcula as features de mercado (RSI, VWAP rolling,
Bollinger Band Width, slope, volume ratio etc.) a partir de candles brutos
de forma **exchange-agnostic**, e devolve a probabilidade de sucesso (WIN)
de um sinal candidato. Não decide nada — apenas prevê; a decisão de disparo
é do bot que o consome.

### `autopsia.py`
Ferramenta de diagnóstico estatístico ("bisturi") sobre o histórico de
trades. Separa operações vencedoras de perdedoras e mede onde a física do
mercado diverge entre elas: MFE/MAE, volume ratio, RSI, BBW, alinhamento
com BTC, duração, distância à VWAP, gatilho de entrada, e performance por
moeda. Produz um relatório de terminal usado para decidir onde ajustar
filtros ou features do modelo.

### `futures_coletor.py`
Coletor unificado para Binance USDT-M Futures com 7 estratégias em paralelo
(momentum long/short, sideways bounce, breakout de volume, mean reversion,
Sniper Purista, e um modo experimental de alavancagem alta apenas para
coleta de dados) e alavancagem dinâmica por score de confiança do sinal.

### `sniper_binance_v9_4_1.py` (Sniper Purista — Binance)
Bot de execução ao vivo com arquitetura de **Ghost dual-track**: grava
simultaneamente o ROE "puro" (sem fricção) e o ROE "friccionado"
(descontando pedágio de entrada/saída estimado por latência natural de
execução), permitindo comparar teoria vs. realidade sem depender de
polling pesado de order book.

### `sniper_v152_hl.py` / `sniper_v152_bn.py`
Bots assíncronos para Hyperliquid e Binance respectivamente. O `_hl`
combina execução real (Long) com Ghost bidirecional (Long/Short virtual)
para testar a viabilidade de shorts antes de arriscar capital neles. O
`_bn` é um **coletor Ghost puro** — não envia nenhuma ordem real,
apenas mede a viabilidade da estratégia com dados reais de mercado.

### `sniper_v15h_coletor.py`
Coletor de geração de dataset por grid search / mutação aleatória de
filtros (Monte Carlo), operando em modo **somente leitura** (API pública,
sem ordens). Alimenta o "Shadow Book" usado para descobrir combinações de
filtros com edge estatístico antes de codificá-las como regra fixa.

---

## Dependências

```
ccxt
pandas
numpy
xgboost
scikit-learn
colorama
```

Os bots `sniper_v152_*.py` dependem adicionalmente de dois módulos não
incluídos neste pacote (`ghost_core.py` e, opcionalmente, `sniper_kernel.py`)
que implementam o livro de posições fantasma e o motor de kernel
compartilhado — devem estar no mesmo diretório para execução.

---

## ⚠️ Riscos — Leia Antes de Usar

- **Alavancagem**: `futures_coletor.py` documenta explicitamente que
  leverage acima de 20x em futuros pode liquidar posições com movimentos de
  1,5–5% no ativo. Isso não é uma sugestão de uso — é um limite testado.
- **Nenhum resultado passado garante resultado futuro.** A validação
  Walk-Forward reduz overfitting, não o elimina, e mercados mudam de regime.
- **Chaves de API**: nunca commite `api_key`/`api_secret`/`private_key`
  reais neste repositório. Os defaults dos scripts são strings vazias —
  mantenha assim no código-fonte e injete credenciais via variável de
  ambiente ou arquivo de config fora do controle de versão.
- **Modo Ghost antes de capital real**: todos os bots aqui têm modo
  fantasma/simulação. A recomendação baseada nos meus próprios 2+ meses de
  teste é: nunca pule essa etapa antes de rodar com capital novo, uma nova
  moeda, ou uma nova versão do modelo.
- Este código foi validado no **meu** contexto de risco, capital e
  disciplina operacional. Rodar isso com capital de terceiros exige que
  cada pessoa refaça sua própria validação — a viabilidade que avaliei foi
  a técnica (o sistema funciona como projetado), não uma garantia
  financeira para qualquer usuário.
