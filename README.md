# Financial Agent

[![CI](https://github.com/SamuelCarlosSilva/financial-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/SamuelCarlosSilva/financial-agent/actions/workflows/ci.yml)

Assistente financeiro conversacional exposto como API REST. Construído com **FastAPI** e
**LangGraph**, responde a perguntas sobre finanças com base em uma base de documentos (RAG com
**pgvector**) e **sempre cita as fontes** usadas. Quando a informação não está nas fontes, ele
diz que não encontrou em vez de inventar.

> **Status:** em desenvolvimento. As cinco histórias estão prontas: busca em documentos (US1),
> guardrail de escopo (US2), cotação de moedas (US3), calculadora (US4) e histórico de conversas
> (US5). Falta o polimento do [roadmap](#roadmap).

## Sumário

- [Status](#status)
- [Arquitetura](#arquitetura)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Como rodar](#como-rodar)
- [Uso da API](#uso-da-api)
- [Configuração](#configuração)
- [Retenção das conversas](#retenção-das-conversas)
- [Base de conhecimento](#base-de-conhecimento)
- [Testes e qualidade](#testes-e-qualidade)
- [Segurança](#segurança)
- [Roadmap](#roadmap)
- [Desenvolvimento](#desenvolvimento)

## Status

| User story | Descrição | Estado |
|---|---|---|
| US1 | Perguntas respondidas com base nos documentos, com fontes citadas | ✅ Pronta |
| US2 | Guardrail de escopo: recusa perguntas fora de finanças e tentativas de *prompt injection* | ✅ Pronta |
| US3 | Cotação de moedas em tempo real (AwesomeAPI) | ✅ Pronta |
| US4 | Calculadora financeira segura (sem `eval`) | ✅ Pronta |
| US5 | Histórico de conversas (`GET /v1/threads/{id}/messages`) e retenção com expurgo | ✅ Pronta |

Especificação completa em [`specs/001-financial-assistant-api/spec.md`](specs/001-financial-assistant-api/spec.md)
e o andamento tarefa a tarefa em [`tasks.md`](specs/001-financial-assistant-api/tasks.md).

## Arquitetura

Cada requisição a `POST /v1/chat` invoca um grafo LangGraph compilado uma única vez na subida da
aplicação:

```mermaid
flowchart LR
    START((START)) --> guardrail
    guardrail -- "in_scope" --> agent
    guardrail -- "out_of_scope" --> refuse
    guardrail -- "ambiguous" --> clarify
    refuse --> END((END))
    clarify --> END
    agent -- "chamou ferramenta" --> tools
    tools --> agent
    agent -- "resposta final" --> collect_sources
    collect_sources --> enforce_grounding
    enforce_grounding --> END
```

- **`guardrail`**: classificador (structured output, `GUARDRAIL_MODEL`) que roda antes de
  qualquer ferramenta. Recebe a mensagem atual e as 2 últimas trocas da conversa, para que
  acompanhamentos como "E o euro?" não sejam recusados, e trata o texto do usuário como dado,
  nunca como instrução. Se o classificador falhar, a mensagem é tratada como fora de escopo.
- **`refuse`** / **`clarify`**: devolvem uma mensagem fixa (recusa padrão ou pedido de
  esclarecimento), sem chamar o LLM nem ferramentas.
- **`agent`**: LLM (`gpt-4o-mini` por padrão) com as ferramentas vinculadas e um *system prompt*
  em pt-BR que exige respostas baseadas só no retorno das ferramentas.
- **`tools`**: executa as ferramentas pedidas pelo agente:
  - `search_financial_documents`: busca por similaridade no pgvector, descartando trechos abaixo
    de `RAG_MIN_SCORE`;
  - `get_currency_quote`: cotação em tempo real na AwesomeAPI (compra, venda e data/hora no
    horário de Brasília), com uma nova tentativa em *timeout* ou erro 5xx. Se o par não existir
    ou o provedor estiver fora, devolve uma mensagem de erro sem nenhum valor, para o agente
    não estimar a cotação;
  - `calculate`: avalia expressões aritméticas (`+ - * / ** %` e parênteses) com `Decimal`,
    percorrendo a AST com uma lista fechada de nós, sem `eval`. O resultado sai com 2 casas
    (`ROUND_HALF_EVEN`), e os limites são 200 caracteres e expoente até 1000. Divisão por zero,
    expressão inválida e valor grande demais voltam como mensagem de erro.
- **`collect_sources`**: extrai as citações (`DocumentSource`, `FxQuoteSource`,
  `CalculationSource`) dos resultados das ferramentas do turno atual.
- **`enforce_grounding`**: trava de fundamentação. Se o agente buscou documentos e terminou sem
  nenhuma fonte citada, a resposta é substituída por
  *"Não encontrei essa informação nas fontes disponíveis."*

**API stateless, estado no `thread_id`.** A aplicação não guarda conversa em memória: o histórico
de cada conversa fica no Postgres, via checkpointer do LangGraph, indexado pelo `thread_id`. Isso
permite reiniciar ou escalar a API sem perder contexto.

Princípios do projeto (detalhados na [constituição](.specify/memory/constitution.md)):

1. Respostas fundamentadas em contexto verificável, com fontes citadas.
2. Guardrail de escopo financeiro.
3. Ferramentas com responsabilidade única.
4. API stateless, com estado no `thread_id`.

**Stack:** Python 3.12, FastAPI, LangGraph, LangChain (OpenAI, Postgres, text splitters),
Postgres 16 + pgvector, psycopg 3, pydantic-settings, structlog, uv, Docker.

## Estrutura do repositório

```text
src/financial_agent/
├── api/           # FastAPI: app, rotas, schemas, erros, autenticação, banco
├── graph/         # LangGraph: estado, prompts, nós (agent, grounding) e builder
├── rag/           # vector store (pgvector) e CLI de ingestão
├── tools/         # ferramentas do agente (busca em documentos, cotação, calculadora)
├── maintenance/   # expurgo das conversas inativas
├── config.py      # configuração tipada via variáveis de ambiente
└── logging.py     # logs estruturados em JSON
tests/
├── unit/          # rápidos, sem rede nem banco
├── contract/      # respostas validadas contra o OpenAPI
├── integration/   # Postgres + pgvector reais via testcontainers
└── eval/          # avaliações com o LLM real e juiz LLM
data/docs/         # documentos de exemplo em pt-BR
specs/             # especificação, plano, contratos e tarefas (spec-kit)
```

## Como rodar

### Pré-requisitos

- Docker e Docker Compose
- Python 3.12 e [uv](https://docs.astral.sh/uv/)
- Uma chave `OPENAI_API_KEY`

### Localmente

```bash
cp .env.example .env                                     # preencha OPENAI_API_KEY
docker compose up -d db                                  # Postgres 16 + pgvector
uv sync
uv run python -m financial_agent.rag.ingest data/docs/   # ingere os documentos de exemplo
uv run uvicorn financial_agent.api.app:app --reload
```

A API sobe em `http://localhost:8000` e a documentação interativa fica em
`http://localhost:8000/docs`.

### Tudo em Docker

```bash
cp .env.example .env
docker compose up --build
```

A ingestão continua sendo feita a partir do host (o banco fica exposto em `localhost:5432`):

```bash
uv run python -m financial_agent.rag.ingest data/docs/
```

## Uso da API

### Saúde

```bash
curl -s localhost:8000/health
# {"status":"ok","database":"ok"}
```

Retorna `503` com `{"status":"degraded","database":"unavailable"}` quando o banco não responde.

### Conversa

```bash
curl -s localhost:8000/v1/chat \
  -H 'content-type: application/json' \
  -d '{"message":"O que é come-cotas?"}'
```

```json
{
  "thread_id": "6f1c2a9e-3b7d-4c1e-9a52-0d8e4f7b1a23",
  "answer": "O come-cotas é a antecipação semestral do imposto de renda ... [1]",
  "scope": "in_scope",
  "sources": [
    {
      "type": "document",
      "document_id": "…",
      "title": "Come-cotas",
      "source": "come-cotas.md",
      "page": null,
      "snippet": "Come-cotas é a antecipação semestral do Imposto de Renda (IR) cobrada sobre o rendimento de ...",
      "score": 0.82
    }
  ]
}
```

Para continuar a mesma conversa, envie o `thread_id` recebido:

```bash
curl -s localhost:8000/v1/chat \
  -H 'content-type: application/json' \
  -d '{"message":"E em quais meses ele é cobrado?","thread_id":"6f1c2a9e-3b7d-4c1e-9a52-0d8e4f7b1a23"}'
```

### Histórico

```bash
curl -s localhost:8000/v1/threads/6f1c2a9e-3b7d-4c1e-9a52-0d8e4f7b1a23/messages
```

```json
{
  "thread_id": "6f1c2a9e-3b7d-4c1e-9a52-0d8e4f7b1a23",
  "messages": [
    {"role": "user", "content": "O que é come-cotas?", "created_at": "2026-10-06T12:00:00.120000+00:00"},
    {"role": "assistant", "content": "O come-cotas é ... [1]", "created_at": "2026-10-06T12:00:03.480000+00:00", "sources": [{"type": "document", "...": "..."}]}
  ]
}
```

Só aparecem as mensagens do usuário e as respostas finais do assistente, em ordem cronológica;
chamadas de ferramenta e mensagens internas ficam de fora.

Com `API_KEYS` definido, inclua o cabeçalho `X-API-Key: <chave>` (o `/health` é isento).

**Erros** seguem o formato `{"error": {"code", "message", "request_id"}}`:

| Status | `code` | Quando |
|---|---|---|
| 401 | `unauthorized` | `X-API-Key` ausente ou inválida |
| 404 | `not_found` | histórico de uma thread que não existe |
| 422 | `validation_error` | `message` vazia ou com mais de 4000 caracteres, `thread_id` que não é UUID, campos extras |
| 503 | `upstream_unavailable` | falha ou *timeout* da OpenAI ou do banco |

O contrato completo está em
[`contracts/openapi.yaml`](specs/001-financial-assistant-api/contracts/openapi.yaml).

## Configuração

Variáveis lidas do ambiente ou do `.env` (veja [`.env.example`](.env.example) e
[`config.py`](src/financial_agent/config.py)):

| Variável | Padrão | Descrição |
|---|---|---|
| `OPENAI_API_KEY` | — | Chave da OpenAI (obrigatória) |
| `LLM_MODEL` | `gpt-4o-mini` | Modelo do agente |
| `GUARDRAIL_MODEL` | `gpt-4o-mini` | Modelo do classificador de escopo |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Modelo de embeddings da busca |
| `LLM_TIMEOUT_SECONDS` | `30` | *Timeout* das chamadas à OpenAI |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/financial_agent` | Postgres com pgvector (checkpoints, metadata das threads e vetores) |
| `RAG_MIN_SCORE` | `0.35` | Relevância mínima (0–1) para um trecho ser usado |
| `RAG_TOP_K` | `4` | Quantidade de trechos buscados por consulta |
| `API_KEYS` | vazio | Chaves aceitas em `X-API-Key`, separadas por vírgula. Vazio desativa a autenticação |
| `LOG_LEVEL` | `INFO` | Nível dos logs |
| `FX_API_BASE_URL` | `https://economia.awesomeapi.com.br` | Provedor das cotações de moedas |
| `FX_TIMEOUT_SECONDS` | `5` | *Timeout* de cada chamada ao provedor de cotações |
| `THREAD_RETENTION_DAYS` | `30` | Dias sem atividade até uma conversa ser expurgada |

## Retenção das conversas

A cada mensagem, a tabela `thread_metadata` registra a última atividade da thread. O expurgo remove
checkpoints e metadata das conversas sem atividade há mais de `THREAD_RETENTION_DAYS` dias:

```bash
docker compose --profile maintenance run --rm purge          # em Docker
uv run python -m financial_agent.maintenance.purge_threads  # local
```

Agende diariamente, por exemplo no cron do host:

```cron
0 3 * * * cd /caminho/do/projeto && docker compose --profile maintenance run --rm purge
```

## Base de conhecimento

A ingestão é offline, por linha de comando:

```bash
uv run python -m financial_agent.rag.ingest <diretório>
```

- Formatos: `.pdf` (um documento por página), `.md` e `.txt`. Em Markdown, o título vem do
  primeiro `# Título`; nos demais, do nome do arquivo.
- Os textos são divididos em trechos de 1000 caracteres com sobreposição de 150.
- Os ids dos trechos são determinísticos (hash de origem, posição e conteúdo), então reingerir o
  mesmo diretório não duplica nada.

Documentos de exemplo em [`data/docs/`](data/docs/): come-cotas, FGC, glossário de renda fixa,
caderneta de poupança e tributação de renda fixa.

## Testes e qualidade

```bash
uv run pytest -m "not eval and not integration"     # unitários e de contrato (sem rede, sem banco)
uv run pytest -m integration                        # Postgres + pgvector reais via testcontainers (requer Docker)
uv run pytest -m eval                               # LLM real: custa tokens, usa o .env

uv run ruff check .
uv run ruff format --check .
uv run mypy                                         # modo strict em src/
```

Um `uv run pytest` sem filtros roda unitários, contrato e integração (requer Docker) e exclui
os testes marcados com `eval`.

**Avaliação de fundamentação** (`tests/eval/test_grounding.py`): roda 48 perguntas pela API real,
26 respondíveis pelos documentos e 22 sem resposta na base, e usa um juiz LLM para verificar
cada afirmação. As metas são:

- ≥ 90% de acerto nas perguntas respondíveis, com a fonte esperada citada;
- ≥ 95% de "não encontrei" nas perguntas sem resposta, sem citar documentos;
- 100% das afirmações sustentadas pelas fontes;
- 100% das respostas em pt-BR.

As afirmações sem sustentação são gravadas em `tests/eval/out/` para diagnóstico.

**Avaliação de escopo** (`tests/eval/test_scope.py`): roda 100 mensagens, sendo 44 fora de
escopo (12 delas tentativas de *prompt injection*), 42 financeiras (8 delas acompanhamentos com
contexto), 6 ambíguas e 8 mistas. As metas são:

- ≥ 95% das mensagens fora de escopo recusadas e ≤ 5% das financeiras recusadas por engano;
- p95 da latência das recusas ≤ 3 s;
- nenhuma mensagem ambígua recusada sem pedir esclarecimento;
- 100% das mistas respondidas na parte financeira, com aviso de que o resto foi ignorado;
- 100% das respostas em pt-BR.

**Avaliação da calculadora** (`tests/eval/test_calc.py`): roda 22 pedidos de cálculo em
linguagem natural (juros simples e compostos, percentuais, parcelas pela Tabela Price e
conversões com a taxa informada na pergunta). A meta é 100% das respostas com o resultado
esperado (aceito como `11268.25`, `11268,25` ou `11.268,25`) e com uma fonte `calculation`.

**CI** ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)): em cada push na `main` e em cada
pull request roda lint e tipos, testes unitários e de contrato, testes de integração e o build da
imagem Docker. A avaliação com o LLM real roda só sob demanda (`workflow_dispatch` com
`run_eval`), usando o secret `OPENAI_API_KEY`.

## Segurança

- **Ative `API_KEYS` em qualquer ambiente que não seja local.** Sem chaves, a API fica aberta.
- O `thread_id` é um identificador, não uma credencial: quem o conhece pode continuar a conversa
  e ler todo o histórico em `GET /v1/threads/{id}/messages`.
- O `.env` nunca deve ser versionado; use o `.env.example` como modelo.
- Os logs são JSON estruturado, com `request_id` por requisição; o conteúdo das mensagens é
  truncado e as chaves nunca são registradas.

## Roadmap

- **Polimento:** relatório consolidado das avaliações, testes de latência e carga, avaliação de
  aviso de "não é recomendação de investimento".

## Desenvolvimento

O projeto segue o fluxo *spec-driven* do [spec-kit](https://github.com/github/spec-kit): a
especificação, o plano técnico, os contratos e as tarefas ficam em
[`specs/001-financial-assistant-api/`](specs/001-financial-assistant-api/), e os princípios em
[`.specify/memory/constitution.md`](.specify/memory/constitution.md). O roteiro de validação
manual de ponta a ponta está em
[`quickstart.md`](specs/001-financial-assistant-api/quickstart.md).
