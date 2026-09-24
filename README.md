# Ecossistema Sniper — pesquisa quantitativa em cripto

Duas gerações de código convivem neste repositório, e elas têm status
**opostos**:

| | o que é | status |
| --- | --- | --- |
| **Sniper V2** | infraestrutura de medição e coleta | **em operação** — coleta ativa, nenhuma ordem |
| **V1** (arquivos com sufixo numérico) | pipeline de execução com ML | **autópsia** — registro histórico, não use |

> **Nenhum código deste repositório envia ordem de compra ou venda no estado
> atual.** A V2 é exclusivamente coleta e análise. A V1 enviava, e é
> justamente por isso que está marcada como autópsia.

---

## O resultado que define o projeto

A tese da V2 — reverter quedas de 1,5% a 3,0% em uma vela de 1 minuto, em
majors, com saída por tempo em 60 minutos — foi **construída, medida e
reprovada** entre 21 e 23/09/2026.

| gate | veredito | números |
| --- | --- | --- |
| **0a** replicação em futures | APROVADO | n=499, alpha +1,712%, WR 72,9% |
| **0** holdout abr→set/2026 | **REPROVADO** | n=253, alpha +0,303%, WR 59,3% |
| **0b** paridade de venue | APROVADO | sobreposição 88,2%, defasagem 0,00 min |

E a reanálise mostrou algo pior que a reprovação: **o edge nunca havia sido
significativo nem dentro da amostra de treino.**

Os 493 eventos in-sample se agrupam em ~65 dias independentes — 28% deles
caíram num único dia, 10/out/2025. Contados como unidades correlacionadas
em vez de eventos independentes, o `t` de 3,97 vira 1,76–1,98. O holdout
não derrubou um resultado sólido; confirmou o que a contagem correta já
dizia no próprio treino.

Somado à comparação múltipla — o bucket vencedor saiu de 78 células
varridas, e a faixa `(−3,0, −1,5]` foi criada fundindo duas células
adjacentes **depois** de ver o resultado — não sobra evidência.

**A Fase 2 (bot de execução) não existe e não está autorizada.**

---

## Sniper V2 — o que roda hoje

### Coleta

```bash
python coletor_contexto.py      # 1 poll/minuto — PRIORIDADE MÁXIMA
python minerador_hl.py          # 1 vez por dia
python coletor_execucao.py      # contínuo, ~2 eventos/dia
```

O `coletor_contexto.py` é o único com relógio correndo. `openInterest`,
`funding` e `markPx` **não têm histórico em fonte nenhuma** — a Binance
retém 1 mês a 5 minutos de granularidade, a Hyperliquid só expõe o
snapshot atual. Cada minuto sem rodar é perdido para sempre.

No Windows ele roda pelo Agendador de Tarefas:

```bash
schtasks /Create /XML "poller_task.xml" /TN "SniperV2 - Poller de contexto" /F
```

Gatilho no logon **e** repetição a cada 10 minutos com
`MultipleInstancesPolicy=IgnoreNew`. O `RestartOnFailure` sozinho não basta:
ele só dispara com `ExitCode != 0`, e um encerramento limpo — fim de sessão,
Ctrl+C — não conta como falha. A proteção contra instância dupla está no
próprio Python, com trava de arquivo.

### Museu e análise

```bash
python minerador_binance.py futures     # ~600k velas/símbolo, 1 min cada
python minerador_binance.py spot
python validacao.py bin_fut             # porteiro: rebaixa, nunca remenda
python analise.py 0a                    # Gate 0a
python analise.py 0                     # Gate 0
python paridade_venue.py                # Gate 0b
```

Os museus (~1 GB) **não estão versionados** e são reproduzíveis pelos
comandos acima. Os dados de `dados_execucao/` também não — e esses **não**
são reproduzíveis, então precisam de backup por outro meio.

### Validação e testes

```bash
python validacao_contexto.py    # porteiro dos CSVs do poller
python teste_detectores.py      # Gate 1b
python invariante10.py          # autoteste dos guardas estatísticos
python fisica_v2.py             # autoteste do dimensionamento
```

---

## Arquivos da V2

| arquivo | papel |
| --- | --- |
| `config.py` | 18 majors estáticos, faixa do gatilho, superfícies, janelas |
| `sinal.py` | **definição única** do gatilho, do σ e das excursões |
| `fisica_v2.py` | dimensionamento; `max_safe_leverage` rebaixada a diagnóstico |
| `relogio.py` | grava em UTC, reporta nos dois fusos |
| `invariante10.py` | guardas estatísticos executáveis |
| `minerador_binance.py` | museu de futures e spot, via ZIP mensal |
| `minerador_hl.py` | acúmulo prospectivo da Hyperliquid |
| `coletor_contexto.py` | poll de OI/funding/mark, 1×/minuto |
| `coletor_execucao.py` | slippage pelo livro, snapshots escalonados |
| `validacao.py` / `validacao_contexto.py` | porteiros |
| `analise.py` / `paridade_venue.py` | Gates 0a, 0 e 0b |
| `teste_detectores.py` | Gate 1b |
| `PRE_REGISTRO_OI.md` | pré-registro lacrado, com adendo datado |

---

## As duas invariantes que este projeto aprendeu

As nove primeiras invariantes de risco protegem a banca de código
defeituoso. Estas duas nasceram de erros cometidos **durante** a própria
análise, e são as mais caras porque não levantam exceção.

### 10 — nenhum alpha sem erro padrão, e nada é contado antes de agrupar

