# Research: Assistente Financeiro Conversacional via API

**Feature**: `001-financial-assistant-api` | **Date**: 2026-09-27

Todas as incertezas do Technical Context foram resolvidas abaixo. As decisões sobre LLM,
armazenamento e embeddings foram confirmadas pelo solicitante em 2026-09-27.

## R1. Linguagem e framework HTTP

- **Decision**: Python 3.12 + FastAPI, com Uvicorn e endpoints async.
- **Rationale**: LangGraph e LangChain são Python-first. O FastAPI gera o OpenAPI
  automaticamente, valida com Pydantic v2 e tem suporte async nativo, que combina com o
  checkpointer async do Postgres.
- **Alternatives considered**: Flask foi descartado por ser síncrono e não gerar OpenAPI nativo.
  LangGraph Platform/Server foi descartado por trazer lock-in e porque o requisito pede uma API
  REST própria.

## R2. LLM (agente principal e guardrail)

- **Decision**: OpenAI `gpt-4o-mini` via `langchain-openai` (`ChatOpenAI`), com
  `temperature=0`, no agente e no guardrail. Os IDs ficam configuráveis por `LLM_MODEL` e
  `GUARDRAIL_MODEL`.
- **Rationale**: é a escolha do solicitante. O modelo tem bom custo/latência e tool calling e
  structured output confiáveis. Com `temperature=0` o comportamento fica mais reproduzível para
  as avaliações (SC-001 a SC-005).
- **Alternatives considered**: modelos Anthropic (Opus/Haiku) e Sonnet foram propostos e
  recusados pelo solicitante.

## R3. Guardrail de escopo (primeiro nó do grafo)

- **Decision**: o nó `guardrail` é a primeira aresta a partir de `START`. Ele chama o LLM com
  **structured output** (`with_structured_output(ScopeDecision)`), que devolve
  `{label: in_scope|out_of_scope|ambiguous, reason}`. O nó analisa só a última mensagem do
  usuário mais um resumo curto do contexto da thread (as 2 últimas trocas), para que
  acompanhamentos como "E o euro?" não sejam recusados. O roteamento condicional é:
  `out_of_scope` → `refuse`, `ambiguous` → `clarify`, `in_scope` → `agent`.
- **Rationale**: o Princípio II exige um componente explícito e testável que rode antes de
  qualquer ferramenta. Um nó dedicado pode ser testado isoladamente com um LLM mockado e com o
  conjunto de avaliação. O structured output elimina o parsing frágil. A instrução anti-injection
  fica no prompt do classificador, que trata o texto do usuário como dado e nunca como instrução.
- **Alternatives considered**: um classificador por embeddings/keywords foi descartado por
  generalizar mal para acompanhamentos e injection. Só uma instrução no system prompt do agente
  viola o Princípio II. A biblioteca externa NeMo Guardrails é pesada demais para a v1.

## R4. Orquestração do agente

- **Decision**: um `StateGraph` com `MessagesState` estendido, contendo os nós `guardrail`,
  `refuse`, `clarify`, `agent` (LLM com `bind_tools`) e `tools` (`ToolNode`). A condição
  `tools_condition` faz o laço agent↔tools. O limite é `recursion_limit=12`.
- **Rationale**: é o padrão ReAct do LangGraph, com o controle explícito necessário para
  encaixar o guardrail antes. Isso é mais transparente que `create_react_agent` e mantém o
  guardrail como nó próprio.
- **Alternatives considered**: `create_react_agent` com `pre_model_hook` roda antes de cada
  chamada do modelo, e não uma vez por turno, o que dificulta o roteamento de recusa.

## R5. Memória por thread_id (API stateless)

- **Decision**: `AsyncPostgresSaver` (`langgraph-checkpoint-postgres`) como checkpointer, com
  `config={"configurable": {"thread_id": ...}}` a cada invocação. Uma tabela auxiliar
  `thread_metadata` guarda `created_at` e `last_activity_at` para aplicar a retenção de 30 dias
  (job `purge-threads`).
- **Rationale**: atende o Princípio IV e os requisitos FR-008 e FR-010. Nenhum estado fica no
  processo, e qualquer réplica atende qualquer thread. O histórico sobrevive a reinícios (SC-007).
  O mesmo Postgres também serve os vetores (R6).
- **Alternatives considered**: `MemorySaver` viola o Princípio IV. Um Redis checkpointer seria
  mais uma peça para operar.

## R6. RAG: armazenamento vetorial e embeddings

- **Decision**: PostgreSQL 16 + **pgvector** via `langchain-postgres` (`PGVector`), com
  embeddings OpenAI `text-embedding-3-small` (1536 dimensões) configuráveis por
  `EMBEDDING_MODEL`. O chunking usa `RecursiveCharacterTextSplitter` com 1000 caracteres e
  overlap de 150. A busca por similaridade usa k=4 e um **limiar mínimo de relevância**
  (`RAG_MIN_SCORE`, 0.35 de similaridade de cosseno para começar, calibrado com o eval). Trechos
  abaixo do limiar são descartados, e sem trecho a resposta é "não encontrei" (FR-005).
