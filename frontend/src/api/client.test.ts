import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiRequestError, getHealth, getThreadMessages, isRetryable, postChat } from './client';

const THREAD = '6f1c2a9e-3b7d-4c1e-9a55-0d2f8e7c1a23';

function json(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
}

function apiError(status: number, code: string, message: string, request_id?: string) {
  return json(status, { error: { code, message, ...(request_id ? { request_id } : {}) } });
}

async function caught(promise: Promise<unknown>): Promise<ApiRequestError> {
  try {
    await promise;
  } catch (e) {
    expect(e).toBeInstanceOf(ApiRequestError);
    return e as ApiRequestError;
  }
  throw new Error('a chamada deveria ter falhado');
}

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function sentHeaders(): Headers[] {
  return fetchMock.mock.calls.map(([, init]) => new Headers(init?.headers));
}

describe('chamadas bem-sucedidas', () => {
  it('postChat envia JSON para /api/v1/chat', async () => {
    const body = { thread_id: THREAD, answer: 'ok', scope: 'in_scope', sources: [] };
    fetchMock.mockResolvedValue(json(200, body));

    await expect(postChat({ message: 'Oi', thread_id: THREAD })).resolves.toEqual(body);

    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe('/api/v1/chat');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(init?.body as string)).toEqual({ message: 'Oi', thread_id: THREAD });
  });

  it('getThreadMessages chama /api/v1/threads/{id}/messages', async () => {
    fetchMock.mockResolvedValue(json(200, { thread_id: THREAD, messages: [] }));

    await getThreadMessages(THREAD);

    expect(fetchMock.mock.calls[0]![0]).toBe(`/api/v1/threads/${THREAD}/messages`);
  });

  it('getHealth devolve o corpo em 200 e em 503 degraded', async () => {
    fetchMock.mockResolvedValueOnce(json(200, { status: 'ok', database: 'ok' }));
    await expect(getHealth()).resolves.toEqual({ status: 'ok', database: 'ok' });

    fetchMock.mockResolvedValueOnce(json(503, { status: 'degraded', database: 'unavailable' }));
    await expect(getHealth()).resolves.toEqual({ status: 'degraded', database: 'unavailable' });

    expect(fetchMock.mock.calls[0]![0]).toBe('/api/health');
  });
});

describe('tabela "Erros" de contracts/client-api.md', () => {
  it('401 unauthorized', async () => {
    fetchMock.mockResolvedValue(apiError(401, 'unauthorized', 'Chave inválida.', 'req-401'));

    const f = await caught(postChat({ message: 'Oi' }));

    expect(f.status).toBe(401);
    expect(f.error).toEqual({
      code: 'unauthorized',
      message: 'Chave inválida.',
      request_id: 'req-401',
    });
    expect(isRetryable(f)).toBe(false);
  });

  it('422 validation_error mantém a mensagem da API', async () => {
    fetchMock.mockResolvedValue(apiError(422, 'validation_error', 'message: muito longa', 'r'));

    const f = await caught(postChat({ message: 'x' }));

    expect(f.status).toBe(422);
    expect(f.error.code).toBe('validation_error');
    expect(f.error.message).toBe('message: muito longa');
    expect(isRetryable(f)).toBe(false);
  });

  it('404 not_found no histórico', async () => {
    fetchMock.mockResolvedValue(apiError(404, 'not_found', 'Conversa não encontrada.', 'r'));

    const f = await caught(getThreadMessages(THREAD));

    expect(f.status).toBe(404);
    expect(f.error.code).toBe('not_found');
    expect(isRetryable(f)).toBe(false);
  });

  it('503 upstream_unavailable', async () => {
    fetchMock.mockResolvedValue(apiError(503, 'upstream_unavailable', 'LLM fora.', 'req-503'));

    const f = await caught(postChat({ message: 'Oi' }));

    expect(f.status).toBe(503);
    expect(f.error.code).toBe('upstream_unavailable');
    expect(isRetryable(f)).toBe(true);
  });

  it.each([502, 504])('%i do proxy com corpo HTML vira upstream_unavailable', async (status) => {
    fetchMock.mockResolvedValue(
      new Response('<html><body>Bad Gateway</body></html>', {
        status,
        headers: { 'Content-Type': 'text/html' },
      }),
    );

    const f = await caught(postChat({ message: 'Oi' }));

    expect(f.status).toBe(status);
    expect(f.error.code).toBe('upstream_unavailable');
    expect(f.error.message).toBe('O serviço está indisponível no momento.');
    expect(isRetryable(f)).toBe(true);
  });

  it('falha de rede vira status 0 network_error', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

    const f = await caught(postChat({ message: 'Oi' }));

    expect(f.status).toBe(0);
    expect(f.error).toEqual({
      code: 'network_error',
      message: 'Não foi possível falar com o servidor. Verifique a conexão.',
    });
    expect(isRetryable(f)).toBe(true);
  });

  it('usa o X-Request-ID do cabeçalho quando o corpo não traz request_id', async () => {
    fetchMock.mockResolvedValue(
      json(
        503,
        { error: { code: 'upstream_unavailable', message: 'fora' } },
        { 'X-Request-ID': 'hdr-123' },
      ),
    );

    const f = await caught(postChat({ message: 'Oi' }));

    expect(f.error.request_id).toBe('hdr-123');
  });

  it('prefere o request_id do corpo ao do cabeçalho', async () => {
    fetchMock.mockResolvedValue(
      json(
        401,
        { error: { code: 'unauthorized', message: 'x', request_id: 'body-1' } },
        { 'X-Request-ID': 'hdr-1' },
      ),
    );

    const f = await caught(postChat({ message: 'Oi' }));

    expect(f.error.request_id).toBe('body-1');
  });

  it('health fora de 200/503 é falha', async () => {
    fetchMock.mockResolvedValue(new Response('Bad Gateway', { status: 502 }));

    const f = await caught(getHealth());

    expect(f.error.code).toBe('upstream_unavailable');
  });
});

it('nenhuma requisição leva X-API-Key', async () => {
  fetchMock.mockImplementation(() =>
    Promise.resolve(json(200, { thread_id: THREAD, answer: '', scope: 'in_scope', sources: [] })),
  );

  await postChat({ message: 'Oi' });
  await getThreadMessages(THREAD).catch(() => undefined);
  await getHealth().catch(() => undefined);

  expect(fetchMock).toHaveBeenCalledTimes(3);
  for (const headers of sentHeaders()) expect(headers.has('X-API-Key')).toBe(false);
});
