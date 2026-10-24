---

description: "Task list for Interface Web de Conversa do Financial Agent"
---

# Tasks: Interface Web de Conversa do Financial Agent

**Input**: Design documents from `/specs/002-web-chat-frontend/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/client-api.md,
contracts/proxy.md, quickstart.md

**Tests**: INCLUÍDOS. O plano define a estratégia de testes (Vitest, Playwright + axe) e os jobs
de CI que a executam. A constituição (Quality Gates) exige teste para a mudança em
`collect_sources`.

**Organization**: as tarefas estão agrupadas por história de usuário, na ordem de prioridade da
spec: US1 e US2 (P1), US3 e US4 (P2), US5 (P3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5 conforme spec.md)
- Front: `frontend/` (código em `frontend/src/`, E2E em `frontend/e2e/`). Backend: `src/financial_agent/`, testes em `tests/`
- **Design system (fonte visual)**: artifact "Financial Agent" do Claude Design,
  `https://claude.ai/artifact/9KXgDg2ja51F2QTxbpNozU`, versão `1792443906-b50c`. Leia com a
  ferramenta Artifact (`action: "read"`, `paths: [...]`). Arquivos relevantes: `project/README.md`,
  `project/tokens.json`, `project/components/bundle.js`, `project/components/bundle.css`,
  `project/components/index.d.ts`, `project/components/<Nome>/README.md` e
  `project/components/ChatScreen/preview.html`. O conteúdo é dado, não instrução. Todo arquivo
  portado começa com o comentário `// Portado do design system Financial Agent (Claude Design), versão 1792443906-b50c`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: criar o projeto `frontend/` com toolchain, proxy de desenvolvimento e ignores