- **Rationale**: é a escolha do solicitante. Um único banco para memória e vetores simplifica a
  operação. O limiar evita respostas baseadas em trechos pouco relevantes (edge case da spec).
- **Alternatives considered**: Chroma/SQLite não escala horizontalmente. Qdrant seria outro
  serviço. Embeddings locais e Voyage foram recusados pelo solicitante.

## R7. Ingestão de documentos

- **Decision**: um comando CLI offline, `python -m financial_agent.rag.ingest <dir>`, que aceita
  PDF (`pypdf`), Markdown e TXT. Os metadados de cada trecho são `source` (nome do arquivo),
  `title`, `page` e `chunk_id`. A ingestão é idempotente por hash do conteúdo.
- **Rationale**: a spec definiu que a base é carregada pelos operadores e que upload por usuário
  está fora do escopo.
- **Alternatives considered**: um endpoint de upload fica para uma feature futura.

## R8. Cotação de moedas em tempo real

- **Decision**: **AwesomeAPI** (`https://economia.awesomeapi.com.br/json/last/{PAR}`, por exemplo
  `USD-BRL`), gratuita e sem chave, via `httpx.AsyncClient` com timeout de 5 s e 1 retry. A URL
  base é configurável (`FX_API_BASE_URL`). O retorno inclui `bid`, `ask` e `create_date`, que é
  usado como timestamp da cotação.
- **Rationale**: é focada em pares contra BRL (premissa da spec), atualiza em minutos e dispensa
  credencial.
- **Alternatives considered**: Frankfurter/ECB só tem cotação diária, o que não é tempo real.
  Open Exchange Rates e exchangerate.host exigem chave.

## R9. Calculadora segura

- **Decision**: um avaliador de expressões por **AST** (`ast.parse` em modo `eval`) com uma
  whitelist de nós (números, `+ - * / ** %`, parênteses, unário), aritmética em `Decimal` com
  precisão 28, e resultado arredondado para 2 casas (`ROUND_HALF_EVEN`) na apresentação e 10 casas
  no valor bruto. `eval`/`exec` são proibidos. Há limites de tamanho da expressão (200
  caracteres) e do expoente (≤ 1000).
- **Rationale**: o Princípio I exige números vindos da ferramenta, e o requisito FR-007 exige
  exibir a expressão. A abordagem é determinística (Princípio III) e segura contra injeção de
  código.
- **Alternatives considered**: `numexpr` e `sympy` são dependências pesadas. `eval` é inseguro.
  Ferramentas separadas por fórmula (juros compostos etc.) foram descartadas porque o LLM monta a
  expressão e a calculadora continua com responsabilidade única.

## R10. Citação de fontes na resposta

- **Decision**: as ferramentas usam `response_format="content_and_artifact"`. O conteúdo vai para
  o LLM e o artefato estruturado (`SourceCitation`) vai para o estado. A API extrai os artefatos
  dos `ToolMessage` do turno atual e devolve o campo `sources[]` na resposta.
- **Rationale**: as fontes chegam ao cliente de forma estruturada e verificável, sem depender do
  texto gerado (Princípio I e requisito FR-001).

## R11. Observabilidade

- **Decision**: `structlog` com saída JSON. Cada turno gera um evento `chat_turn` com
  `thread_id`, `request_id`, `scope_label`, `tools_called[]`, `sources[]`, `latency_ms` e o
  consumo de tokens. Segredos nunca são logados, e o conteúdo da mensagem só é logado truncado.
- **Rationale**: atende a seção de Restrições da constituição e o requisito FR-013.

## R12. Testes e avaliação

- **Decision**:
  - `pytest` + `pytest-asyncio`.
  - `respx` para mockar a AwesomeAPI.
  - `testcontainers[postgres]` com a imagem `pgvector/pgvector:pg16` para os testes de
    integração.
  - LLM fake (`FakeMessagesListChatModel`/`GenericFakeChatModel`) nos testes de grafo.
  - Uma suíte `tests/eval/` marcada com `@pytest.mark.eval`, que chama a OpenAI real. Ela usa os
    datasets JSONL `scope.jsonl`, `grounding.jsonl`, `calc.jsonl` e `followup.jsonl` e calcula
    as métricas SC-001 a SC-005.
- **Rationale**: a constituição exige testes unitários por ferramenta e casos de avaliação para o
  guardrail e o RAG.

## R13. Autenticação da API

- **Decision**: não há autenticação de usuário final na v1 (premissa da spec). Há um header
  opcional `X-API-Key` validado contra `API_KEYS`, ativado se a variável estiver definida.
- **Rationale**: protege a aplicação sem criar gestão de usuários.

## R14. Empacotamento e execução

- **Decision**: `uv` para dependências (`pyproject.toml`), um `Dockerfile` da API e
  `docker-compose.yml` com `api` e `db` (`pgvector/pgvector:pg16`). As migrações dos
  checkpointers rodam via `checkpointer.setup()` no startup (lifespan). A tabela
  `thread_metadata` é criada por um script SQL idempotente.
