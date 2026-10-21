# Research: Interface Web de Conversa do Financial Agent

Decisões da Phase 0. Todas as incógnitas do Technical Context estão resolvidas.

## 1. Framework e build

- **Decision**: SPA com React 18.3 + TypeScript strict, empacotada com Vite. Sem roteador: há uma
  única tela e a conversa ativa vai no fragmento da URL (`#/t/<thread_id>`) para sobreviver ao
  recarregamento. Estado com `useReducer` e hooks, sem biblioteca de estado ou de cache de dados.
- **Rationale**: o design system foi escrito para React 18 (`index.d.ts` usa `React.ReactElement`
  e a preview carrega React 18). Uma SPA estática é servida por qualquer servidor HTTP e combina
  com o proxy da §2. São 3 endpoints e 1 tela, então TanStack Query, Redux ou um roteador não se
  pagam.
- **Alternatives considered**: **Next.js**: traria rotas de servidor para o proxy, mas exige um
  runtime Node em produção, SSR que nenhuma tela precisa e mais superfície para errar onde a chave
  vive. **React 19**: funcionaria, mas o design system foi validado em 18; a atualização fica
  trivial depois. **Usar `bundle.js` do design system como script global**: sem tipos, sem
  tree-shaking e acoplado ao `window.FinAgent`; rejeitado em favor do port (§5).

## 2. Proxy e acesso à API (FR-015, SC-007)

- **Decision**: o navegador chama só a própria origem em `/api/*`.
  - **Produção (container `web`)**: Nginx serve `dist/` e faz o proxy de `/api/v1/*` → `${API_UPSTREAM}/v1/*`
    e `/api/health` → `${API_UPSTREAM}/health`, com `proxy_set_header X-API-Key "${FINAGENT_API_KEY}"`.
    Os valores entram pelo `envsubst` nativo da imagem oficial (`/etc/nginx/templates/*.template`),
    que só substitui variáveis definidas no ambiente e preserva as variáveis do Nginx (`$uri` etc.).
  - **Desenvolvimento**: `server.proxy` do Vite com a mesma reescrita, lendo `API_UPSTREAM` e
    `FINAGENT_API_KEY` via `loadEnv(mode, cwd, '')`. Sem o prefixo `VITE_`, as variáveis nunca são
    embutidas no bundle.
  - Qualquer outro caminho sob `/api/` responde 404 no próprio proxy (não expõe `/docs` nem
    `/openapi.json`). O cabeçalho `X-API-Key` vindo do cliente é sempre sobrescrito.
  - Timeout de leitura de 90 s (LLM 30 s + ferramentas + verificação, com folga).
  - Detalhes em [contracts/proxy.md](contracts/proxy.md).
- **Rationale**: mesma origem dispensa CORS e não exige nenhuma mudança na API. A chave fica só no
  ambiente do servidor. Um container a menos que um BFF dedicado, e o mesmo Nginx que já serviria
  os estáticos.
- **Alternatives considered**: **BFF em Node/Express**: mais código e mais um runtime para o
  mesmo resultado. **CORS na API + chave digitada pelo usuário**: rejeitado pelo usuário na spec.
  **Rotas de proxy dentro do FastAPI**: misturaria a API pública com a origem do front e o
  Princípio IV não ganharia nada.
- **Verificação**: o job de CI builda com `FINAGENT_API_KEY=ci-sentinel-...` e falha se a
  sentinela aparecer em `dist/`. O E2E confere que nenhuma requisição do navegador leva
  `X-API-Key`.

## 3. Ligação marcador `[n]` ↔ cartão de fonte

- **Finding**: o prompt manda citar trechos como `[n]`, onde `n` é a posição do trecho no
  resultado da busca (`_header(index, …)` em `tools/document_search.py`, com `first` contínuo entre
  buscas do turno). `collect_sources` mantém só os trechos citados, em ordem, **sem** guardar o
  número. Exemplo: busca com 4 trechos, resposta cita `[2]` e `[4]` e `sources` tem 2 documentos.
  O front não tem como saber que o primeiro é o `[2]`. Cotação e cálculo não recebem marcador no
  texto (o prompt pede par/data e expressão por extenso).
- **Decision**: campo aditivo `marker: int | None = None` em `DocumentSource`, preenchido em
  `collect_sources` com `first + offset`, o mesmo número que decide se o trecho entra. O front
  liga `[n]` à fonte de documento com `marker == n`. Um `[n]` sem fonte correspondente (histórico
  antigo sem `marker`) é renderizado como texto simples, não como botão. Cotação e cálculo
  aparecem só como cartões, numerados depois dos documentos.
