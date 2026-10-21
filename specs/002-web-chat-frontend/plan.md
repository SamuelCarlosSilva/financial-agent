# Implementation Plan: Interface Web de Conversa do Financial Agent

**Branch**: `002-web-chat-frontend` | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-web-chat-frontend/spec.md`

## Summary

Uma SPA em **React 18 + TypeScript**, empacotada com **Vite**, em `frontend/` na raiz do
repositório. Ela implementa a tela de conversa do design system "Financial Agent" (Claude Design),
com os componentes portados para TSX e os tokens copiados como CSS. O navegador só fala com a
própria origem em `/api/*`. Um **proxy reverso Nginx**, no mesmo container que serve os arquivos
estáticos, encaminha para a API e injeta o `X-API-Key` lido do ambiente, então a chave nunca chega
ao navegador e não é preciso CORS. Em desenvolvimento, o proxy do Vite faz o mesmo papel. A lista
de conversas fica no `localStorage`. O histórico vem de `GET /v1/threads/{id}/messages`. A
apresentação de cada turno (aviso, cartões de fonte, passos do agente) é uma função pura dos
campos da API.

O backend recebe uma única mudança aditiva: `DocumentSource.marker`, o número `[n]` com que o
trecho foi citado no texto. Sem esse campo, o front não consegue ligar o marcador ao cartão certo
(ver [research.md §3](research.md#3-ligação-marcador-n--cartão-de-fonte)). O front entra no
`docker-compose` como o serviço `web` e no CI com dois jobs (checagens + testes, e E2E com
acessibilidade), além do build da imagem. Os detalhes das decisões estão em [research.md](research.md).

## Technical Context

**Language/Version**: TypeScript 5.x (strict) sobre Node.js 22 LTS. Python 3.12 só para a mudança
aditiva no backend.

**Primary Dependencies**: React 18.3 e React DOM, Vite (+ `@vitejs/plugin-react`), `@fontsource`
(Newsreader, IBM Plex Sans, IBM Plex Mono). Sem biblioteca de estado, de roteamento ou de
componentes: os componentes vêm do design system. Nginx (`nginx-unprivileged`, Alpine) na imagem
de produção.

**Storage**: `localStorage` do navegador, só para o índice de conversas (chave versionada, ver
[data-model.md](data-model.md)). O conteúdo das conversas continua no Postgres da API.

**Testing**: Vitest + Testing Library + jsdom (unidade e componentes), Playwright com respostas
da API simuladas por `page.route` (E2E) e `@axe-core/playwright` (acessibilidade). Backend: pytest
para `marker`.

**Target Platform**: navegadores evergreen (Chrome, Firefox, Safari e Edge nas duas últimas
versões), desktop primeiro e responsivo até 360 px. Container Linux para servir e fazer o proxy.

**Project Type**: aplicação web (SPA + proxy) ao lado da API existente

**Performance Goals**: primeira renderização útil em ≤ 2 s numa conexão local, JS inicial
≤ 200 kB gzip. A latência da resposta é a da API (p95 ≤ 10 s, SC-006 da feature 001).

**Constraints**: chave da API nunca no bundle nem em resposta ao navegador (FR-015, SC-007).
Nenhuma requisição a terceiros, incluindo fontes (FR-017). Timeout do proxy de 90 s. Mensagens de
até 4.000 caracteres. Texto do assistente exibido sem alteração (FR-009). Números formatados sem
arredondar (Princípio I).

**Scale/Scope**: 1 tela (conversa + lista lateral), cerca de 10 componentes do design system,
3 endpoints consumidos e operador único.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Como o design atende | Status |
|---|---|---|
| I. Respostas fundamentadas em contexto verificável | O front não gera nem altera fatos: exibe `answer` como veio (FR-009) e mostra cada item de `sources[]` em um cartão visível. Números de fonte só ganham separadores pt-BR, sem arredondamento, por formatação de string ([research §6](research.md#6-formatação-de-números-e-datas)). O campo aditivo `marker` torna rastreável qual trecho sustenta cada `[n]`. | ✅ PASS |
| II. Guardrail de escopo inegociável | O guardrail continua só no backend. O front não pré-classifica perguntas; apenas apresenta `scope` (`out_of_scope` → recusa, `ambiguous` → esclarecimento) de forma distinta de erro. | ✅ PASS |
| III. Ferramentas com responsabilidade única | Nenhuma ferramenta muda. `marker` é preenchido em `collect_sources`, que já conhece o número de cada trecho. | ✅ PASS |
| IV. API stateless / thread_id | O proxy não guarda estado. O índice local de conversas só guarda `thread_id`, título e data; o conteúdo é sempre relido da API. Qualquer instância de `web` ou `api` atende qualquer requisição. | ✅ PASS |
| Restrições (segredos, logs, dados pessoais) | `FINAGENT_API_KEY` só existe no ambiente do container `web` (ou no `.env.local` do dev, sem prefixo `VITE_`). O CI verifica que uma chave-sentinela não aparece em `dist/`. As fontes são servidas pela própria origem e não há analytics. O log de acesso do Nginx não registra cabeçalhos. | ✅ PASS |
| Quality gates | A mudança em `collect_sources` vem com teste unitário e com uma checagem no eval de fundamentação (todo `[n]` citado tem fonte com `marker == n`). O contrato OpenAPI da feature 001 é atualizado. Guardrail, recuperação e prompts não mudam, então os datasets não mudam. | ✅ PASS |

**Re-check pós-design (Phase 1)**: ✅ PASS. Os contratos [client-api.md](contracts/client-api.md)
e [proxy.md](contracts/proxy.md) não introduzem estado no servidor nem caminho para a chave chegar
ao navegador. Perguntas mistas, que a API não sinaliza, são exibidas como resposta comum,
conforme o FR-008 ajustado e [research §4](research.md#4-classificação-do-turno-aviso-e-variante).

## Project Structure

### Documentation (this feature)

```text
specs/002-web-chat-frontend/
├── plan.md              # Este arquivo
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── client-api.md    # O que o front consome da API (campos, mensagens fixas, `marker`, erros)
│   └── proxy.md         # Rotas /api/*, cabeçalhos, timeouts e erros do proxy
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/financial_agent/              # Backend existente, só a mudança aditiva:
├── graph/state.py                #   DocumentSource.marker: int | None
└── graph/nodes/agent.py          #   collect_sources preenche marker (first + offset)

frontend/                         # NOVO: projeto independente (package.json próprio)
├── package.json  package-lock.json
├── index.html
├── vite.config.ts                # Proxy de dev /api → API_UPSTREAM com X-API-Key do ambiente
├── tsconfig.json  tsconfig.node.json
├── eslint.config.js  .prettierrc.json
├── playwright.config.ts
├── .env.example                  # API_UPSTREAM, FINAGENT_API_KEY (lidos só pelo Vite/Nginx)
├── Dockerfile                    # build Node 22 → nginx-unprivileged
├── .dockerignore
├── nginx/
│   └── default.conf.template     # SPA + proxy /api (envsubst de API_UPSTREAM e FINAGENT_API_KEY)
├── src/
│   ├── main.tsx  App.tsx         # Monta o layout: ThreadSidebar + ChatView
│   ├── design-system/            # Portado do Claude Design, sem lógica de negócio
│   │   ├── tokens.css            #   gerado a partir de tokens.json (claro/escuro)
│   │   ├── fonts.ts              #   @fontsource self-hosted
│   │   ├── icons.tsx
│   │   └── components/           #   Button, ScopeBadge, CitationMarker, MessageBubble,
│   │                             #   SourceCard, ScopeNotice, ToolStatus, ErrorBanner,
│   │                             #   Composer, ThreadList (+ .css de cada um)
│   ├── api/
│   │   ├── types.ts              # Espelho de ChatResponse, ThreadHistory, SourceCitation, Error
│   │   ├── client.ts             # fetch para /api/*, normaliza erros em ApiError
│   │   └── messages.ts           # Mensagens fixas do backend (contrato)
│   ├── features/
│   │   ├── chat/
│   │   │   ├── ChatView.tsx
│   │   │   ├── useConversation.ts   # useReducer: idle → sending → answered | failed
│   │   │   ├── presentTurn.ts       # Função pura: resposta → aviso, cartões, passos
│   │   │   └── citations.tsx        # Divide o texto em trechos e CitationMarker
│   │   └── threads/
│   │       ├── ThreadSidebar.tsx
│   │       └── threadIndex.ts       # Leitura/escrita validada do localStorage
│   └── lib/
│       └── format.ts             # Decimais pt-BR sem arredondar, data/hora de Brasília
└── e2e/
    ├── fixtures/                 # Respostas da API por cenário (in/out/ambiguous/not_found/…)
    └── *.spec.ts                 # Fluxos US1–US5 + axe

docker-compose.yml                # + serviço web (8080) dependente de api
.github/workflows/ci.yml          # + jobs frontend e frontend-e2e; docker-build vira matriz api/web
.gitignore  .dockerignore         # node_modules, dist, relatórios; contexto da API ignora frontend/
.env.example                      # + FINAGENT_API_KEY
```

**Structure Decision**: o front é um projeto irmão em `frontend/`, com toolchain, Dockerfile e
lockfile próprios. O backend continua em `src/` sem reorganização. Testes unitários ficam ao lado
do código (`*.test.ts[x]`) e E2E em `frontend/e2e/`. O design system portado fica isolado em
`src/design-system/` (só apresentação). As regras de apresentação ficam em `features/` como
funções puras e testáveis, para que uma nova versão do design system substitua só a pasta
`design-system/`.

## Complexity Tracking

Sem violações constitucionais. Uma decisão fora do "zero mudança no backend" previsto na spec foi
registrada aqui por transparência:

| Decisão | Por quê | Alternativa mais simples rejeitada porque |
|---|---|---|
| Campo aditivo `DocumentSource.marker` na API | FR-005 exige ligar `[n]` ao cartão. O número no texto é a posição do trecho na busca, não o índice em `sources[]`. | Inferir no front (marcadores citados em ordem ↔ fontes de documento em ordem) depende de um detalhe interno de `collect_sources` e quebraria em silêncio se ele mudar. |
