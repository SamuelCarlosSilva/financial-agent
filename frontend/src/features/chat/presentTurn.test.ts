import { describe, expect, it } from 'vitest';

import type {
  CalculationSource,
  DocumentSource,
  FxQuoteSource,
  SourceCitation,
} from '../../api/types';
import { presentTurn } from './presentTurn';

function doc(marker: number | null | undefined, title = `Doc ${marker}`): DocumentSource {
  return {
    type: 'document',
    document_id: title.toLowerCase(),
    title,
    source: `${title}.md`,
    page: 1,
    snippet: 'trecho',
    score: 0.8,
    ...(marker === undefined ? {} : { marker }),
  };
}

const fx: FxQuoteSource = {
  type: 'fx_quote',
  pair: 'EUR-BRL',
  bid: '6.0123',
  ask: '6.0187',
  quoted_at: '2026-10-18T09:40:00-03:00',
  provider: 'awesomeapi',
};

const calc: CalculationSource = {
  type: 'calculation',
  expression: '500 * 6.0123',
  result: '3006.15',
};

describe('presentTurn: variante answer', () => {
  it('divide o texto em trechos e marcadores ligados aos documentos de mesmo marker', () => {
    const sources: SourceCitation[] = [doc(2), doc(4)];

    const p = presentTurn({ answer: 'A [2] e B [4].', scope: 'in_scope', sources });

    expect(p.variant).toBe('answer');
    expect(p.segments).toEqual([
      { kind: 'text', text: 'A ' },
      { kind: 'cite', n: 2, sourceIndex: 0 },
      { kind: 'text', text: ' e B ' },
      { kind: 'cite', n: 4, sourceIndex: 1 },
      { kind: 'text', text: '.' },
    ]);
  });

  it('liga pelo marker, não pela posição em sources', () => {
    const p = presentTurn({ answer: 'X [4] Y [2]', sources: [doc(2), doc(4)] });

    expect(p.segments.filter((s) => s.kind === 'cite')).toEqual([
      { kind: 'cite', n: 4, sourceIndex: 1 },
      { kind: 'cite', n: 2, sourceIndex: 0 },
    ]);
  });

  it('um [n] sem fonte correspondente vira texto', () => {
    const p = presentTurn({ answer: 'A [2] e [9].', sources: [doc(2)] });

    expect(p.segments).toEqual([
      { kind: 'text', text: 'A ' },
      { kind: 'cite', n: 2, sourceIndex: 0 },
      { kind: 'text', text: ' e [9].' },
    ]);
  });

  it('documentos mantêm o marker como número; cotação e cálculo vêm depois do maior', () => {
    const p = presentTurn({ answer: 'r', sources: [doc(4), fx, doc(2), calc] });

    expect(p.sources.map((s) => [s.source.type, s.index])).toEqual([
      ['document', 4],
      ['fx_quote', 5],
      ['document', 2],
      ['calculation', 6],
    ]);
  });

  it('sem documentos, cotação e cálculo começam em 1', () => {
    const p = presentTurn({ answer: 'r', sources: [fx, calc] });

    expect(p.sources.map((s) => s.index)).toEqual([1, 2]);
  });

  it('documento sem marker (histórico antigo) ganha número sequencial mas nenhum cite', () => {
    const p = presentTurn({
      answer: 'Antigo [1] e [2].',
      sources: [doc(undefined, 'A'), doc(null, 'B')],
    });

    expect(p.sources.map((s) => s.index)).toEqual([1, 2]);
    expect(p.segments).toEqual([{ kind: 'text', text: 'Antigo [1] e [2].' }]);
  });

  it('body é exatamente o answer (FR-009)', () => {
    const answer = '  Linha 1 [2]\n\nLinha 2  ';

    const p = presentTurn({ answer, sources: [doc(2)] });

    expect(p.body).toBe(answer);
    expect(p.segments.map((s) => (s.kind === 'text' ? s.text : `[${s.n}]`)).join('')).toBe(answer);
  });

  it('aceita sources ausente ou null', () => {
    expect(presentTurn({ answer: 'oi', sources: null }).sources).toEqual([]);
    expect(presentTurn({ answer: 'oi' }).segments).toEqual([{ kind: 'text', text: 'oi' }]);
  });
});
