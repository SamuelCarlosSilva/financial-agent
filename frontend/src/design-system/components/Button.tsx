// Portado do design system Financial Agent (Claude Design), versão 1792443906-b50c
import type { ButtonHTMLAttributes } from 'react';

import { Icon, type IconName } from '../icons';
import './Button.css';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** `quiet` é o padrão; `primary` no máximo uma vez por área; `ghost` para ações terciárias. */
  variant?: 'primary' | 'quiet' | 'ghost';
  icon?: IconName;
}

/** Rótulo em caixa de frase começando por verbo: "Enviar", "Tentar de novo", "Nova conversa". */
export function Button({
  variant = 'quiet',
  icon,
  className,
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  const classes = ['fa-btn', `fa-btn-${variant}`, className].filter(Boolean).join(' ');
  return (
    <button type={type} {...rest} className={classes}>
      {icon ? <Icon name={icon} /> : null}
      {children}
    </button>
  );
}
