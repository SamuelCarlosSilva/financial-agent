// Portado do design system Financial Agent (Claude Design), versão 1792443906-b50c
import type { ReactNode } from 'react';

import type { SourceCitation } from '../../api/types';
import { formatBrasiliaDateTime, formatDecimal, formatScore } from '../../lib/format';
import { Icon } from '../icons';
import './CitationMarker.css';
import './SourceCard.css';

export interface SourceCardProps {
  /** O objeto da API, sem transformar. */
  source: SourceCitation;
  /** Número do marcador [n] correspondente. */
  index?: number;
  highlighted?: boolean;
  id?: string;
  className?: string;
}

const TYPE_LABEL = { document: 'Documento', fx_quote: 'Cotação', calculation: 'Cálculo' } as const;

function body(source: SourceCitation): ReactNode {
  switch (source.type) {
    case 'document': {
      const meta = [
        source.source,
        source.page != null ? `p. ${source.page}` : null,
        `relevância ${formatScore(source.score)}`,
      ].filter(Boolean);
      return (
        <>
          <div className="fa-src-title">{source.title}</div>
          <div className="fa-src-meta tabular">{meta.join(' · ')}</div>
          {source.snippet ? (
            <blockquote className="fa-src-snippet">{source.snippet}</blockquote>
          ) : null}
        </>
      );
    }
    case 'fx_quote':
      return (
        <>
          <div className="fa-src-title">{source.pair}</div>
          <div className="fa-src-figures">
            <div>
              <span className="fa-src-k">Compra</span>
              <span className="fa-figure">{formatDecimal(source.bid)}</span>
              <span className="fa-src-k">valor usado nas conversões</span>
            </div>
            <div>
              <span className="fa-src-k">Venda</span>
              <span className="fa-figure fa-figure-quiet">{formatDecimal(source.ask)}</span>
            </div>
          </div>
          <div className="fa-src-meta tabular">
            {formatBrasiliaDateTime(source.quoted_at)} · {source.provider}
          </div>
        </>
      );
    case 'calculation':
      // Resultado sem arredondar (research §6), ao contrário das "2 casas" do README.
      return (
        <>
          <code className="fa-src-expr">{source.expression}</code>
          <div className="fa-src-result">
            <span className="fa-src-k">Resultado</span>
            <span className="fa-figure">{formatDecimal(source.result)}</span>
          </div>
        </>
      );
  }
}

export function SourceCard({ source, index, highlighted, id, className }: SourceCardProps) {
  const classes = ['fa-src', `fa-src-${source.type}`, highlighted && 'is-highlighted', className]
    .filter(Boolean)
    .join(' ');
  return (
    <article id={id} className={classes}>
      <header className="fa-src-head">
        {index != null ? <span className="fa-cite fa-cite-static">{index}</span> : null}
        <Icon name={source.type} />
        <span className="fa-label">{TYPE_LABEL[source.type]}</span>
      </header>
      {body(source)}
    </article>
  );
}
