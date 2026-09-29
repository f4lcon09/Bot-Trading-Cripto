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

---

# Adendo 2 — 2026-09-25

**Acréscimo datado, não edição.** O texto original de 2026-09-22 e o
Adendo 1 ficam intactos acima. Este adendo troca a **regra de parada** e
declara a cobertura parcial. Continua legítimo porque **ainda não existe
um único evento na base**: a coleta tem quatro dias e zero gatilhos.

## O problema: cobertura parcial e sistemática

A coleta roda em máquina pessoal, sem alimentação dedicada. Medido em
2026-09-25:

| dia | minutos | cobertura |
| --- | --- | --- |
| 2026-09-22 | 20 | 1% (primeiro dia, parcial) |
| 2026-09-23 | 822 | **57%** |
| 2026-09-24 | 867 | **60%** |
| 2026-09-25 | 476 | 33% — **dia em curso**, 55% do decorrido |
| agregado | 2.185 | **38%** |

**Base declarada:** minutos com registro dividido pelos 1.440 minutos do
dia. *Não* contra a janela do primeiro ao último registro do arquivo —
essa base dá 63% / 60% / 53% e é exatamente o erro que o validador do
museu corrigiu em 22/09. Cobertura medida contra a própria janela do dado
sempre parece melhor do que é.

**Faixa cega: 06:00–10:59 UTC**, zero absoluto nos quatro dias. A hora
11:00 tem 9 de 180 minutos (5%) e por isso não entra no intervalo.

A causa é desligamento e suspensão da máquina, não defeito do coletor —
o `contexto_falhas` distingue `processo ausente` de `minutos pulados
(processo vivo)`, e foi essa distinção que permitiu identificar a causa.

## Regra de parada: 15 dias qualificados

A regra de "30 dias qualificados ou 2027-03-22" **cai**, e a regra de
parada por *eventos* que chegou a ser considerada **também cai**.

**Novo critério: coletar até haver 15 DIAS QUALIFICADOS.**

Um **dia qualificado** é um dia UTC com pelo menos um evento em **cada**
bucket extremo: ao menos um com `ΔOI ≤ −0,5%` e ao menos um com
`ΔOI ≥ +0,5%`.

### Por que dias e não eventos

A regra por eventos foi considerada e **medida como insuficiente**. A
unidade de análise é o dia, não o evento, e sob agrupamento a conversão
entre os dois depende da cobertura:

| cobertura | 100 eventos rendem | dias por grupo extremo |
| --- | --- | --- |
| 37% | 45,3 dias com evento | 22,6 |
| 60% | 37,0 dias com evento | 19,5 |
| 100% | 29,6 dias com evento | 16,1 |

Mais cobertura junta os eventos em menos dias, e menos dias independentes
significam **menos** poder. Uma regra por eventos faria a cobertura afetar
o poder — precisamente o que ela fora introduzida para evitar.

Contar na mesma unidade da análise resolve na raiz: **o poder fica fixo
por construção e a cobertura mexe só no calendário.**

### Qualificar não é selecionar por resultado

O critério de qualificação depende do **ΔOI**, que é a variável
classificadora, e **não** do retorno de 60 minutos, que é o desfecho.
Nenhum dia entra ou sai da contagem por causa do resultado que produziu.

Isto está escrito com estas palavras de propósito: daqui a meses, "dia
qualificado" precisa ser lido como "dia com os dois regimes de OI
presentes", nunca como "dia escolhido".

### Dia não qualificado continua na análise

Um dia com eventos em um só bucket **não conta** para os 15, mas o dado
dele existe e **entra na análise**. Regra de parada e conjunto de análise
são coisas diferentes; confundi-las é como o conjunto final acaba sendo
escolhido depois de ver o dado.

## Cálculo de poder, com os pressupostos declarados

Um cálculo de poder é uma medida como qualquer outra: carrega n, σ e
unidade de agrupamento, ou não é reportável (invariante 10).

**σ da diferença intradiária, medido** — para cada dia com ≥2 eventos, os
eventos foram divididos em duas metades ao acaso e mediu-se a diferença
das médias. É a dispersão sob H0, que é a referência correta:

| janela | dias elegíveis | σ diário | **σ da diferença** | ganho do pareamento |
| --- | --- | --- | --- | --- |
| 0a futures | 34 | 2,33% | **1,97%** | 1,68× |
| 0a spot | 33 | 2,24% | **1,92%** | 1,65× |
| holdout futures | 33 | 1,80% | **2,05%** | 1,25× |

**Design effect = 1, por construção.** A unidade é o dia. O DE de 3,51 a
7,45 medido neste projeto descreve quantos eventos cabem num dia — é
exatamente o que o agrupamento absorve, e usar σ do dia já o incorpora.
Com pareamento intradiário o DE deixa de dominar a conta, o que torna
este número mais confiável que uma projeção baseada em contagem de
eventos.

**Parâmetros:** teste pareado, α = 0,0125 bicaudal, poder 80%, N = 15.

**Efeito detectável: 1,66 a 1,76 pontos percentuais**, conforme o σ
adotado. A faixa vem das três janelas acima e é reportada inteira, não
reduzida a um número.

## O limiar, e um conflito registrado

A decisão de pré-registrar **os dois esquemas** — não pareado como
principal, pareado como confirmatório — leva a família de 3 para 4
células, e o limiar de Bonferroni de 0,0167 para **0,0125**.

Ao cravar N = 15 foi mencionado o limiar de 0,0167 em passagem. Os dois
não podem valer juntos. **Fica 0,0125**, por ser a leitura conservadora e
a consistente com a família de quatro. Se a intenção era 0,0167, isso
implica abandonar o pareado-como-confirmatório, e exige Adendo 3.

## Horizonte

Calendário estimado até 15 dias qualificados, pela distribuição real de
eventos por dia do holdout:

| cobertura | calendário |
| --- | --- |
| 37% (atual) | **9,6 meses** |
| 60% | 6,1 meses |
| 100% | 4,2 meses |

**O calendário não está cravado; só o N está.** Melhorar a cobertura
encurta o prazo **sem custar poder** — o incentivo aponta na direção
certa. Reduzir a cobertura atrasa, mas não enfraquece o teste.

## Consequências declaradas

1. **Todo resultado reporta a cobertura por hora UTC** da janela usada,
   junto com `n` e erro padrão. `cobertura.py` produz essa tabela.
2. **Enquanto a cobertura for parcial, a conclusão vale para a janela
   observada** e não é extrapolada para as horas ausentes. Com 06:00–10:59
   em zero, o teste não sabe nada sobre manhã europeia e tarde asiática.
3. **Quando a cobertura passar a ser contínua, a data é registrada aqui
   por novo adendo**, para que a análise distinga período subamostrado de
   período completo.
4. **Variar o horário do desligamento** transforma ponto cego estrutural
   em perda de poder. Ausência sistemática não se corrige com mais dias;
   ausência aleatória, sim. Isto é recomendação operacional, não critério.

## Contar não é espiar

Com regra de parada por dias qualificados, **acompanhar o contador é
instrumentação e é permitido**. Olhar o *resultado* antes de fechar os 15
não é — é o "51,7% de WR" da V1 se repetindo.

Isto fica escrito porque daqui a meses o contador em 13 vai ser tentador.

## Depois do dia 15

A coleta **não para** no dia 15. A regra de parada define quando o teste
é aberto, não quando o coletor desliga.

**Tudo que for analisado depois do dia 15 é exploratório por declaração**,
e não pode ser reportado como confirmatório. Uma segunda olhada com o
mesmo limiar são duas chances no mesmo teste — a mesma família de erro das
78 células. Exploratório depois é legítimo; exploratório disfarçado de
confirmatório é o que matou a V1.

## Registro de integridade deste adendo

| campo | valor |
| --- | --- |
| escrito em | 2026-09-25 |
| eventos na base nesta data | **zero** |
| dias de coleta | 4 |
| cobertura agregada | 38% |
| regra de parada | 15 dias qualificados |
| limiar corrigido | 0,0125 (família de 4) |
| efeito detectável | 1,66 a 1,76 pp |
| unidade de agrupamento | dia |
| design effect assumido | 1, por construção |

### Fechamento do Adendo 2 — mesmo dia, ainda com zero eventos na base

Duas correções feitas antes de lacrar, ambas em 2026-09-25.

#### 1. O limiar: conflito resolvido, e sem Adendo 3

A menção a 0,0167 ao cravar N = 15 foi **descuido de aritmética** —
repetição do número do pré-registro original sem recontar a família
depois que ela mudou. Não houve intenção de abandonar o pareado como
confirmatório.

**Fica 0,0125.** A inconsistência permanece registrada acima de
propósito: é o registro honesto do que aconteceu, e apagá-la seria
reescrever a história de uma decisão.

**O cálculo de poder NÃO precisou ser refeito** — ele já havia sido feito
a 0,0125. Verificado nos dois limiares:

| janela | σ da diferença | α = 0,0167 | **α = 0,0125** |
| --- | --- | --- | --- |
| holdout futures | 2,05% | 1,71 pp | **1,77 pp** |
| 0a spot | 1,92% | 1,60 pp | **1,66 pp** |
| 0a futures | 1,97% | 1,65 pp | **1,70 pp** |

`z(0,0167) = 3,235` contra `z(0,0125) = 3,339`. A faixa publicada acima
é a de 0,0125.

**Correção de arredondamento:** onde se lê "1,66 a 1,76 pp", o valor
exato do limite superior é **1,77 pp**. A faixa correta é **1,66 a
1,77 pp**.

Com 1,77 pp de teto, N = 15 permanece: o critério declarado era que o
efeito precisa aparecer **bem acima de 1,3 pp** se a hipótese estiver
certa, e a margem é de 0,47 pp. O teto de reavaliação estabelecido —
1,9 pp — não foi atingido.

#### 2. As quatro células, enumeradas nominalmente

"Bonferroni a 4" não é declaração de família: é conta que exige dedução
para ser auditada. Três baldes sob dois controles dariam **seis**. O
quatro só fecha por uma escolha de desenho, e escolha de desenho se
escreve, não se deduz.

A família é esta, e é fechada:

| # | célula | esquema de controle | papel |
| --- | --- | --- | --- |
| 1 | `OI caindo` × `OI subindo` | não pareado, agrupado por dia | **primária** |
| 2 | `OI caindo` × `OI estável` | não pareado, agrupado por dia | secundária |
| 3 | `OI estável` × `OI subindo` | não pareado, agrupado por dia | secundária |
| 4 | `OI caindo` × `OI subindo` | **pareado dentro do dia** | **confirmatória da célula 1** |

**A escolha de desenho, explícita:** apenas a comparação primária é
duplicada sob os dois esquemas de controle. As duas secundárias rodam
sob o esquema não pareado apenas.

O motivo é que a célula 4 existe para testar a robustez da célula 1 ao
esquema de controle — que é a exigência da invariante 10 sobre amplitude
entre controles defensáveis — e não para multiplicar comparações. Duplicar
também as secundárias custaria duas células a mais, levando o limiar a
0,0083, sem responder nenhuma pergunta nova.

