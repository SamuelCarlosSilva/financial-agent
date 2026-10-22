// Espelho de specs/001-financial-assistant-api/contracts/openapi.yaml + contracts/client-api.md.
// Valores decimais (bid, ask, result) chegam como string e nunca viram Number.

export interface DocumentSource {
  type: 'document';
  document_id: string;
  title: string;
  source: string;
  page: number | null;
  snippet: string;
  score: number;
  /** Número [n] com que o trecho foi citado. Ausente em fontes salvas antes do campo. */
  marker?: number | null;
}

export interface FxQuoteSource {
  type: 'fx_quote';
  pair: string;
  bid: string;
  ask: string;
  quoted_at: string;
  provider: string;
}

export interface CalculationSource {
  type: 'calculation';
  expression: string;
  result: string;
}

export type SourceCitation = DocumentSource | FxQuoteSource | CalculationSource;

export type Scope = 'in_scope' | 'out_of_scope' | 'ambiguous';

export interface ChatRequest {
  message: string;
  thread_id?: string;
}

export interface ChatResponse {
  thread_id: string;
  answer: string;
  scope: Scope;
  sources: SourceCitation[];
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  created_at?: string | null;
  sources?: SourceCitation[] | null;
}

export interface ThreadHistory {
  thread_id: string;
  messages: ChatMessage[];
}

export interface Health {
  status: 'ok' | 'degraded';
  database: 'ok' | 'unavailable';
}

export interface ApiError {
  code: string;
  message: string;
  request_id?: string;
}

/** Qualquer falha de chamada, normalizada pelo cliente. `status` 0 = falha de rede. */
export interface ApiFailure {
  status: number;
  error: ApiError;
}