- **Rationale**: compatível com clientes atuais (campo opcional) e com o histórico já salvo no
  checkpointer (o default `None` valida). Não depende de inferência no front.
- **Alternatives considered**: inferir por ordem no front (frágil, ver Complexity Tracking do
  plano); renumerar o texto no backend (altera a resposta do LLM, pior para auditoria).

## 4. Classificação do turno (aviso e variante)

Função pura `presentTurn(response)` com regras em ordem:

| Regra | Sinal na API | Apresentação |
|---|---|---|
| 1 | `scope == "out_of_scope"` | `ScopeNotice refused` com `answer`, sem fontes |
| 2 | `scope == "ambiguous"` | `ScopeNotice clarify` com `answer` |
| 3 | `answer.trim() == NOT_FOUND_MESSAGE` | `ScopeNotice not_found` |
| 4 | `answer` contém o núcleo do aviso (case-insensitive) | `MessageBubble` com `answer` sem a frase do aviso (texto antes **e depois** preservados, quebras de linha extras colapsadas) + `ScopeNotice advice` com a frase como veio. Se a frase não puder ser isolada (não termina em ponto), `body` = `answer` inteiro e o `ScopeNotice` aparece mesmo assim |
| 5 | demais | `MessageBubble` + `SourceCard` por fonte |

- As mensagens fixas ficam em `frontend/src/api/messages.ts`, copiadas de
  `graph/prompts.py` e listadas em [contracts/client-api.md](contracts/client-api.md).
- **Desvio da spec, variante `partial` (FR-008)**: a API não sinaliza pergunta mista. O guardrail
  a classifica como `in_scope` e o próprio LLM escreve o aviso no meio da resposta, com redação
  livre. Detectar por texto seria adivinhação, então a resposta aparece como resposta comum (o
  aviso escrito pelo LLM continua visível no texto). Para ter o aviso dedicado é preciso um sinal
  explícito na API (ex.: `partial: true` vindo do guardrail). Isso fica proposto como evolução
  futura, fora desta feature. O FR-008 da spec foi ajustado para refletir isso.
- **Passos do agente (US5)**: durante a espera, `[guardrail: running]`. Ao responder: `guardrail
  done`; se o escopo não é `in_scope`, para aí. Senão, um passo por tipo de fonte, na ordem em que
  aparece pela primeira vez (`document` → `search_financial_documents` com o título;
  `fx_quote` → `get_currency_quote` com o par; `calculation` → `calculate` com a expressão) e,
  havendo fontes, `verify_grounding done`. Em `not_found` sem fontes não há como saber se houve
  busca, então só aparece o guardrail.

## 5. Port do design system

- **Decision**: a fonte de verdade é o artifact "Financial Agent" do Claude Design (versão
  `1792443906-b50c`). Os 10 componentes de `components/bundle.js`/`bundle.css` são portados para
  TSX em `frontend/src/design-system/components/`, mantendo nomes, props de `index.d.ts` e classes
  CSS. `tokens.json` vira `tokens.css` com variáveis em `:root` (claro) e
  `@media (prefers-color-scheme: dark)` (escuro). Cada arquivo portado leva um comentário com a
  versão de origem. A `ChatScreen` é a referência de layout de `App.tsx`.
- **Rationale**: tipos, tree-shaking e testes de componente. A troca de versão do design system
  fica localizada numa pasta.
- **Alternatives considered**: publicar o design system como pacote npm (overhead para um único
  consumidor); carregar `bundle.js` em runtime (§1).

## 6. Formatação de números e datas

- **Decision**: `bid`, `ask` e `result` chegam como string decimal (o pydantic serializa `Decimal`
  como string) e são formatados **por string**: separador de milhar `.` e decimal `,`, todos os
  dígitos preservados, sem arredondar e sem passar por `Number`. `score` (float, só exibição) usa
  `Intl.NumberFormat('pt-BR', {maximumFractionDigits: 2})`. Datas usam `Intl.DateTimeFormat('pt-BR',
  {timeZone: 'America/Sao_Paulo'})` com o sufixo "horário de Brasília". Algarismos tabulares via
  `font-variant-numeric: tabular-nums` (token `figure`).
- **Rationale**: Princípio I, o número exibido é exatamente o da ferramenta. Converter para float
  poderia alterar casas.
