# Feature Specification: Assistente Financeiro Conversacional via API

**Feature Branch**: `001-financial-assistant-api`

**Created**: 2026-09-27

**Status**: Draft

**Input**: User description: "Construir um assistente financeiro via API REST que orquestra um agente LangGraph com três ferramentas (RAG sobre documentos financeiros, cotação de moedas em tempo real e calculadora), mantém memória de conversa por thread_id e recusa perguntas fora do domínio financeiro via guardrail no primeiro nó do grafo."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consultar documentos financeiros com resposta fundamentada (Priority: P1)

Um cliente (aplicação integradora ou pessoa usando uma interface) envia uma pergunta sobre
finanças, por exemplo "Qual a taxa de administração do fundo X?" ou "Como funciona o
come-cotas?". O assistente busca a resposta na base de documentos financeiros do projeto e
responde em linguagem natural, indicando os documentos que usou. Se a base não tiver a
informação, o assistente diz isso explicitamente e não inventa a resposta.

**Why this priority**: é o núcleo de valor do produto: respostas financeiras confiáveis e
verificáveis (Princípio I da constituição). Sozinha, esta história já entrega um MVP útil.

**Independent Test**: carregar um conjunto conhecido de documentos, fazer perguntas cuja resposta
está neles e outras cuja resposta não está, e conferir as citações e as recusas.

**Acceptance Scenarios**:

1. **Given** a base contém um documento que responde à pergunta, **When** o cliente envia essa
   pergunta, **Then** a resposta traz a informação correta e identifica o(s) documento(s) de origem.
2. **Given** a base não contém informação sobre o tema perguntado, **When** o cliente envia a
   pergunta, **Then** o assistente informa que não encontrou a informação nas fontes disponíveis
   e não apresenta dados inventados.

---

### User Story 2 - Recusar perguntas fora do domínio financeiro (Priority: P1)

