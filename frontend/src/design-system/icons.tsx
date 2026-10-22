// Portado do design system Financial Agent (Claude Design), versão 1792443906-b50c

const ICON_PATHS = {
  document: 'M4 2h6l3 3v9H4z M10 2v3h3 M6 8h5 M6 11h5',
  fx_quote: 'M3 5h9l-2-2 M13 11H4l2 2',
  calculation: 'M3 3h10v10H3z M5.5 6h2 M6.5 5v2 M9 6h2 M5.5 10h2 M9 9.5h2 M9 10.5h2',
  send: 'M2 8h11 M9 4l4 4-4 4',
  alert: 'M8 2l6 11H2z M8 6v3.5 M8 11.2v.3',
  info: 'M8 2a6 6 0 1 0 0 12A6 6 0 0 0 8 2z M8 7v4 M8 4.8v.4',
} as const;

export type IconName = keyof typeof ICON_PATHS;

interface IconProps {
  name: IconName;
  size?: number;
  className?: string;
}

/** Ícone decorativo: sempre acompanha um texto, então fica fora da árvore de acessibilidade. */
export function Icon({ name, size = 16, className }: IconProps) {
  return (
    <svg
      className={className ? `fa-icon ${className}` : 'fa-icon'}
      viewBox="0 0 16 16"
      width={size}
      height={size}
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={ICON_PATHS[name]} />
    </svg>
  );
}
