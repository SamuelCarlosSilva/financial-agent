// Apresentação de um turno como função pura dos campos da API (research §4, data-model.md).
import {
  ADVICE_DISCLAIMER_CORE,
  CLARIFY_MESSAGE,
  NOT_FOUND_MESSAGE,
  OUT_OF_SCOPE_MESSAGE,
} from '../../api/messages';
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
  /** Texto exibido: o `answer` como veio, menos a frase do aviso de recomendação (FR-009). */
  body: string;
  /**
   * Frase do aviso de recomendação como veio. Vazia quando o aviso existe mas a frase não pôde
   * ser isolada (o texto continua todo no `body`). Ausente quando não há aviso.
   */
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

/** Fim da frase anterior: pontuação seguida de espaço, ou quebra de linha. */
const SENTENCE_BREAK = /[.!?]\s+|\n/g;

/**
 * Separa a frase que contém o núcleo do aviso. Devolve `null` se não há aviso e `advice` vazio
 * se a frase não termina em pontuação (nesse caso nada é removido do texto).
 */
export function splitAdvice(answer: string): { body: string; advice: string } | null {
  const at = answer.toLowerCase().indexOf(ADVICE_DISCLAIMER_CORE);
  if (at < 0) return null;

  const end = answer.slice(at + ADVICE_DISCLAIMER_CORE.length).search(/[.!?]/);
  if (end < 0) return { body: answer, advice: '' };
  const stop = at + ADVICE_DISCLAIMER_CORE.length + end + 1;

  let start = 0;
  for (const match of answer.slice(0, at).matchAll(SENTENCE_BREAK)) {
    start = match.index + match[0].length;
  }

  // O espaço antes da frase separa o que fica dos dois lados ("A.\n\n<aviso>\n\nB." → "A.\n\nB.").
  const before = answer.slice(0, start);
  const after = answer.slice(stop).replace(/^\s+/, '');
  const kept = before.trimEnd();
  const gap = kept && after ? before.slice(kept.length) || ' ' : '';
  return { body: kept + gap + after, advice: answer.slice(start, stop) };
}

function notice(variant: 'refused' | 'clarify' | 'not_found', answer: string): TurnPresentation {
  return {
    variant,
    body: answer,
    sources: [],
    steps: [],
    segments: [{ kind: 'text', text: answer }],
  };
}

/**
 * Regras de research §4, nesta ordem: recusa, esclarecimento, "não encontrei", aviso de
 * recomendação e resposta comum. Sem `scope` (histórico), recusa e esclarecimento vêm do texto.
 */
export function presentTurn({ answer, scope, sources }: TurnInput): TurnPresentation {
  const text = answer.trim();
  if (scope === 'out_of_scope' || (!scope && text === OUT_OF_SCOPE_MESSAGE)) {
    return notice('refused', answer);
  }
  if (scope === 'ambiguous' || (!scope && text === CLARIFY_MESSAGE)) {
    return notice('clarify', answer);
  }
  if (text === NOT_FOUND_MESSAGE) return notice('not_found', answer);

  const list = sources ?? [];
  const split = splitAdvice(answer);
  const body = split?.body ?? answer;
  return {
    variant: 'answer',
    body,
    ...(split ? { advice: split.advice } : {}),
    sources: indexSources(list),
    steps: [],
    segments: segmentBody(body, list),
  };
}
