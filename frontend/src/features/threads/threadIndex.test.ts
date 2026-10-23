import { describe, expect, it, vi } from 'vitest';

import { createThreadIndex, THREADS_KEY, titleFrom, type ThreadIndexEntry } from './threadIndex';

/** Storage em memória com o mínimo que o índice usa. */
function fakeStorage(initial?: string) {
  const data = new Map<string, string>(initial === undefined ? [] : [[THREADS_KEY, initial]]);
  return {
    getItem: vi.fn((key: string) => data.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => void data.set(key, value)),
    raw: () => data.get(THREADS_KEY),
  };
}

function uuid(n: number): string {
  return `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
}

function day(n: number): string {
  return new Date(Date.UTC(2026, 9, 1, 12) + n * 60_000).toISOString();
}

function entry(n: number, extra: Partial<ThreadIndexEntry> = {}): ThreadIndexEntry {
  return { id: uuid(n), title: `Conversa ${n}`, lastActivity: day(n), ...extra };
}

describe('threadIndex', () => {
  it('JSON corrompido vira índice vazio', () => {
    const index = createThreadIndex(() => fakeStorage('{não é json'));

    expect(index.load()).toEqual([]);
  });

  it('formato desconhecido vira índice vazio', () => {
    expect(createThreadIndex(() => fakeStorage('{"a":1}')).load()).toEqual([]);
  });

  it('descarta entradas com id inválido, campo ausente ou título fora de 1–60', () => {
    const stored = [
      entry(1),
      { ...entry(2), id: 'não-é-uuid' },
      { id: uuid(3), title: 'Sem data' },
      { ...entry(4), title: '' },
      { ...entry(5), title: 'x'.repeat(61) },
      { ...entry(6), lastActivity: 'ontem' },
      null,
    ];

    const index = createThreadIndex(() => fakeStorage(JSON.stringify(stored)));

    expect(index.load()).toEqual([entry(1)]);
  });

  it('ordena por lastActivity, da mais recente para a mais antiga', () => {
    const stored = [entry(1), entry(3), entry(2)];

    const index = createThreadIndex(() => fakeStorage(JSON.stringify(stored)));

    expect(index.load().map((e) => e.id)).toEqual([uuid(3), uuid(2), uuid(1)]);
  });

  it('upsert cria a entrada com a primeira pergunta como título', () => {
    const storage = fakeStorage();
    const index = createThreadIndex(() => storage);

    index.upsert({ id: uuid(1), firstQuestion: '  O que é   come-cotas? ', lastActivity: day(1) });

    expect(index.load()).toEqual([
      { id: uuid(1), title: 'O que é come-cotas?', lastActivity: day(1) },
    ]);
    expect(JSON.parse(storage.raw()!)).toEqual(index.load());
  });

  it('upsert de uma conversa existente só atualiza a data e a leva para o topo', () => {
    const index = createThreadIndex(() => fakeStorage(JSON.stringify([entry(2), entry(1)])));

    index.upsert({ id: uuid(1), firstQuestion: 'Outra pergunta', lastActivity: day(9) });

    expect(index.load()).toEqual([entry(1, { lastActivity: day(9) }), entry(2)]);
  });

  it('título acima de 60 caracteres é cortado com "…"', () => {
    const index = createThreadIndex(() => fakeStorage());

    index.upsert({ id: uuid(1), firstQuestion: 'a'.repeat(80), lastActivity: day(1) });

    const [first] = index.load();
    expect(first?.title).toHaveLength(60);
    expect(first?.title.endsWith('…')).toBe(true);
    expect(titleFrom('a'.repeat(60))).toBe('a'.repeat(60));
  });

  it('guarda no máximo 50 entradas: a mais antiga sai ao inserir a 51ª', () => {
    const stored = Array.from({ length: 50 }, (_, i) => entry(i + 1));
    const index = createThreadIndex(() => fakeStorage(JSON.stringify(stored)));

    index.upsert({ id: uuid(99), firstQuestion: 'Nova', lastActivity: day(99) });

    const ids = index.load().map((e) => e.id);
    expect(ids).toHaveLength(50);
    expect(ids[0]).toBe(uuid(99));
    expect(ids).not.toContain(uuid(1));
  });

  it('remove tira a entrada', () => {
    const index = createThreadIndex(() => fakeStorage(JSON.stringify([entry(1), entry(2)])));

    index.remove(uuid(1));

    expect(index.load()).toEqual([entry(2)]);
  });

  it('com localStorage que lança erro, funciona em memória sem lançar', () => {
    const broken = {
      getItem: () => {
        throw new DOMException('bloqueado', 'SecurityError');
      },
      setItem: () => {
        throw new DOMException('cheio', 'QuotaExceededError');
      },
    };
    const index = createThreadIndex(() => broken);

    expect(index.load()).toEqual([]);
    index.upsert({ id: uuid(1), firstQuestion: 'Pergunta', lastActivity: day(1) });
    expect(index.load().map((e) => e.id)).toEqual([uuid(1)]);
    index.remove(uuid(1));
    expect(index.load()).toEqual([]);
  });

  it('sem localStorage nenhum (acesso lança), também funciona em memória', () => {
    const index = createThreadIndex(() => {
      throw new DOMException('negado', 'SecurityError');
    });

    index.upsert({ id: uuid(1), firstQuestion: 'Pergunta', lastActivity: day(1) });

    expect(index.load()).toHaveLength(1);
  });

  it('avisa os inscritos a cada mudança', () => {
    const index = createThreadIndex(() => fakeStorage());
    const listener = vi.fn();
    const unsubscribe = index.subscribe(listener);

    index.upsert({ id: uuid(1), firstQuestion: 'P', lastActivity: day(1) });
    index.remove(uuid(1));
    unsubscribe();
    index.upsert({ id: uuid(2), firstQuestion: 'P', lastActivity: day(2) });

    expect(listener).toHaveBeenCalledTimes(2);
  });
});
