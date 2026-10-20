# Feature Specification: Interface Web de Conversa do Financial Agent

**Feature Branch**: `002-web-chat-frontend`

**Created**: 2026-10-19

**Status**: Draft

**Input**: User description: "Quero criar um frontend para o projeto, preciso pensar em organização de pastas, novas tarefas, já tenho um system design pronto que está no claude design"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Conversar e ver a resposta fundamentada (Priority: P1)

Uma pessoa abre a interface, escreve uma pergunta de finanças ("Quanto são 500 euros em reais?",
"O que é come-cotas?") e envia. Enquanto o assistente trabalha, a tela mostra que a pergunta está
sendo processada. Quando a resposta chega, ela aparece em linguagem natural com marcadores
numerados ([1], [2]…) que apontam para cartões de fonte logo abaixo: um cartão por fonte, com o
tipo escrito por extenso (documento, cotação ou cálculo) e os dados que tornam a resposta
verificável (trecho do documento, valor de compra e horário da cotação, expressão e resultado do
cálculo).

**Why this priority**: é o núcleo de valor do produto: ver de onde veio cada número (Princípio I
da constituição). Sozinha, esta história já é um MVP demonstrável.

**Independent Test**: com a API no ar, enviar uma pergunta que use documentos e outra que use
cotação + cálculo e conferir que cada resposta mostra os marcadores e um cartão por fonte
devolvida pela API.

**Acceptance Scenarios**:

1. **Given** a tela de conversa vazia, **When** a pessoa digita uma pergunta e envia, **Then** a
   pergunta aparece na conversa, um indicador de processamento é exibido e o envio de nova
   mensagem fica bloqueado até a resposta chegar.
2. **Given** a API devolveu uma resposta com fontes, **When** a resposta é exibida, **Then** cada
   fonte aparece em um cartão visível sem cliques extras, identificado pelo tipo em texto.
3. **Given** uma resposta com marcadores [n], **When** a pessoa ativa o marcador [2], **Then** o
   cartão da fonte 2 é destacado e levado à área visível.
4. **Given** uma fonte de cotação, **When** o cartão é exibido, **Then** ele indica que o valor
   usado é a cotação de compra e mostra data e hora no horário de Brasília, com números no formato
   brasileiro (vírgula decimal).

---

### User Story 2 - Entender recusas e avisos do assistente (Priority: P1)

Quando a pergunta está fora de finanças, é ambígua, não tem resposta nas fontes ou pede
recomendação de investimento, o assistente devolve uma mensagem padronizada. A interface apresenta cada caso como um aviso próprio, com título e ícone,
em tom neutro ou de atenção, nunca como erro técnico, e mostra o texto exatamente como veio do
assistente.

**Why this priority**: o guardrail é inegociável (Princípio II); se a interface confundir recusa
com falha, a pessoa não entende o comportamento do produto.

**Independent Test**: enviar uma pergunta fora de escopo, uma ambígua, uma sem resposta na base e
uma pedindo recomendação; cada uma deve gerar o aviso correspondente, distinto dos demais e de um
erro técnico.

**Acceptance Scenarios**:

1. **Given** a API classificou a pergunta como fora de escopo, **When** a resposta é exibida,
   **Then** aparece um aviso de recusa em tom neutro com a mensagem padrão, sem cartões de fonte.
2. **Given** a API classificou a pergunta como ambígua, **When** a resposta é exibida, **Then**
   aparece um aviso de esclarecimento em tom de atenção convidando a pessoa a reformular.
3. **Given** a resposta é "Não encontrei essa informação nas fontes disponíveis.", **When** ela é
   exibida, **Then** aparece um aviso de informação não encontrada, sem fontes.
4. **Given** a resposta contém o aviso de que não constitui recomendação de investimento,
   **When** ela é exibida, **Then** o aviso aparece destacado abaixo da resposta.

---

### User Story 3 - Retomar conversas anteriores (Priority: P2)

