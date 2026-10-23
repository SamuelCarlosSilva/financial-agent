import type { ReactNode } from 'react';

import { CitationMarker } from '../../design-system/components/CitationMarker';
import type { Segment } from './presentTurn';
import './citations.css';

interface RenderOptions {
  /** Marcador `[n]` cujo cartão está destacado. */
  activeIndex?: number | null;
  onCite?: (n: number) => void;
}

/** Pontuação logo depois do marcador, que não deve cair sozinha na linha seguinte. */
const TRAILING_PUNCTUATION = /^[.,;:!?)\]]+/;

/**
 * Texto e CitationMarker na ordem do corpo. As quebras de linha ficam nas strings e aparecem
 * pelo `white-space: pre-wrap` da bolha. O texto exibido é exatamente o do corpo (FR-009).
 */
export function renderSegments(
  segments: Segment[],
  { activeIndex, onCite }: RenderOptions = {},
): ReactNode[] {
  const nodes: ReactNode[] = [];
  let carried = '';
  segments.forEach((segment, i) => {
    if (segment.kind === 'text') {
      nodes.push(segment.text.slice(carried.length));
      carried = '';
      return;
    }
    const next = segments[i + 1];
    carried = next?.kind === 'text' ? (TRAILING_PUNCTUATION.exec(next.text)?.[0] ?? '') : '';
    const marker = (
      <CitationMarker
        key={i}
        index={segment.n}
        active={activeIndex === segment.n}
        onClick={onCite ? () => onCite(segment.n) : undefined}
      />
    );
    nodes.push(
      carried ? (
        <span key={i} className="cite-group">
          {marker}
          {carried}
        </span>
      ) : (
        marker
      ),
    );
  });
  return nodes.filter((node) => node !== '');
}
