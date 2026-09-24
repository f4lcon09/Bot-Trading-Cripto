# Pré-registro — teste de open interest

**Escrito em 2026-09-22, antes de o dado existir.**

Esta é a forma mais forte de pré-registro possível, e aqui ela sai de graça
porque não há alternativa: a Binance retém `openInterestHist` por 1 mês com
granularidade de 5 minutos, e a Hyperliquid só expõe snapshot. Não há como
espiar um dado que ainda não foi coletado.

O `coletor_contexto.py` começou a acumular em **2026-09-22 17:09 UTC**.
Antes dessa data não existe OI de 1 minuto em fonte nenhuma, para ninguém.

---

## A hipótese

Uma queda de 1,5% a 3,0% em um minuto pode ser três coisas diferentes com
o mesmo retorno:

1. **desalavancagem forçada** — liquidações em cascata
2. **reprecificação por notícia** — informação nova, preço novo
3. **beta de BTC** — o ativo seguindo o mercado

A tese original supunha (1) sem nunca medir, e derivou dela a mecânica da
segunda vaga. **H1:** eventos com queda simultânea de open interest se
comportam de forma diferente, nos 60 minutos seguintes, de eventos sem ela.

**H0:** não há diferença.

---

## Definição operacional

Fixada agora, e não se mexe depois.

| termo | definição |
| --- | --- |
| evento | gatilho de `sinal.py`, retorno 1m em [−3,0%, −1,5%], majors |
| `oi_t` | `openInterest` no minuto de fechamento da vela-gatilho |
| `oi_t-1` | `openInterest` no minuto imediatamente anterior |
| **ΔOI** | `oi_t / oi_t-1 − 1`, em % |
| evento com OI caindo | ΔOI ≤ **−0,5%** |
| evento com OI estável | −0,5% < ΔOI < +0,5% |
| evento com OI subindo | ΔOI ≥ **+0,5%** |
| desfecho | retorno de preço em 60 minutos, entrada no fechamento da vela-gatilho |

O limiar de ±0,5% é escolhido **agora, sem ver nenhum dado de OI**, por ser
redondo e por estar acima do ruído de arredondamento do campo. Não será
ajustado depois.

Evento sem `oi_t` ou `oi_t-1` disponível — poller caído, símbolo ausente do
universo — é **excluído**, não imputado, e o número de excluídos entra no
relatório.

---

## Família de busca

**Declarada fechada, com 3 células:**

1. OI caindo × horizonte 60 min
2. OI estável × horizonte 60 min
3. OI subindo × horizonte 60 min

Horizonte único de 60 minutos, o mesmo da tese. Um só limiar (±0,5%). Um só
universo (os 18 majors). Bonferroni a 3 dá limiar de **0,0167**.

**Nada mais entra.** Se depois parecer interessante testar 30 ou 120 minutos,
ou um limiar de 1%, isso é uma família nova e o custo é assumido
explicitamente — não se acrescenta célula a esta.

---

## Unidade de agrupamento

**O dia**, declarada antes de ver o dado, e não escolhida por maximizar
nada.

Motivo: o design effect medido neste mercado variou de 3,51 a 7,45 entre
janelas do mesmo sinal, e eventos de cascata se agrupam. Contar eventos
como independentes é o erro que matou a tese. O DE será **recalculado**
sobre esta amostra e reportado, nunca herdado daqueles números.

---

## Estratégias de controle

A invariante 10 exige rodar todas as defensáveis e reportar a amplitude.
Três, declaradas agora:

1. **Contraste direto entre buckets de ΔOI** — o teste principal, e o único
   que não depende de benchmark externo. É uma comparação *dentro* dos
   eventos, então não sofre do problema que derrubou o item 4 da auditoria.
2. **Pareado por dia** — evento contra instantes do mesmo dia calendário.
3. **Casado por σ** — vizinhos mais próximos em log σ, com K ∈ {50, 200}
   declarados aqui.

Se as três discordarem, **a amplitude é o resultado** e H1 não é afirmada.
Reportar a melhor é seleção.

---

## Critério de aprovação

H1 é afirmada **apenas se todas** as condições valerem:

- diferença entre bucket "OI caindo" e bucket "OI subindo" com **p < 0,0167**
  (Bonferroni a 3), agrupado por dia
- **n ≥ 30 dias** com ao menos um evento em cada um dos dois buckets
  extremos
- a conclusão **não muda de sinal** entre as três estratégias de controle
- o resultado se mantém excluindo o dia de maior concentração de eventos

Falhando qualquer uma: **H0 não é rejeitada**, e isso é registrado como
resultado, não como "precisa de mais dados".

---

## Quando abrir

**Não antes de 2027-03-22** — seis meses de acúmulo — ou de haver 30 dias
qualificados, o que vier depois.

Olhar antes disso é instrumentação: conferir que o poller está gravando,
que os campos não vieram vazios, que o join com as velas casa no minuto.
Isso é permitido e não conta como julgamento.

**Julgamento, uma vez só.** Abrir o resultado a cada semana e parar quando
estiver bonito reproduz o "51,7% de WR" da V1.

