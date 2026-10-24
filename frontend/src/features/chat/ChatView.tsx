import { useEffect, useRef, useState } from 'react';

import { isRetryable } from '../../api/client';
import { ErrorBanner } from '../../design-system/components/ErrorBanner';
import { MessageBubble } from '../../design-system/components/MessageBubble';
import { ScopeNotice } from '../../design-system/components/ScopeNotice';
import { SourceCard } from '../../design-system/components/SourceCard';
import { ToolStatus, type ToolStep } from '../../design-system/components/ToolStatus';
import { formatTime } from '../../lib/format';
import { renderSegments } from './citations';
import { pendingSteps, presentTurn } from './presentTurn';
import type { ConversationState, Turn } from './useConversation';
import './ChatView.css';

interface ChatViewProps extends Pick<
  ConversationState,
  'turns' | 'status' | 'expired' | 'loadError'
> {
  /** Reenvia a pergunta de um turno que falhou (só falhas transitórias). */
  onRetry: (turnId: number) => void;
  /** Tenta carregar de novo o histórico que falhou. */
  onReloadThread: () => void;
}

const EXPIRED_TEXT = 'Esta conversa expirou e foi apagada. Abrimos uma nova.';

interface ActiveCitation {
  turnId: number;
  n: number;
}

function cardId(turnId: number, index: number): string {
  return `src-${turnId}-${index}`;
}

/** Resumo recolhível dos passos do agente, acima da resposta. */
function StepsSummary({
  id,
  steps,
  expanded,
  onToggle,
}: {
  id: string;
  steps: ToolStep[];
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="chat-steps">
      <button
        type="button"
        className="chat-steps-toggle"
        aria-expanded={expanded}
        aria-controls={id}
        onClick={onToggle}
      >
        Passos do agente
      </button>
      <ToolStatus id={id} steps={steps} hidden={!expanded} />
    </div>
  );
}

function AnsweredTurn({
  turn,
  active,
  onCite,
  stepsExpanded,
  onToggleSteps,
}: {
  turn: Turn & { response: NonNullable<Turn['response']> };
  active: number | null;
  onCite: (n: number) => void;
  stepsExpanded: boolean;
  onToggleSteps: () => void;
}) {
  const p = presentTurn(turn.response);
  const steps = (
    <StepsSummary
      id={`steps-${turn.id}`}
      steps={p.steps}
      expanded={stepsExpanded}
      onToggle={onToggleSteps}
    />
  );
  // Recusa, esclarecimento e "não encontrei" são avisos, não respostas: sem bolha e sem fontes.
  if (p.variant !== 'answer') {
    return (
      <>
        {steps}
        <ScopeNotice variant={p.variant}>{p.body}</ScopeNotice>
      </>
    );
  }

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
      {steps}
      <MessageBubble role="assistant" footer={footer}>
        {renderSegments(p.segments, { activeIndex: active, onCite })}
      </MessageBubble>
      {p.advice !== undefined ? (
        <ScopeNotice variant="advice">{p.advice || null}</ScopeNotice>
      ) : null}
    </>
  );
}

export function ChatView({
  turns,
  status,
  expired,
  loadError,
  onRetry,
  onReloadThread,
}: ChatViewProps) {
  const [active, setActive] = useState<ActiveCitation | null>(null);
  // Passos abertos ou fechados pelo usuário; sem escolha, só o turno mais novo fica aberto.
  const [toggledSteps, setToggledSteps] = useState<Record<number, boolean>>({});
  const newest = turns.at(-1);

  function stepsExpanded(turn: Turn): boolean {
    return toggledSteps[turn.id] ?? (!turn.fromHistory && turn.id === newest?.id);
  }
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
    return (
      <ErrorBanner {...loadError} onRetry={isRetryable(loadError) ? onReloadThread : undefined} />
    );
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
          {turn.status === 'sending' ? <ToolStatus steps={pendingSteps()} /> : null}
          {turn.status === 'answered' && turn.response ? (
            <AnsweredTurn
              turn={{ ...turn, response: turn.response }}
              active={active?.turnId === turn.id ? active.n : null}
              onCite={(n) => cite(turn.id, n)}
              stepsExpanded={stepsExpanded(turn)}
              onToggleSteps={() =>
                setToggledSteps((all) => ({ ...all, [turn.id]: !stepsExpanded(turn) }))
              }
            />
          ) : null}
          {turn.status === 'failed' && turn.error ? (
            <ErrorBanner
              {...turn.error}
              onRetry={isRetryable(turn.error) ? () => onRetry(turn.id) : undefined}
            />
          ) : null}
        </div>
      ))}
      <div ref={end} />
    </>
  );
}
