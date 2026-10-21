# Contrato: o que o front consome da API

Base: `specs/001-financial-assistant-api/contracts/openapi.yaml`. O navegador chama tudo com o
prefixo `/api` (ver [proxy.md](proxy.md)) e nunca envia `X-API-Key`.

## Endpoints usados

| Uso | Navegador chama | API recebe | Respostas tratadas |
|---|---|---|---|
| Disponibilidade ao abrir (FR-021) | `GET /api/health` | `GET /health` | 200 `ok`; 503 `degraded`; erro de rede |
| Enviar pergunta | `POST /api/v1/chat` `{message, thread_id?}` | `POST /v1/chat` | 200 `ChatResponse`; 401; 422; 503 |
| Abrir conversa | `GET /api/v1/threads/{id}/messages` | idem sem `/api` | 200 `ThreadHistory`; 401; 404; 503 |

## Mudança aditiva na API (feature 002)

`DocumentSource` ganha `marker` (opcional):

```yaml
DocumentSource:
  required: [type, document_id, title, source, snippet, score]   # inalterado
  properties:
    marker:
      type: [integer, 'null']
      minimum: 1
      description: Número [n] com que o trecho foi citado em `answer`/`content`.
```

- Presente em `ChatResponse.sources[]` e em `ThreadHistory.messages[].sources[]`.
- Ausente (`null`) em fontes salvas antes da mudança. O front então não torna o `[n]` clicável.
- `fx_quote` e `calculation` não mudam.

## Mensagens fixas (espelho de `src/financial_agent/graph/prompts.py`)

O front reconhece estas mensagens por igualdade de texto (após `trim`) ou, no caso do aviso, por
`includes` case-insensitive do núcleo. Mudá-las no backend exige mudar
`frontend/src/api/messages.ts`, e os testes de `presentTurn` usam estas mesmas strings.

| Constante | Texto | Variante |
|---|---|---|
| `OUT_OF_SCOPE_MESSAGE` | "Sou um assistente especializado em finanças e só posso ajudar com temas como investimentos, câmbio, produtos e conceitos financeiros e cálculos financeiros. Como posso ajudar nesse assunto?" | `refused` (também quando `scope == out_of_scope`) |
| `CLARIFY_MESSAGE` | "Não ficou claro para mim se sua pergunta é sobre finanças. Pode dar mais detalhes? Posso ajudar com investimentos, câmbio, produtos e conceitos financeiros e cálculos financeiros." | `clarify` (também quando `scope == ambiguous`) |
| `NOT_FOUND_MESSAGE` | "Não encontrei essa informação nas fontes disponíveis." | `not_found` |
| `ADVICE_DISCLAIMER` | "Esta resposta é informativa e não constitui recomendação de investimento." (núcleo: "não constitui recomendação de investimento") | `advice`, separado do corpo |

`scope` existe só em `ChatResponse`. No histórico, as variantes vêm só do texto.

## Erros

Formato da API: `{"error": {"code", "message", "request_id"}}`. O front normaliza qualquer falha
para `{status, error: {code, message, request_id?}}`:

| Situação | `status` | `code` | Texto ao usuário (pt-BR) | "Tentar de novo" |
|---|---|---|---|---|
| API 401 | 401 | `unauthorized` | A interface não está autorizada a falar com o serviço. Avise quem administra. | não |
| API 422 | 422 | `validation_error` | A mensagem não foi aceita: {message} | não |
| API 404 no histórico | 404 | `not_found` | Esta conversa expirou e foi apagada. Abrimos uma nova. | não (abre nova) |
| API 503 | 503 | `upstream_unavailable` | O serviço está indisponível no momento. | sim |
| Proxy sem upstream (502/504, corpo não JSON) | 502/504 | `upstream_unavailable` | idem | sim |
| Falha de rede no navegador | 0 | `network_error` | Não foi possível falar com o servidor. Verifique a conexão. | sim |

O `request_id` vem do corpo ou, na falta dele, do cabeçalho `X-Request-ID`. Sempre aparece em mono
quando existir.
