# Contrato: proxy `/api` (Nginx em produção, Vite em desenvolvimento)

## Configuração (ambiente do servidor, nunca do navegador)

| Variável | Exemplo | Obrigatória | Notas |
|---|---|---|---|
| `API_UPSTREAM` | `http://api:8000` | sim | Sem barra final |
| `FINAGENT_API_KEY` | (uma das chaves de `API_KEYS`) | não | Vazia → nenhum `X-API-Key` é enviado (API sem autenticação) |

Em dev, as mesmas variáveis ficam em `frontend/.env.local` (no `.gitignore`), **sem** o prefixo
`VITE_`.

## Rotas

| Requisição do navegador | Encaminhada para | Observação |
|---|---|---|
| `GET /api/health` | `GET ${API_UPSTREAM}/health` | sem chave |
| `* /api/v1/<resto>` | `* ${API_UPSTREAM}/v1/<resto>` | com `X-API-Key: ${FINAGENT_API_KEY}` |
| qualquer outro `/api/*` | — | `404` do próprio proxy, corpo `{"error":{"code":"not_found","message":"Rota não encontrada."}}` |
| `GET /assets/*` | arquivos de `dist/assets` | `Cache-Control: public, max-age=31536000, immutable` |
| demais `GET` | `dist/index.html` (fallback de SPA) | `Cache-Control: no-cache` |

## Cabeçalhos

- **Para a API**: `X-API-Key` sempre definido pelo proxy (sobrescreve o do cliente). Repassa
  `X-Request-ID` do cliente, se houver, além de `Host`, `X-Forwarded-For` e `X-Forwarded-Proto`.
- **Para o navegador**: `X-Request-ID` da API é repassado. `X-API-Key` nunca aparece.
- **Segurança** (todas as respostas): CSP `default-src 'self'; img-src 'self' data:; style-src
  'self'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'`,
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`.

## Limites

- `proxy_read_timeout 90s`, `proxy_connect_timeout 5s`, `client_max_body_size 64k`.
- Upstream indisponível → `502`/`504` padrão do Nginx. O front trata como `upstream_unavailable`
  ([client-api.md](client-api.md#erros)).
- Log de acesso no formato padrão (sem cabeçalhos de requisição, portanto sem a chave).

## Garantias verificadas

1. Nenhum arquivo de `dist/` contém o valor de `FINAGENT_API_KEY` (CI, chave-sentinela).
2. Nenhuma requisição feita pelo navegador leva `X-API-Key` (E2E).
3. `curl -i http://localhost:8080/api/docs` → 404 (quickstart).
