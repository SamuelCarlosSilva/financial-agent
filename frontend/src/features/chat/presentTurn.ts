// Apresentação de um turno como função pura dos campos da API (research §4, data-model.md).
import type { Scope, SourceCitation } from '../../api/types';

/** Fonte com o número exibido no cartão. */
export interface IndexedSource {
  source: SourceCitation;
  index: number;
}

/** Trecho do corpo: texto ou um `[n]` ligado à fonte `sources[sourceIndex]`. */
export type Segment =
  { kind: 'text'; text: string } | { kind: 'cite'; n: number; sourceIndex: number };

export interface ToolStep {
  tool:
    | 'guardrail'
    | 'search_financial_documents'
    | 'get_currency_quote'
    | 'calculate'
    | 'verify_grounding';
  state: 'running' | 'done' | 'error';
  detail?: string;
}

export interface TurnPresentation {
  variant: 'answer' | 'refused' | 'clarify' | 'not_found';
  /** Texto exibido na bolha: o `answer` como veio (FR-009). */
  body: string;
  /** Frase do aviso de recomendação, quando houver (US2). */
  advice?: string;
  sources: IndexedSource[];
  steps: ToolStep[];
  segments: Segment[];
}

export interface TurnInput {
  answer: string;
  /** Só existe em ChatResponse; no histórico a variante vem do texto. */
  scope?: Scope;
  sources?: SourceCitation[] | null;
}

const CITATION = /\[(\d+)\]/g;

/**
 * Documentos com `marker` usam o próprio número. As demais fontes (cotação, cálculo e documento
 * sem `marker`, de histórico antigo) são numeradas depois do maior marker, na ordem da API.
 */
export function indexSources(sources: SourceCitation[]): IndexedSource[] {
  let next = Math.max(0, ...sources.map((s) => (s.type === 'document' ? (s.marker ?? 0) : 0)));
  return sources.map((source) => {
    const marker = source.type === 'document' ? source.marker : null;
    return { source, index: marker ?? ++next };
  });
}

/** Divide o texto em trechos; um `[n]` só vira marcador se há documento com `marker == n`. */
export function segmentBody(body: string, sources: SourceCitation[]): Segment[] {
  const byMarker = new Map<number, number>();
  sources.forEach((s, i) => {
    if (s.type === 'document' && s.marker != null) byMarker.set(s.marker, i);
  });

  const segments: Segment[] = [];
  let text = '';
  let last = 0;
  for (const match of body.matchAll(CITATION)) {
    const n = Number(match[1]);
    const sourceIndex = byMarker.get(n);
    if (sourceIndex === undefined) continue;
    text += body.slice(last, match.index);
    if (text) segments.push({ kind: 'text', text });
    segments.push({ kind: 'cite', n, sourceIndex });
    text = '';
    last = match.index + match[0].length;
  }
  text += body.slice(last);
  if (text) segments.push({ kind: 'text', text });
  return segments;
}

export function presentTurn({ answer, sources }: TurnInput): TurnPresentation {
  const list = sources ?? [];
  return {
    variant: 'answer',
    body: answer,
    sources: indexSources(list),
    steps: [],
    segments: segmentBody(answer, list),
  };
}
