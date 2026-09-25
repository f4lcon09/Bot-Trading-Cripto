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
