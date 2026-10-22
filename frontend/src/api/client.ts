import type {
  ApiError,
  ApiFailure,
  ChatRequest,
  ChatResponse,
  Health,
  ThreadHistory,
} from './types';

// O navegador só fala com a própria origem. O X-API-Key é posto pelo proxy, nunca aqui.
const BASE = '/api';

const UPSTREAM_UNAVAILABLE = 'O serviço está indisponível no momento.';

/** Falha lançada pelo cliente: um `Error` com a forma `ApiFailure` do contrato. */
export class ApiRequestError extends Error implements ApiFailure {
  readonly status: number;
  readonly error: ApiError;

  constructor(status: number, error: ApiError) {
    super(error.message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.error = error;
  }
}

function failure(status: number, error: ApiError): ApiRequestError {
  return new ApiRequestError(status, error);
}

/** Só falhas transitórias valem "Tentar de novo": 503, proxy sem upstream e rede. */
export function isRetryable(f: ApiFailure): boolean {
  return f.status === 503 || f.status === 502 || f.status === 504 || f.status === 0;
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return undefined;
  }
}

function errorBody(body: unknown): ApiError | undefined {
  if (typeof body !== 'object' || body === null || !('error' in body)) return undefined;
  const error = body.error;
  if (typeof error !== 'object' || error === null) return undefined;
  const { code, message, request_id } = error as Record<string, unknown>;
  if (typeof code !== 'string') return undefined;
  return {
    code,
    message: typeof message === 'string' ? message : '',
    ...(typeof request_id === 'string' ? { request_id } : {}),
  };
}

function toFailure(response: Response, body: unknown): ApiRequestError {
  const headerId = response.headers.get('X-Request-ID') ?? undefined;
  const fromBody = errorBody(body);
  if (fromBody) {
    const request_id = fromBody.request_id ?? headerId;
    return failure(response.status, { ...fromBody, ...(request_id ? { request_id } : {}) });
  }
  const upstream = response.status === 502 || response.status === 504;
  return failure(response.status, {
    code: upstream ? 'upstream_unavailable' : 'http_error',
    message: upstream
      ? UPSTREAM_UNAVAILABLE
      : `Resposta inesperada do servidor (${response.status}).`,
    ...(headerId ? { request_id: headerId } : {}),
  });
}

async function send(
  path: string,
  init?: RequestInit,
): Promise<{ response: Response; body: unknown }> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, init);
  } catch {
    throw failure(0, {
      code: 'network_error',
      message: 'Não foi possível falar com o servidor. Verifique a conexão.',
    });
  }
  return { response, body: await readJson(response) };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const { response, body } = await send(path, init);
  if (!response.ok) throw toFailure(response, body);
  return body as T;
}

function isHealth(body: unknown): body is Health {
  return typeof body === 'object' && body !== null && 'status' in body;
}

/** 200 (`ok`) e 503 com corpo Health (`degraded`) são respostas; o resto é falha. */
export async function getHealth(): Promise<Health> {
  const { response, body } = await send('/health');
  if ((response.ok || response.status === 503) && isHealth(body)) return body;
  throw toFailure(response, body);
}

export function postChat(payload: ChatRequest): Promise<ChatResponse> {
  return request<ChatResponse>('/v1/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export function getThreadMessages(threadId: string): Promise<ThreadHistory> {
  return request<ThreadHistory>(`/v1/threads/${encodeURIComponent(threadId)}/messages`);
}
