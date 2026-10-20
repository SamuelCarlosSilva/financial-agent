# Quickstart: validar a interface web

Roteiro para provar que a feature funciona de ponta a ponta. Os contratos estão em
[contracts/](contracts/) e os estados em [data-model.md](data-model.md).

## Pré-requisitos

- Docker + Docker Compose; Node.js 22 (só para desenvolvimento local do front).
- `.env` na raiz com `OPENAI_API_KEY` e, para testar a autenticação, `API_KEYS=chave-local` e
  `FINAGENT_API_KEY=chave-local`.
- Documentos ingeridos, como no quickstart da feature 001.

## 1. Tudo via compose

```bash
docker compose up --build -d db api web
curl -s http://localhost:8080/api/health          # {"status":"ok","database":"ok"}
curl -si http://localhost:8080/api/docs | head -1  # HTTP/1.1 404
```

Abra http://localhost:8080.

## 2. Desenvolvimento do front

```bash
cd frontend
cp .env.example .env.local      # API_UPSTREAM=http://localhost:8000, FINAGENT_API_KEY=chave-local
npm ci
npm run dev                     # http://localhost:5173, proxy /api → API local
```

## 3. Checagens automáticas (as mesmas do CI)

```bash
cd frontend
npm run lint && npm run format:check && npm run typecheck
npm test                        # Vitest
FINAGENT_API_KEY=ci-sentinel-123 npm run build && { grep -rq "ci-sentinel-123" dist/ && echo "VAZOU" || echo "ok"; }
npx playwright install chromium && npm run e2e   # E2E com API simulada + axe
cd .. && uv run pytest -m "not eval and not integration"   # inclui o teste de `marker`
```

Esperado: tudo verde, e o `grep` não encontra a sentinela.

## 4. Roteiro manual (API real)

| # | Ação | Esperado | Cobre |
|---|---|---|---|
| 1 | Perguntar "O que é come-cotas?" | Indicador "verificando escopo"; resposta com `[n]` clicáveis; cartão de documento por fonte; clicar `[n]` destaca o cartão | US1, FR-004/005 |
| 2 | "Quanto são 500 euros em reais?" | Cartões de cotação (compra destacada, horário de Brasília, vírgula decimal) e de cálculo; passos cotação → cálculo → verificação | US1, US5, FR-006/007 |
| 3 | "Me dá uma receita de bolo" | Aviso de recusa neutro, sem cartões, texto idêntico a `OUT_OF_SCOPE_MESSAGE` | US2 |
| 4 | "Qual o melhor banco?" | Aviso de esclarecimento âmbar | US2 |
| 5 | "Devo comprar dólar agora?" | Resposta + aviso de não recomendação separado abaixo | US2 |
| 6 | Pergunta sem resposta na base | Aviso "não encontrei" | US2 |
| 7 | Recarregar a página e escolher a conversa 1 na lista | Histórico e cartões voltam; nova pergunta continua a conversa | US3, SC-004 |
| 8 | `docker compose stop api` e perguntar | Erro com `request_id` ou mensagem de indisponibilidade + "Tentar de novo"; religar a API e tentar de novo funciona | US4 |
| 9 | Trocar `FINAGENT_API_KEY` por um valor errado e reiniciar `web` | Erro de autorização, sem "Tentar de novo" | US4 |
| 10 | DevTools → Network | Nenhuma requisição com `X-API-Key` nem para domínios externos | FR-015/017, SC-007 |
| 11 | Usar só Tab/Enter/Esc em todo o fluxo; alternar o tema do SO | Foco sempre visível; tudo operável; tema escuro legível | SC-005/006, FR-018/019 |
| 12 | Colar 4.001 caracteres; Enter duplo rápido | Envio bloqueado com o motivo; só um envio | Edge cases |

Registrar o resultado ao lado do roteiro existente em `docs/roteiro-testes-manuais.md`.