Toda medida carrega `n`, σ medido **naquela** amostra, erro padrão e `t`.
Eventos correlacionados são agrupados pela unidade independente antes de
qualquer contagem, e o design effect é recalculado a cada análise, nunca
herdado — ele variou de **3,51 a 7,45** entre janelas do mesmo sinal.

A família de busca é declarada **antes** da varredura. Fundir células
adjacentes depois de ver o resultado conta como busca.

E quando existir mais de uma estratégia de controle defensável, rodar todas
e reportar a amplitude. Um alpha que vai de `t = 0,05` a `t = 2,10`
conforme o controle escolhido **não é medida, é escolha**.

`invariante10.py` torna isso executável: não há construtor de `Medida` sem
unidade de agrupamento declarada, e `analise.py` recusa julgar gate sem
família de busca selada.

### 11 — ausência de medição nunca é medição de zero

Um `open_interest` igual a `0.0` num símbolo deslistado e um igual a `0.0`
num mercado vivo são o mesmo número e coisas opostas. A exclusão é por
**validade**, não por presença: `is_delisted` é soberano quando a fonte o
declara.

E todo instrumento que existe para detectar silêncio precisa **falhar
ruidosamente**. Um arquivo de falhas que só grava em saída limpa não
registra morte abrupta. Um coletor que só escreve quando há evento não
distingue uma semana sem gatilho de uma semana morto. Um detector de lacuna
que exige cabeçalho idêntico fica cego a cada mudança de esquema.

Nos três casos o instrumento devolve "nada a relatar" — que é exatamente o
que ele devolveria se estivesse funcionando. Por isso existe o
`teste_detectores.py`: ele não testa que os detectores ficam quietos, testa
que **cada um consegue disparar**.

---

## O que fica de pé da pesquisa

Com a redação fraca que os dados sustentam, e nada além dela:

- **Binance e Hyperliquid são o mesmo mercado para este sinal** — 88,2% de
  sobreposição de gatilhos, defasagem mediana de 0,00 minuto. Vale para
  qualquer pesquisa futura de 1 minuto em majors: pesquise na Binance,
  opere na HL.
- **Design effect de eventos de cascata: 5,2 a 7,5** — e **não é constante
  de bolso**. Qualquer análise futura calcula o próprio.
- **O museu** — 10,8 M velas em futures, 10,2 M em spot, duas superfícies,
  417 dias, com validador que recusa dado sujo.

---

## V1 — autópsia, não fundação

**Os sete arquivos `.py` da V1 neste repositório estão vazios — 0 byte
cada.** Foram commitados como placeholders em 21/07/2026 e nunca
preencheridos. O que existe da V1 aqui é o nome do arquivo e a descrição
abaixo, nada mais.

Isso fica registrado porque o README anterior os descrevia módulo a módulo
como se houvesse código, e um README que documenta arquivo inexistente é o
mesmo defeito que o resto deste projeto passou a semana corrigindo: o
instrumento afirmando algo que não aconteceu.

A descrição do que a V1 **fazia** segue abaixo por ser o que sustenta a
decisão de não reaproveitá-la.

Quatro defeitos independentes, cada um suficiente sozinho para zerar a
conta:

1. **Universo errado** — o sinal nas ilíquidas é ruído (51% de acerto).
2. **Alavancagem fixa em 10×** — o MAE p10 de −14,23% em preço é liquidação.
3. **O stop cortava os vencedores** — a 10×, 54% dos caminhos vencedores
   passavam pelo stop antes de virar.
4. **O simulador cobrava 3,3× a taxa verdadeira** — `blood_toll_pct = 0.0015`
   contra 0,045% taker real, em cada uma das 44.164 operações de treino.

O quarto é o mais caro: não quebrou nada em execução, apenas enterrou uma
estratégia dentro de um custo que não existia, por meses.

O modelo XGBoost tem poder discriminante nulo (p = 1,0000 no teste exato de
Fisher). **Não retreinar, não portar, não carregar o `.ubj`.** O motivo de
fundo é mais duro que aquele resultado: com ~65 unidades independentes,
nenhum modelo aprende — o limite é o N efetivo, não a classe do modelo.

---

## Autoria

O código foi implementado com apoio de IA (LLM) sob direção técnica, em
sessões de arquitetura e depuração linha a linha. A especificação, os
critérios de aceitação e as decisões de risco são do autor do repositório.

Na V2 isso inclui algo incomum e que vale registrar: **boa parte das
correções deste repositório são retratações de conclusões anteriores do
próprio projeto**, verificadas por medição independente em segunda
superfície. A seção da física e o item 4 da auditoria estão marcados como
`RETRATADO` no documento de especificação, com os números que derrubaram
cada afirmação.

---

## Riscos

- **Nada aqui é recomendação de investimento.** É registro de pesquisa, e a
  pesquisa principal deu negativo.
- **A V1 enviava ordens reais.** O código não está neste repositório — os
  arquivos são placeholders vazios — mas se ele for recuperado de outra
  cópia, está marcado como autópsia por quatro motivos medidos.
- **Alavancagem acima de 2× está fora de escopo** por decisão, e o número
  que originalmente sustentava esse teto foi retratado — a exclusão
  permanece porque não construir por falta de suporte medido continua sendo
  boa razão, enquanto construir não seria.
- **Um bucket bonito no holdout gasto é evidência de que a busca funciona,
  não de que o edge existe.**

---

## Dependências

```
numpy
requests
websockets
scipy
```

Python 3.10+. A V1 depende adicionalmente de `ccxt`, `pandas`, `xgboost`,
`scikit-learn` e `colorama`.
