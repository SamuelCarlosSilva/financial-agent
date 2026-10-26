# Correções pendentes (aplicar ao fim dos testes manuais)

## COR-01: resposta trocada por "Não encontrei" ao reaproveitar o histórico

**Status:** aplicada na branch `fix/agent-forced-tool-call` (falta a verificação manual na API).

**Sintoma.** `chat "O que é come-cotas?"` pelo `/docs` devolve
`Não encontrei essa informação nas fontes disponíveis.` com `sources: []`, mas o log mostra que
o LLM gerou a resposta completa e ela foi trocada (`ungrounded_answer_replaced`). O `chat_turn`
sai com `tools_called: []` e `tokens` zerados.

**Causa (confirmada em 2026-10-17).**

1. O Swagger preenche `thread_id` com o placeholder `3fa85f64-5717-4562-b3fc-2c963f66afa6`.
   Todos os testes feitos pelo `/docs` caíram na mesma thread, que já tem uns 30 turnos no
   Postgres (`GET /v1/threads/3fa85f64…/messages`), com respostas anteriores sobre come-cotas e
   dólar que citam `[1]`.
2. `agent_view` (`graph/nodes/agent.py`) mostra ao agente as respostas finais dos turnos
   anteriores. O modelo copia a resposta do histórico sem chamar ferramenta. Em todos os turnos
   do `api.log` saiu `tools_called: []`; até "Quanto está o dólar?" voltou com R$ 5,0627 [1],
   tirado do histórico.
3. `enforce_grounding` (`graph/nodes/grounding.py`) vê `[n]` sem busca no turno e troca a
   resposta pela mensagem padrão. A trava funcionou como projetada; o defeito é o agente pular
   as ferramentas.
4. Bug secundário: `tokens` sai zerado porque o `AIMessage` que substitui a resposta
   (`grounding.py` e `verify.py`) não leva o `usage_metadata` da resposta original.

**Impacto nos testes.** Casos rodados nessa thread compartilhada podem ter falhado por causa
dela, e não do caso em si: vale repetir RAG-05, RAG-06 e ESC-09 (`docs/reivsao-testes.md`) com
thread nova (sem `thread_id`) antes de abrir bugs separados.

**Correção proposta.**

1. *Retry com ferramenta obrigatória* (`graph/nodes/agent.py`, `make_agent_node`): quando a
   resposta não tem `tool_calls`, nenhuma ferramenta foi chamada no turno (`rounds == 0`) e
   `cited_markers(response.text)` não é vazio, reinvocar uma vez com
   `llm.bind_tools(tools, tool_choice="required")` e devolver essa resposta. O laço
   tools → agent segue normalmente, e `enforce_grounding` continua como rede de segurança.
   Logar `agent_forced_tool_call`. O retry acontece dentro do mesmo nó, então não gasta passo
   do `RECURSION_LIMIT` (`builder.py`).
2. *Preservar o uso de tokens*: em `grounding.py` e `verify.py`, criar o substituto com
   `usage_metadata=final.usage_metadata`.
3. *Swagger sem thread compartilhada* (`api/schemas.py:18`):
   `thread_id: UUID | None = Field(default=None, examples=[None])`, para o `/docs` não mandar o
   placeholder fixo.

**Testes.**

- Unitário (fake LLM, no padrão de `tests/unit/test_document_search.py`): o agente responde com
  `[1]` sem chamar ferramenta → a segunda chamada usa `tool_choice="required"` e a resposta
  final sai com fonte. Uma resposta sem marcador e sem chamada de ferramenta não dispara o
  retry.
- Unitário: o substituto de `enforce_grounding` e de `verify_grounding` mantém o
  `usage_metadata`.
- Schema: o OpenAPI de `ChatRequest` não traz o UUID placeholder.

**Verificação.**

- `uv run pytest` e os evals de follow-up.
- Repetir "O que é come-cotas?" na thread `3fa85f64…` (que tem histórico): esperar
  `search_financial_documents` em `tools_called`, `sources` preenchido e `tokens` > 0. Repetir sem
  `thread_id` para comparar.

## COR-02: `api.log` fora do controle de versão