A pessoa tem várias conversas. Uma lista lateral mostra as conversas iniciadas naquele navegador,
cada uma com título (a primeira pergunta) e última atividade. Ao escolher uma, o histórico
completo é recarregado com suas fontes. Um botão "Nova conversa" começa outra do zero. A lista
informa que conversas sem atividade por 30 dias são apagadas.

**Why this priority**: memória por conversa já existe na API (Princípio IV); sem a lista, ela fica
invisível. Não é necessária para o MVP de pergunta e resposta.

**Independent Test**: criar duas conversas, recarregar a página, abrir cada uma e conferir que o
histórico e as fontes voltam; simular uma conversa expurgada e conferir que ela sai da lista.

**Acceptance Scenarios**:

1. **Given** duas conversas criadas, **When** a página é recarregada, **Then** ambas continuam na
   lista com título e última atividade.
2. **Given** uma conversa na lista, **When** a pessoa a seleciona, **Then** as mensagens e fontes
   anteriores são exibidas e novas perguntas continuam a mesma conversa.
3. **Given** uma conversa que não existe mais no servidor, **When** a pessoa a seleciona,
   **Then** ela é removida da lista, um aviso explica que expirou e uma nova conversa é aberta.
4. **Given** qualquer conversa aberta, **When** a pessoa escolhe "Nova conversa", **Then** a área
   de conversa fica vazia e a próxima pergunta inicia uma conversa nova.

---

### User Story 4 - Entender falhas técnicas (Priority: P2)

Se o serviço estiver indisponível, recusar o acesso ou rejeitar a mensagem, a interface mostra um
erro claro em português: o que aconteceu, o que fazer e o identificador da requisição para
reportar o problema. Quando faz sentido tentar de novo, há um botão para isso.

**Why this priority**: sem isso, uma falha parece travamento. Vem depois do fluxo feliz.

**Independent Test**: derrubar o serviço, enviar uma pergunta e conferir a mensagem, o
identificador e o "Tentar de novo"; religar e tentar de novo com sucesso.

**Acceptance Scenarios**:

1. **Given** o serviço está indisponível, **When** a pessoa envia uma pergunta, **Then** aparece
   um erro com o identificador da requisição e a opção "Tentar de novo", que reenvia a mesma
   pergunta sem que ela precise redigitar.
2. **Given** o acesso ao serviço foi negado, **When** a resposta chega, **Then** o erro explica
   que a interface não está autorizada e não oferece nova tentativa.
3. **Given** um erro técnico, **When** ele é exibido, **Then** tem aparência distinta das recusas
   e avisos da US2.

---

### User Story 5 - Ver o agente trabalhando (Priority: P3)

Acima de cada resposta, um resumo mostra os passos do turno: verificação de escopo, ferramentas
usadas (busca em documentos, cotação, cálculo, com o detalhe de cada uma) e verificação final.
Durante a espera aparece só a verificação de escopo em andamento; ao fim, os passos são
reconstruídos a partir das fontes devolvidas. O resumo pode ser recolhido.

**Why this priority**: torna a interface uma vitrine técnica do agente, mas a resposta já é
útil sem ele.

**Independent Test**: enviar uma pergunta de conversão de moeda e conferir que o resumo lista
cotação (com o par) e cálculo (com a expressão).

**Acceptance Scenarios**:

1. **Given** uma pergunta em processamento, **When** a pessoa observa a tela, **Then** vê a
   verificação de escopo em andamento, anunciada também a leitores de tela.
2. **Given** uma resposta com fonte de cotação e de cálculo, **When** ela chega, **Then** o
   resumo mostra os passos de cotação e cálculo concluídos com seus detalhes.

---

### Edge Cases

- Mensagem vazia, só com espaços ou acima de 4.000 caracteres: o envio é impedido na própria
  interface, com indicação do motivo e do limite.