Quando o cliente pergunta algo que não é de finanças ("Me dá uma receita de bolo", "Quem ganhou
o jogo ontem?"), o assistente recusa educadamente com uma mensagem padronizada e lembra qual é o
seu escopo. Isso acontece antes de qualquer consulta a documentos, cotações ou cálculos.

**Why this priority**: o guardrail de escopo é inegociável (Princípio II). Sem ele, o produto
não pode ser exposto.

**Independent Test**: enviar um conjunto de perguntas classificadas como dentro/fora de escopo e
verificar que as de fora recebem a mensagem padrão e que nenhuma fonte ou ferramenta foi acionada.

**Acceptance Scenarios**:

1. **Given** uma pergunta claramente fora de finanças, **When** o cliente a envia, **Then** a
   resposta é a mensagem padrão de recusa e nenhuma consulta a fontes é registrada.
2. **Given** uma mensagem que tenta instruir o assistente a ignorar suas regras e sair do escopo,
   **When** o cliente a envia, **Then** o assistente a trata como fora de escopo e recusa.
3. **Given** uma pergunta financeira legítima, **When** o cliente a envia, **Then** ela não é
   recusada pelo guardrail.

---

### User Story 3 - Cotação de moedas em tempo real (Priority: P2)

O cliente pergunta a cotação atual de uma moeda ("Quanto está o dólar hoje?") ou pede uma
conversão ("Quanto são 500 euros em reais?"). O assistente consulta a cotação vigente, responde
com o valor, o par de moedas e o momento da cotação, e usa o cálculo exato na conversão.

**Why this priority**: é um caso de uso muito frequente e de alto valor, mas depende da base de
conversa e do guardrail (P1) para existir com segurança.

**Independent Test**: perguntar a cotação de pares suportados e comparar com a fonte de cotação
no mesmo instante. Perguntar por uma moeda inexistente e verificar o erro amigável.

**Acceptance Scenarios**:

1. **Given** um par de moedas suportado, **When** o cliente pergunta a cotação, **Then** a
   resposta traz o valor, o par e a data/hora da cotação.
2. **Given** um pedido de conversão de valor, **When** o cliente o envia, **Then** o valor
   convertido é igual a valor × cotação de compra (bid) informada, arredondado para 2 casas
   decimais, e a resposta indica que usou a cotação de compra.
3. **Given** que a fonte de cotação está indisponível, **When** o cliente pede uma cotação,
   **Then** o assistente informa que não conseguiu obter a cotação agora e não apresenta um valor
   estimado.

---

### User Story 4 - Cálculos financeiros exatos (Priority: P2)

O cliente pede um cálculo ("Quanto rende R$ 10.000 a 1% ao mês por 12 meses em juros
compostos?", "Quanto é 15% de 2.340?"). O assistente faz a conta exata e mostra o resultado e a
expressão usada, sem estimar de cabeça.

**Why this priority**: números vindos do modelo sem ferramenta violam o Princípio I. A
calculadora garante exatidão.

**Independent Test**: enviar um conjunto de cálculos com resultado conhecido e comparar as respostas.

**Acceptance Scenarios**:

1. **Given** um pedido de cálculo bem formado, **When** o cliente o envia, **Then** o resultado
   é exato (tolerância de arredondamento de 2 casas decimais) e a expressão usada é exibida.
2. **Given** uma expressão inválida (por exemplo, divisão por zero), **When** o cliente a envia,
   **Then** o assistente explica que não é possível calcular e o motivo.

---

### User Story 5 - Continuidade da conversa por identificador de thread (Priority: P1)

O cliente conduz uma conversa em vários turnos usando um identificador de conversa (`thread_id`).
Perguntas de acompanhamento ("E em euro?", "E se fossem 24 meses?") são entendidas com base no
histórico daquela thread. Threads diferentes não compartilham histórico.

**Why this priority**: sem memória por thread, a experiência conversacional não funciona, e o
Princípio IV exige que o estado dependa só do `thread_id`.

**Independent Test**: fazer uma pergunta e depois um acompanhamento na mesma thread, e repetir o
acompanhamento em outra thread. Reiniciar o serviço entre os turnos e verificar que a memória
se mantém.

**Acceptance Scenarios**:

1. **Given** uma thread com uma pergunta anterior sobre o dólar, **When** o cliente envia "E o
   euro?" na mesma thread, **Then** o assistente entende que o pedido é a cotação do euro.
2. **Given** duas threads distintas, **When** o cliente faz um acompanhamento na segunda thread,
   **Then** o histórico da primeira não influencia a resposta.
3. **Given** que o serviço foi reiniciado entre dois turnos, **When** o cliente continua a
   thread, **Then** o histórico anterior continua disponível.
4. **Given** uma requisição sem `thread_id`, **When** ela é enviada, **Then** uma nova thread é
   criada e seu identificador é devolvido na resposta.

---

### Edge Cases

- Uma pergunta mista (parte financeira e parte fora de escopo): o assistente responde só a parte
  financeira e informa que ignorou o restante.
- Uma pergunta ambígua entre finanças e outro domínio (por exemplo, "banco" de praça): na dúvida
  o assistente pede esclarecimento, e não recusa sem perguntar.
- Uma pergunta que exige várias ferramentas ("converta 1.000 USD para BRL e aplique 1% ao mês por
  6 meses"): o assistente encadeia cotação e cálculo e apresenta cada etapa.
- Uma moeda não suportada ou um código inválido gera uma mensagem amigável com exemplos de
  moedas suportadas.
- Um `thread_id` em formato inválido gera um erro de requisição claro.
- Uma mensagem vazia ou acima do limite de tamanho gera um erro de validação.
- Um documento relevante encontrado com baixa relevância não é usado como base. Nesse caso vale
  "não encontrei".
- Uma fonte externa lenta é tratada com um tempo limite e uma mensagem de indisponibilidade.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE expor um endpoint de conversa que recebe uma mensagem do usuário e
  um `thread_id` opcional, e devolve a resposta do assistente, o `thread_id` usado e a lista de
  fontes consultadas.
- **FR-002**: O sistema DEVE avaliar o escopo de toda mensagem como primeira etapa, antes de
  qualquer consulta a documentos, cotações ou cálculo.
- **FR-003**: Mensagens fora do domínio financeiro DEVEM receber uma mensagem de recusa
  padronizada, que descreve o escopo atendido.
- **FR-004**: O sistema DEVE responder perguntas conceituais e documentais com base apenas em
  trechos recuperados da base de documentos financeiros, identificando os documentos de origem.
- **FR-005**: Quando nenhuma fonte fornecer informação suficiente, o sistema DEVE declarar que
  não sabe. É proibido responder com conhecimento não verificado.
- **FR-006**: O sistema DEVE obter cotações de moedas de uma fonte em tempo real e informar o par,
  o valor e a data/hora da cotação.
- **FR-007**: Todo valor numérico calculado (conversões, juros, percentuais) DEVE ser produzido
  pela calculadora, e a resposta DEVE mostrar a expressão usada.
- **FR-008**: O sistema DEVE manter o histórico de cada conversa associado ao `thread_id`,
  persistido fora do processo do serviço, e preservá-lo após reinícios.
- **FR-009**: Uma requisição sem `thread_id` DEVE criar uma nova conversa e devolver o
  identificador gerado.
- **FR-010**: Conversas de `thread_id` diferentes DEVEM ser totalmente isoladas.
- **FR-011**: O sistema DEVE validar a entrada (mensagem não vazia, tamanho máximo de 4.000
  caracteres, formato válido de `thread_id`) e devolver um erro descritivo quando ela for inválida.
- **FR-012**: Falhas ou lentidão das fontes externas DEVEM gerar uma resposta amigável de
  indisponibilidade, sem valores estimados.
- **FR-013**: O sistema DEVE registrar em log estruturado, por resposta, a decisão do guardrail,
  as ferramentas acionadas e as fontes usadas.
- **FR-014**: As respostas DEVEM ser em português do Brasil.
- **FR-015**: O sistema DEVE expor um endpoint de verificação de saúde para monitoramento.
- **FR-016**: O sistema DEVE permitir consultar o histórico de mensagens de um `thread_id`.

### Key Entities

- **Thread (Conversa)**: identificada por `thread_id`. Agrupa a sequência ordenada de mensagens
  de uma conversa.
- **Mensagem**: um turno da conversa. Tem papel (usuário ou assistente), conteúdo, data/hora e,
  no caso do assistente, as fontes citadas.
- **Documento Financeiro**: uma unidade da base de conhecimento, com título, origem e conteúdo
  dividido em trechos recuperáveis.
- **Fonte Citada**: a referência que fundamenta uma resposta (trecho de documento, cotação com
  data/hora ou cálculo com expressão).
- **Cotação**: par de moedas, valor e data/hora de referência.
- **Decisão de Escopo**: resultado do guardrail para uma mensagem (dentro, fora ou ambígua) e
  seu motivo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: ≥ 95% das perguntas fora de escopo de um conjunto de avaliação são recusadas, e
  ≤ 5% das perguntas financeiras legítimas são recusadas indevidamente.
- **SC-002**: 100% das afirmações factuais das respostas avaliadas remetem a uma fonte citada
  (documento, cotação ou cálculo). Nenhuma resposta traz dados inventados no conjunto de avaliação.
- **SC-003**: ≥ 90% das perguntas cuja resposta está na base de documentos recebem uma resposta
  correta, e ≥ 95% das perguntas sem resposta na base recebem "não encontrei".
- **SC-004**: 100% dos cálculos do conjunto de avaliação batem com o resultado esperado
  (tolerância de 2 casas decimais).
- **SC-005**: ≥ 90% das perguntas de acompanhamento dependentes do contexto são interpretadas
  corretamente dentro da mesma thread, com 0 casos de vazamento de contexto entre threads.
- **SC-006**: 95% das respostas chegam ao usuário em até 10 segundos, e as recusas de escopo em
  até 3 segundos.
- **SC-007**: O histórico de uma thread continua disponível após reinício do serviço em 100% dos
  testes.

## Assumptions

- Os consumidores são aplicações integradoras (front-ends, bots) que chamam a API. A interface de
  usuário final está fora do escopo desta feature.
- A base de documentos financeiros é fornecida e carregada previamente pelos operadores, por
  exemplo com um processo de ingestão executado offline. Upload de documentos pelo usuário final
  está fora do escopo da v1.
- As cotações vêm de um provedor público de câmbio. As moedas suportadas são as oferecidas pelo
  provedor, com foco nos pares contra o real (BRL).
- A v1 não tem autenticação de usuário final. O acesso é protegido no nível de infraestrutura
  (rede interna ou chave de acesso da aplicação), e o `thread_id` funciona como identificador de
  conversa, não como credencial.
- O histórico de conversas é mantido por 30 dias, salvo definição posterior.
- O assistente não faz recomendações personalizadas de investimento ("compre/venda X"). Ele
  explica conceitos, informa dados e faz cálculos. Pedidos de recomendação recebem um aviso de que
  não constituem aconselhamento financeiro.
- Restrição técnica indicada pelo solicitante: a orquestração usará um agente baseado em grafo
  (LangGraph), com o guardrail como primeiro nó e três ferramentas: busca em documentos, cotação
  e calculadora. O detalhamento fica para o plano.