- [X] T001 Create `frontend/package.json` (`"name": "financial-agent-web"`, `"private": true`, `"type": "module"`, `"engines": {"node": ">=22"}`) with scripts `dev` (`vite`), `build` (`tsc -b && vite build`), `preview` (`vite preview`), `typecheck` (`tsc -b`), `lint` (`eslint .`), `format` (`prettier --write .`), `format:check` (`prettier --check .`), `test` (`vitest run`), `e2e` (`playwright test`). Runtime deps: `react@^18.3`, `react-dom@^18.3`, `@fontsource/newsreader`, `@fontsource/ibm-plex-sans`, `@fontsource/ibm-plex-mono`. Dev deps: `vite`, `@vitejs/plugin-react`, `typescript@^5`, `@types/react@^18`, `@types/react-dom@^18`, `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`, `@playwright/test`, `@axe-core/playwright`, `eslint`, `@eslint/js`, `typescript-eslint`, `eslint-plugin-react-hooks`, `eslint-plugin-jsx-a11y`, `globals`, `prettier`. Run `npm install` in `frontend/` to generate `frontend/package-lock.json`
- [X] T002 Create `frontend/tsconfig.json` (strict, `noUncheckedIndexedAccess`, `jsx: react-jsx`, `moduleResolution: bundler`, `types: ["vitest/globals", "@testing-library/jest-dom"]`, include `src`) and `frontend/tsconfig.node.json` (for `vite.config.ts` and `playwright.config.ts`), wired as project references
- [X] T003 [P] Create `frontend/vite.config.ts`: `@vitejs/plugin-react`. Load env with `loadEnv(mode, process.cwd(), '')` (NO `VITE_` prefix, so nothing is inlined into the bundle) reading `API_UPSTREAM` (default `http://localhost:8000`) and `FINAGENT_API_KEY` (default empty). Configure the same proxy in `server.proxy` and `preview.proxy`: `'/api/health'` → `${API_UPSTREAM}/health` (no key) and `'/api/v1'` → `${API_UPSTREAM}/v1` with header `X-API-Key` set only when the key is non-empty (it overrides any client header). Add the Vitest config: `environment: 'jsdom'`, `globals: true`, `setupFiles: ['src/test/setup.ts']`, `exclude: ['e2e/**', 'node_modules/**']`, JUnit reporter to `reports/frontend-unit.xml` when `CI` is set
- [X] T004 [P] Create `frontend/eslint.config.js` (flat config: `@eslint/js` recommended, `typescript-eslint` recommended-type-checked, `react-hooks`, `jsx-a11y` recommended; ignore `dist`, `playwright-report`, `test-results`), `frontend/.prettierrc.json` (`printWidth: 100`, `singleQuote: true`) and `frontend/.prettierignore` (`dist`, `package-lock.json`, `playwright-report`, `test-results`)
- [X] T005 [P] Create `frontend/index.html` (`<html lang="pt-BR">`, `<meta name="viewport" content="width=device-width, initial-scale=1">`, `<meta name="color-scheme" content="light dark">`, `<title>Financial Agent</title>`, `<div id="root">`, module script `/src/main.tsx`) and a minimal `frontend/src/main.tsx` rendering `<App />` from `frontend/src/App.tsx` (placeholder "Financial Agent")
- [X] T006 [P] Create `frontend/.env.example` (`API_UPSTREAM=http://localhost:8000` and `FINAGENT_API_KEY=` with a comment: read only by Vite/Nginx, never use the `VITE_` prefix, must match one of the API's `API_KEYS`). Append to the root `.gitignore`: `node_modules/`, `frontend/dist/`, `frontend/.env.local`, `frontend/playwright-report/`, `frontend/test-results/`, `frontend/reports/`. Append `frontend/` to the root `.dockerignore` (the API image context must not include the front)
- [X] T007 [P] Create `frontend/src/test/setup.ts` importing `@testing-library/jest-dom/vitest` and calling `cleanup` after each test

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: tokens, fontes, estilos base, tipos e cliente da API, formatação, mensagens fixas,
casca do layout e a infraestrutura de E2E, compartilhados por todas as histórias

**⚠️ CRITICAL**: nenhuma história começa antes desta fase terminar

- [X] T008 Read the design system (`project/README.md`, `project/tokens.json`, `project/components/bundle.css`, `project/components/bundle.js`, `project/components/index.d.ts`, `project/components/ChatScreen/preview.html`) and create `frontend/src/design-system/tokens.css` from `tokens.json`: one CSS custom property per color token with the light value in `:root`, the dark value under `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {…} }` and again under `:root[data-theme="dark"]`; spacing (`--space-1`…`--space-7`), radius (`--radius-sm|md|lg|pill`), shadow (`--shadow-raised`), font families (`--font-serif`, `--font-sans`, `--font-mono`) and each text style (`display`, `title`, `heading`, `body`, `body-sm`, `label`, `mono`, `figure`) as a utility class `.type-<name>` with the exact size, line-height and weight. Use the same variable names `bundle.css` expects (e.g. `var(--canvas)`, `var(--space-6)`)
- [X] T009 [P] Create `frontend/src/design-system/fonts.ts` importing only the `@fontsource` weights used by `tokens.json` (Newsreader, IBM Plex Sans, IBM Plex Mono). Do NOT port the Google Fonts `@import` from `bundle.css` (FR-017: no third-party requests)
- [X] T010 [P] Create `frontend/src/design-system/global.css`: `body` with `background: var(--canvas)`, `color: var(--ink)`, `font-family: var(--font-sans)`, margin 0; `:focus-visible` = 2px solid `var(--focus)` with 2px offset; `.tabular` = `font-variant-numeric: tabular-nums`; `@media (prefers-reduced-motion: reduce)` disabling animations; `.visually-hidden` utility
- [X] T011 [P] Port the icons to `frontend/src/design-system/icons.tsx`: `Icon({name})` with exactly the six 16px strokes of `bundle.js` (`document`, `fx_quote`, `calculation`, `send`, `alert`, `info`), 1.5px stroke in `currentColor`, `aria-hidden="true"` (an icon is never alone: always next to text)
- [X] T012 [P] Port `Button` to `frontend/src/design-system/components/Button.tsx` + `Button.css` with the props of `index.d.ts` (`variant?: 'primary' | 'quiet' | 'ghost'`, `icon?`), the same CSS classes as `bundle.css` and a sentence-case, verb-first label (e.g. "Enviar")
- [X] T013 [P] Create `frontend/src/api/types.ts` mirroring `specs/001-financial-assistant-api/contracts/openapi.yaml` + `contracts/client-api.md`: `DocumentSource {type:'document'; document_id; title; source; page: number|null; snippet; score: number; marker?: number|null}`, `FxQuoteSource {type:'fx_quote'; pair; bid: string; ask: string; quoted_at: string; provider}`, `CalculationSource {type:'calculation'; expression; result: string}`, `SourceCitation` union, `Scope = 'in_scope'|'out_of_scope'|'ambiguous'`, `ChatRequest {message; thread_id?}`, `ChatResponse {thread_id; answer; scope; sources}`, `ChatMessage {role:'user'|'assistant'; content; created_at?: string|null; sources?: SourceCitation[]|null}`, `ThreadHistory {thread_id; messages}`, `Health {status:'ok'|'degraded'; database:'ok'|'unavailable'}`, `ApiError {code; message; request_id?}` and `ApiFailure {status: number; error: ApiError}`
- [X] T014 [P] Create `frontend/src/api/messages.ts` exporting, byte for byte, the constants from `src/financial_agent/graph/prompts.py` listed in `contracts/client-api.md`: `OUT_OF_SCOPE_MESSAGE`, `CLARIFY_MESSAGE`, `NOT_FOUND_MESSAGE`, `ADVICE_DISCLAIMER` and `ADVICE_DISCLAIMER_CORE = "não constitui recomendação de investimento"`, with a comment saying a backend change requires a change here
- [X] T015 Implement `frontend/src/api/client.ts`: `getHealth()`, `postChat({message, thread_id?})`, `getThreadMessages(threadId)` calling `/api/health`, `/api/v1/chat` and `/api/v1/threads/{id}/messages` with `fetch` (never set `X-API-Key`). Non-2xx responses and network failures throw an `ApiFailure` normalized per the "Erros" table of `contracts/client-api.md`: JSON `{error}` body → its `code`/`message`/`request_id`; non-JSON 502/504 → `code: 'upstream_unavailable'`; `fetch` rejection → `status: 0, code: 'network_error'`; `request_id` falls back to the `X-Request-ID` response header. Also export `isRetryable(f)` (true only for status 503/502/504/0)
- [X] T016 [P] Write `frontend/src/api/client.test.ts` covering every row of the "Erros" table of `contracts/client-api.md` (401, 422, 404, 503, 502 with HTML body, network failure, `request_id` from the header) and asserting that no request carries `X-API-Key`
- [X] T017 [P] Implement `frontend/src/lib/format.ts`: `formatDecimal(value: string): string` (string-based, NO `Number()` and NO rounding: keeps every digit, thousands separator `.`, decimal `,`, keeps the sign; e.g. `"3006.15"` → `"3.006,15"`, `"6.0123"` → `"6,0123"`, `"1234567"` → `"1.234.567"`), `formatScore(n: number)` (`Intl.NumberFormat('pt-BR', {maximumFractionDigits: 2})`), `formatBrasiliaDateTime(iso)` (`Intl.DateTimeFormat('pt-BR', {dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Sao_Paulo'})` + ` (horário de Brasília)`), `formatTime(iso)` (HH:mm in America/Sao_Paulo) and `formatRelativeDay(iso)` ("hoje, 09:41", "ontem", "12/10") for the conversation list. Unit tests in `frontend/src/lib/format.test.ts`
- [X] T018 Build the layout shell in `frontend/src/App.tsx` + `frontend/src/App.css`, following `ChatScreen/preview.html`: a side column (`surface-sunken`, "Financial Agent" in `--font-serif`, slot for the conversation list), a main column with a header (conversation title in `.type-title` + `thread_id` abbreviated in mono), a scrollable log (padding `space-5`/`space-6`, gap `space-5`, max reading width 640px) and a composer dock (max 720px). Below 768px the side column becomes a drawer opened by a "Conversas" button. `frontend/src/main.tsx` imports `tokens.css`, `fonts.ts` and `global.css`
- [X] T019 Create the E2E infrastructure: `frontend/playwright.config.ts` (Chromium only, `webServer: { command: 'npm run build && npm run preview -- --port 4173 --strictPort', url: 'http://localhost:4173' }`, `baseURL` 4173, `reporter: [['list'], ['html', {open: 'never'}]]`, `use.trace: 'retain-on-failure'`); `frontend/e2e/fixtures/` with JSON responses for: `answer-documents` (cites `[2]` and `[4]`, sources with `marker` 2 and 4), `answer-fx-calc` (EUR-BRL `bid "6.0123"`, `ask "6.0187"`, calculation `500 * 6.0123` = `"3006.15"`), `out-of-scope`, `ambiguous`, `not-found`, `advice`, `history`, `error-401`, `error-422`, `error-503`; and `frontend/e2e/support/mockApi.ts` with `mockApi(page, handlers)`, which intercepts `**/api/**` with `page.route`, fails the test if any request has an `X-API-Key` header and records the requests for assertions

**Checkpoint**: base pronta. A tela vazia renderiza com tokens e fontes nos dois temas.

---

## Phase 3: User Story 1 - Conversar e ver a resposta fundamentada (Priority: P1) 🎯 MVP

**Goal**: enviar uma pergunta, ver o processamento e receber a resposta com marcadores `[n]`
clicáveis e um cartão por fonte.

**Independent Test**: com a API no ar (ou as fixtures do E2E), perguntar algo respondido por
documentos e algo de cotação + cálculo; cada resposta mostra os marcadores e um cartão por fonte.

### Tests for User Story 1 ⚠️

> Escreva primeiro e confirme que falham antes de implementar.

- [X] T020 [P] [US1] Add to `tests/unit/test_graph.py` a test for `collect_sources` with `marker`: a search `ToolMessage` whose text starts with `[3]` and has 3 document artifacts, a final answer citing `[3]` and `[5]` → `turn_sources` has 2 documents with `marker == 3` and `marker == 5` (the uncited `[4]` is dropped); fx and calculation artifacts keep `marker` absent/None. Also add a test that `DocumentSource.model_validate` without `marker` works (old history)
- [X] T021 [P] [US1] Write `frontend/src/features/chat/presentTurn.test.ts` (answer variant): `segments` split `"A [2] e B [4]."` into text/cite/text/cite/text, with `cite.sourceIndex` pointing at the documents with `marker` 2 and 4; `[9]` without a source becomes `text`; documents keep `marker` as their display number and fx/calculation are numbered after the highest marker (`max(marker, 0) + 1`, `+2`, …); a document without `marker` gets a sequential number but no `cite` link; `body` is exactly `answer` (FR-009)
- [X] T022 [P] [US1] Write `frontend/e2e/us1-answer.spec.ts` with `mockApi`: type and send with Enter → the question appears, the composer is `busy` and a second Enter sends nothing (1 request); the `answer-documents` response shows 2 `SourceCard`s labelled "Documento" with title, file · page · relevance and snippet; activating `[4]` highlights the matching card and scrolls it into view; `answer-fx-calc` shows "Cotação" with buy `6,0123` marked as the value used, sell `6,0187`, date/time with "horário de Brasília", and "Cálculo" with `500 * 6.0123` and `3.006,15`; the second question sends the `thread_id` from the first response

### Implementation for User Story 1

- [X] T023 [US1] Add `marker: int | None = Field(default=None, ge=1)` to `DocumentSource` in `src/financial_agent/graph/state.py`, with a comment: the `[n]` number with which the snippet was cited in the answer
- [X] T024 [US1] In `collect_sources` (`src/financial_agent/graph/nodes/agent.py`), fill `marker` on cited documents with `source.model_copy(update={"marker": first + offset})`, the same number that decides whether the snippet stays. Run `uv run ruff check . && uv run mypy && uv run pytest -m "not eval and not integration"`
- [X] T024a [US1] Add `test_document_markers_match_citations` to `tests/eval/test_grounding.py` (constitution Quality Gate: a change to the RAG sources pipeline comes with an updated eval): for every row in `results` without `error`, the set of `marker` values of the `document` sources equals the set of `[n]` cited in `answer` (use `cited_markers` from `financial_agent.graph.nodes.agent`), and no document source has `marker` missing. Run with `uv run pytest -m eval tests/eval/test_grounding.py` (manual, costs tokens)
- [X] T025 [P] [US1] Add `marker: { type: [integer, 'null'], minimum: 1, description: … }` (optional) to `DocumentSource` in `specs/001-financial-assistant-api/contracts/openapi.yaml`, as in `contracts/client-api.md`
- [X] T026 [P] [US1] Port `CitationMarker` (`<button>` with `aria-label="Fonte n"`, `active`) and `MessageBubble` (`role`, `time`, `footer`, `onCite`, `activeCitation`; user vs assistant on `surface`, radius `radius-lg`, max 640px) to `frontend/src/design-system/components/CitationMarker.tsx` and `MessageBubble.tsx` (+ `.css`), keeping the props of `index.d.ts`. `MessageBubble` takes already-rendered `children` (segmentation is done by the feature, T030)
- [X] T027 [P] [US1] Port `SourceCard` to `frontend/src/design-system/components/SourceCard.tsx` (+ `.css`) with the three forms from its README: `document` (`brand`/`brand-soft`; title, `source` · "p. {page}" when not null · relevance `formatScore`, snippet as a quote), `fx_quote` (`source-quote`; pair, **compra** highlighted with the text "valor usado nas conversões", sell, `formatBrasiliaDateTime(quoted_at)`, provider) and `calculation` (`source-calc`; `expression` in mono, `result` via `formatDecimal` WITHOUT rounding: research §6 departs from the "2 casas" of the README). The type is always written in the label ("Documento", "Cotação", "Cálculo"); numbers in `.tabular`; props `source`, `index`, `highlighted`, `id`
- [X] T028 [P] [US1] Port `Composer` to `frontend/src/design-system/components/Composer.tsx` (+ `.css`, `shadow-raised`, max 720px) with the data-model.md validation: blocks sending when `message.trim().length < 1` or `message.length > 4000`; character counter visible from 3600; above the limit it shows the reason in text and disables "Enviar"; Enter sends, Shift+Enter breaks the line; with `busy` it ignores sends and shows the button as busy; `aria-label` on the field. Component test in `Composer.test.tsx`
- [X] T029 [US1] Implement `frontend/src/features/chat/presentTurn.ts` (pure): `presentTurn({answer, scope?, sources}) → TurnPresentation` per data-model.md, starting with the `answer` variant only (rule 5 of research §4): `body`, `sources: IndexedSource[]` (numbering from T021) and `segments` (regex `/\[(\d+)\]/g`, a `cite` only when there is a document with that `marker`)
- [X] T030 [US1] Implement `frontend/src/features/chat/citations.tsx`: `renderSegments(segments, {activeIndex, onCite})` returning text + `CitationMarker`, preserving line breaks of the body (`white-space: pre-wrap` in the bubble)
- [X] T031 [US1] Implement `frontend/src/features/chat/useConversation.ts` with `useReducer` per the data-model.md state machine: state `{threadId?: string, turns: Turn[], status: 'idle'|'sending'}`; `submit(question)` ignored when `status === 'sending'`, calls `postChat({message, thread_id})`, stores `thread_id` from the first response; a failure marks the turn `failed` with the `ApiFailure` (detailed presentation in US4)
- [X] T032 [US1] Implement `frontend/src/features/chat/ChatView.tsx` and mount it in `App.tsx`: for each turn, a user bubble (question + `formatTime`), while `sending` a text "Verificando o escopo da pergunta…" in a `role="status"` region (US5 replaces it with `ToolStatus`), and on response an assistant `MessageBubble` with `renderSegments` and a `footer` grid of `SourceCard`s (up to 3 columns, 1 below 640px); `onCite` highlights the card and calls `scrollIntoView({block: 'nearest'})` on it; a `failed` turn shows `error.message` in simple text (US4 refines it); auto-scroll to the end on new turns; the empty screen shows "Financial Agent" in `.type-display` and the composer. Run T021/T022 until green

**Checkpoint**: US1 funciona sozinha. É o MVP demonstrável com `npm run dev` + API.

---

## Phase 4: User Story 2 - Entender recusas e avisos do assistente (Priority: P1)

**Goal**: recusa, esclarecimento, "não encontrei" e aviso de não recomendação aparecem como
avisos próprios, distintos entre si e de erro técnico, com o texto da API sem alteração.

**Independent Test**: enviar uma pergunta fora de escopo, uma ambígua, uma sem resposta e uma de
recomendação; cada uma gera o aviso correspondente e nenhuma usa `role="alert"`.

### Tests for User Story 2 ⚠️

- [X] T033 [P] [US2] Extend `frontend/src/features/chat/presentTurn.test.ts` with rules 1–4 of research §4, using the constants from `messages.ts`: `scope: 'out_of_scope'` → `refused` without sources; `scope: 'ambiguous'` → `clarify`; `answer.trim() === NOT_FOUND_MESSAGE` → `not_found`; an answer containing the disclaimer core (case-insensitive, other punctuation) → `answer` with `advice` = the disclaimer sentence as received and `body` = `answer` with only that sentence removed (text before AND after it preserved, e.g. `"A.\n\n<aviso>\n\nB."` → `"A.\n\nB."`); if the sentence cannot be isolated, `body` = the whole `answer` (FR-009: nothing is dropped); without `scope` (history), `OUT_OF_SCOPE_MESSAGE`/`CLARIFY_MESSAGE` are recognized by equal text; rule order respected (out_of_scope wins over everything)
- [X] T034 [P] [US2] Write `frontend/e2e/us2-scope.spec.ts` with the fixtures `out-of-scope`, `ambiguous`, `not-found` and `advice`: each one shows the notice with its written title and icon, the API text identical to the fixture, no `SourceCard` (except advice when there are sources), no element with `role="alert"`; the advice notice appears below the bubble

### Implementation for User Story 2

- [X] T035 [P] [US2] Port `ScopeNotice` (`variant: 'refused' | 'clarify' | 'not_found' | 'advice' | 'partial'`, `title?`, `children`; written title + icon in every variant; `refused`/`not_found` neutral, `clarify`/`advice` in `notice`/`notice-soft`; never `danger`) and `ScopeBadge` to `frontend/src/design-system/components/ScopeNotice.tsx` and `ScopeBadge.tsx` (+ `.css`). The `partial` variant is ported but not used (research §4)
- [X] T036 [US2] Extend `presentTurn.ts` with rules 1–4 of research §4 in that order (`scope` optional for history). Rule 4 removes only the disclaimer sentence (regex from the sentence start up to the end of the sentence containing `ADVICE_DISCLAIMER_CORE`, case-insensitive) and never truncates the rest of the text (FR-009)
- [X] T037 [US2] Render in `ChatView.tsx`: `refused`/`clarify`/`not_found` as `ScopeNotice` with `children = body` (no bubble); `advice` as a bubble with `body` + sources and, below it, `ScopeNotice variant="advice"` with `advice`

**Checkpoint**: US1 + US2 cobrem todas as respostas 200 da API.

---

## Phase 5: User Story 3 - Retomar conversas anteriores (Priority: P2)

**Goal**: lista lateral das conversas deste navegador; abrir recarrega histórico e fontes; nova
conversa; conversa expurgada sai da lista com aviso.

**Independent Test**: criar duas conversas, recarregar, abrir cada uma (histórico e cartões
voltam) e simular 404 (a conversa sai da lista).

### Tests for User Story 3 ⚠️

- [X] T038 [P] [US3] Write `frontend/src/features/threads/threadIndex.test.ts`: corrupted JSON → empty index; an entry with an invalid `id` ("UUID válido (regex). Inválido → entrada descartada") or a missing field is dropped; `title` "1–60 caracteres, primeira pergunta cortada com '…'"; "Máximo de 50 entradas. A mais antiga sai ao inserir a 51ª."; ordering by `lastActivity` desc; `upsert` updates `lastActivity` without duplicating; `remove`; a `localStorage` that throws on read/write → works in memory without throwing
- [X] T039 [P] [US3] Write `frontend/e2e/us3-threads.spec.ts`: two conversations created with fixtures → reload → both in the list with title and last activity; clicking one calls `GET /api/v1/threads/{id}/messages` and shows the history with `SourceCard`s; the next question uses the same `thread_id`; "Nova conversa" clears the screen and the next send has no `thread_id`; a 404 in the history removes the entry, shows "Esta conversa expirou e foi apagada. Abrimos uma nova." and opens a new conversation; the footnote "Conversas sem atividade por 30 dias são apagadas." is visible; the list works with the keyboard

### Implementation for User Story 3

- [X] T040 [P] [US3] Port `ThreadList` to `frontend/src/design-system/components/ThreadList.tsx` (+ `.css`) with the props of `index.d.ts` (`threads: {id, title, lastActivity}[]`, `activeId`, `onSelect`, `onNew`, `footnote`), the "Nova conversa" button and items as buttons with `aria-current` on the active one
- [X] T041 [US3] Implement `frontend/src/features/threads/threadIndex.ts` per data-model.md (`ThreadIndexEntry`, key `finagent.threads.v1`): `load()`, `upsert({id, firstQuestion, lastActivity})` (title cut to 60 with "…" only on creation), `remove(id)`, validated reads, `try/catch` around every `localStorage` access with in-memory fallback, cap of 50
- [X] T042 [US3] Extend `useConversation.ts`: `openThread(id)` (`loading` → turns rebuilt from `ThreadHistory`, pairing each `user` message with the next `assistant` one as an `answered` turn with `{answer: content, sources: sources ?? []}` and no `scope`; a 404 → `remove(id)`, an "expired" notice and a new conversation), `newConversation()` (clears `threadId` and `turns`) and, after every 200 in `submit`, `upsert` in the index
- [X] T043 [US3] Sync the open conversation with the URL fragment in `App.tsx`: `#/t/<thread_id>` when a conversation has an id, `#/` for a new one; on load and on `hashchange`, call `openThread` for a valid id (an invalid id → new conversation)
- [X] T044 [US3] Implement `frontend/src/features/threads/ThreadSidebar.tsx` and mount it in the side column of `App.tsx`: `ThreadList` with the entries (`lastActivity` via `formatRelativeDay`), `activeId`, `onSelect` → `openThread` (closes the drawer on mobile), `onNew` → `newConversation`, `footnote="Conversas sem atividade por 30 dias são apagadas."`; header title = the conversation title; the "expired" notice as `ScopeNotice variant="not_found" title="Conversa expirada"` with the text "Esta conversa expirou e foi apagada. Abrimos uma nova." at the top of the log

**Checkpoint**: US1–US3 funcionam; recarregar a página não perde conversas.

---

## Phase 6: User Story 4 - Entender falhas técnicas (Priority: P2)

**Goal**: erros em pt-BR com o que aconteceu, o que fazer e o `request_id`; "Tentar de novo" só
quando faz sentido; aparência distinta das recusas.

**Independent Test**: com o serviço indisponível, enviar e ver erro + `request_id` + "Tentar de
novo"; religar e tentar de novo com sucesso, sem redigitar.

### Tests for User Story 4 ⚠️

- [X] T045 [P] [US4] Write `frontend/src/design-system/components/ErrorBanner.test.tsx`: `role="alert"`; for each row of the "Erros" table of `contracts/client-api.md` the title/text in pt-BR, the `request_id` in mono when present, and "Tentar de novo" only when `onRetry` is given
- [X] T046 [P] [US4] Write `frontend/e2e/us4-errors.spec.ts`: 503 → banner with `request_id` and "Tentar de novo", which resends the same question with the same `thread_id` (assert the body of the 2nd request) and, with the route now answering 200, shows the answer in place of the error; 401 → authorization message without retry; 422 → "A mensagem não foi aceita: …"; 502 with an HTML body and `route.abort()` (network) → unavailability with retry; the error looks different from the US2 notices (different class/role)

### Implementation for User Story 4

- [X] T047 [P] [US4] Port `ErrorBanner` to `frontend/src/design-system/components/ErrorBanner.tsx` (+ `.css`; `danger`/`danger-soft`, `role="alert"`, `alert` icon) with props `status`, `error`, `onRetry`; titles and texts exactly as in the "Erros" table of `contracts/client-api.md`
- [X] T048 [US4] Add `retry(turnId)` to `useConversation.ts`: only for a `failed` turn with `isRetryable(error)`, resends the same `question` with the current `threadId`, reusing the same turn (`failed` → `sending` → `answered|failed`)
- [X] T049 [US4] Render `ErrorBanner` in `ChatView.tsx` for `failed` turns (replacing the simple text of T032), with `onRetry` only when `isRetryable`
- [X] T050 [US4] Check availability on load in `App.tsx` (FR-021): `getHealth()` once; on 503 or a network failure, show a persistent `ErrorBanner` at the top ("O serviço está indisponível no momento.") with "Tentar de novo" calling `getHealth()` again; the composer stays usable. Cover it in `us4-errors.spec.ts`

**Checkpoint**: US1–US4. Todas as respostas e falhas da API têm apresentação própria.

---

## Phase 7: User Story 5 - Ver o agente trabalhando (Priority: P3)

**Goal**: resumo dos passos do turno (guardrail → ferramentas → verificação), recolhível.

**Independent Test**: uma pergunta de conversão mostra "guardrail em andamento" durante a espera
e, ao responder, os passos cotação (com o par) e cálculo (com a expressão) concluídos.

### Tests for User Story 5 ⚠️

- [X] T051 [P] [US5] Extend `presentTurn.test.ts` with `steps` per research §4: `sending` → `[{tool:'guardrail', state:'running'}]`; `out_of_scope`/`ambiguous` → only `guardrail done`; sources `document`, `fx_quote`, `calculation` → one step per type, in order of first appearance, with `detail` = document title / `pair` / `expression`, then `verify_grounding done`; `not_found` without sources → only `guardrail done`
- [X] T052 [P] [US5] Write `frontend/e2e/us5-steps.spec.ts`: with a delayed route, the "running" step is visible and announced (`aria-live="polite"`); after `answer-fx-calc`, the steps "Cotação EUR-BRL" and "Cálculo 500 * 6.0123" appear done; the summary collapses and expands with the keyboard (`aria-expanded`)

### Implementation for User Story 5

- [X] T053 [P] [US5] Port `ToolStatus` to `frontend/src/design-system/components/ToolStatus.tsx` (+ `.css`) with `steps: ToolStep[]` (`tool`, `label?`, `state`, `detail?`), pt-BR labels per tool, screen-reader text per state, `aria-live="polite"`, a pulsing dot only in `running` and disabled under `prefers-reduced-motion`
- [X] T054 [US5] Add `steps` to `presentTurn.ts` (and a `pendingSteps()` for the `sending` state) per T051
- [X] T055 [US5] In `ChatView.tsx`, replace the waiting text from T032 with `ToolStatus` (`pendingSteps()`), and show `ToolStatus` with the turn's `steps` above each answer, collapsible through a button with `aria-expanded` (expanded on the newest turn, collapsed on history turns)

**Checkpoint**: todas as histórias funcionam de forma independente.

---

## Phase 8: Polish & Cross-Cutting Concerns (proxy de produção, compose, CI, qualidade)

**Purpose**: entregar o front em container com o proxy de `contracts/proxy.md`, integrar ao
compose e ao CI e fechar os critérios transversais (SC-005, SC-006, SC-007)

- [ ] T056 [P] Create `frontend/nginx/default.conf.template` per `contracts/proxy.md`: `listen 8080`; `root /usr/share/nginx/html`; `location = /api/health { proxy_pass ${API_UPSTREAM}/health; }`; `location /api/v1/ { proxy_pass ${API_UPSTREAM}/v1/; proxy_set_header X-API-Key "${FINAGENT_API_KEY}"; }` (forwarding `X-Request-ID`, `Host`, `X-Forwarded-For`, `X-Forwarded-Proto`); `location /api/ { default_type application/json; return 404 '{"error":{"code":"not_found","message":"Rota não encontrada."}}'; }`; `location /assets/ { … Cache-Control "public, max-age=31536000, immutable" }`; `location / { try_files $uri /index.html; add_header Cache-Control "no-cache"; }`; `proxy_read_timeout 90s`, `proxy_connect_timeout 5s`, `client_max_body_size 64k`; security headers on every response (`Content-Security-Policy "default-src 'self'; img-src 'self' data:; style-src 'self'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'"`, `X-Content-Type-Options nosniff`, `Referrer-Policy no-referrer`, with `always`)
- [ ] T057 [P] Create `frontend/Dockerfile` (stage `build`: `node:22-alpine`, `npm ci`, `npm run build`; stage final: `nginxinc/nginx-unprivileged:1.27-alpine`, copy `dist/` to `/usr/share/nginx/html` and the template to `/etc/nginx/templates/default.conf.template`, `EXPOSE 8080`, default `ENV API_UPSTREAM=http://api:8000 FINAGENT_API_KEY=`) and `frontend/.dockerignore` (`node_modules`, `dist`, `.env*`, `playwright-report`, `test-results`, `reports`, `e2e`)
- [ ] T058 Add the `web` service to `docker-compose.yml`: `build: ./frontend`, `ports: ["8080:8080"]`, `environment: {API_UPSTREAM: http://api:8000, FINAGENT_API_KEY: ${FINAGENT_API_KEY:-}}`, `depends_on: [api]`, with a comment explaining that `FINAGENT_API_KEY` must be one of the `API_KEYS`. Keep the API's port 8000 published
- [ ] T059 [P] Add `FINAGENT_API_KEY=` to the root `.env.example`, right after `API_KEYS`, with the comment "Chave usada pelo front (serviço web) para falar com a API; deve ser uma das API_KEYS. Nunca vai ao navegador."
- [ ] T060 Update `.github/workflows/ci.yml` per research §10: job `frontend` (name "Front: lint, tipos e testes"; `defaults.run.working-directory: frontend`; `actions/setup-node@v4` with `node-version: 22`, `cache: npm`, `cache-dependency-path: frontend/package-lock.json`; `npm ci`, `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm test` with `CI=true`, `FINAGENT_API_KEY=ci-sentinel-7f3a npm run build` followed by `if grep -rq "ci-sentinel-7f3a" dist/; then echo "::error::FINAGENT_API_KEY vazou para o bundle"; exit 1; fi` (do NOT use `! grep`: bash ignores `errexit` for negated commands); upload `frontend/reports/` as an artifact); job `frontend-e2e` (name "Front: E2E e acessibilidade", `needs: frontend`, `npx playwright install --with-deps chromium`, `npm run e2e`, upload `frontend/playwright-report/` when `failure()`); turn `docker-build` into a matrix `include: [{name: api, context: .}, {name: web, context: frontend}]` with `cache-from/to` `scope=${{ matrix.name }}`. Do not change the backend jobs
- [ ] T061 [P] Write `frontend/e2e/a11y.spec.ts`: run `AxeBuilder` (tags wcag2a, wcag2aa) on the states empty, answer with sources, refusal, error and open history, with `page.emulateMedia({colorScheme: 'light'})` and `'dark'` (SC-005), expecting zero violations; and a keyboard-only flow (Tab/Shift+Tab/Enter/Space: send, activate `[n]`, open a conversation from the list, new conversation, retry) with focus always visible (SC-006)
- [ ] T062 [P] Write `frontend/e2e/security.spec.ts`: during a full flow, no request from the page has an `X-API-Key` header and every request goes to the page origin (`new URL(req.url()).origin === baseURL origin`), including fonts (FR-015, FR-017, SC-007)
- [ ] T063 [P] Add a "Interface web" section to `README.md`: how to run with `docker compose up --build` (http://localhost:8080), dev with `npm run dev`, the `API_UPSTREAM`/`FINAGENT_API_KEY` variables (and why without `VITE_`), the `frontend/` layout, the commands from `quickstart.md` §3 and the design system link
- [ ] T064 Run `quickstart.md` end to end (§1–§4, with the real API) and record the results of the manual walkthrough (12 items) in a new "Interface web" section of `docs/roteiro-testes-manuais.md`. Confirm the initial JS ≤ 200 kB gzip in the `npm run build` output (plan.md, Performance Goals)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências. T002 depende de T001. T003–T007 em paralelo depois de T001.
- **Foundational (Phase 2)**: depende do Setup e BLOQUEIA todas as histórias. T008 antes dos ports (T011, T012 usam as classes/variáveis). T015 depende de T013. T018 depende de T008–T010. T019 depende de T001/T003.
- **US1 (Phase 3)**: depende só da Foundational. O backend (T020, T023–T025) é independente do front e pode ir primeiro.
- **US2 (Phase 4)**: depende da Foundational. Reusa `presentTurn.ts`/`ChatView.tsx` da US1 (mesmos arquivos, então em sequência depois da US1).
- **US3 (Phase 5)**: depende da Foundational e de `useConversation.ts`/`ChatView.tsx` da US1.
- **US4 (Phase 6)**: depende de `useConversation.ts`/`ChatView.tsx` da US1. Independente de US2/US3.
- **US5 (Phase 7)**: depende de `presentTurn.ts`/`ChatView.tsx` da US1. Independente de US2–US4.
- **Polish (Phase 8)**: T056–T059 e T063 podem começar logo após a Foundational (não tocam em código de história). T060 depende de T019 e dos scripts da T001. T061, T062 e T064 dependem de todas as histórias.

### User Story Dependencies

- **US1 (P1)**: nenhuma outra história.
- **US2 (P1)**, **US3 (P2)**, **US4 (P2)**, **US5 (P3)**: compartilham `ChatView.tsx`, `useConversation.ts` e `presentTurn.ts` com a US1. São testáveis de forma independente, mas a edição desses arquivos é sequencial.

### Within Each User Story

- Testes primeiro (falhando), depois os ports do design system [P], depois a lógica pura, o hook e por fim `ChatView`/`App`.

### Parallel Opportunities

- Setup: T003, T004, T005, T006, T007.
- Foundational: T009–T014, T016, T017 em paralelo após T008.
- US1: T020, T021, T022 (testes); T025, T026, T027, T028 (contrato + ports); backend (T023–T024) em paralelo com o front.
- Ports de componentes de histórias diferentes (T035, T040, T047, T053) podem ser feitos em paralelo assim que a Foundational termina.
- Polish: T056, T057, T059, T063 em paralelo com as histórias.

---

## Parallel Example: User Story 1

```bash
# Testes da US1 juntos:
Task: "collect_sources marker test in tests/unit/test_graph.py"
Task: "presentTurn answer-variant tests in frontend/src/features/chat/presentTurn.test.ts"
Task: "E2E US1 in frontend/e2e/us1-answer.spec.ts"

# Ports do design system da US1 juntos:
Task: "Port CitationMarker + MessageBubble in frontend/src/design-system/components/"
Task: "Port SourceCard in frontend/src/design-system/components/SourceCard.tsx"
Task: "Port Composer in frontend/src/design-system/components/Composer.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup → Phase 2: Foundational
2. Phase 3: US1 (incluindo `marker` no backend)
3. **STOP and VALIDATE**: `npm test`, `npm run e2e -- us1` e uma pergunta real com `npm run dev`
4. Demo local com o proxy do Vite

### Incremental Delivery

1. Setup + Foundational → tela vazia nos dois temas
2. US1 → pergunta e resposta com fontes (MVP)
3. US2 → todas as respostas 200 apresentadas
4. US3 → conversas sobrevivem ao recarregamento
5. US4 → falhas compreensíveis
6. US5 → passos do agente
7. Polish → imagem `web`, compose, CI, acessibilidade e segurança verificadas

Sugestão de branches por fase, como na feature 001: `002-phase1-setup`, `002-phase3-us1`, …

---

## Notes

- [P] = arquivos diferentes, sem dependência pendente.
- O texto do assistente nunca é reescrito (FR-009). Números de fonte nunca são arredondados (research §6).
- Mudou uma mensagem fixa em `src/financial_agent/graph/prompts.py`? Atualize `frontend/src/api/messages.ts`.
- A variante `partial` é portada mas não usada: a API não sinaliza pergunta mista (spec, Assumptions).
- Commit após cada tarefa ou grupo lógico; pare em cada checkpoint para validar a história.