- Duplo envio (Enter repetido, clique duplo) enquanto a resposta não chegou: só um envio ocorre.
- Resposta demorada (dezenas de segundos): o indicador de processamento continua visível e a
  interface não trava.
- Serviço fora do ar ao abrir a interface: a tela carrega e indica a indisponibilidade antes do
  primeiro envio.
- Armazenamento do navegador indisponível ou bloqueado: a conversa funciona; só a lista de
  conversas anteriores não é mantida.
- Dados salvos no navegador corrompidos ou com identificador inválido: são descartados sem
  quebrar a tela.
- Resposta sem fontes e sem aviso padrão: exibida como texto simples, sem área de fontes vazia.
- Muitas fontes em uma resposta (ex.: 6+): todas visíveis, organizadas em grade.
- Tema claro e escuro do sistema operacional; telas estreitas (celular), com a lista de conversas
  acessível sem esconder a conversa permanentemente.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A interface DEVE permitir enviar uma pergunta em texto e exibir a resposta do
  assistente na mesma conversa.
- **FR-002**: A interface DEVE exibir um indicador de processamento enquanto aguarda a resposta e
  bloquear novos envios nesse intervalo.
- **FR-003**: A interface DEVE validar antes do envio que a mensagem não está vazia nem só com
  espaços e tem no máximo 4.000 caracteres.
- **FR-004**: Toda resposta com fontes DEVE exibir um cartão por fonte, visível sem interação,
  identificado pelo tipo em texto (documento, cotação, cálculo), e não apenas por cor.
- **FR-005**: Marcadores [n] no texto da resposta DEVEM ser interativos e destacar o cartão da
  fonte correspondente.
- **FR-006**: Cartões de documento DEVEM mostrar título, arquivo, página (quando houver),
  relevância e trecho; cartões de cotação, o par, compra (destacada como valor usado), venda,
  data e hora em horário de Brasília e provedor; cartões de cálculo, a expressão e o resultado.
- **FR-007**: Números DEVEM ser exibidos no formato brasileiro (vírgula decimal, separador de
  milhar) e com algarismos de largura fixa.
- **FR-008**: A interface DEVE apresentar de forma distinta cada classificação da resposta:
  dentro do escopo, fora do escopo (recusa), ambígua (esclarecimento), informação não encontrada,
  e aviso de não recomendação. Uma pergunta mista é exibida como resposta comum, com o aviso
  escrito pelo próprio assistente no texto.
- **FR-009**: A interface NÃO DEVE reescrever, resumir ou complementar o texto devolvido pelo
  assistente; as mensagens padronizadas aparecem exatamente como recebidas.
- **FR-010**: A interface DEVE manter, por navegador, a lista de conversas iniciadas, com título
  (primeira pergunta, abreviada) e data da última atividade, ordenada pela atividade mais recente.
- **FR-011**: Ao selecionar uma conversa, a interface DEVE recuperar e exibir seu histórico
  completo, incluindo as fontes de cada resposta.
- **FR-012**: Se uma conversa não existir mais no servidor, a interface DEVE removê-la da lista,
  informar que expirou e abrir uma conversa nova.
- **FR-013**: A interface DEVE permitir iniciar uma nova conversa a qualquer momento e informar
  que conversas sem atividade por 30 dias são apagadas.
- **FR-014**: Falhas técnicas (acesso negado, mensagem rejeitada, serviço indisponível) DEVEM
  exibir mensagem em português com o que aconteceu, o que fazer e o identificador da requisição;
  apenas a indisponibilidade oferece "Tentar de novo".
- **FR-015**: A credencial de acesso ao serviço NÃO DEVE ser enviada ao navegador nem ficar
  acessível ao usuário final; o acesso DEVE ser intermediado pelo lado servidor da interface.
- **FR-016**: A interface DEVE exibir o resumo dos passos do turno, derivado da verificação de
  escopo e das fontes devolvidas, recolhível pela pessoa.