**Nada mais entra.** Horizonte único de 60 minutos. Um só limiar de ΔOI
(±0,5%). Um só universo (os 18 majors). Outra granularidade, outro
limiar ou outro horizonte é família nova, com o custo assumido
explicitamente — não se acrescenta célula a esta.

`0,05 / 4 = 0,0125`.

### Fechamento do Adendo 2, parte 2 — a regra de decisão, e uma correção de método

Ainda 2026-09-25. Ainda **zero eventos na base**.

Enumerar as quatro células expôs um buraco que nenhuma das duas partes
havia nomeado: **não existia regra de decisão para quando a célula 1 e a
célula 4 discordarem.** As duas testam a mesma comparação sob controles
diferentes. O adendo dizia o que *reportar* — a amplitude, como a
invariante 10 exige — mas reportar não é decidir, e "reportar os dois e
ver no que dá" é, na prática, escolher depois de olhar. É a estrutura
exata do casamento por σ contra o pareamento por dia, onde `t` variou de
0,05 a 2,10 e o veredito acabou dependendo de qual esquema alguém decidiu
chamar de o certo.

#### 3. A regra: hierárquica, com a pareada decisiva

**A célula 4 decide. As células 1, 2 e 3 são contexto.**

| célula 4 (pareada) | veredito | o que as células 1–3 fazem |
| --- | --- | --- |
| cruza 0,0125 | **positivo** | entram no relatório como amplitude entre controles |
| não cruza | **negativo** | idem — inclusive se a célula 1 cruzar |

O motivo é que foi o pareamento dentro do dia que sobreviveu à autópsia:
foi ele que deu `t = 2,10` quando o casamento por σ desmontou, e é o
único esquema cujo defeito já foi procurado e não encontrado.

**Uma célula 1 que cruza com uma célula 4 que não cruza é negativo.** A
pareada é o teste mais sensível dos dois (ver a tabela abaixo); um sinal
que aparece só no esquema menos sensível é sinal de problema no controle,
não de efeito.

#### A contradição na formulação, e por que ela foi resolvida assim

A regra foi proposta como "a pareada decide, a não pareada é contexto;
**discordância é negativo**". As duas metades se contradizem no caso
assimétrico — célula 1 não cruza, célula 4 cruza. Pela primeira metade é
positivo; pela segunda é negativo. E se discordância for sempre negativo,
a regra hierárquica e a conjuntiva viram **a mesma tabela de decisão**, e
escolher entre elas deixa de decidir qualquer coisa.

Resolvido pela hierárquica pura — o caso assimétrico é **positivo** — por
medida, não por preferência:

| esquema | efeito detectável, N = 15, α = 0,0125, t exata |
| --- | --- |
| célula 4, pareada | **1,87 a 1,99 pp** |
| célula 1, não pareada | **2,33 a 3,01 pp** |

Para a célula 1 enxergar 1,9 pp seriam precisos **22 a 36 dias por
grupo**. Exigir que ela acompanhe é fazer o veredito depender do teste
mais cego da família: com um efeito verdadeiro perto de 2 pp, a pareada
o vê e a não pareada o perde com frequência alta, e a regra conjuntiva
transformaria **assimetria de poder em veredito negativo**.

Esta é a única cláusula deste adendo escrita contra a redação original da
proposta. Reverter custa uma linha — mas custa junto o argumento acima.

#### O rótulo agora está invertido, e fica registrado

A célula 4 está rotulada **confirmatória** e é a que decide. A célula 1
está rotulada **primária** e não decide. A tabela das quatro células
permanece como está: renomear depois de ver a regra seria arrumar o
registro em vez de registrá-lo. Onde os dois textos divergirem, **a regra
de decisão manda sobre o rótulo**.

#### 4. O cálculo de poder estava otimista — normal contra t

O `poder.py`, escrito hoje com autoteste, mediu um defeito no próprio
cálculo publicado acima: a fórmula `(z + z) × σ / √n` supõe **σ
conhecido**. Com N = 15 ele não é. O valor crítico vem da `t` com 14
graus de liberdade.

| esquema | valor crítico | efeito detectável, N = 15 |
| --- | --- | --- |
| normal, σ conhecido | z = 2,4977 | 1,66 a 1,77 pp |
| **t exata, gl = 14** | **t = 2,8640** | **1,87 a 1,99 pp** |

São **+12,8%**. O número publicado acima — 1,66 a 1,77 pp — está
**otimista**, e fica registrado como tal em vez de ser apagado.

**Isto aciona o teto de reavaliação declarado de 1,9 pp**, em duas das
três janelas (1,99 no holdout futures, 1,92 no 0a futures; o 0a spot fica
em 1,87). A distância até a referência de 1,3 pp cresce de 0,47 para
**0,69 pp**.

Para restaurar a condição declarada, agora pela `t` exata:

| alvo | N pareado necessário (pior janela) |
| --- | --- |
| 1,90 pp — o teto | **17 dias qualificados** |
| 1,77 pp — o publicado | 19 dias qualificados |
| 1,30 pp — a referência | 31 dias qualificados |

**N = 15 permanece em vigor até decisão em contrário**, registrada aqui.
A regra de parada não muda por medição que o projeto fez sobre si mesmo
sem decisão explícita — mas a medição fica escrita, com o teto marcado
como atingido.

#### Duas saídas convenientes, recusadas por escrito

A descoberta de que o desenho é mais cego que o declarado cria pressão
por dois remendos que restaurariam N = 15 sem coletar um dia a mais:

1. **Continuar reportando a aproximação normal.** Ela dá 1,77 pp e cabe
   sob o teto. É a `t` que está certa a N = 15.
2. **Reduzir a família a uma célula**, já que só a 4 decide, levando α de
   0,0125 para 0,05 e o detectável para baixo. As células 1–3 continuam
   sendo testes declarados e reportados; afrouxar a correção logo depois
   de descobrir a falta de poder é escolher o limiar pelo resultado que
   ele produz.

**Fica 0,0125, e fica a `t` exata.** Os dois remendos estão escritos aqui
para que, se um dia forem adotados, seja preciso adotá-los contra este
parágrafo — e não por esquecimento.

#### Registro de integridade desta parte

| campo | valor |
| --- | --- |
| escrito em | 2026-09-25 |
| eventos na base nesta data | **zero** |
| regra de decisão | hierárquica, célula 4 decisiva |
| caso assimétrico | positivo |
| método de poder | `t` exata, gl = 14 |
| efeito detectável corrigido | **1,87 a 1,99 pp** |
| teto de reavaliação (1,9 pp) | **atingido** |
| N em vigor | 15, sem alteração |
| instrumento | `poder.py`, 36/36 no autoteste |

### Fechamento do Adendo 2, parte 3 — N = 17, e a cláusula de sinais opostos

Ainda 2026-09-25. Ainda **zero eventos na base**.

#### 5. A regra de parada passa a ser 17 dias qualificados

O teto de reavaliação de 1,9 pp foi declarado antes, disparou em duas das
três janelas, e a resposta é **mexer no N, não no teto**.

Mover o teto agora seria a operação que a primeira linha dos critérios de
aceitação deste projeto condena — mover o limiar depois de olhar. Que o
1,9 fosse um número arbitrário não muda nada: ele foi escrito antes, e a
correção que o derrubou chegou pelo lado inconveniente. O momento em que
a medição fica mais honesta é exatamente o momento em que relaxar o
critério é mais tentador.

**Por que isto não é espiar:** não há um único evento na base. A correção
é sobre a **fórmula do poder**, não sobre resultado. Ajustar N a partir
de uma correção de método, antes de qualquer dado, é legítimo e é a
direção conservadora; ajustar o teto seria a mesma operação na direção
oposta.

| N | célula 4, `t` exata | crítico | teto de 1,9 pp |
| --- | --- | --- | --- |
| 15 | 1,87 a 1,99 pp | t(14) = 2,8640 | **atingido** |
| **17** | **1,73 a 1,84 pp** | t(16) = 2,8131 | respeitado, folga de 0,06 pp |

Por janela, a N = 17: 1,73 pp no 0a spot, 1,77 pp no 0a futures, 1,84 pp
no holdout futures.

**Custo no calendário**, pela mesma taxa de dias qualificados por dia
corrido usada acima — a taxa é constante, então o calendário escala
linear com N:

| cobertura | 15 dias | **17 dias** | custo |
| --- | --- | --- | --- |
| 37% (atual) | 9,6 meses | **10,9 meses** | +39 dias |
| 60% | 6,1 meses | 6,9 meses | +25 dias |
| 100% | 4,2 meses | 4,8 meses | +17 dias |

Seis semanas sobre um horizonte de dez meses. **N = 17 substitui N = 15
em todo este documento**, inclusive nas tabelas de integridade acima, que
ficam como estão pelo mesmo motivo que o 1,76 ficou: o registro anterior
não se apaga, se corrige por adendo.

#### 6. A família continua em 4, e a célula 1 continua consumindo alfa

Reduzir a família a uma célula — já que só a 4 decide — é estreitamento
que parece limpeza e é seleção. A célula 1 continua podendo produzir uma
afirmação confirmatória própria, e rebaixá-la **depois** de descobrir que
ela é a fraca é narrowing pós-hoc que por acaso ajuda.

Manter 0,0125 é o preço de ter declarado quatro células antes de saber
qual seria a forte. `0,05 / 4 = 0,0125` segue valendo.

#### 7. Sinais opostos: inconclusivo declarado

A hierarquia resolve "uma cruza e a outra não" — isso é diferença de
poder, e está medido. Ela **não** resolve estimativas com sinais opostos,
e lida ao pé da letra chamaria isso de positivo.

Sinais opostos não são assimetria de poder. São a situação literal que a
emenda da invariante 10 descreve: um efeito que troca de sinal conforme o
controle escolhido **não é medida, é escolha**.

**A tabela de decisão completa, que substitui a da parte 2:**

| célula 4 (pareada) | estimativa pontual da célula 1 | veredito |
| --- | --- | --- |
| cruza 0,0125, na direção da tese | mesmo sinal, ou zero | **positivo** |
| cruza 0,0125, na direção da tese | **estritamente oposta** | **inconclusivo declarado** |
| cruza 0,0125, contra a tese | qualquer | **negativo**, e reportado alto |
| não cruza | qualquer | **negativo** |

No inconclusivo declarado, **a amplitude entre os controles é o
resultado** — não um pé de página de um resultado. A conclusão publicável
é "o efeito depende do esquema de controle", com as duas estimativas e os
dois erros padrão lado a lado, e nenhuma das duas promovida a principal.

O critério é o **sinal**, sem limiar de magnitude. Um limiar de magnitude
seria mais um parâmetro livre, e parâmetro livre é o que se ajusta depois.

**O que isso custa, medido.** A célula 1 é imprecisa — erro padrão de
0,62 a 0,80 pp a N = 17 — então ela pode cair do lado negativo por ruído
mesmo com efeito verdadeiro positivo:

| efeito verdadeiro | P(estimativa da célula 1 sair negativa) |
| --- | --- |
| 1,0 pp | 5,3% a 10,5% |
| 2,0 pp | 0,06% a 0,62% |
| 3,0 pp | praticamente zero |

A cláusula só é consultada quando a célula 4 já cruzou, o que exige um
efeito observado perto de 1,8 pp ou mais; e as duas estimativas são
positivamente correlacionadas por virem dos mesmos dias, o que empurra a
probabilidade conjunta para baixo da marginal acima. **A correlação não
é conhecida sem os dados** e não está estimada aqui.

