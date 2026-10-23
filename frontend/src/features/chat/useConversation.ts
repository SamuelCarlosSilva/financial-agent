// Estado da conversa aberta (máquina de estados de data-model.md).
import { useCallback, useEffect, useReducer, useRef } from 'react';

import { ApiRequestError, postChat } from '../../api/client';
import type { ApiFailure, ChatResponse } from '../../api/types';

export interface Turn {
  id: number;
  question: string;
  askedAt: Date;
  status: 'sending' | 'answered' | 'failed';
  response?: ChatResponse;
  error?: ApiFailure;
}

export interface ConversationState {
  threadId?: string;
  turns: Turn[];
  status: 'idle' | 'sending';
}

type Action =
  | { type: 'sent'; turn: Turn }
  | { type: 'answered'; id: number; response: ChatResponse }
  | { type: 'failed'; id: number; error: ApiFailure };

const initialState: ConversationState = { turns: [], status: 'idle' };

function updateTurn(turns: Turn[], id: number, patch: Partial<Turn>): Turn[] {
  return turns.map((turn) => (turn.id === id ? { ...turn, ...patch } : turn));
}

export function conversationReducer(state: ConversationState, action: Action): ConversationState {
  switch (action.type) {
    case 'sent':
      return { ...state, status: 'sending', turns: [...state.turns, action.turn] };
    case 'answered':
      return {
        threadId: state.threadId ?? action.response.thread_id,
        status: 'idle',
        turns: updateTurn(state.turns, action.id, {
          status: 'answered',
          response: action.response,
        }),
      };
    case 'failed':
      return {
        ...state,
        status: 'idle',
        turns: updateTurn(state.turns, action.id, { status: 'failed', error: action.error }),
      };
  }
}

function toFailure(error: unknown): ApiFailure {
  if (error instanceof ApiRequestError) return { status: error.status, error: error.error };
  return {
    status: 0,
    error: { code: 'unknown_error', message: 'Algo deu errado. Tente de novo.' },
  };
}

export function useConversation() {
  const [state, dispatch] = useReducer(conversationReducer, initialState);
  // Espelho síncrono do estado: dois Enter no mesmo tick não podem disparar dois envios.
  const current = useRef(state);
  useEffect(() => {
    current.current = state;
  }, [state]);
  const nextId = useRef(1);

  const submit = useCallback(async (question: string) => {
    const { status, threadId } = current.current;
    if (status === 'sending') return;

    const id = nextId.current++;
    const turn: Turn = { id, question, askedAt: new Date(), status: 'sending' };
    current.current = { ...current.current, status: 'sending' };
    dispatch({ type: 'sent', turn });

    try {
      const response = await postChat({
        message: question,
        ...(threadId ? { thread_id: threadId } : {}),
      });
      dispatch({ type: 'answered', id, response });
    } catch (error) {
      dispatch({ type: 'failed', id, error: toFailure(error) });
    }
  }, []);

  return { ...state, submit };
}