---

## Ressalva de interpretação, registrada antes

Queda de OI **não é prova de liquidação**. É compatível com fechamento
voluntário de posição. Mesmo com H1 afirmada, a conclusão válida é
"eventos com OI caindo se comportam diferente", **não** "eventos de
liquidação se comportam diferente".

Afirmar o mecanismo a partir do proxy é exatamente o erro original: observar
o proxy e declarar a causa. A confirmação exigiria o feed global de
liquidações de terceiros (`liquidationFills`) — a API nativa da HL só expõe
liquidações da própria carteira, via `userEvents`.

---

## Registro de integridade

| campo | valor |
| --- | --- |
| escrito em | 2026-09-22 |
| coleta iniciada | 2026-09-22 17:09 UTC |
| dado existente na data de escrita | **nenhum** |
| abertura prevista | 2027-03-22, ou 30 dias qualificados |
| células na família | 3 |
| limiar corrigido | 0,0167 |
| unidade de agrupamento | dia |
| estratégias de controle | 3 |

Qualquer alteração neste arquivo depois de a coleta começar deve ser feita
**por acréscimo datado**, nunca por edição do texto acima. Um pré-registro
editado é um pré-registro que não existe.

---

# Adendo 1 — 2026-09-23

**Acréscimo datado, não edição.** O texto acima fica como escrito em
2026-09-22. Este adendo corrige a regra de exclusão, e a correção é
legítima porque foi feita **antes de existir qualquer evento**: a coleta
tinha 22 polls e zero gatilhos quando o problema foi detectado.

## O que estava errado

A regra da linha 51 excluía por **presença**: *"evento sem `oi_t` ou
`oi_t-1` disponível é excluído"*.

TON está deslistado na Hyperliquid. O OI dele **está disponível** — é o
número zero. Passa pelo filtro de presença, entra no cálculo, e
`ΔOI = 0/0 − 1` estoura ou vira `NaN`. Se virar `NaN` e a comparação de
bucket for feita na ordem errada, o evento cai silenciosamente em
`−0,5% < ΔOI < +0,5%`: a categoria **"OI estável"**, que é o controle do
teste.

Ausência de mercado seria lida como medição de estabilidade. É a mesma
família de erro do poller que perdeu 8h37 sem registrar — ausência de
observação lida como observação.

## Medido em 2026-09-23

| | |
| --- | --- |
| polls com TON zerado | 22 de 22, cobrindo 8h35 |
| `open_interest` | `0.0` em todos |
| `mark_px` | `1.8014`, congelado e idêntico |
| `mid_px` | vazio |
| `day_ntl_vlm` | `0.0` |
| `museu_hl/TON.csv` | velas reais de 11–15/jun, volume mediano 1.896 |
| idade do último dado | **99,7 dias** |
| `candleSnapshot` hoje | **n = 0** |
| `universe` | **`isDelisted: True`**, `maxLeverage: 10` |

Os outros 17 símbolos variaram normalmente no mesmo período.

**A API nunca mentiu.** As velas de junho são reais — houve negociação
com volume. A retenção da HL segurava as últimas 5.000 velas do TON, que
eram de junho porque nenhuma nova foi produzida. Hoje nem isso: expiraram.
A corretora **declara** o deslistamento no mesmo payload que o poller já
busca todo minuto. O campo estava sendo descartado.

## A regra nova

Exclusão por **validade**, não por presença. Um símbolo-minuto é inválido
se qualquer uma valer:

1. `is_delisted == 1` — **critério declarado pela corretora, e soberano**
2. `open_interest <= 0`
3. `mid_px` ausente ou vazio
4. `day_ntl_vlm <= 0`

O critério 1 é o que decide. Os outros três ficam como segunda linha: um
símbolo pode estar morrendo sem ainda ter sido marcado, e nesse caso os
zeros aparecem antes da flag.

Eventos em símbolo-minuto inválido são **excluídos e contados**, nunca
imputados, e o número de exclusões por motivo entra no relatório.

**A linha é gravada mesmo assim.** Filtrar na coleta apagaria a evidência
de que o símbolo estava morto naquele minuto. A exclusão acontece na
análise, a partir das colunas.

## O universo continua com 18

TON fica. Sair da lista depois de olhar o dado é escolha pós-hoc, mesmo
sendo a escolha óbvia, e mudaria a contagem declarada de 18 para 17 no
meio do caminho. Ele contribui só com exclusões, que ficam contadas.

Há também um motivo prático: com `is_delisted` gravado, a exclusão é
automática e auditável em vez de julgamento. Se TON voltar a ser listado,
ele volta ao cálculo sozinho, sem editar universo nenhum.

## Mudança de contrato

`contexto_<data>.csv` passa de 12 para **14 colunas**, com `is_delisted`
e `max_leverage` no fim. Arquivos gravados antes de 2026-09-23 02:15 UTC
têm 12 colunas e não trazem a flag — para eles, a exclusão depende dos
critérios 2 a 4.
