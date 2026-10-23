// Estado da conversa aberta (máquina de estados de data-model.md).
import { useCallback, useEffect, useReducer, useRef, type Dispatch } from 'react';

import { ApiRequestError, getThreadMessages, isRetryable, postChat } from '../../api/client';
import type { ApiFailure, ChatResponse, ThreadHistory } from '../../api/types';
import { threadIndex } from '../threads/threadIndex';
import type { TurnInput } from './presentTurn';

export interface Turn {
  id: number;
  question: string;
  askedAt: Date;
  status: 'sending' | 'answered' | 'failed';
  /** A resposta do chat ou, vinda do histórico, sem `scope`. */
  response?: TurnInput;
  error?: ApiFailure;
}

export interface ConversationState {
  threadId?: string;
  turns: Turn[];
  status: 'idle' | 'sending' | 'loading';
  /** A conversa pedida expirou (404) e foi trocada por uma nova. */
  expired: boolean;
  /** Falha ao carregar o histórico, exceto 404 (apresentação detalhada na US4). */
  loadError?: ApiFailure;
}

type Action =
  | { type: 'sent'; turn: Turn }
  | { type: 'retrying'; id: number }
  | { type: 'answered'; id: number; response: ChatResponse }
  | { type: 'failed'; id: number; error: ApiFailure }
  | { type: 'loading'; threadId: string }
  | { type: 'loaded'; turns: Turn[] }
  | { type: 'loadFailed'; error: ApiFailure }
  | { type: 'expired' }
  | { type: 'reset' };

const initialState: ConversationState = { turns: [], status: 'idle', expired: false };

function updateTurn(turns: Turn[], id: number, patch: Partial<Turn>): Turn[] {
  return turns.map((turn) => (turn.id === id ? { ...turn, ...patch } : turn));
}

export function conversationReducer(state: ConversationState, action: Action): ConversationState {
  switch (action.type) {
    case 'sent':
      return {
        threadId: state.threadId,
        status: 'sending',
        expired: false,
        turns: [...state.turns, action.turn],
      };
    case 'retrying':
      // O mesmo turno volta a `sending`: a pergunta não se repete na tela.
      return {
        ...state,
        status: 'sending',
        turns: state.turns.map((turn) =>
          turn.id === action.id
            ? { id: turn.id, question: turn.question, askedAt: turn.askedAt, status: 'sending' }
            : turn,
        ),
      };
    case 'answered':
      // A conversa pode ter sido trocada enquanto a resposta não chegava.
      if (!state.turns.some((turn) => turn.id === action.id)) return state;
      return {
        ...state,
        threadId: state.threadId ?? action.response.thread_id,
        status: 'idle',
        turns: updateTurn(state.turns, action.id, {
          status: 'answered',
          response: action.response,
        }),
      };
    case 'failed':
      if (!state.turns.some((turn) => turn.id === action.id)) return state;
      return {
        ...state,
        status: 'idle',
        turns: updateTurn(state.turns, action.id, { status: 'failed', error: action.error }),
      };
    case 'loading':
      return { threadId: action.threadId, turns: [], status: 'loading', expired: false };
    case 'loaded':
      return { ...state, status: 'idle', turns: action.turns };
    case 'loadFailed':
      return { ...state, status: 'idle', loadError: action.error };
    case 'expired':
      return { ...initialState, expired: true };
    case 'reset':
      return initialState;
  }
}

function toFailure(error: unknown): ApiFailure {
  if (error instanceof ApiRequestError) return { status: error.status, error: error.error };
  return {
    status: 0,
    error: { code: 'unknown_error', message: 'Algo deu errado. Tente de novo.' },
  };
}

/**
 * Turnos do histórico: cada mensagem `user` com a `assistant` seguinte. O histórico não traz
 * `scope`, então a apresentação vem só do texto (research §4).
 */
export function turnsFromHistory(history: ThreadHistory, firstId = 1): Turn[] {
  const turns: Turn[] = [];
  const { messages } = history;
  for (let i = 0; i < messages.length; i++) {
    const question = messages[i];
    const answer = messages[i + 1];
    if (question?.role !== 'user' || answer?.role !== 'assistant') continue;
    turns.push({
      id: firstId + turns.length,
      question: question.content,
      askedAt: new Date(question.created_at ?? answer.created_at ?? Date.now()),
      status: 'answered',
      response: { answer: answer.content, sources: answer.sources ?? [] },
    });
    i++;
  }
  return turns;
}

/** Envia a pergunta do turno `id` e registra nele a resposta, ou a falha. */
async function deliver(
  dispatch: Dispatch<Action>,
  id: number,
  question: string,
  threadId: string | undefined,
  firstQuestion: string,
) {
  try {
    const response = await postChat({
      message: question,
      ...(threadId ? { thread_id: threadId } : {}),
    });
    threadIndex.upsert({
      id: response.thread_id,
      firstQuestion,
      lastActivity: new Date().toISOString(),
    });
    dispatch({ type: 'answered', id, response });
  } catch (error) {
    dispatch({ type: 'failed', id, error: toFailure(error) });
  }
}

export function useConversation() {
  const [state, dispatch] = useReducer(conversationReducer, initialState);
  // Espelho síncrono do estado: dois Enter no mesmo tick não podem disparar dois envios.
  const current = useRef(state);
  useEffect(() => {
    current.current = state;
  }, [state]);
  const nextId = useRef(1);
  // Só a última conversa pedida pode preencher a tela (abrir A e logo B mostra B).
  const loadToken = useRef(0);

  const submit = useCallback(async (question: string) => {
    const { status, threadId, turns } = current.current;
    if (status !== 'idle') return;

    const id = nextId.current++;
    const turn: Turn = { id, question, askedAt: new Date(), status: 'sending' };
    current.current = { ...current.current, status: 'sending' };
    dispatch({ type: 'sent', turn });
    await deliver(dispatch, id, question, threadId, turns[0]?.question ?? question);
  }, []);

  /** Reenvia a pergunta de um turno que falhou por motivo transitório, na conversa atual. */
  const retry = useCallback(async (id: number) => {
    const { status, threadId, turns } = current.current;
    const turn = turns.find((t) => t.id === id);
    if (status !== 'idle' || turn?.status !== 'failed' || !turn.error) return;
    if (!isRetryable(turn.error)) return;

    current.current = { ...current.current, status: 'sending' };
    dispatch({ type: 'retrying', id });
    await deliver(dispatch, id, turn.question, threadId, turns[0]?.question ?? turn.question);
  }, []);

  const openThread = useCallback(async (threadId: string) => {
    const { threadId: openId, loadError } = current.current;
    if (threadId === openId && !loadError) return;

    const token = ++loadToken.current;
    current.current = { ...current.current, threadId, status: 'loading' };
    dispatch({ type: 'loading', threadId });

    try {
      const history = await getThreadMessages(threadId);
      if (token !== loadToken.current) return;
      const turns = turnsFromHistory(history, nextId.current);
      nextId.current += turns.length;
      dispatch({ type: 'loaded', turns });
    } catch (error) {
      if (token !== loadToken.current) return;
      const failure = toFailure(error);
      if (failure.status === 404) {
        threadIndex.remove(threadId);
        dispatch({ type: 'expired' });
      } else {
        dispatch({ type: 'loadFailed', error: failure });
      }
    }
  }, []);

  const newConversation = useCallback(() => {
    loadToken.current++;
    current.current = initialState;
    dispatch({ type: 'reset' });
  }, []);

  return { ...state, submit, retry, openThread, newConversation };
}