A leitura: a cláusula é barata onde importa, e cara exatamente na faixa
de efeito fraco — que é a faixa onde declarar inconclusivo é a resposta
certa.

#### Uma linha acrescentada por conta própria

A terceira linha da tabela — célula 4 cruzando **contra** a tese — não
estava na proposta. O teste é bicaudal a 0,0125, então cruzar na direção
oposta é resultado possível, e a regra escrita sem essa linha o chamaria
de positivo por omissão. Está marcada aqui para poder ser riscada.

#### Registro de integridade desta parte

| campo | valor |
| --- | --- |
| escrito em | 2026-09-25 |
| eventos na base nesta data | **zero** |
| regra de parada | **17 dias qualificados** (substitui 15) |
| efeito detectável, `t` exata | **1,73 a 1,84 pp** |
| teto de 1,9 pp | respeitado |
| família | 4 células, α = 0,0125 |
| sinais opostos | inconclusivo declarado, amplitude como resultado |
| calendário a 37% de cobertura | 10,9 meses |

### Fechamento do Adendo 2, parte 4 — escopo da tabela, e a correlação medida

Ainda 2026-09-25. Ainda **zero eventos na base**.

#### 8. O escopo da tabela de decisão

A tabela da parte 3, como estava, se contradizia com a justificativa da
parte 2 para manter a família em 4. A linha "não cruza → negativo,
qualquer que seja a célula 1" faz parecer que o alfa gasto pelas células
1, 2 e 3 não compra nada — e se não compra nada, a saída conveniente de
reduzir a família volta pela porta dos fundos.

As duas coisas convivem, mas só com o escopo escrito. Fica assim, como
cabeçalho da tabela:

> **A tabela decide o veredito sobre a tese.** As células 1, 2 e 3
> continuam individualmente reportáveis a α = 0,0125 como **achados
> secundários**. Nenhuma delas manda no veredito; todas podem ser
> afirmadas. É isso que justifica o alfa que consomem — e é por isso
> que a família continua em 4.

Um veredito negativo sobre a tese **não** significa que não há mais nada
a dizer. Significa que a tese não passou. Sem essa frase, alguém lê
"negativo" daqui a um ano e joga fora três testes declarados que podem
ter produzido afirmação própria.

É diferença de redação, não de desenho.

#### 9. A correlação entre os estimadores: medida, não mais ausente

A parte 3 declarou a correlação entre a célula 4 e a célula 1 como **não
conhecida**, e por isso deu só a probabilidade marginal — 5,3% a 10,5%
com efeito verdadeiro de 1 pp. Ela era mensurável sem tocar em nada
lacrado, e foi medida.

**Procedência, declarada porque daqui a um ano isto pode parecer outra
coisa:**

| campo | valor |
| --- | --- |
| fonte | **museu Binance**, futures e spot |
| janelas | Gate 0a e holdout — as mesmas já gastas |
| eventos | 499 (0a fut), 492 (0a spot), 253 (holdout fut) |
| open interest | **nenhum**; o museu não tem OI |
| dados da coleta ao vivo | **zero eventos usados** |
| amostra do teste | **não tocada** — ela não existe ainda |

O classificador do teste é o ΔOI, que o museu não tem. A correlação foi
medida sob três classificadores **substitutos**, todos particionando
dentro do dia como o ΔOI fará, e nenhum deles enxergando o desfecho —
o autoteste verifica isso permutando `ret_60m` e exigindo que a partição
não mude.

`correlacao_controles.py`, 19/19 no autoteste, bootstrap de 4000
réplicas sobre dias, reamostrando na dimensão do desenho (N = 17):

| janela | aleatório | σ | gatilho | dias qualif. | não qualif. |
| --- | --- | --- | --- | --- | --- |
| 0a futures | 0,709 | 0,893 | 0,818 | 32–34 | 33–35 |
| 0a spot | 0,582 | 0,880 | 0,693 | 27–33 | 33–39 |
| holdout futures | 0,613 | 0,639 | 0,679 | 28–33 | 39–44 |

**ρ medido: 0,58 a 0,89.**

#### O que a medição encontrou, e não era o número

O autoteste expôs uma identidade que ninguém tinha escrito: **se todo dia
qualificar, os dois estimadores são o mesmo número.** A média das
diferenças diárias é igual à diferença das médias diárias quando os dois
grupos vivem nos mesmos dias. Nesse cenário ρ = 1 exato, e a cláusula de
sinais opostos **não pode disparar**.

Ela dispara só pelos **dias não qualificados** — os que têm um regime de
OI só, que entram no estimador não pareado e não no pareado. No museu
esses dias são 33 a 44 contra 27 a 34 qualificados: mais da metade do
conteúdo do estimador não pareado vem de dias que o pareado nunca vê.

É isso, e não a aleatoriedade, que separa as duas células.

#### O custo da cláusula, agora com faixa

P(célula 4 cruza na direção da tese **e** célula 1 sai negativa):

| efeito verdadeiro | marginal (parte 3) | ρ = 0,58 | ρ = 0,89 |
| --- | --- | --- | --- |
| 1,0 pp | 5,3% – 10,5% | 0,05% – 0,21% | ~0% |
| 2,0 pp | 0,06% – 0,62% | 0,01% – 0,23% | ~0,01% |
| 3,0 pp | ~0% | ~0,01% | ~0% |

Varrendo o efeito verdadeiro continuamente, o **pior caso de toda a
grade** é **0,36%**, em efeito de 1,5 pp, ρ = 0,58, janela 0a futures. A
cláusula tem pico perto de 1,5 pp porque é ali que a célula 4 já cruza e
a célula 1 ainda é ruidosa; abaixo disso a 4 não cruza, acima a 1 não
erra o sinal.

**A cláusula sai praticamente de graça.** A marginal da parte 3
superestimava o custo em cerca de trinta vezes — ela ignorava que as duas
estimativas vêm dos mesmos dias.

Isto **não** afrouxa nada: a cláusula continua escrita como está, com
critério pelo sinal e sem limiar de magnitude. O que muda é que o custo
dela deixou de ser desconhecido e passou a ser 0,36% no pior caso.

#### Limite desta estimativa, declarado

ρ foi medido sob classificadores substitutos, não sob o ΔOI. Se o ΔOI
produzir uma proporção de dias não qualificados muito diferente da do
museu, ρ muda junto — a razão entre dias qualificados e não qualificados
é o que governa a separação entre os dois estimadores. A faixa 0,58–0,89
é a que os três substitutos produzem, e o extremo inferior vem do
classificador aleatório, que é o que menos se parece com o ΔOI.

**Quando os dias reais existirem, ρ é remensurável com o mesmo arquivo**,
e essa remensuração é instrumentação, não espiar: ela depende só de quais
dias qualificam, nunca do desfecho.

#### Registro de integridade desta parte

| campo | valor |
| --- | --- |
| escrito em | 2026-09-25 |
| eventos na base nesta data | **zero** |
| escopo da tabela | veredito sobre a tese; células 1–3 reportáveis a 0,0125 |
| família | 4 células, sem alteração |
| ρ medido | **0,58 a 0,89** |
| fonte de ρ | **museu**, não a amostra do teste |
| custo da cláusula, pior caso | **0,36%**, em efeito de 1,5 pp |
| instrumento | `correlacao_controles.py`, 19/19 |

### Fechamento do Adendo 2, parte 5 — o que a célula 4 testa de verdade

Ainda 2026-09-25. Ainda **zero eventos na base**.

#### 10. A descrição da célula 4 estava prometendo mais do que entrega

A identidade encontrada pelo autoteste tem uma consequência que não foi
tirada na parte 4. Se as células 1 e 4 só divergem pelos dias **não
qualificados**, então elas não são dois controles: são **o mesmo
contraste sobre dois conjuntos de dias**.

A emenda da invariante 10 fala em "mais de uma estratégia de controle
defensável", e isso significa formas genuinamente diferentes de construir
o contrafactual. Aqui, no limite em que todo dia qualifica, as duas dão o
**mesmo número**. Logo:

> **A célula 4 não testa robustez à escolha do controle. Testa robustez
> à restrição de amostra** — o mesmo contraste, calculado sobre os dias
> em que os dois regimes coexistem, contra o calculado sobre todos os
> dias.

Onde a parte 2 diz que a célula 4 "existe para testar a robustez da
célula 1 ao esquema de controle — que é a exigência da invariante 10
sobre amplitude entre controles defensáveis", **essa frase está corrigida
por esta**. O texto original fica onde está.

**A consequência desagradável, escrita por extenso:** esta família **não
satisfaz** a exigência da invariante 10 sobre amplitude entre controles.
Ela tem um contraste sob duas restrições de amostra, o que é menos.
Um controle genuinamente diferente — casamento por σ, por exemplo, que
foi justamente o que desmontou na autópsia — seria outra célula, com
outro custo de alfa, e **não está sendo acrescentada agora**. Fica
registrado que a exigência está parcialmente atendida, e não que está
atendida.

#### 11. Células 1 e 4 agregam por dia — verificado no código

A identidade só vale se a célula 1 também agregar por dia. Se ela
empilhasse eventos, ponderaria cada dia pelo número de eventos que teve,
as duas não coincidiriam nem com 100% de qualificação, e ρ = 1 nunca
apareceria.

**Conferido no código, não na intenção.** Em
`correlacao_controles.estimadores`, o estimador não pareado é a média das
médias **diárias**, um peso por dia. A definição agora é executável em
vez de documental: a função aceita `empilhado=True`, e o autoteste exige
que as duas definições se separem —

| definição | ρ com 100% de dias qualificados |
| --- | --- |
| agregado por dia (o declarado) | **1,000000** exato |
| empilhado por evento (o defeito) | 0,718 |

Se alguém trocar a definição, a identidade quebra e o autoteste reprova.

**O risco não está eliminado, está um passo ao lado.** O `analise.py`
empilha eventos — `rets.mean()` sobre todos os eventos de todos os
símbolos e dias. Isso é deliberado lá: aquele arquivo reaplica o
procedimento da tese sem alterar um parâmetro, e foi exatamente essa
contagem que produziu o design effect de 3,51 a 7,45.

**Não existe ainda código que implemente o teste de OI.** Quando ele for
escrito, reutilizar `medir()` do `analise.py` reintroduz a primeira causa
da morte da tese dentro do teste escrito para não repeti-la. Fica
declarado aqui: **o teste de OI agrega por dia, um peso por dia, nas
quatro células.**

#### 12. O custo da cláusula, parametrizado pelo que o governa

Como a cláusula só dispara pelos dias não qualificados, o custo dela é
função da **fração de dias não qualificados**, não de ρ como número
solto. No museu essa fração ficou em torno de 55% sob os substitutos; sob
o ΔOI real ela pode ser bem outra, e ρ anda junto.

Registrado como limite parametrizado, para ser **lido na linha** quando
os dias reais existirem — sem remodelar nada, e sem que a leitura pareça
ajuste feito depois:

