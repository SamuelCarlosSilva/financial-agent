# Implementation Plan: Assistente Financeiro Conversacional via API

**Branch**: `001-financial-assistant-api` | **Date**: 2026-09-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-financial-assistant-api/spec.md`

## Summary

A feature é uma API REST (FastAPI) que expõe um agente LangGraph de finanças. O grafo começa
por um nó **guardrail**, um classificador com structured output que roteia a mensagem para
`agent`, `refuse` ou `clarify`. O nó `agent` (OpenAI `gpt-4o-mini`) usa três ferramentas de
responsabilidade única: `search_financial_documents` (RAG com pgvector e embeddings OpenAI),
`get_currency_quote` (AwesomeAPI em tempo real) e `calculate` (avaliador AST com `Decimal`). O
estado da conversa fica só no checkpointer Postgres, indexado por `thread_id`. As fontes usadas
em cada turno são devolvidas de forma estruturada em `sources[]`. Os detalhes das decisões estão
em [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: FastAPI, Uvicorn, LangGraph, langchain-openai, langchain-postgres
(PGVector), langgraph-checkpoint-postgres, psycopg[binary,pool] 3, httpx, pydantic v2,
pydantic-settings, pypdf, structlog

**Storage**: PostgreSQL 16 + pgvector, com checkpoints do LangGraph, `thread_metadata` e a
coleção vetorial `financial_docs`

**Testing**: pytest, pytest-asyncio, respx, testcontainers[postgres], fakes de chat model do
LangChain e a suíte `eval` com o LLM real

**Target Platform**: servidor Linux em container Docker. Desenvolvimento via docker-compose.

**Project Type**: web-service (API REST, backend único)

**Performance Goals**: p95 ≤ 10 s por resposta completa e p95 ≤ 3 s para recusas de escopo
(SC-006). A meta inicial é de 20 requisições concorrentes por instância.

**Constraints**: nenhum estado em memória entre requisições. Timeout de 5 s no provedor de câmbio
e de 30 s no LLM. `recursion_limit=12` no grafo. Mensagens de até 4000 caracteres. Retenção de 30
dias.

**Scale/Scope**: v1 com até cerca de 1.000 documentos (≈ 50k trechos), dezenas de usuários
simultâneos, 3 endpoints e 3 ferramentas.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Como o design atende | Status |
|---|---|---|
| I. Respostas fundamentadas em contexto verificável | Fatos vêm só do RAG ou da API de câmbio. Há limiar de relevância e "NENHUM_RESULTADO_RELEVANTE" leva a "não encontrei". Todo número passa por `calculate`. `sources[]` estruturado vem dos artefatos das ferramentas. O system prompt proíbe conhecimento não verificado. As métricas SC-002 e SC-003 estão no eval. | ✅ PASS |
| II. Guardrail de escopo inegociável | O nó `guardrail` é a primeira aresta a partir de `START`, antes de qualquer ferramenta. É um componente isolado com testes unitários (LLM fake) e o dataset `scope.jsonl`, que inclui injection. A mensagem de recusa é uma constante. | ✅ PASS |
| III. Ferramentas com responsabilidade única | São 3 ferramentas, cada uma com uma única função e docstring-contrato em [contracts/tools.md](contracts/tools.md). São determinísticas e testadas isoladamente com mocks (respx, fake embeddings). | ✅ PASS |
| IV. API stateless / thread_id | `AsyncPostgresSaver` com `thread_id` no `configurable`. Não há cache de conversa no processo. O teste de reinício (SC-007) e o de isolamento entre threads estão previstos. | ✅ PASS |
| Restrições (segredos, logs, dados pessoais) | Segredos vêm só do `.env`/variáveis de ambiente via pydantic-settings. O log estruturado `chat_turn` registra ferramentas e fontes. O conteúdo das mensagens é logado truncado. Só a query/mensagem é enviada à OpenAI. | ✅ PASS |
| Quality gates | Cada ferramenta tem teste unitário. O guardrail e o RAG têm datasets de eval. | ✅ PASS |

**Re-check pós-design (Phase 1)**: ✅ PASS. O contrato OpenAPI expõe `scope` e `sources`,
o que permite auditar os Princípios I e II pelo cliente. O data model não introduz estado no
processo. Nenhuma violação a justificar.

## Project Structure

### Documentation (this feature)

```text
specs/001-financial-assistant-api/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── openapi.yaml     # Contrato REST
│   └── tools.md         # Contrato das ferramentas e do guardrail
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
src/financial_agent/
├── config.py                  # Settings (pydantic-settings): modelos, DB, limiares, timeouts
├── logging.py                 # structlog JSON + request_id
├── api/
│   ├── app.py                 # FastAPI + lifespan (pool, checkpointer.setup, grafo compilado)
│   ├── routes.py              # POST /v1/chat, GET /v1/threads/{id}/messages, GET /health
│   ├── schemas.py             # ChatRequest/ChatResponse/SourceCitation (Pydantic)
│   ├── security.py            # X-API-Key opcional
│   └── errors.py              # handlers → formato Error
├── graph/
│   ├── state.py               # GraphState, ScopeDecision
│   ├── builder.py             # build_graph(checkpointer) → CompiledStateGraph
│   ├── prompts.py             # system prompt do agente e do guardrail, OUT_OF_SCOPE_MESSAGE
│   └── nodes/
│       ├── guardrail.py
│       ├── agent.py
│       ├── refuse.py
│       └── clarify.py
├── tools/
│   ├── __init__.py            # get_tools(settings, vectorstore, http_client): fábricas make_*_tool
│   ├── document_search.py     # search_financial_documents
│   ├── currency_quote.py      # get_currency_quote
│   └── calculator.py          # calculate (AST + Decimal)
├── rag/
│   ├── vectorstore.py         # fábrica PGVector + embeddings
│   └── ingest.py              # CLI de ingestão (PDF/MD/TXT)
└── maintenance/
    └── purge_threads.py       # CLI de retenção de 30 dias

tests/
├── unit/                      # calculator, currency_quote (respx), document_search (fake), guardrail, nodes
├── contract/                  # API vs openapi.yaml (TestClient + grafo fake)
├── integration/               # Postgres real (testcontainers): memória, reinício, isolamento, RAG
└── eval/                      # marker eval (OpenAI real)
    ├── judge.py               # juiz LLM: fundamentação, idioma, aviso parcial, disclaimer
    ├── report.py              # relatório agregado SC-001..SC-006 + FR-014 + disclaimer
    ├── datasets/              # grounding, scope, calc, followup, advice (*.jsonl)
    └── test_*.py              # grounding, scope, calc, followup, latency, advice

data/docs/                     # documentos financeiros de exemplo
docker-compose.yml             # api + db (pgvector/pgvector:pg16) + purge (profile maintenance)
Dockerfile
pyproject.toml
.env.example
```

**Structure Decision**: projeto único no layout `src/`, só com backend e sem frontend. A pasta
`graph/` isola a orquestração, `tools/` guarda uma ferramenta por arquivo (Princípio III) e
`rag/` concentra a ingestão e a busca vetorial. A camada `api/` não guarda estado e só traduz
HTTP ↔ invocação do grafo com `thread_id`.

## Complexity Tracking

Nenhuma violação da constituição. Seção não aplicável.
