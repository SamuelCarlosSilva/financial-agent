import { describe, expect, it } from 'vitest';

import type { ThreadHistory } from '../../api/types';
import history from '../../../e2e/fixtures/history.json';
import { turnsFromHistory } from './useConversation';

describe('turnsFromHistory', () => {
  it('cada pergunta com a resposta seguinte vira um turno respondido, sem scope', () => {
    const turns = turnsFromHistory(history as ThreadHistory, 7);

    expect(turns).toHaveLength(2);
    expect(turns[0]).toMatchObject({
      id: 7,
      question: 'O que é come-cotas?',
      status: 'answered',
      response: {
        answer: history.messages[1]!.content,
        sources: history.messages[1]!.sources,
      },
    });
    expect(turns[0]!.askedAt.toISOString()).toBe('2026-10-17T12:40:00.000Z');
    expect(turns[0]!.response).not.toHaveProperty('scope');
    expect(turns[1]).toMatchObject({ id: 8, question: 'Quanto são 500 euros em reais?' });
  });

  it('sources null vira lista vazia e uma pergunta sem resposta é descartada', () => {
    const turns = turnsFromHistory({
      thread_id: history.thread_id,
      messages: [
        { role: 'user', content: 'Oi', created_at: null, sources: null },
        { role: 'assistant', content: 'Olá', sources: null },
        { role: 'user', content: 'Sem resposta' },
      ],
    });

    expect(turns).toHaveLength(1);
    expect(turns[0]!.response).toEqual({ answer: 'Olá', sources: [] });
  });
});
