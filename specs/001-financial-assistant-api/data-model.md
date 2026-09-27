# Data Model: Assistente Financeiro Conversacional via API

**Feature**: `001-financial-assistant-api` | **Date**: 2026-09-27

## 1. Thread (Conversa)

Persistida pelo checkpointer do LangGraph (tabelas `checkpoints`, `checkpoint_blobs` e
`checkpoint_writes`, gerenciadas pela biblioteca) e pela tabela auxiliar `thread_metadata`.

| Campo | Tipo | Regras |
|---|---|---|
| `thread_id` | UUID (string) | PK. Gerado pelo servidor quando ausente (FR-009). Um UUID válido e desconhecido cria uma thread com esse id. Um formato inválido retorna 422 (FR-011). |
| `created_at` | timestamptz | Definido na criação. |
| `last_activity_at` | timestamptz | Atualizado a cada turno. |

**Retenção**: o job `purge-threads` remove as threads com `last_activity_at < now() - 30 days`
(checkpoints + metadata).
**Isolamento**: todo acesso ao histórico é filtrado pelo `thread_id` (FR-010).

## 2. Mensagem

Faz parte do estado do grafo (`messages`). É serializada pelo checkpointer e exposta pela API
como `ChatMessage`.

| Campo | Tipo | Regras |
|---|---|---|
| `role` | enum `user` \| `assistant` | Mensagens `tool` e `system` são internas e não saem na API de histórico. |
| `content` | string | Mensagem do usuário: 1–4000 caracteres, sem ser só espaço em branco (FR-011). |
| `created_at` | datetime | Guardado em `additional_kwargs`/metadados. |
| `sources` | `SourceCitation[]` | Só existe nas mensagens do assistente. |

## 3. GraphState (estado interno do agente)

| Campo | Tipo | Descrição |
|---|---|---|
| `messages` | `list[BaseMessage]` (reducer `add_messages`) | Histórico completo, incluindo tool calls. |
| `scope` | `ScopeDecision \| None` | Decisão do guardrail no turno atual. |
| `turn_sources` | `list[SourceCitation]` (reset a cada turno) | Fontes coletadas dos artefatos das ferramentas no turno. |

## 4. ScopeDecision (Decisão de Escopo)

| Campo | Tipo | Regras |
|---|---|---|
| `label` | enum `in_scope` \| `out_of_scope` \| `ambiguous` | Obrigatório. |
| `reason` | string | Justificativa curta, até 200 caracteres. Vai só para o log. |

**Transições** (roteamento a partir do nó `guardrail`):

```text
START → guardrail ─┬─ in_scope     → agent ⇄ tools → END
                   ├─ out_of_scope → refuse → END   (mensagem padrão, nenhuma ferramenta)
                   └─ ambiguous    → clarify → END  (pede esclarecimento)
```

## 5. SourceCitation (Fonte Citada)

União discriminada por `type`:

| `type` | Campos | Origem |
|---|---|---|
| `document` | `document_id`, `title`, `source`, `page?`, `snippet` (≤ 300 caracteres), `score` | ferramenta `search_financial_documents` |
| `fx_quote` | `pair`, `bid`, `ask`, `quoted_at`, `provider` | ferramenta `get_currency_quote` |
| `calculation` | `expression`, `result` | ferramenta `calculate` |

## 6. FinancialDocument / DocumentChunk

Tabela gerenciada pelo `langchain-postgres` (`langchain_pg_embedding` e
`langchain_pg_collection`), coleção `financial_docs`.

| Campo | Tipo | Regras |
|---|---|---|
| `id` (`chunk_id`) | string | `sha256(source + chunk_index + content)`, o que torna a ingestão idempotente. |
| `document` | text | Trecho de até cerca de 1000 caracteres. |
| `embedding` | vector(1536) | `text-embedding-3-small`. |
| `cmetadata.source` | string | Nome do arquivo de origem. |
| `cmetadata.title` | string | Título do documento (nome do arquivo sem extensão, por padrão). |
| `cmetadata.page` | int? | Página, no caso de PDF. |
| `cmetadata.document_id` | string | `sha256(source)`. |

## 7. CurrencyQuote (Cotação)

Valor em memória. Não é persistido.

| Campo | Tipo | Regras |
|---|---|---|
| `pair` | string `XXX-YYY` | Códigos ISO 4217 em maiúsculas. Regex `^[A-Z]{3}-[A-Z]{3}$`. |
| `bid` / `ask` | Decimal | > 0 |
| `quoted_at` | datetime (America/Sao_Paulo → ISO 8601) | Vem do `create_date` do provedor. |
| `provider` | string | `awesomeapi` |

## 8. Calculation

| Campo | Tipo | Regras |
|---|---|---|
| `expression` | string | ≤ 200 caracteres. Só números, `+ - * / ** %`, parênteses e ponto decimal. |
| `result` | Decimal → string | Arredondado para 2 casas na exibição. |
| erros | `division_by_zero`, `invalid_expression`, `too_large` | Voltam como mensagem da ferramenta, não como exceção. |
