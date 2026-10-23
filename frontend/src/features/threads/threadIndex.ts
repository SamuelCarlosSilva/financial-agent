// Índice das conversas deste navegador (data-model.md, ThreadIndexEntry; research §7).
import { useSyncExternalStore } from 'react';

export const THREADS_KEY = 'finagent.threads.v1';
export const MAX_THREADS = 50;
const TITLE_MAX = 60;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export interface ThreadIndexEntry {
  id: string;
  /** Primeira pergunta, cortada em 60 caracteres com "…". */
  title: string;
  /** ISO-8601 da última resposta recebida. */
  lastActivity: string;
}

/** O que o índice usa do `localStorage`. */
export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export function isThreadId(value: string): boolean {
  return UUID.test(value);
}

/** Hash da URL de uma conversa: `#/t/<thread_id>`; `#/` é uma conversa nova. */
export function threadPath(id?: string): string {
  return id ? `#/t/${id}` : '#/';
}

/** O `thread_id` de um hash `#/t/<id>`, se for um id válido. */
export function threadFromHash(hash: string): string | undefined {
  const id = /^#\/t\/([^/]+)$/.exec(hash)?.[1];
  return id && isThreadId(id) ? id : undefined;
}

/** Título da conversa: a primeira pergunta, cortada em 60 caracteres com "…". */
export function titleFrom(question: string | undefined): string | undefined {
  const text = question?.trim().replace(/\s+/g, ' ');
  if (!text) return undefined;
  return text.length > TITLE_MAX ? `${text.slice(0, TITLE_MAX - 1).trimEnd()}…` : text;
}

function isEntry(value: unknown): value is ThreadIndexEntry {
  if (typeof value !== 'object' || value === null) return false;
  const { id, title, lastActivity } = value as Record<string, unknown>;
  return (
    typeof id === 'string' &&
    isThreadId(id) &&
    typeof title === 'string' &&
    title.length >= 1 &&
    title.length <= TITLE_MAX &&
    typeof lastActivity === 'string' &&
    !Number.isNaN(Date.parse(lastActivity))
  );
}

/** Mais recente primeiro, no máximo 50. */
function normalize(entries: ThreadIndexEntry[]): ThreadIndexEntry[] {
  return [...entries]
    .sort((a, b) => Date.parse(b.lastActivity) - Date.parse(a.lastActivity))
    .slice(0, MAX_THREADS);
}

/** JSON inválido ou formato desconhecido vira índice vazio; entradas inválidas são descartadas. */
function parse(raw: string | null): ThreadIndexEntry[] {
  if (raw === null) return [];
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return [];
  }
  return Array.isArray(data) ? normalize(data.filter(isEntry)) : [];
}

/**
 * Índice guardado em `storage`. Se o storage lançar erro (modo privado, cota, bloqueio), o
 * índice passa a viver só em memória até o fim da sessão, sem quebrar a tela.
 */
export function createThreadIndex(getStorage: () => StorageLike) {
  let memory: ThreadIndexEntry[] = [];
  let usable = true;
  // Snapshot estável para o useSyncExternalStore: só muda quando o índice muda.
  let snapshot: ThreadIndexEntry[] | null = null;
  const listeners = new Set<() => void>();

  function read(): ThreadIndexEntry[] {
    if (!usable) return memory;
    try {
      return parse(getStorage().getItem(THREADS_KEY));
    } catch {
      usable = false;
      return memory;
    }
  }

  function write(entries: ThreadIndexEntry[]) {
    memory = entries;
    snapshot = entries;
    if (usable) {
      try {
        getStorage().setItem(THREADS_KEY, JSON.stringify(entries));
      } catch {
        usable = false;
      }
    }
    listeners.forEach((listener) => listener());
  }

  function load(): ThreadIndexEntry[] {
    snapshot ??= read();
    return snapshot;
  }

  return {
    load,

    /** Cria a entrada (título da primeira pergunta) ou só atualiza `lastActivity`. */
    upsert({
      id,
      firstQuestion,
      lastActivity,
    }: {
      id: string;
      firstQuestion: string;
      lastActivity: string;
    }) {
      const list = load();
      const existing = list.find((entry) => entry.id === id);
      const entry = existing
        ? { ...existing, lastActivity }
        : { id, title: titleFrom(firstQuestion) ?? 'Nova conversa', lastActivity };
      write(normalize([entry, ...list.filter((e) => e.id !== id)]));
    },

    remove(id: string) {
      write(load().filter((entry) => entry.id !== id));
    },

    /** Relê o storage (ex.: mudança feita em outra aba). */
    refresh() {
      snapshot = null;
      listeners.forEach((listener) => listener());
    },

    subscribe(listener: () => void): () => void {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

export const threadIndex = createThreadIndex(() => window.localStorage);

function subscribe(listener: () => void): () => void {
  const onStorage = (event: StorageEvent) => {
    if (event.key === THREADS_KEY) threadIndex.refresh();
  };
  window.addEventListener('storage', onStorage);
  const unsubscribe = threadIndex.subscribe(listener);
  return () => {
    window.removeEventListener('storage', onStorage);
    unsubscribe();
  };
}

/** Entradas do índice, atualizadas a cada mudança (nesta aba ou em outra). */
export function useThreadIndex(): ThreadIndexEntry[] {
  return useSyncExternalStore(subscribe, threadIndex.load);
}
