// Portado do design system Financial Agent (Claude Design), versão 1792443906-b50c
import type { ButtonHTMLAttributes } from 'react';

import './CitationMarker.css';

export interface CitationMarkerProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  index: number;
  /** O cartão correspondente está destacado. */
  active?: boolean;
}

/** Marcador `[n]` da resposta, ligado ao SourceCard de mesmo número. */
export function CitationMarker({ index, active, className, ...rest }: CitationMarkerProps) {
  const classes = ['fa-cite', active && 'is-active', className].filter(Boolean).join(' ');
  return (
    <button type="button" aria-label={`Fonte ${index}`} {...rest} className={classes}>
      {index}
    </button>
  );
}