| fração não qualif. | dias nq (N=17) | ρ medido | pior custo | no efeito |
| --- | --- | --- | --- | --- |
| 20% | 4 | 0,875 – 0,968 | 0,014% | 2,28 pp |
| 30% | 7 | 0,808 – 0,944 | 0,045% | 2,00 pp |
| 40% | 11 | 0,723 – 0,917 | 0,123% | 1,76 pp |
| 50% | 17 | 0,673 – 0,885 | 0,191% | 1,66 pp |
| **55% (museu)** | — | 0,58 – 0,89 | **0,36%** | 1,52 pp |
| 60% | 25 | 0,567 – 0,856 | 0,389% | 1,50 pp |
| 70% | 40 | 0,476 – 0,788 | 0,618% | 1,40 pp |
| 80% | 68 | 0,435 – 0,715 | 0,738% | 1,36 pp |

O custo é o teto sob o ρ **menos favorável** medido naquela fração,
varrendo todo efeito verdadeiro até 5 pp, nas três janelas. Fração maior
→ mais dia que só o estimador não pareado enxerga → menos correlação →
cláusula mais cara. **Mesmo no extremo de 80%, o custo é 0,74%.**

A cláusula sai barata em toda a faixa plausível. Isso é registro de
custo, não permissão para afrouxá-la.

#### Registro de integridade desta parte

| campo | valor |
| --- | --- |
| escrito em | 2026-09-25 |
| eventos na base nesta data | **zero** |
| o que a célula 4 testa | **restrição de amostra**, não escolha de controle |
| invariante 10, amplitude entre controles | **parcialmente atendida** |
| agregação das quatro células | **por dia, um peso por dia** |
| verificação | no código, com autoteste que separa as definições |
| custo da cláusula | 0,014% a 0,738%, conforme a fração não qualificada |
| instrumento | `correlacao_controles.py`, 23/23 |

### Fechamento do Adendo 2, parte 6 — a armadilha desarmada no código

Ainda 2026-09-25. Ainda **zero eventos na base**.

#### 13. `medir()` perdeu o padrão

`analise.medir()` agregava por evento **por omissão**. Esse padrão é
correto para reaplicar a tese — ela foi medida assim — e errado para
qualquer coisa nova. Quem escrevesse o teste de OI daqui a alguns meses
importaria `medir()` porque ela existe, funciona e é a função que todos
usam, e herdaria a contagem de eventos correlacionados como independentes
sem erro, sem aviso e com número plausível.

O Adendo 2 já declarava que o teste de OI agrega por dia. **Declaração em
documento não segura** — a própria invariante 10 tem escrito nela que as
nove primeiras quebram sozinhas e a décima é prosa. O `raise` segura.

| antes | depois |
| --- | --- |
| `medir(..., rotulo)` → agrega por evento | `medir(..., rotulo, agregacao=...)` |
| padrão implícito | **sem padrão**; `AgregacaoNaoDeclarada` |

Quem chama escreve `agregacao="evento"` e assume, ou `agregacao="dia"` e
está certo. As chamadas existentes no `analise.py` ganharam o `"evento"`
explícito, com o comentário de que ali é deliberado: aquele arquivo
reproduz o erro para poder exibi-lo, e é esse o propósito do Gate 0a.

**Guardado por teste, não por parágrafo.** O Gate 1b ganhou o bloco 9,
que verifica quatro coisas: que a chamada sem agregação levanta exceção,
que agregação desconhecida é recusada, que o parâmetro continua sem
padrão útil, e que o `analise.py` declara `"evento"` explicitamente. Se
alguém reintroduzir o padrão numa refatoração, o Gate 1b reprova.

**Verificação de que nada se moveu:** Gate 0a e Gate 0 reproduzem saída
idêntica à anterior, byte a byte. O veredito APROVADO/REPROVADO, o n, o
alpha e o win rate são os mesmos.

#### O que a agregação por dia mostra, medido agora que ela existe

Com a opção implementada, a mesma janela pode ser medida nas duas
unidades. Não era possível antes, porque a unidade era implícita:

| janela | agregação | n | alpha | win rate |
| --- | --- | --- | --- | --- |
| 0a in-sample | evento | 499 | **+1,712%** | 72,9% |
| 0a in-sample | **dia** | 67 | **+0,501%** | 65,7% |
| holdout | evento | 253 | **+0,303%** | 59,3% |
| holdout | **dia** | 72 | **+0,123%** | 52,8% |

*(alpha por dia = média, nos dias com evento, da média diária do evento,
menos a média das médias diárias do benchmark. Evento e benchmark na
mesma unidade — foi para isso que `analisar_simbolo` passou a devolver o
carimbo de tempo do benchmark.)*

**Isto não é retratação nova.** O veredito do Gate 0a foi dado sobre o
procedimento empilhado, de propósito, para replicar a tese; e a reanálise
já dizia que agrupado por dia o `t` caía de 3,97 para 1,76–1,98. O que
não existia era a **estimativa pontual** sob contagem correta.

Ela é **+0,501% in-sample**, não +1,712%. O fator de 3,4× é o peso dos
dias pesados — 28% dos eventos in-sample caíram em 10/out/2025.

E o win rate do holdout agregado por dia é **52,8%**. O pré-registro cita
o "51,7% de WR" da V1 como o exemplo do que não se deve fazer. Os dois
números estão a 1,1 ponto um do outro.

#### 14. A dívida da invariante 10, declarada e não resolvida

A parte 5 registrou que esta família **não satisfaz** a exigência de
amplitude entre controles genuinamente diferentes, e que nenhuma célula
seria acrescentada. Isso foi decisão, não conserto, e o que ela deixa em
aberto precisa ter nome:

> **Se em 2027 o resultado der positivo pela célula 4, alguém vai
> perguntar como ele se comporta sob casamento por σ. A resposta honesta
> será: não foi testado, de propósito, porque a célula custaria alfa e a
> decisão foi tomada e registrada em 2026-09-25.**

Está escrito agora para que seja **dívida declarada** e não buraco
descoberto depois. A diferença entre as duas coisas é inteira a data em
que a frase foi escrita.

O casamento por σ é o candidato óbvio justamente porque foi ele que
desmontou na autópsia — `t` de 0,05 a 2,10 conforme o esquema. Quem
quiser fechar esta dívida no futuro acrescenta a célula **antes** de
olhar o resultado, e paga o alfa. Acrescentá-la depois é a mesma operação
que criou a 79ª célula da tese.

#### Registro de integridade desta parte

| campo | valor |
| --- | --- |
| escrito em | 2026-09-25 |
| eventos na base nesta data | **zero** |
| `medir()` | sem padrão de agregação; `AgregacaoNaoDeclarada` |
| guarda | Gate 1b, bloco 9, quatro verificações |
| Gates 0a e 0 | saída idêntica à anterior |
| alpha in-sample por dia | **+0,501%** (era +1,712% empilhado) |
| alpha holdout por dia | **+0,123%** (era +0,303% empilhado) |
| dívida da invariante 10 | declarada, não resolvida |

### Fechamento do Adendo 2, parte 7 — o que os vereditos responderam

Escrito em 2026-09-27. **Zero eventos na base** — a coleta de OI segue
acumulando contexto, e nenhum gatilho da tese de OI ocorreu ainda.

#### 15. O Gate 0a respondeu a pergunta de replicação, não a de edge

Os critérios do 0a: passa acima de **+0,7% de alpha e 65% de WR**,
reprova abaixo de +0,3%. Foi aprovado com **+1,712% e 72,9%**.

Agregado por dia, a mesma janela dá **+0,501% e 65,7%**, com n = 67 dias.
O alpha cai na **zona intermediária** — nem passa nem reprova
explicitamente — e o win rate encosta no piso com 0,7 ponto de folga.

E o 0a é o gate cuja reprovação encerra o projeto: *"Reprovando, o
projeto termina."*

**Isto não é retratação.** O 0a existe para responder "o procedimento da
tese replica em futures?", e responder isso exige rodar o mesmo
procedimento — empilhado e tudo. Os limiares de +0,7% e 65% também foram
calibrados em unidade empilhada, então o gate é internamente consistente.

Mas a frase precisa estar **ao lado do veredito**, e agora está — o
`analise.py` a imprime junto, não numa seção de autópsia trinta
parágrafos acima:

> **O gate respondeu "o pipeline reproduz a tese em futures", não "existe
> edge em futures".** Sob contagem por dia a estimativa pontual cai na
> faixa que o próprio documento trata como não-passagem. Limiares por dia
> não existem, então isso não é um veredito — é o aviso de que o
> APROVADO vale para a pergunta de replicação, e só para ela.

#### 16. Nenhum limiar declarava sua unidade — consertado

Se +0,7% e 65% são números em unidade empilhada, e a diferença entre as
unidades é **3,4×**, então todo limiar de aceitação do documento carrega
uma unidade implícita que ninguém escreveu. O Gate 0 tem +0,5% e 60%. O
Gate 0b tem 70% de sobreposição.

É o `blood_toll_pct` promovido a critério de aceitação: valor medido numa
situação, aplicado em outra, por não carregar consigo de onde veio. E
como critério ele é pior que como custo — não enterra uma estratégia,
**absolve ou condena uma** sem levantar exceção.

O conserto é o do `medir()`, aplicado ao julgador:

| antes | depois |
| --- | --- |
| `GATES` traz só os números | cada gate declara `"agregacao"` |
| `julgar()` compara qualquer coisa | `UnidadeIncompativel` se as unidades diferirem |
| a unidade não aparecia na saída | primeira linha do veredito é a unidade |

`julgar()` **não converte**. O fator de 3,4 é propriedade desta amostra,
não constante de bolso — exatamente como o design effect, que variou de
3,51 a 7,45. Quem quiser julgar por dia declara limiares por dia.

**Gate 1b, bloco 9, estendido:** verifica que cada gate declara a
unidade, que `julgar()` recusa medida por dia contra limiar por evento,
que recusa medida sem unidade, que recusa gate sem unidade, e que aceita
quando as duas batem.

#### 17. Os dois win rates, lado a lado

| número | o que é |
| --- | --- |
| **51,7%** | o WR que a V1 reportou, e que este documento cita como o exemplo do que não fazer |
| **52,8%** | o WR do holdout da V2, agregado por dia |

Estão a **1,1 ponto** um do outro. Não é coincidência com significado: é
a mesma coisa medida duas vezes. **O holdout é ruído**, e agora está dito
no número que o próprio documento escolheu como símbolo de amostra
pequena lida com otimismo.

A diferença entre os dois é só quem mediu: um é a V1 se avaliando, o
outro é a V2 medindo a V1 corretamente. É o fecho que a autópsia podia
ter.

#### 18. A cobertura, e uma causa que ainda não estava consertada

Medido em 2026-09-27, sete dias de coleta:

| campo | valor |
| --- | --- |
| cobertura agregada | **48%** (4859 de 10080 minutos) |
| **09:00–10:59 UTC** | **zero absoluto nos sete dias** |
| 05:00–08:59 UTC | 12% a 27% |
| suspensão automática, na tomada | 3600 s |
| suspensão automática, na bateria | 600 s |
| hibernação | desabilitada; só S3 disponível |
| modo de logon da tarefa | **Interativo apenas** |
| último resultado da tarefa | `0x800710E0` |

Duas notas de leitura, porque as duas são armadilhas:

1. **`0x800710E0` não é falha.** É "o operador ou administrador recusou o
   pedido": a repetição de 10 minutos disparando e sendo recusada porque
   já existe instância, que é o `MultipleInstancesPolicy=IgnoreNew`
   funcionando. Lido como código de erro, mandaria alguém depurar o que
   está correto.
2. **A melhora de cobertura dos últimos dias não teve causa de código.**
   Até 2026-09-27 o `SetThreadExecutionState` **não estava
   implementado**, e o `powercfg` seguia intocado. Atribuir a melhora a
   um conserto inexistente seria construir causalidade falsa sobre a
   única série que este projeto não pode recuperar.

**Agora está implementado.** `coletor_contexto.impedir_suspensao()` pede
`ES_CONTINUOUS | ES_SYSTEM_REQUIRED` na subida, sem
`ES_DISPLAY_REQUIRED` — a tela pode apagar, e suspender manualmente
continua funcionando. Um processo que só faz requisição de rede não
reseta o contador de ociosidade do sistema; o pedido explícito reseta.

**Invariante 11 aplicada:** o pedido pode ser recusado, e recusa em
silêncio é indistinguível de sucesso. O resultado vai para o
`poller.log` na subida — `suspensao por ociosidade: BLOQUEADA` ou `NAO
BLOQUEADA`, com o motivo. Se o furo reaparecer, o log distingue "nunca
pedimos" de "pedimos e suspendeu de todo jeito".

O que isto **não** conserta: a tarefa em `Interativo apenas` não roda sem
sessão logada, então desligamento e logoff continuam produzindo furo.
Isso é configuração de sistema e fica como decisão em aberto, não como
conserto silencioso.

#### Registro de integridade desta parte

| campo | valor |
| --- | --- |
| escrito em | 2026-09-27 |
| eventos na base nesta data | **zero** |
| nota do Gate 0a | impressa junto ao veredito |
| limiares | todos declaram `agregacao` |
| `julgar()` | `UnidadeIncompativel`; não converte |
| guarda | Gate 1b, bloco 9, dez verificações |
| WR V1 / WR V2 por dia | 51,7% / 52,8% |
| cobertura agregada | 48%; 09:00–10:59 UTC em zero |
| suspensão | bloqueada por código, com resultado logado |
| tarefa em `Interativo apenas` | **não consertado**, decisão em aberto |

### Fechamento do Adendo 2, parte 8 — cobertura com causa declarada, e o backup

Escrito em 2026-09-28. **Zero eventos na base** da tese de OI.

#### 19. A causa da cobertura, declarada em vez de inferida

A cobertura subiu de 38% para 48% agregado e para 73–76% nos melhores
dias. Essa melhora foi atribuída, em conversa, ao `SetThreadExecutionState`
ou ao `powercfg`. **Nenhum dos dois existia.** O código só entrou em
2026-09-28 e o `powercfg` segue intocado.

Fica registrado porque inferir causa de código a partir de uma mudança
no padrão dos motivos de falha é a mesma operação que este documento
combate: ler um sinal como confirmação do mecanismo que se esperava
encontrar.

**A causa real, agora declarada pelo autor:** a máquina é **desligada
deliberadamente para economizar energia**. Não é suspensão, não é
logoff, não é defeito. É decisão operacional.

Isso converte a cobertura de "causa desconhecida" em **premissa do
desenho**, e tem três consequências:

1. **Trocar a tarefa para `SYSTEM` está descartado.** Máquina desligada
   não executa tarefa agendada, com conta nenhuma. Custaria privilégio
   ampliado e revalidação de caminhos para comprar zero.
2. **O `SetThreadExecutionState` cobre suspensão por ociosidade e nada
   além.** Ele é correto e barato, e não toca no modo de falha dominante.
3. **A cobertura depende de comportamento humano não modelado** e pode
   regredir sem aviso. Está escrito aqui para que uma regressão futura
   seja lida como mudança de hábito, não como defeito de software.

#### 20. As seis janelas, e a borda que não randomizou

| dia | janela UTC | minutos |
| --- | --- | --- |
| 23/09 | 04:22 → 11:50 | 449 |
| 24/09 | 05:09 → 12:01 | 413 |
| 25/09 | 05:44 → 12:10 | 387 |
| 26/09 | 03:54 → 12:25 | 512 |
| 27/09 | 08:49 → 14:39 | 351 |
| 28/09 | 06:26 → 13:21 | 416 |

Média: **421 min/dia, 29,3% do dia.** Teto de cobertura nesta máquina
≈ 71%, coerente com os 73–76% observados.

**A interseção das seis é `08:49–11:50 UTC`** — três horas ausentes em
*todos* os dias. É por isso que o `cobertura.py` acusa 09:00–10:59 UTC em
zero absoluto: a faixa está dentro da interseção, e as horas 08 e 11 só
escapam por arredondamento de hora cheia.

O diagnóstico fica mais preciso que "ponto cego estrutural":

> **Os horários de início variam de 00:54 a 05:49 local — essa borda
> randomizou. Os de fim estão agrupados entre 08:50 e 11:39, porque
> dependem de alguém ligar a máquina de manhã. A borda que produz o
> ponto cego é justamente a que não varia.**

O Adendo já declarava que variar o horário do desligamento converte
ausência sistemática em perda de poder. **Variar só uma borda não basta**
— é preciso que a borda de fim varie também, e ela não depende de
sorteio.

**Alavanca disponível, não usada:** Wake on RTC na BIOS (`Resume by
Alarm`, `Power On by RTC`) é o único mecanismo que liga a máquina a
partir de S5 — o Agendador do Windows só desperta de suspensão. Com RTC
às 04:00 local, o furo de 26/09 cairia de 8h31 para 3h06, e em cinco das
seis noites a máquina estaria ligada durante a faixa `08:49–11:50 UTC`,
**esvaziando a interseção**. É firmware da máquina, decisão do autor, e
está registrado como alavanca conhecida e não acionada.

#### 21. O calendário não é linear — e a curvatura é ao contrário do esperado

O Adendo tabulou calendário a 37%, 60% e 100%, e ficou a tentação de ler
72% por interpolação. `calendario.py` calcula em vez de interpolar:

> P(qualifica | k eventos) = 1 − (1−c·pA)^k − (1−c·pB)^k + (1−c·pA−c·pB)^k

Com `k = 1` o resultado é **sempre zero** — um evento não ocupa dois
baldes. É daí que vem a curvatura.

**Validação:** a 37% de cobertura e pA=pB=0,33, o modelo devolve
**10,9 meses** — exatamente o número que o Adendo já publicava, obtido
por outro caminho.

| cobertura | pA=pB=0,25 | **0,33** | 0,40 |
| --- | --- | --- | --- |
| 37% | 15,1 meses | **10,9** | 9,0 |
| 50% | 10,7 | 8,1 | 6,9 |
| 60% | 8,9 | 6,9 | 5,9 |
| **72% (atual)** | 7,5 | **5,9** | 5,2 |
| 85% | 6,5 | 5,2 | 4,6 |
| 100% | 5,7 | 4,7 | 4,1 |

**À cobertura atual o calendário é 5,9 meses, não 10,9.**

**E a intuição da curvatura estava errada.** O raciocínio de que exigir
dois eventos faria a probabilidade cair perto do quadrado vale para dias
de `k = 2`, e a distribuição real não é feita deles: 253 eventos em 72
dias com evento, muitos deles com `k` alto, onde `P(qualifica)` **satura**.

| taxa (pA=pB=0,33) | valor |
| --- | --- |
| a 100% de cobertura | 0,1197 dia qualificado / dia corrido |
| a 50%, se fosse proporcional | 0,0599 |
| **a 50%, medida** | **0,0693** |

A função é **côncava**, não convexa: metade da cobertura rende **58%** da
taxa, não 50% nem 25%. **Cada hora recuperada vale menos do que um
modelo quadrático sugere**, e o argumento do Wake on RTC **não se
sustenta pelo calendário**.

Ele se sustenta por outra coisa, que esta tabela não mede: com
`08:49–11:50 UTC` ausente em todos os dias, os eventos daquela faixa
**nunca são observados**. Isso não é custo de calendário, é custo de
**validade** — e mais dias não ensinam. A tabela inteira supõe cobertura
aleatória no tempo; enquanto o ponto cego existir, ela é **teto
otimista**.

#### 22. O backup, que era o item mais caro em aberto

Seis dias de OI, funding e mark price existiam **em um disco só**. O
museu volta com dois comandos; isto não volta com nenhum, em lugar
nenhum do mundo.

