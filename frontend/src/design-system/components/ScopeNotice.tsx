// Portado do design system Financial Agent (Claude Design), versão 1792443906-b50c
import type { ReactNode } from 'react';

import { Icon, type IconName } from '../icons';
import './ScopeNotice.css';

export type ScopeNoticeVariant = 'refused' | 'clarify' | 'not_found' | 'advice' | 'partial';

export interface ScopeNoticeProps {
  variant?: ScopeNoticeVariant;
  /** Substitui o título padrão da variante. */
  title?: string;
  /** O texto devolvido pela API, sem reescrever. */
  children?: ReactNode;
  className?: string;
}

/** `partial` foi portado mas não é usado: a API não sinaliza pergunta mista (research §4). */
const NOTICE: Record<ScopeNoticeVariant, { title: string; icon: IconName }> = {
  refused: { title: 'Fora do escopo financeiro', icon: 'info' },
  clarify: { title: 'Preciso de um esclarecimento', icon: 'info' },
  not_found: { title: 'Não encontrei nas fontes', icon: 'document' },
  advice: { title: 'Não é recomendação de investimento', icon: 'alert' },
  partial: { title: 'Respondi só a parte financeira', icon: 'info' },
};

/** Resposta fixa ou aviso do assistente, com título escrito e ícone. Recusa não é erro. */
export function ScopeNotice({ variant = 'refused', title, children, className }: ScopeNoticeProps) {
  const notice = NOTICE[variant];
  const classes = ['fa-notice', `fa-notice-${variant}`, className].filter(Boolean).join(' ');
  return (
    <div role="note" className={classes}>
      <Icon name={notice.icon} />
      <div>
        <div className="fa-notice-title">{title ?? notice.title}</div>
        {children ? <div className="fa-notice-text">{children}</div> : null}
      </div>
    </div>
  );
}
