// Portado do design system Financial Agent (Claude Design), versão 1792443906-b50c
import type { ReactNode } from 'react';

import type { Scope } from '../../api/types';
import './ScopeBadge.css';

export interface ScopeBadgeProps {
  scope?: Scope;
  children?: ReactNode;
}

const SCOPE_LABEL: Record<Scope, string> = {
  in_scope: 'Em escopo',
  out_of_scope: 'Fora de escopo',
  ambiguous: 'Ambígua',
};

/** Etiqueta da decisão do guardrail. Nunca é a única explicação: recusa sempre vem com ScopeNotice. */
export function ScopeBadge({ scope = 'in_scope', children }: ScopeBadgeProps) {
  return <span className={`fa-badge fa-badge-${scope}`}>{children ?? SCOPE_LABEL[scope]}</span>;
}