- **Note**: o README do componente `SourceCard` sugere o resultado "com 2 casas". O plano
  prefere fidelidade ao valor e não arredonda. Fica como ajuste a refletir no design system.

## 7. Estado local e conversas

- **Decision**: índice em `localStorage["finagent.threads.v1"]`, um array de
  `{id, title, lastActivity}` validado na leitura (entrada inválida descartada, sem quebrar a tela).
  Título = primeira pergunta cortada em 60 caracteres. Uma conversa entra no índice só depois da
  primeira resposta bem-sucedida (é quando existe `thread_id`). Se o `localStorage` lançar erro, a
  lista fica só em memória durante a sessão. Um 404 em `GET /threads/{id}/messages` remove a
  entrada e abre uma conversa nova com aviso. Até 50 entradas: as mais antigas saem (a API expurga
  em 30 dias de qualquer forma).
- **Alternatives considered**: endpoint de listagem na API (fora do escopo e exigiria um conceito
  de usuário); IndexedDB (desnecessário para algumas dezenas de registros).

## 8. Testes

- **Decision**:
  - **Vitest + Testing Library + jsdom**: `presentTurn`, `citations`, `format`, `threadIndex`,
    `client` (mapeamento de erros) e componentes do design system (rótulos em texto, `aria-*`).
  - **Playwright** (Chromium no CI) contra `vite preview`, com a API simulada por `page.route` e
    fixtures por cenário. Cobre US1–US5, os edge cases de validação e duplo envio e o teclado
    (SC-006).
  - **`@axe-core/playwright`** em cada estado (vazio, resposta, recusa, erro), nos temas claro e
    escuro (SC-005).
  - **Backend**: teste unitário de `collect_sources` com `marker`, e teste de contrato garantindo
    que o campo é opcional.
- **Rationale**: o E2E não depende de LLM, de banco nem de chaves, então é rápido e determinístico
  no CI. A integração real com a API é coberta pelo roteiro manual do [quickstart](quickstart.md).
- **Alternatives considered**: MSW (duplicaria o que `page.route` já faz no E2E); E2E contra a
  API real no CI (custo de tokens e não determinismo; já existe o job `eval` manual para isso).

## 9. docker-compose

- **Decision**: novo serviço `web` com `build: ./frontend`, porta `8080:8080`,
  `API_UPSTREAM=http://api:8000`, `FINAGENT_API_KEY=${FINAGENT_API_KEY:-}` (interpolado do `.env`
  da raiz) e `depends_on: api`. A porta 8000 da API continua publicada para uso direto e para os
  testes manuais existentes. Se `API_KEYS` estiver definido, `FINAGENT_API_KEY` deve ser uma das
  chaves (documentado no `.env.example`).
- **Rationale**: `docker compose up` sobe banco, API e front de uma vez, sem mudar o fluxo atual.

## 10. CI

- **Decision** (no `.github/workflows/ci.yml` existente):
  - **job `frontend`** (Lint, tipos e testes do front): `actions/setup-node@v4` (Node 22, cache npm
    com `frontend/package-lock.json`), `npm ci`, `lint`, `format:check`, `typecheck`, `test` (JUnit
    em `reports/`), `build` com chave-sentinela + verificação de que ela não está em `dist/`.
  - **job `frontend-e2e`** (`needs: frontend`): instala o Chromium do Playwright, roda o E2E e o
    axe e publica `playwright-report/` como artifact em caso de falha.
  - **job `docker-build`** vira matriz `{api: ., web: frontend}` com `scope` de cache GHA separado.
  - Os jobs de backend não mudam. O campo `marker` é coberto pelo `test` atual.
- **Rationale**: segue o padrão atual (um job por preocupação, sem push de imagem). O
  `concurrency` já existente cancela execuções antigas.
- **Alternatives considered**: filtro de caminhos (`paths-filter`) para pular jobs. Hoje o custo
  é baixo e o filtro esconderia quebras de contrato entre front e API; reavaliar se o CI ficar
  lento.

## 11. Fontes e terceiros (FR-017)

- **Decision**: fontes via `@fontsource/*` empacotadas pelo Vite (nada do Google Fonts em
  runtime, ao contrário do `@import` do `bundle.css` original). O Nginx envia uma CSP
  `default-src 'self'; img-src 'self' data:; style-src 'self'; font-src 'self'; connect-src 'self';
  frame-ancestors 'none'`, além de `X-Content-Type-Options: nosniff` e `Referrer-Policy: no-referrer`.
- **Rationale**: nenhuma requisição sai para terceiros, e a CSP impede regressões.
