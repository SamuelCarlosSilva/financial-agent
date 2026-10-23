import { describe, expect, it } from 'vitest';

import type {
  CalculationSource,
  DocumentSource,
  FxQuoteSource,
  SourceCitation,
} from '../../api/types';
import {
  ADVICE_DISCLAIMER,
  CLARIFY_MESSAGE,
  NOT_FOUND_MESSAGE,
  OUT_OF_SCOPE_MESSAGE,
} from '../../api/messages';
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

describe('presentTurn: recusas e avisos (research §4, regras 1–4)', () => {
  it('scope out_of_scope vira refused, com o texto como veio e sem fontes', () => {
    const p = presentTurn({ answer: OUT_OF_SCOPE_MESSAGE, scope: 'out_of_scope', sources: [] });

    expect(p.variant).toBe('refused');
    expect(p.body).toBe(OUT_OF_SCOPE_MESSAGE);
    expect(p.sources).toEqual([]);
  });

  it('scope ambiguous vira clarify', () => {
    const p = presentTurn({ answer: CLARIFY_MESSAGE, scope: 'ambiguous', sources: [] });

    expect(p.variant).toBe('clarify');
    expect(p.body).toBe(CLARIFY_MESSAGE);
  });

  it('a mensagem fixa de "não encontrei" vira not_found, mesmo com espaços em volta', () => {
    const answer = `  ${NOT_FOUND_MESSAGE}\n`;

    const p = presentTurn({ answer, scope: 'in_scope', sources: [] });

    expect(p.variant).toBe('not_found');
    expect(p.body).toBe(answer);
  });

  it('out_of_scope vence as outras regras', () => {
    const answer = `${NOT_FOUND_MESSAGE} ${ADVICE_DISCLAIMER}`;

    expect(presentTurn({ answer, scope: 'out_of_scope' }).variant).toBe('refused');
    expect(presentTurn({ answer: NOT_FOUND_MESSAGE, scope: 'ambiguous' }).variant).toBe('clarify');
  });

  it('sem scope (histórico), recusa e esclarecimento são reconhecidos pelo texto', () => {
    expect(presentTurn({ answer: OUT_OF_SCOPE_MESSAGE }).variant).toBe('refused');
    expect(presentTurn({ answer: CLARIFY_MESSAGE }).variant).toBe('clarify');
    expect(presentTurn({ answer: NOT_FOUND_MESSAGE }).variant).toBe('not_found');
  });

  it('com scope in_scope, o texto da recusa não basta para virar refused', () => {
    expect(presentTurn({ answer: OUT_OF_SCOPE_MESSAGE, scope: 'in_scope' }).variant).toBe('answer');
  });

  it('separa a frase do aviso de recomendação e mantém as fontes', () => {
    const answer = `CDB é renda fixa [1].\n\n${ADVICE_DISCLAIMER}`;

    const p = presentTurn({ answer, scope: 'in_scope', sources: [doc(1)] });

    expect(p.variant).toBe('answer');
    expect(p.advice).toBe(ADVICE_DISCLAIMER);
    expect(p.body).toBe('CDB é renda fixa [1].');
    expect(p.sources).toHaveLength(1);
    expect(p.segments).toEqual([
      { kind: 'text', text: 'CDB é renda fixa ' },
      { kind: 'cite', n: 1, sourceIndex: 0 },
      { kind: 'text', text: '.' },
    ]);
  });

  it('preserva o texto antes e depois do aviso', () => {
    const p = presentTurn({ answer: `A.\n\n${ADVICE_DISCLAIMER}\n\nB.` });

    expect(p.body).toBe('A.\n\nB.');
    expect(p.advice).toBe(ADVICE_DISCLAIMER);
  });

  it('acha o aviso no meio de um parágrafo, sem diferenciar maiúsculas', () => {
    const aviso = 'Isto NÃO CONSTITUI RECOMENDAÇÃO DE INVESTIMENTO!';

    const p = presentTurn({ answer: `Primeiro. ${aviso} Depois.` });

    expect(p.advice).toBe(aviso);
    expect(p.body).toBe('Primeiro. Depois.');
  });

  it('se a frase não termina em pontuação, body fica com o answer inteiro (FR-009)', () => {
    const answer = 'Texto. Isto não constitui recomendação de investimento';

    const p = presentTurn({ answer });

    expect(p.variant).toBe('answer');
    expect(p.body).toBe(answer);
    expect(p.advice).toBe('');
  });

  it('sem o núcleo do aviso, não há advice', () => {
    expect(presentTurn({ answer: 'Só uma resposta.' }).advice).toBeUndefined();
  });
});
