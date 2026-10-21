# Data Model: Interface Web de Conversa do Financial Agent

Os tipos da API são espelhados em `frontend/src/api/types.ts` a partir de
[contracts/client-api.md](contracts/client-api.md). O resto é estado do cliente.

## Entidades vindas da API

### SourceCitation (união discriminada por `type`)

| Tipo | Campos | Exibição |
|---|---|---|
| `document` | `document_id`, `title`, `source`, `page?`, `snippet` (≤300), `score`, **`marker?` (novo)** | título, arquivo · página · relevância, trecho |
| `fx_quote` | `pair` (`AAA-BBB`), `bid`, `ask` (string decimal), `quoted_at` (ISO-8601), `provider` | par, compra em destaque ("valor usado"), venda, data/hora de Brasília, provedor |
| `calculation` | `expression` (≤200), `result` (string decimal) | expressão em mono, resultado sem arredondar |

**Regra**: `marker`, quando presente, é único entre as fontes de documento do turno e
corresponde a um `[marker]` no texto da resposta.

### ChatResponse / ThreadHistory / ApiError

Exatamente como em `specs/001-financial-assistant-api/contracts/openapi.yaml`, mais `marker`.
`ChatMessage` do histórico não traz `scope`: no histórico, `presentTurn` usa só o texto (regras
3–5 de [research §4](research.md#4-classificação-do-turno-aviso-e-variante)), e as mensagens fixas
de recusa e esclarecimento são reconhecidas pelo texto igual às constantes.

## Entidades do cliente

### ThreadIndexEntry (persistida)

`localStorage["finagent.threads.v1"]`: `ThreadIndexEntry[]`, ordenado por `lastActivity` desc.

| Campo | Tipo | Regra |
|---|---|---|
| `id` | string | UUID válido (regex). Inválido → entrada descartada |
| `title` | string | 1–60 caracteres, primeira pergunta cortada com "…" |
| `lastActivity` | string | ISO-8601 da última resposta recebida |

- Máximo de 50 entradas. A mais antiga sai ao inserir a 51ª.
- JSON inválido ou formato desconhecido → índice tratado como vazio, sem lançar erro.
- Atualizada após cada resposta 200 (cria ou atualiza `lastActivity`) e removida após um 404 no
  histórico.

### Turn (memória, por conversa aberta)

| Campo | Tipo | Notas |
|---|---|---|
| `question` | string | texto enviado |
| `askedAt` | Date | |
| `status` | `sending` \| `answered` \| `failed` | |
| `response?` | ChatResponse | quando `answered` |
| `error?` | `{status, error: ApiError}` | quando `failed` |

### TurnPresentation (derivada, pura)

`presentTurn(turn) → { variant: 'answer' | 'refused' | 'clarify' | 'not_found', body: string,
advice?: string, sources: IndexedSource[], steps: ToolStep[], segments: Segment[] }`

- `IndexedSource`: fonte + número exibido no cartão (`marker` para documentos; números seguintes
  para cotação e cálculo).
- `Segment`: `{kind: 'text', text}` \| `{kind: 'cite', n, sourceIndex}`. Um `[n]` sem fonte vira
  `text`.
- `ToolStep`: `{tool, state, detail?}`, como no `index.d.ts` do design system.

## Máquina de estados da conversa (`useConversation`)

```text
            submit(valid)                   200
  idle ───────────────────▶ sending ──────────────────▶ idle (turn answered)
   ▲                           │ 4xx/5xx/rede
   │                           ▼
   └──────── retry (503) ── failed ── submit(nova) ─▶ sending
```

- Em `sending`, `submit` é ignorado (sem duplo envio) e o `Composer` fica em `busy`.
- `retry` só existe para `503`/erro de rede e reenvia a mesma `question` com o mesmo `thread_id`.
- `openThread(id)`: `loading` → `idle` com os turnos reconstruídos do histórico, ou →
  `expired` (404) → nova conversa + aviso.
- `newConversation()`: limpa os turnos e o `thread_id`. O próximo envio vai sem `thread_id`.

## Validação de entrada (antes do envio)

- `message.trim().length ≥ 1` e `message.length ≤ 4000` (mesmos limites de `ChatRequest`).
- Contador de caracteres aparece a partir de 3.600. Acima do limite, o envio fica desabilitado com
  o motivo em texto.
