import { expect, type Page, type Request } from '@playwright/test';

/** Resposta simulada: corpo JSON e status (200 por padrão). */
export interface MockResponse {
  status?: number;
  body?: unknown;
  headers?: Record<string, string>;
  /** Segura a resposta por este tempo, para testar o estado de espera. */
  delayMs?: number;
}

/** Uma resposta fixa, uma sequência (uma por chamada, a última se repete) ou uma função. */
export type MockHandler = MockResponse | MockResponse[] | ((request: Request) => MockResponse);

export interface MockHandlers {
  /** GET /api/health. Sem handler: `{status: 'ok', database: 'ok'}`. */
  health?: MockHandler;
  /** POST /api/v1/chat */
  chat?: MockHandler;
  /** GET /api/v1/threads/{id}/messages */
  history?: MockHandler;
}

export interface RecordedRequest {
  method: string;
  path: string;
  body: unknown;
}

const HEALTHY: MockResponse = { body: { status: 'ok', database: 'ok' } };

function pick(handler: MockHandler, request: Request, call: number): MockResponse {
  if (typeof handler === 'function') return handler(request);
  if (Array.isArray(handler)) return handler[Math.min(call, handler.length - 1)] ?? {};
  return handler;
}

function routeOf(path: string, method: string): keyof MockHandlers | undefined {
  if (method === 'GET' && path === '/api/health') return 'health';
  if (method === 'POST' && path === '/api/v1/chat') return 'chat';
  if (method === 'GET' && /^\/api\/v1\/threads\/[^/]+\/messages$/.test(path)) return 'history';
  return undefined;
}

/**
 * Intercepta `/api/**`, responde com os handlers e grava as requisições. Falha o teste se
 * alguma requisição do navegador levar `X-API-Key` (FR-015). Rotas sem handler respondem 404.
 */
export async function mockApi(page: Page, handlers: MockHandlers = {}) {
  const requests: RecordedRequest[] = [];
  const calls: Record<keyof MockHandlers, number> = { health: 0, chat: 0, history: 0 };

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();

    expect(
      Object.keys(await request.allHeaders()).map((h) => h.toLowerCase()),
      `${method} ${pathname} não pode levar X-API-Key`,
    ).not.toContain('x-api-key');

    requests.push({ method, path: pathname, body: request.postDataJSON() as unknown });

    const name = routeOf(pathname, method);
    const handler = name
      ? (handlers[name] ?? (name === 'health' ? HEALTHY : undefined))
      : undefined;
    if (!name || !handler) {
      await route.fulfill({
        status: 404,
        json: { error: { code: 'not_found', message: 'sem mock' } },
      });
      return;
    }

    const response = pick(handler, request, calls[name]++);
    if (response.delayMs) await new Promise((resolve) => setTimeout(resolve, response.delayMs));
    await route.fulfill({
      status: response.status ?? 200,
      json: response.body ?? {},
      ...(response.headers ? { headers: response.headers } : {}),
    });
  });

  return {
    requests,
    /** Requisições feitas a uma rota: `requestsTo('POST', '/api/v1/chat')`. */
    requestsTo: (method: string, path: string | RegExp) =>
      requests.filter(
        (r) =>
          r.method === method && (typeof path === 'string' ? r.path === path : path.test(r.path)),
      ),
  };
}
