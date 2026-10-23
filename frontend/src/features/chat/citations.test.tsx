import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderSegments } from './citations';
import type { Segment } from './presentTurn';

function text(segments: Segment[]): string {
  const { container } = render(<p>{renderSegments(segments)}</p>);
  return container.textContent ?? '';
}

describe('renderSegments', () => {
  it('mantém o texto do corpo, com a pontuação colada ao marcador', () => {
    const segments: Segment[] = [
      { kind: 'text', text: 'A ' },
      { kind: 'cite', n: 2, sourceIndex: 0 },
      { kind: 'text', text: '. B\nC ' },
      { kind: 'cite', n: 4, sourceIndex: 1 },
    ];

    const { container } = render(<p>{renderSegments(segments)}</p>);

    expect(text(segments)).toBe('A 2. B\nC 4');
    expect(container.querySelector('.cite-group')?.textContent).toBe('2.');
    expect(container.querySelectorAll('button')).toHaveLength(2);
  });

  it('não engole o texto quando ele é só pontuação', () => {
    const segments: Segment[] = [
      { kind: 'cite', n: 1, sourceIndex: 0 },
      { kind: 'text', text: '.' },
    ];

    expect(text(segments)).toBe('1.');
  });
});
