import { describe, expect, it } from 'vitest';

import {
  formatBrasiliaDateTime,
  formatDecimal,
  formatRelativeDay,
  formatScore,
  formatTime,
} from './format';

describe('formatDecimal', () => {
  it.each([
    ['3006.15', '3.006,15'],
    ['6.0123', '6,0123'],
    ['1234567', '1.234.567'],
    ['0.5', '0,5'],
    ['999', '999'],
    ['1000', '1.000'],
    ['-1234.5', '-1.234,5'],
    ['11268.250000', '11.268,250000'],
    [
      '123456789012345678901234.123456789012345678',
      '123.456.789.012.345.678.901.234,123456789012345678',
    ],
  ])('%s → %s', (input, expected) => {
    expect(formatDecimal(input)).toBe(expected);
  });

  it('não arredonda nem perde dígitos', () => {
    const value = '0.1000000000000000055511151231257827';
    expect(formatDecimal(value).replace(',', '.')).toBe(value);
  });

  it.each(['1E+3', 'abc', '', '1.2.3'])('devolve %j sem mudança', (input) => {
    expect(formatDecimal(input)).toBe(input);
  });
});

describe('formatScore', () => {
  it('usa vírgula e no máximo 2 casas', () => {
    expect(formatScore(0.8234)).toBe('0,82');
    expect(formatScore(0.5)).toBe('0,5');
  });
});

describe('datas em horário de Brasília', () => {
  it('formatBrasiliaDateTime converte do UTC e diz o fuso', () => {
    expect(formatBrasiliaDateTime('2026-10-18T12:40:00Z')).toBe(
      '18/10/2026, 09:40 (horário de Brasília)',
    );
  });

  it('formatTime dá HH:mm em Brasília', () => {
    expect(formatTime('2026-10-18T12:05:00Z')).toBe('09:05');
    expect(formatTime('2026-10-18T03:00:00Z')).toBe('00:00');
  });
});

describe('formatRelativeDay', () => {
  const now = new Date('2026-10-18T15:00:00Z'); // 12:00 em Brasília

  it('hoje mostra a hora', () => {
    expect(formatRelativeDay('2026-10-18T12:41:00Z', now)).toBe('hoje, 09:41');
  });

  it('ontem', () => {
    expect(formatRelativeDay('2026-10-17T20:00:00Z', now)).toBe('ontem');
  });

  it('antes de ontem mostra dd/MM', () => {
    expect(formatRelativeDay('2026-10-12T15:00:00Z', now)).toBe('12/10');
  });

  it('compara o dia em Brasília, não em UTC', () => {
    // 01:30 UTC do dia 18 ainda é dia 17 em Brasília.
    expect(formatRelativeDay('2026-10-18T01:30:00Z', now)).toBe('ontem');
    // 23:30 em Brasília do dia 18 já é dia 19 em UTC.
    const lateNow = new Date('2026-10-19T02:30:00Z');
    expect(formatRelativeDay('2026-10-18T13:00:00Z', lateNow)).toBe('hoje, 10:00');
  });
});
