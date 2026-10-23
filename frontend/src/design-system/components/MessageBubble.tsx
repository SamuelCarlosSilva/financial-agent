// Portado do design system Financial Agent (Claude Design), versão 1792443906-b50c
import type { ReactNode } from 'react';

import './MessageBubble.css';

export interface MessageBubbleProps {
  role?: 'user' | 'assistant';
  /**
   * Conteúdo já pronto. No bundle original a bolha convertia `[n]` em CitationMarker; aqui a
   * segmentação é da feature de chat (features/chat/citations.tsx), que liga cada `[n]` ao marker.
   */
  children?: ReactNode;
  /** Cartões de fonte abaixo da resposta. */
  footer?: ReactNode;
  /** Hora já formatada em pt-BR. */
  time?: string;
  className?: string;
}

export function MessageBubble({
  role = 'assistant',
  children,
  footer,
  time,
  className,
}: MessageBubbleProps) {
  const classes = ['fa-msg', `fa-msg-${role}`, className].filter(Boolean).join(' ');
  return (
    <div className={classes}>
      <div className="fa-msg-body">{children}</div>
      {footer ? <div className="fa-msg-footer">{footer}</div> : null}
      {time ? <div className="fa-msg-time">{time}</div> : null}
    </div>
  );
}
