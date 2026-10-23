// Portado do design system Financial Agent (Claude Design), versão 1792443906-b50c
import { Button } from './Button';
import './ThreadList.css';

export interface ThreadSummary {
  id: string;
  title: string;
  /** Última atividade já formatada ("hoje, 09:41", "ontem", "12/10"). */
  lastActivity: string;
}

export interface ThreadListProps {
  threads: ThreadSummary[];
  activeId?: string;
  onSelect?: (id: string) => void;
  onNew?: () => void;
  footnote?: string;
}

/** Conversas deste navegador, com "Nova conversa" no topo e a conversa aberta marcada. */
export function ThreadList({ threads, activeId, onSelect, onNew, footnote }: ThreadListProps) {
  return (
    <nav className="fa-threads" aria-label="Conversas">
      {onNew ? (
        <Button className="fa-threads-new" onClick={onNew}>
          Nova conversa
        </Button>
      ) : null}
      <ul>
        {threads.map((thread) => {
          const active = thread.id === activeId;
          return (
            <li key={thread.id}>
              <button
                type="button"
                className={active ? 'fa-thread is-active' : 'fa-thread'}
                aria-current={active ? 'page' : undefined}
                onClick={onSelect ? () => onSelect(thread.id) : undefined}
              >
                <span className="fa-thread-title">{thread.title}</span>
                <span className="fa-thread-meta">{thread.lastActivity}</span>
              </button>
            </li>
          );
        })}
      </ul>
      {footnote ? <p className="fa-threads-foot">{footnote}</p> : null}
    </nav>
  );
}