**Status:** aplicada na branch `fix/agent-forced-tool-call` (`*.log` no `.gitignore`).

O `api.log` (saída do uvicorn usada nos testes manuais) aparece como arquivo não rastreado no
`git status`. Adicionar ao `.gitignore`, de preferência com o padrão `*.log`, para cobrir
outros logs locais.

## COR-03: evals falham com 401 quando `API_KEYS` está definido

**Status:** pendente (encontrada em 2026-10-20, ao rodar o eval da branch `002-api-document-marker`).

**Sintoma.** Com `API_KEYS` preenchido no `.env`, `uv run pytest -m eval` devolve
`401 unauthorized` ("X-API-Key ausente ou inválida.") em todas as perguntas. Os testes de
métrica falham em cascata (acerto 0%, "não encontrei" 0%). No CI não aparece porque lá
`API_KEYS` fica vazio.

**Causa.** Os cinco evals (`test_grounding`, `test_scope`, `test_calc`, `test_advice`,
`test_followup`) criam `TestClient(create_app())` com as configurações reais, mas não mandam
`X-API-Key`.

**Contorno.** `API_KEYS= uv run pytest -m eval …` (a variável de ambiente vazia tem prioridade
sobre o `.env`).

**Correção proposta.** Um helper em `tests/eval/common.py`:

```python
def auth_headers() -> dict[str, str]:
    keys = get_settings().API_KEYS
    return {"X-API-Key": keys[0]} if keys else {}
```

usado nos cinco arquivos como `TestClient(create_app(), headers=auth_headers())`.

## COR-04: eval de fundamentação não mostra por que uma pergunta errou

**Status:** pendente (encontrada em 2026-10-20).

**Sintoma.** `test_answerable_questions_accuracy` deu 88,5% (23/26, meta 90%) e falhou em
"Como funciona a tributação de fundos de renda fixa de curto prazo?", "O que é o CDI?" e
"Quem calcula o IPCA?". Não dá para saber se faltou o fato esperado no texto ou o documento
esperado nas fontes: `grounding_failures.jsonl` só registra afirmações sem sustentação e saiu
vazio.

**Correção proposta.** Gravar também as perguntas reprovadas no acerto (em
`grounding_failures.jsonl` ou num `grounding_misses.jsonl`), com `answer`, `sources`, os
`expected_facts` que faltaram e se o `expected_source` foi citado.

**Pendente junto.** Confirmar que os 88,5% são oscilação do LLM e não regressão: rodar o mesmo
eval na `main` e comparar (o campo `marker` não altera respostas nem o critério de acerto).

## COR-05: trecho do cartão de documento mostra o markdown cru

**Status:** pendente (encontrada em 2026-10-26, roteiro da interface web, item 1).

**Sintoma.** O `excerpt` das fontes `document` vem do chunk do `.md` com os marcadores de título
e de citação (`# Come-cotas > Material educativo … ## O que é`), e o `SourceCard` o mostra como
texto. A leitura fica truncada no meio do cabeçalho do documento em vez de começar no conteúdo.

**Correção proposta.** Limpar o markdown no backend ao montar o `excerpt` (remover `#`, `>` e
quebras de linha de cabeçalho) ou, na ingestão, guardar o texto do chunk sem a sintaxe. Não
reescrever no front: o trecho é a evidência da fonte.

## COR-06: Nginx resolve o nome `api` só ao subir

**Status:** pendente (encontrada em 2026-10-26, roteiro da interface web, item 8).

**Sintoma.** `proxy_pass ${API_UPSTREAM}` com um nome fixo é resolvido uma vez, na partida do
Nginx. Um `docker compose stop/start api` manteve o IP e funcionou, mas se o container da API for
recriado com outro IP (`up --build api`, `--force-recreate`), o `web` passa a responder 502/504
até ser reiniciado.

**Correção proposta.** Usar `resolver 127.0.0.11 valid=10s;` (DNS do Docker) e `proxy_pass` com
variável (`set $upstream ${API_UPSTREAM};`), ajustando o `rewrite` de `/api/v1/` e `/api/health`,
já que `proxy_pass` com variável não troca o prefixo da URI. Alternativa simples: documentar que
o `web` deve ser reiniciado junto com a API.