**Primeira cópia em 2026-09-28T13:52Z: 14 arquivos, 12,6 MB**, para
`OneDrive\SniperV2_backup\`.

`backup.py`, 20/20 no autoteste:

- **Aditivo, nunca espelho.** Arquivo removido na origem permanece no
  destino.
- **Recusa destino que não protege** — inexistente, dentro da origem, ou
  no mesmo volume, *exceto* sob raiz sincronizada declarada pelo sistema
  (`%OneDrive%`). A permissão é por variável de ambiente, **nunca por
  nome de pasta**: uma pasta batizada "OneDrive" sem sincronização não
  replica nada, e aceitar por nome deixaria passar exatamente o caso que
  não protege. O status grava **por que** aquele destino conta.
- **Falha ruidosa.** O poller copia uma vez ao dia e grita no log se
  falhar, sem morrer — coleta vale mais que cópia. E o
  `validacao_contexto.py` **reprova** se a última cópia passar de 24 h,
  com ausência de status contando como vencido. O detector de silêncio
  do backup é o porteiro que já recusa dado sujo, não um segundo
  instrumento que também pode emudecer.

Dois defeitos que o próprio autoteste pegou durante a construção, ambos
da mesma família: `arquivos_no_destino` contava o `backup_status.json` —
métrica que mudava de definição entre a primeira e a segunda execução — e
depois contava o `poller.lock` vazio que o `copy2` cria antes de falhar.

**O que este backup não é:** proteção contra exclusão acidental. O
OneDrive sincroniza exclusões; a lixeira de 30 dias é a única rede. Ele
protege contra o risco declarado, que é o disco morrer.

#### 23. A migração para 24 h não conserta o passado

Registrado com estas palavras, porque a tentação de tratar o buraco como
transitório vai existir:

> **Migrar para 24 h não conserta retroativamente os 29% já perdidos.**
> Os dias que já existem carregam o buraco para sempre, e a data da
> migração vira a fronteira entre dois regimes de amostragem.

O Adendo já exige que a passagem para cobertura contínua seja registrada
por novo adendo. Isto reforça o motivo: não é formalidade de registro, é
que **os dois períodos não são a mesma amostra** e qualquer análise que
os junte precisa dizer que os juntou.

#### Registro de integridade desta parte

| campo | valor |
| --- | --- |
| escrito em | 2026-09-28 |
| eventos na base nesta data | **zero** |
| causa da cobertura | **desligamento deliberado**, declarado pelo autor |
| `SYSTEM` na tarefa | **descartado**, não compra nada |
| interseção das seis janelas | **08:49–11:50 UTC** |
| perda média | 421 min/dia (29,3%) |
| calendário à cobertura atual | **5,9 meses** (era 10,9 a 37%) |
| curvatura | **côncava**; 50% de cobertura rende 58% da taxa |
| Wake on RTC | alavanca conhecida, **não acionada** |
| primeira cópia de backup | 2026-09-28T13:52Z, 14 arquivos, 12,6 MB |
| instrumentos | `calendario.py` 14/14, `backup.py` 20/20 |

### Fechamento do Adendo 2, parte 9 — o backup mentiu, e o que sobrou de pé

Escrito em 2026-09-28, horas depois da parte 8. **Zero eventos na base.**

#### 24. O autoteste sobrescreveu o status de produção

Horas depois da primeira cópia, o `backup_status.json` da raiz do projeto
não descrevia o backup. Descrevia **o autoteste**:

| campo | valor encontrado |
| --- | --- |
| `quando_utc` | 2026-09-28T13:59:42Z |
| `origem` | `...\Temp\backup_teste_gqqlgixm\dados` |
| `destino` | `...\Temp\backup_teste_gqqlgixm\espelho\dados` |
| `por_que_conta_como_copia` | **"sem justificativa"** |
| `arquivos_no_destino` | 3 |
| `bytes_copiados` | 17 |
| `ok` | **true** |

A cópia real foi às 13:52:59Z. O autoteste rodou às 13:59:42Z e
sobrescreveu. **O `validacao_contexto.py` teria lido um carimbo de menos
de 24 h e reportado "backup em dia", sustentado por 17 bytes numa pasta
temporária.**

É o vazamento do bloco de isolamento do Gate 1b outra vez — o terceiro
desta família, depois do `CAMINHO_LOG` preso no import e do `>> log` no
`.bat` — e agora atingindo exatamente o arquivo que o porteiro lê para
decidir se há cópia.

**Por que o detector não pegou:** o bloco de isolamento tira impressão
digital de `dados_execucao/`. O `backup_status.json` mora na **raiz do
projeto**. O detector de vazamento tinha **escopo menor que o
vazamento** — ele estava funcionando e olhando para o lugar errado.

**E havia contradição interna no próprio registro:** `ok: true` com
`por_que_conta_como_copia: "sem justificativa"`. O guarda escrito para
exigir que o destino replique para fora do disco registrou que não havia
justificativa, e o status dizia que estava tudo bem.

#### O que sobreviveu, e por quê

A cópia real aconteceu: o destino tem **14 arquivos e 12.639.618 bytes**,
e carrega o **próprio** `backup_status.json`, carimbo 13:52:59Z, com a
justificativa preenchida.

Sobreviveu porque a cópia do status é escrita **dentro do destino**. Isso
tinha sido feito para o caso de o disco morrer, e acabou servindo para um
caso não previsto: o registro local ser corrompido por algo rodando nesta
máquina.

#### 25. Os quatro consertos

**1. O autoteste não escreve mais em produção.** `caminho_status()` passa
por `_STATUS_ALT`, que o autoteste redireciona para a pasta temporária. E
o autoteste ganhou um **bloco 4 de isolamento** que tira impressão de
`backup_status.json` e `replicacao_confirmada.json` antes e depois, e
reprova se algo mudou. O instrumento agora testa a si mesmo pelo defeito
que cometeu.

**2. O escopo do detector do Gate 1b foi ampliado** para os arquivos de
estado da raiz, não só `dados_execucao/`. É o conserto estrutural: a
lição não é "o backup vazou", é que **um detector precisa cobrir todo
lugar onde produção é escrita**.

**3. `ok` passa a exigir justificativa.** Destino sem justificativa de
cópia externa entra como erro e o status vira `ok: false`. A contradição
não é mais representável.

**4. A autoridade passou a ser o destino.** `verificar_frescor()` lê o
status local, descobre o destino, e **lê o status que está dentro do
backup**. Os dois têm de existir, estar frescos, marcar `ok` e concordar
sobre o destino. Um status local fresco apontando para um destino sem
status **reprova** — que é exatamente o estado que o vazamento produziu.

O motivo é geral: o status local mora no disco que pode morrer e pode ser
escrito por qualquer coisa nesta máquina. O que está dentro do backup,
não.

#### 26. O buraco conceitual, que era maior que os quatro

`copiar()` prova que os arquivos foram **escritos** na pasta do OneDrive.
**Não prova que o OneDrive replicou nada.** Cliente pausado, deslogado ou
sem quota: os arquivos ficam no mesmo disco, o status diz "em dia", e a
proteção é zero.

É um instrumento afirmando sucesso que não mediu — a família inteira de
erros deste projeto, na última camada que sobrou.

**Não há como medir isso daqui** sem depender de sinal frágil: atributo
de arquivo, log do cliente, processo vivo. Nenhum deles prova replicação.
Então não se finge que mede:

> **Exige-se atestado humano da primeira replicação, por destino.** O
> atestado é uma **afirmação datada de uma pessoa** que abriu o serviço na
> web e viu os arquivos lá — não uma medição — e o próprio arquivo de
> atestado diz isso no campo `natureza`.

`verificar_frescor()` reprova sem atestado. Destino novo exige atestado
novo. E o comando imprime, antes de gravar, o que a pessoa está afirmando.

**Estado nesta data: o atestado NÃO existe.** O porteiro reprova, e é o
comportamento correto — ninguém verificou ainda se os arquivos chegaram
ao servidor. Fica assim até alguém conferir em `onedrive.com` e rodar
`python backup.py --confirmar-replicacao`.

`backup.py`: **30/30**, incluindo os quatro blocos novos.

#### O que este episódio custou e o que não custou

Não custou dado: os 14 arquivos estão no destino, e a segunda cópia do
status provou isso. Custou **a confiança no registro local**, por seis
horas, durante as quais o porteiro teria dito "em dia" sem base.

E vale nomear o que quase aconteceu: a parte 8 deste adendo afirma
"primeira cópia em 2026-09-28T13:52Z, 14 arquivos, 12,6 MB". Aquela frase
estava **certa**, mas a prova dela tinha sido destruída minutos depois, e
ninguém teria notado se o status não morasse também do lado de lá.

#### Registro de integridade desta parte

| campo | valor |
| --- | --- |
| escrito em | 2026-09-28 |
| eventos na base nesta data | **zero** |
| dado perdido | **nenhum** — 14 arquivos, 12.639.618 bytes no destino |
| registro local | corrompido por 6 h, refeito às 14:08:15Z |
| autoteste escrevendo em produção | **consertado**, com bloco que prova |
| escopo do detector do Gate 1b | ampliado à raiz do projeto |
| `ok` com "sem justificativa" | **impossível** agora |
| autoridade do frescor | **o status dentro do backup** |
| replicação de fato | **não verificada**; atestado humano exigido e ausente |
| `backup.py` | 30/30 |

### Fechamento do Adendo 2, parte 10 — o atestado vence

Escrito em 2026-09-28. **Zero eventos na base.**

#### 27. Afirmação pontual não é garantia contínua

O atestado humano da parte 9 resolve *"ninguém verificou nunca"*. **Não
resolve *"alguém verificou uma vez, em março"*.**

O cliente de sincronização pode ser pausado, deslogado, estourar quota ou
perder a vinculação da conta a qualquer momento **depois** da
confirmação. O `replicacao_confirmada.json` continua lá, o porteiro
continua aprovando, e a replicação parou meses atrás.

É a forma exata do defeito que este projeto passou a semana caçando — uma
afirmação pontual tratada como garantia contínua — agora na camada que
protege o único ativo irrecuperável. A mesma estrutura do
`blood_toll_pct`, do `0x800710E0` lido como falha, do design effect
herdado entre janelas: **um valor verdadeiro num instante, aplicado a
outro instante em que ninguém o reconferiu.**

#### O conserto: o atestado tem prazo

| campo | valor |
| --- | --- |
| validade | **30 dias** |
| aviso antecipado | 7 dias |
| gravado no atestado | `vence_em_utc`, `validade_dias`, `por_que_vence` |

Passou de 30 dias, `verificar_frescor()` reprova e pede reconfirmação.
Custa dez segundos por mês, e converte "verificado uma vez" em
**"verificado periodicamente"** — a única forma honesta de afirmar uma
propriedade que muda sozinha.

O prazo fica **escrito dentro do próprio atestado**, ao lado do
`natureza: "AFIRMACAO HUMANA, NAO MEDICAO"`, junto com o motivo. Quem
abrir o arquivo daqui a um ano lê por que ele vence sem precisar do
código.

**O poller avisa antes de doer.** Na cópia diária ele consulta o frescor
e registra no log quando faltam 7 dias ou menos, ou quando a replicação
já não tem atestado válido. Sem isso o vencimento só apareceria quando
alguém rodasse o porteiro — e o ponto inteiro é não depender de alguém
lembrar.

#### O vencimento é provado, não afirmado

`backup.py`: **37/37**, com o bloco `2d` cobrindo atestado de 40 dias, de
31, de 29, o aviso em 25, a ausência de aviso em 1, carimbo ilegível, e o
prazo gravado no arquivo.

**Gate 1b, bloco 9b:** injeta um atestado datado de 40 dias atrás e exige
reprovação; injeta um de 2 dias e exige aprovação; remove o atestado e
exige reprovação. O vencimento entra na mesma categoria dos outros
detectores — não basta ele existir, ele precisa **disparar em teste**.

E o bloco 9b redireciona status e atestado para pasta temporária via
`_STATUS_ALT`. Escrever o atestado de produção ali seria repetir
literalmente o vazamento de horas antes; o **bloco 10** confere que não
foi, e conferiu.

#### Estado nesta data

| item | estado |
| --- | --- |
| cópia local para `%OneDrive%` | **feita** — 14 arquivos, 12,6 MB |
| status local | correto, `ok: true` sustentado |
| status dentro do destino | presente e concordante |
| **replicação de fato** | **não verificada** |
| atestado | **não existe** |
| porteiro | **reprova**, saída 1 |

O porteiro reprovar é o comportamento certo. Até alguém abrir o serviço
na web, ver os arquivos e rodar `python backup.py
--confirmar-replicacao`, o projeto tem duas cópias no mesmo disco cuja
replicação ninguém checou.

#### Registro de integridade desta parte

| campo | valor |
| --- | --- |
| escrito em | 2026-09-28 |
| eventos na base nesta data | **zero** |
| validade do atestado | **30 dias**, aviso em 7 |
| prova do vencimento | Gate 1b bloco 9b + `backup.py` bloco 2d |
| isolamento do bloco novo | verificado pelo bloco 10 |
| `backup.py` | **37/37** |
| replicação | **ainda não atestada** |

### Fechamento do Adendo 2, parte 11 — destino final e replicação atestada

Escrito em 2026-09-28. **Zero eventos na base.**

#### 28. O destino mudou por modo de falha, não por comodidade

O backup passou de `%OneDrive%` para **`G:\Meu Drive\SniperV2_backup`**,
a letra do Google Drive em modo streaming.

O argumento decisivo foi um modo de falha que **o atestado não pega**:

> Com a quota estourada, o cliente para de sincronizar mas a pasta em
> `C:` continua existindo. O `backup.py` copia, conta 14 arquivos, grava
> `ok: true`, e nada sai do disco. Entre duas renovações do atestado
> haveria até **30 dias de cópia imaginária**.

O `G:` não tem esse estado: ou a letra existe e replica, ou some e o
backup quebra na hora. **O destino que quebra alto é o que satisfaz a
invariante 11 por construção**, sem precisar de guarda.

Duas consequências de desenho:

1. O critério de volume passou a ser perguntado ao **sistema de
   arquivos** (`st_dev`), não deduzido da string do caminho. Uma pasta
   batizada "Google Drive" em `C:` tem letra `C:` e não replica nada.
   Sem poder perguntar, a resposta conservadora é "mesmo volume", que
   **exige** justificativa em vez de dispensá-la.
2. O mecanismo de raiz sincronizada (`%OneDrive%`) **fica no código**.
   Ele resolve o caso geral de pasta sincronizada dentro do mesmo
   volume, e vale para qualquer provedor assim. **Saiu a configuração,
   não a lição.**

**Gate 1b, bloco 9c** prova o que dá a vantagem: destino ausente
**reprova em vez de criar a pasta** — `conferir_destino` recusa e não
cria, `copiar()` recusa e não cria, volume inteiro ausente recusa. Sem
esse teste, um `os.makedirs` numa refatoração traria o silêncio de volta.

#### 29. A ordem das operações preservou a garantia

A troca seguiu ordem declarada antes de começar: apontar, copiar,
conferir na web, atestar, e **só então** remover a cópia antiga.

Entre o primeiro e o quarto passo, a única cópia verificada era a do
OneDrive. Removê-la antes deixaria os sete dias existindo só no disco
desta máquina, por alguns minutos. **É o mesmo raciocínio de não fundir
células antes de declarar a família: a ordem das operações é que preserva
a garantia.**

#### Estado nesta data

| item | estado |
| --- | --- |
| destino | `G:\Meu Drive\SniperV2_backup\dados_execucao` |
| cópia | 14 arquivos, 12,5 MB |
| justificativa gravada | `volume distinto (G:), confirmado por st_dev` |
| **replicação atestada** | **sim** — 2026-09-28T15:03:20Z, por `User` |
| validade do atestado | 29 dias restantes |
| porteiro | **aprova**, saída 0 |
| cópia antiga no OneDrive | **mantida**, remoção não executada |

#### O que ainda não está automático

O poller em execução (PID 17768, subida às 13:22Z) **não tem o gancho de
backup**: ele subiu antes do código existir, e o `.bat` só passou a
definir `SNIPER_BACKUP_DIR` depois. A cópia de hoje foi **manual**.

O gancho e a variável entram na próxima subida do poller — que acontece
quando a máquina for ligada de novo. Fica registrado para que ninguém
leia "backup automático" como algo que já rodou alguma vez: **até esta
data, toda cópia foi disparada à mão.**

O bloqueio de suspensão, esse sim, está ativo no processo de pé desde
13:22Z.

### Fechamento do Adendo 2, parte 12 — a cópia antiga vira instrumento

Escrito em 2026-09-28. **Zero eventos na base.**

#### 30. A cópia do OneDrive fica, e com função declarada

Decisão do autor: **manter**, por dois motivos. O segundo não estava no
desenho e é melhor que o primeiro.

1. **Segundo provedor.** O destino vivo depende da conta Google; esta
   cópia cobre perder o acesso a ela. Custa 12 MB.
2. **Referência de integridade.** A série é **append-only** — um dia já
   escrito nunca deveria mudar. Uma cópia congelada e datada permite
   perguntar depois: *o passado continua igual, ou alguém reescreveu
   história?*

O risco de mantê-la era nomeado: uma pasta parada com dados de setembro
**pode parecer cópia em março**. Isso foi resolvido fazendo a cópia
**declarar o que é** — um `LEIA-ME.txt` dentro dela diz que é instantâneo
datado, que não é mantido, onde fica o backup vivo, e que estar velha é
desenho e não defeito.

#### 31. O instantâneo, e por que o critério é o prefixo

Comparar o hash do **arquivo inteiro** não serviria: ele muda a cada
linha nova, e o detector gritaria todo minuto — ruído que ninguém lê, que
é uma das formas de um instrumento morrer.

O que se congela é, por arquivo, o **tamanho em bytes naquela data** e o
**SHA-256 desses primeiros bytes**. Mais tarde, re-hashear os mesmos N
bytes responde à pergunta certa:

| evento | veredito |
| --- | --- |
| arquivo cresceu | **não é divergência** — a série só cresce |
| arquivo novo apareceu | **não é divergência** |
| byte alterado dentro do prefixo | **HISTORIA ALTERADA** |
| arquivo truncado | **ENCOLHEU** |
| arquivo sumiu | **REMOVIDO** |

`backup.py`: **45/45**, com o bloco `3b` provando cada uma dessas cinco
linhas, mais a que justifica o desenho — o hash do arquivo inteiro muda
com o append e o do prefixo não.

**O manifesto é versionado no git.** Se as duas cópias morrerem, o
repositório ainda prova o que os arquivos eram em 2026-09-28. É a única
peça desta cadeia que não depende de disco nem de provedor.

#### Estado nesta data

| item | estado |
| --- | --- |
| backup vivo | `G:\Meu Drive\SniperV2_backup`, atestado, 29 dias |
| instantâneo datado | OneDrive, com `LEIA-ME.txt` declarando a natureza |
| manifesto | `instantaneo_2026-09-28.json`, 14 arquivos, versionado |
| comparação hoje | **nenhuma divergência** |
| porteiro | aprova, saída 0 |

### Fechamento do Adendo 2, parte 13 — uma retratação e quatro defeitos

Escrito em 2026-09-28. **Zero eventos na base.**

#### 32. RETRATADO: os arquivos não sumiram do destino

Foi afirmado nesta data, com tabela de horários, que os 14 arquivos
copiados para o `G:` às 14:58Z **desapareceram** e que o atestado
testemunhava conteúdo inexistente. **Isso está errado.**

A evidência usada foi `copiados=14, inalterados=0` numa cópia posterior,
lida como "o destino estava vazio". Medido depois, arquivo a arquivo:
`contexto_2026-09-23.csv` com 2.013.201 bytes na origem e no destino,
mtime idêntico ao milissegundo; o mesmo para os demais.

Os arquivos estavam lá o tempo todo. **O defeito era da detecção de
mudança**, não do destino.

#### 33. A causa: comparar `st_mtime_ns` com `>` estrito

A decisão de recopiar usava `st_o.st_mtime_ns > st_d.st_mtime_ns`. Isso
parece exato e é **errado entre sistemas de arquivos diferentes**: o `G:`
do cliente de sincronização guarda o carimbo com precisão menor que o
NTFS, então a origem é sempre "mais nova" por nanossegundos e **todo
arquivo era recopiado em toda passada**.

O estrago não foi o trabalho extra. Foi que `inalterados` ficava
permanentemente em zero, e **isso foi lido como perda de dados, e um
incidente que não houve foi afirmado.**

Corrigido com tolerância de 2 s — a mesma do `rsync`, pelo mesmo motivo.
Depois da correção: `copiados=1, inalterados=13`, o esperado para uma
série append-only com um arquivo crescendo.

**A lição não é sobre nanossegundos.** É que um instrumento cuja saída
alguém interpreta precisa ser verificado antes da interpretação. Os
bytes só foram medidos depois de a acusação já estar escrita.

#### 34. Os quatro defeitos reais que o episódio expôs

**(a) O destino morava em dois lugares.** Estava no
`iniciar_poller.bat`, onde só o poller o enxergava. O procedimento
documentado no README — *"rode `python backup.py
--confirmar-replicacao`"* — **não funcionava num shell limpo**. Pior: se
o `.bat` declarasse um caminho e o ambiente do usuário outro, o poller e
a pessoa copiariam para pastas **diferentes**, cada um achando que era a
mesma. Duas cópias parciais, duas sensações de backup completo.

Agora há **fonte única**: `destino_backup.txt`, lido pelos dois. Se a
variável de ambiente e o arquivo discordarem, `destino()` **levanta** em
vez de escolher no escuro. Gate 1b testa o conflito.

**(b) O poller não tentava de novo.** Às 15:52Z ele subiu e o backup
falhou porque **o `G:` ainda não estava montado** — o cliente monta no
logon e o poller sobe antes. O dia era marcado como tentado *antes* de
saber o resultado, então uma falha na subida matava o backup daquele dia
inteiro. Com a máquina desligada toda noite, isso significaria backup
automático falhando em **todo boot, para sempre**, com o log gritando uma
vez por dia e nada sendo feito.

Agora o dia só é marcado no **sucesso**, e a falha reagenda em 10 min.

**(c) O atestado era automatizável.** Ele é a única peça do sistema que
não pode ser, porque existe precisamente porque nenhum código consegue
verificar se o serviço replicou. E o campo `quem` não protege: registra a
conta do Windows, e qualquer processo rodando como o usuário assina com o
nome dele.

Agora exige **teclado interativo e a palavra `CONFIRMO`**. `stdin` que
não seja terminal é recusado. Verificado: um processo não consegue
assinar. **Um elo humano automatizável não é elo nenhum.**

**(d) A contagem incluía o próprio instrumento** — de novo. O
`INSTANTANEO_*.json` entrava em `arquivos_no_destino`, o que quebrava o
detector de esvaziamento. Terceira ocorrência desta família. Agora há uma
definição única, `e_dado()`, usada nos três lugares.

#### 35. O detector de esvaziamento, que ficou de pé

Mesmo sendo falso alarme desta vez, o cenário é real: se o destino for
esvaziado, um atestado anterior continuaria valendo, porque estava
amarrado ao **caminho** e não ao conteúdo.

Agora a cópia detecta o esvaziamento — cópia anterior registrava N
arquivos, esta recopiou todos sem encontrar nenhum igual —, grava o
carimbo, **persiste a marca nas cópias seguintes**, e
`exigir_atestado_posterior_ao_zeramento()` reprova atestado anterior ao
evento.

`backup.py`: **54/54**.

#### 36. E o bloco de isolamento pegou o próprio autor, de novo

Ao inserir os testes novos, eles foram colocados **depois** do `finally`
que desfaz o redirecionamento do status. Rodaram apontando para o status
de **produção** e o sobrescreveram com dados de pasta temporária — o
mesmo vazamento de horas antes, pela terceira vez no mesmo arquivo.

O **bloco 4 reprovou**, que é exatamente para isso que ele existe. A
limpeza foi movida para o fim, com um comentário dizendo que bloco novo
entra acima dela.

E a falha quase foi atribuída ao poller, por hipótese, antes de alguém
ler o conteúdo do status. Ele dizia `origem: ...\Temp\backup_teste_...`.
A hipótese confortável estava errada e o arquivo dizia isso.

#### 37. Wake on RTC: acionado

O autor ativou, na BIOS, despertar automático às **06:00 locais,
diário**. A lacuna de 13 min em 15:39–15:51Z foi essa configuração sendo
feita, não defeito.

**Efeito esperado sobre o ponto cego:** a interseção das janelas de falha
era `08:49–11:50 UTC`. Com a máquina ligando às 06:00 locais = **09:00
UTC**, a faixa `09:00–11:50 UTC` passa a ser coberta em toda noite cuja
parada tenha sido anterior. A interseção encolhe para, no máximo,
`08:49–09:00 UTC` — onze minutos —, e as horas `09:00–10:59`, que estavam
em **zero absoluto nos sete dias**, deixam de estar.

Isto é **previsão, não medição**. Será verificado com `cobertura.py`
depois de alguns dias, e o resultado entra aqui com a data.

E há um efeito colateral: o boot por RTC vai reproduzir **toda manhã** a
corrida entre o poller e a montagem do `G:`. A retentativa do item (b)
deixa de ser detalhe e passa a ser o que faz o backup automático existir.

#### Registro de integridade desta parte

| campo | valor |
| --- | --- |
| escrito em | 2026-09-28 |
| eventos na base nesta data | **zero** |
| perda de dados | **nenhuma** — afirmação anterior retratada |
| destino | fonte única em `destino_backup.txt` |
| retentativa do poller | 10 min, dia marcado só no sucesso |
| atestado | exige teclado e a palavra `CONFIRMO` |
| atestado atual | **apagado**; precisa ser refeito |
| Wake on RTC | **acionado**, 06:00 locais |
| `backup.py` | 54/54 |

### Fechamento do Adendo 2, parte 14 — as previsões, verificadas

Escrito em 2026-09-29. **Zero eventos na base.**

#### 38. O ponto cego quebrou

A parte 37 previu que, com despertar por RTC às 06:00 locais, as horas
`09:00–10:59 UTC` deixariam de estar em zero absoluto. **Confirmado.**

| hora UTC | 28/09 (7 dias) | 29/09 (8 dias) |
| --- | --- | --- |
| 09:00 | **0%** | **12%** |
| 10:00 | **0%** | **12%** |
| agregado | 48% | **55%** |

`cobertura.py` agora imprime: *"Nenhuma hora com cobertura zero em todos
os dias."* É a primeira vez que essa linha aparece desde que o
instrumento existe.

O mecanismo está no log, e o RTC disparou no minuto: a lacuna noturna
terminou às `08:59 UTC` e a subida do poller está carimbada em
`29/09 06:00 (29/09 09:00 UTC)`.

#### A métrica de ontem estava frágil, e isto é correção de método

A parte 20 mediu o ponto cego pela **interseção das janelas de falha**,
como `[maior início, menor fim]`. Recalculada hoje sobre os mesmos
arquivos, ela devolve **zero minutos** — e não porque o problema sumiu,
mas porque a fórmula quebra em dois casos que passaram a existir:

- uma janela que **cruza a meia-noite** (22/09, `17:29 → 02:05 UTC`), em
  que "início" é numericamente maior que "fim";
- uma janela **diurna** (24/09, `17:04 → 19:28 UTC`), que não é parada
  noturna e não deveria entrar na mesma conta.

A conta servia enquanto havia exatamente uma parada por noite, nenhuma
cruzando meia-noite. Era **métrica ad hoc apresentada como estrutural**.

A medida correta já existia e é a do `cobertura.py`: **cobertura por hora
UTC contra o dia de 1440 minutos**, que não depende de as janelas serem
bem-comportadas. É ela que vale, e é ela que confirma a previsão.

#### 39. O risco mudou de borda, não desapareceu

A parte 20 dizia: *"a borda que produz o ponto cego é justamente a que
não varia"* — e a borda travada era o fim, porque dependia de alguém
acordar.

**O RTC inverteu isso.** O fim agora é determinístico às `09:00 UTC`. A
borda que precisa variar passou a ser o **início** — a hora de desligar.

| noite | desligou (UTC) |
| --- | --- |
| 23/09 | 04:22 |
| 24/09 | 05:09 |
| 25/09 | 05:44 |
| 26/09 | 03:54 |
| 27/09 | 08:49 |
| 28/09 | 06:26 |
| 29/09 | 01:52 |

Hoje esse início varia numa faixa de quase sete horas, e é por isso que
nenhuma hora fica em zero. **Mas se o hábito de desligar se regularizar**
— sempre por volta das 23:00 locais, por exemplo — a faixa `02:00–09:00
UTC` vira ponto cego estrutural novo, com o fim travado pelo RTC e o
início travado pelo hábito.

Fica registrado como **o que observar**, não como problema atual. A
alavanca disponível, se acontecer, é um segundo despertar por RTC no meio
da madrugada: ele parte a janela em duas e nenhuma hora fica ausente em
todas as noites.

#### 40. O backup automático rodou pela primeira vez

Até 28/09 **toda cópia havia sido disparada à mão**, e isso estava
registrado na parte 11. Hoje o poller copiou sozinho, três vezes:

```
[29/09 00:00 UTC] backup ok: 16 arquivos em G:\Meu Drive\SniperV2_backup
[29/09 09:01 UTC] backup ok: 16 arquivos
[29/09 16:10 UTC] backup ok: 16 arquivos
```

16 arquivos e não 14 porque o dia 29/09 trouxe o seu `contexto_` e o seu
`contexto_falhas_`.

E o aviso de replicação dispara em toda cópia, como desenhado: *"BACKUP
SEM REPLICACAO VALIDA: ninguem confirmou..."*. O atestado foi apagado em
28/09 e ainda não foi refeito.

#### A retentativa ainda NÃO foi exercitada

A parte 34(b) implementou reagendamento em 10 min para o caso de o `G:`
ainda não estar montado na subida. **Ela não foi testada em produção.**

- A falha de `28/09 15:52 UTC` ocorreu sob o código **antigo**, que
  marcava o dia antes de saber o resultado. O sucesso seguinte, às
  `00:00 UTC`, veio da **virada do dia**, não da retentativa.
- A subida de hoje às `09:00 UTC` copiou com sucesso em `09:01`, **sem
  falhar antes**. O `G:` já estava montado.

Ou seja: a corrida existe (aconteceu uma vez), o conserto está no código,
e **nenhuma execução provou que ele funciona**. Fica assim escrito para
não ser lido como verificado. Um autoteste para esse caminho é dívida
declarada.

#### Registro de integridade desta parte

| campo | valor |
| --- | --- |
| escrito em | 2026-09-29 |
| eventos na base nesta data | **zero** |
| horas em zero absoluto | **nenhuma** (eram 09:00–10:59) |
| cobertura agregada | 48% → **55%** |
| RTC | disparou às 09:00 UTC, no minuto |
| métrica de interseção | **retirada** — frágil a janela noturna e a meia-noite |
| backup automático | **primeira vez**, 3 cópias hoje |
| retentativa do backup | implementada, **não exercitada** |
| atestado de replicação | **ausente**; porteiro reprovando |

### Fechamento do Adendo 2, parte 15 — o limiar binário, e a alavanca que não existe

Escrito em 2026-09-29. **Zero eventos na base.**

#### 41. "Nenhuma hora com cobertura zero" é verdade e é frágil

A parte 38 celebrou a frase do `cobertura.py`. Ela está correta e
**esconde que o suporte é de um dia por hora**. Medido:

| hora UTC | local | dias que contribuem | cobertura |
| --- | --- | --- | --- |
| 06:00 | 03:00 | 27/09 (60 min), 28/09 (26 min) | 17,9% |
| 07:00 | 04:00 | **só 27/09** (60 min) | 12,5% |
| 08:00 | 05:00 | **só 27/09** (49 min) | 10,2% |
| 09:00 | 06:00 | **só 29/09** (59 min) | 12,3% |
| 10:00 | 07:00 | **só 29/09** (60 min) | 12,5% |

As horas `09:00` e `10:00` existem **só por causa de hoje**, o primeiro
dia com RTC. As `07:00` e `08:00` existem **só por causa de 27/09**, uma
noite atípica em que a máquina ficou ligada até tarde.

**"Zero horas em zero" é um limiar binário sobre uma contagem de dias,
não uma medida de cobertura.** Ele foi cruzado por um dia. Removido o
29/09, as horas 09 e 10 voltam a zero.

É o mesmo defeito que a invariante 10 combate em outro lugar: **`n = 1`
não é medida**. A frase passou a valer com uma observação por hora, e foi
lida como propriedade estabelecida.

**A leitura honesta:** o mecanismo está provado — o RTC dispara no minuto
e a coleta começa junto. O **remendo estatístico não existe ainda**. A
faixa precisa sair de ~12% e chegar perto dos ~80% do resto do dia, e
isso são semanas de alarme disparando, não uma manhã.

Fica declarado: **a verificação da parte 38 é do mecanismo, não da
cobertura.** A cobertura se reavalia quando a faixa tiver dias
suficientes para não depender de nenhum deles em particular.

#### 42. CORRIGIDO: o segundo alarme de RTC não é implementável

A parte 39 registrou, como alavanca disponível, *"um segundo despertar
por RTC no meio da madrugada"*. **A BIOS tem um alarme só** — não existe
segundo `Resume By RTC Alarm` nesta placa nem na maioria delas.

Registrar alavanca que não existe é pior que não registrar nada: daqui a
três meses alguém tenta usá-la e descobre. Fica retirada.

**A alavanca que existe** é o Agendador de Tarefas do Windows: ele não
liga máquina desligada, mas **acorda da suspensão** — a opção *"Despertar
o computador para executar esta tarefa"* — e pode ser usada em quantos
horários se quiser. Isso exige **suspender em vez de desligar**.

#### E ela tem uma interação com o conserto de 28/09 que precisa estar escrita

O `SetThreadExecutionState` com `ES_CONTINUOUS | ES_SYSTEM_REQUIRED`
**impede a suspensão automática por ociosidade enquanto o poller roda**.
Consequências, nesta ordem:

1. A máquina **não vai suspender sozinha** à noite. A suspensão teria de
   ser manual — o que funciona, porque o bloqueio nunca impediu
   suspensão manual, de propósito.
2. Depois de um despertar agendado às 03:00, a máquina **não volta a
   suspender sozinha**, pelo mesmo bloqueio. Ela fica ligada até alguém
   agir.

Ou seja: **como está, um despertar agendado não parte a madrugada em
duas — ele encerra a suspensão da noite.** Isso aumenta cobertura e
aumenta consumo, e não é o que a palavra "partir" sugeria.

Partir de verdade exigiria o poller **liberar o bloqueio** dentro de uma
janela noturna declarada, para que a máquina pudesse voltar a suspender.
Isso é **mudança de desenho, não de configuração**, e não está
autorizada nem implementada. Fica como opção descrita, com o custo
explícito.

**E há o precedente:** a suspensão foi o modo que produziu o furo de
25/09, com o processo vivo e a máquina dormindo. O comportamento mudou
desde então — o bloqueio existe e o log registra se o pedido foi aceito —
mas trocar desligamento por suspensão reintroduz uma família de falha que
este projeto já pagou para aprender.

#### Registro de integridade desta parte

| campo | valor |
| --- | --- |
| escrito em | 2026-09-29 |
| eventos na base nesta data | **zero** |
| "nenhuma hora em zero" | verdade, com **n = 1 dia** em 4 das 5 horas |
| o que a parte 38 verificou | **o mecanismo**, não a cobertura |
| segundo alarme de RTC | **retirado** — a BIOS tem um só |
| alavanca real | despertar por tarefa agendada, a partir da **suspensão** |
| interação declarada | o bloqueio de ociosidade impede re-suspender sozinho |
| atestado de replicação | **ainda ausente** |
