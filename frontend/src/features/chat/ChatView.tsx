import { useEffect, useRef, useState } from 'react';

import { MessageBubble } from '../../design-system/components/MessageBubble';
import { ScopeNotice } from '../../design-system/components/ScopeNotice';
import { SourceCard } from '../../design-system/components/SourceCard';
import { formatTime } from '../../lib/format';
import { renderSegments } from './citations';
import { presentTurn } from './presentTurn';
import type { ConversationState, Turn } from './useConversation';
import './ChatView.css';

type ChatViewProps = Pick<ConversationState, 'turns' | 'status' | 'expired' | 'loadError'>;

const EXPIRED_TEXT = 'Esta conversa expirou e foi apagada. Abrimos uma nova.';

interface ActiveCitation {
  turnId: number;
  n: number;
}

function cardId(turnId: number, index: number): string {
  return `src-${turnId}-${index}`;
}

function AnsweredTurn({
  turn,
  active,
  onCite,
}: {
  turn: Turn & { response: NonNullable<Turn['response']> };
  active: number | null;
  onCite: (n: number) => void;
}) {
  const p = presentTurn(turn.response);
  // Recusa, esclarecimento e "não encontrei" são avisos, não respostas: sem bolha e sem fontes.
  if (p.variant !== 'answer') return <ScopeNotice variant={p.variant}>{p.body}</ScopeNotice>;

  const footer =
    p.sources.length > 0 ? (
      <div className="chat-sources">
        {p.sources.map(({ source, index }) => (
          <SourceCard
            key={index}
            id={cardId(turn.id, index)}
            source={source}
            index={index}
            highlighted={active === index}
          />
        ))}
      </div>
    ) : null;

  return (
    <>
      <MessageBubble role="assistant" footer={footer}>
        {renderSegments(p.segments, { activeIndex: active, onCite })}
      </MessageBubble>
      {p.advice !== undefined ? (
        <ScopeNotice variant="advice">{p.advice || null}</ScopeNotice>
      ) : null}
    </>
  );
}

export function ChatView({ turns, status, expired, loadError }: ChatViewProps) {
  const [active, setActive] = useState<ActiveCitation | null>(null);
  const end = useRef<HTMLDivElement>(null);

  // Cada turno novo ou resposta recebida leva a conversa para o fim.
  const lastStatus = turns.at(-1)?.status;
  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' });
  }, [turns.length, lastStatus]);

  function cite(turnId: number, n: number) {
    setActive({ turnId, n });
    document.getElementById(cardId(turnId, n))?.scrollIntoView({ block: 'nearest' });
  }

  const expiredNotice = expired ? (
    <ScopeNotice variant="not_found" title="Conversa expirada">
      {EXPIRED_TEXT}
    </ScopeNotice>
  ) : null;

  if (status === 'loading') {
    return (
      <div role="status" className="chat-pending">
        Carregando a conversa…
      </div>
    );
  }

  if (loadError) {
    return <p className="chat-failed">{loadError.error.message}</p>;
  }

  if (turns.length === 0) {
    return (
      <div className="chat-empty">
        {expiredNotice}
        <p className="type-display">Financial Agent</p>
        <p className="chat-empty-hint">
          Pergunte sobre investimentos, câmbio, produtos financeiros ou cálculos. Toda resposta
          mostra de onde veio cada informação.
        </p>
      </div>
    );
  }

  return (
    <>
      {expiredNotice}
      {turns.map((turn) => (
        <div key={turn.id} className="chat-turn">
          <MessageBubble role="user" time={formatTime(turn.askedAt)}>
            {turn.question}
          </MessageBubble>
          {turn.status === 'sending' ? (
            <div role="status" className="chat-pending">
              Verificando o escopo da pergunta…
            </div>
          ) : null}
          {turn.status === 'answered' && turn.response ? (
            <AnsweredTurn
              turn={{ ...turn, response: turn.response }}
              active={active?.turnId === turn.id ? active.n : null}
              onCite={(n) => cite(turn.id, n)}
            />
          ) : null}
          {turn.status === 'failed' && turn.error ? (
            <p className="chat-failed">{turn.error.error.message}</p>
          ) : null}
        </div>
      ))}
      <div ref={end} />
    </>
  );
}