- **FR-017**: A interface NÃO DEVE enviar o conteúdo das conversas a nenhum serviço além do
  próprio Financial Agent (sem analytics ou terceiros).
- **FR-018**: A interface DEVE ser operável só por teclado, com foco sempre visível, anunciar o
  processamento a leitores de tela de forma não intrusiva e anunciar erros imediatamente.
- **FR-019**: A interface DEVE suportar tema claro e escuro, seguindo a preferência do sistema, e
  respeitar a preferência por movimento reduzido.
- **FR-020**: A interface DEVE seguir o design system "Financial Agent" já definido (cores,
  tipografia, espaçamento, componentes e voz em português do Brasil).
- **FR-021**: A interface DEVE indicar ao abrir se o serviço está indisponível.

### Key Entities

- **Conversa**: identificador da conversa no serviço, título (primeira pergunta), data da última
  atividade. Guardada no navegador; o conteúdo vive no serviço.
- **Mensagem**: papel (pessoa ou assistente), texto, horário e, nas respostas, a classificação de
  escopo e a lista de fontes.
- **Fonte**: uma de três formas: documento (título, arquivo, página, trecho, relevância), cotação
  (par, compra, venda, horário, provedor) ou cálculo (expressão, resultado).
- **Passo do turno**: etapa exibida no resumo (verificação de escopo, ferramenta usada,
  verificação final) com estado (em andamento, concluído, falhou) e detalhe.
- **Erro**: código, mensagem e identificador da requisição devolvidos pelo serviço.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A partir da tela vazia, uma pessoa obtém a primeira resposta com no máximo 2 ações
  (digitar e enviar), sem instruções prévias.
- **SC-002**: 100% das respostas com fontes exibem um cartão por fonte devolvida, conferido no
  roteiro de testes manuais.
- **SC-003**: 100% das classificações de resposta (FR-008) e das falhas técnicas (FR-014) têm
  apresentação visual e textual distinta, verificável em teste lado a lado.
- **SC-004**: Após recarregar a página, uma conversa anterior é retomada com no máximo 1 clique,
  com histórico e fontes completos.
- **SC-005**: Todo texto atinge contraste mínimo de 4,5:1 (3:1 para controles e texto grande)
  nos temas claro e escuro.
- **SC-006**: Todos os fluxos das US1–US4 são concluídos só com teclado.
- **SC-007**: A credencial de acesso ao serviço não aparece em nenhum conteúdo recebido ou
  armazenado pelo navegador.
- **SC-008**: Em pelo menos 9 de 10 sessões de teste, a pessoa identifica corretamente a fonte de
  um número da resposta sem ajuda.

## Assumptions

- Uso de demonstração/vitrine técnica com um operador único: não há login de usuário final; o
  acesso ao serviço usa uma credencial configurada no servidor da interface.
- O serviço responde a cada pergunta de uma vez, sem envio progressivo; o resumo de passos é
  reconstruído a partir das fontes (US5).
- O serviço não lista conversas; a lista é local a cada navegador e não sincroniza entre
  dispositivos.
- A retenção de 30 dias é a configuração atual do serviço.
- Português do Brasil é o único idioma; foco em desktop, com uso viável em celular.
- O design system "Financial Agent" no Claude Design (tokens, componentes e tela de referência de
  conversa) é a fonte visual e de voz.
- A interface ficará em uma pasta própria na raiz do repositório, sem reorganizar o serviço
  existente; estrutura de pastas, tecnologia, execução local e integração ao pipeline são
  definidas no `/speckit-plan`.
- A única mudança no serviço é aditiva: cada fonte de documento passa a informar o número `[n]`
  com que foi citada, para ligar o marcador ao cartão (FR-005). O acesso intermediado não exige
  mudança no serviço.
- A API não sinaliza perguntas mistas (parte financeira + parte fora do escopo): um aviso
  dedicado para esse caso depende de um sinal explícito na API e fica para uma feature futura.
