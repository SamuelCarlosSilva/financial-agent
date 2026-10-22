// Formatação pt-BR. Decimais vindos da API são strings e são formatados sem virar Number,
// para não arredondar nem perder dígitos (Princípio I).

const TIME_ZONE = 'America/Sao_Paulo';

const DECIMAL = /^(-?)(\d+)(?:\.(\d+))?$/;

/** `"3006.15"` → `"3.006,15"`. Entradas fora do formato decimal simples voltam como vieram. */
export function formatDecimal(value: string): string {
  const match = DECIMAL.exec(value.trim());
  if (!match) return value;
  const [, sign = '', integer = '', fraction] = match;
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return `${sign}${grouped}${fraction === undefined ? '' : `,${fraction}`}`;
}

const scoreFormat = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 });

export function formatScore(n: number): string {
  return scoreFormat.format(n);
}

const dateTimeFormat = new Intl.DateTimeFormat('pt-BR', {
  dateStyle: 'short',
  timeStyle: 'short',
  timeZone: TIME_ZONE,
});

export function formatBrasiliaDateTime(iso: string): string {
  return `${dateTimeFormat.format(new Date(iso))} (horário de Brasília)`;
}

const timeFormat = new Intl.DateTimeFormat('pt-BR', {
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
  timeZone: TIME_ZONE,
});

export function formatTime(iso: string | Date): string {
  return timeFormat.format(typeof iso === 'string' ? new Date(iso) : iso);
}

const dayKeyFormat = new Intl.DateTimeFormat('en-CA', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  timeZone: TIME_ZONE,
});

const shortDayFormat = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit',
  month: '2-digit',
  timeZone: TIME_ZONE,
});

/** Dia civil em Brasília, como número de dias desde a época, para comparar "hoje"/"ontem". */
function brasiliaDay(date: Date): number {
  const [y, m, d] = dayKeyFormat.format(date).split('-').map(Number);
  return Date.UTC(y!, m! - 1, d) / 86_400_000;
}

/** Última atividade na lista de conversas: "hoje, 09:41", "ontem" ou "12/10". */
export function formatRelativeDay(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  const diff = brasiliaDay(now) - brasiliaDay(date);
  if (diff === 0) return `hoje, ${formatTime(date)}`;
  if (diff === 1) return 'ontem';
  return shortDayFormat.format(date);
}
