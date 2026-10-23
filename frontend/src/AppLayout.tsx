import { useEffect, useState, type ReactNode } from 'react';

import { Button } from './design-system/components/Button';
import './AppLayout.css';

export interface AppLayoutProps {
  /** Lista de conversas (ThreadSidebar). */
  sidebar?: ReactNode;
  title?: string;
  threadId?: string | null;
  /** Conteúdo do log: mensagens, avisos, erros. */
  children?: ReactNode;
  /** Composer fixo no rodapé. */
  composer?: ReactNode;
}

const SIDEBAR_ID = 'app-sidebar';

/** `6f1c2a9e-…-0d2f8e7c1a23` → `6f1c2a9e…1a23`, como no ChatScreen do design system. */
function shortThreadId(id: string): string {
  return id.length > 12 ? `${id.slice(0, 8)}…${id.slice(-4)}` : id;
}

export function AppLayout({
  sidebar,
  title = 'Nova conversa',
  threadId,
  children,
  composer,
}: AppLayoutProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setDrawerOpen(false);
    };
    // Abrir uma conversa (ou começar outra) muda o hash: a gaveta fecha no celular.
    const onNavigate = () => setDrawerOpen(false);
    window.addEventListener('keydown', onKey);
    window.addEventListener('hashchange', onNavigate);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('hashchange', onNavigate);
    };
  }, [drawerOpen]);

  return (
    <div className={drawerOpen ? 'app is-drawer-open' : 'app'}>
      <aside id={SIDEBAR_ID} className="app-sidebar">
        <div className="app-brand">Financial Agent</div>
        {sidebar}
      </aside>
      {drawerOpen ? (
        // Fundo da gaveta no celular: tocar fora fecha (Esc e o botão também fecham).
        <div className="app-scrim" aria-hidden="true" onClick={() => setDrawerOpen(false)} />
      ) : null}
      <main className="app-main">
        <header className="app-top">
          <Button
            className="app-drawer-toggle"
            aria-expanded={drawerOpen}
            aria-controls={SIDEBAR_ID}
            onClick={() => setDrawerOpen((open) => !open)}
          >
            Conversas
          </Button>
          <h1 className="app-title type-title">{title}</h1>
          {threadId ? (
            <span className="app-thread-id type-mono" title={threadId}>
              thread {shortThreadId(threadId)}
            </span>
          ) : null}
        </header>
        <div className="app-log" role="log" aria-label="Conversa">
          {children}
        </div>
        {composer ? <div className="app-dock">{composer}</div> : null}
      </main>
    </div>
  );
}
