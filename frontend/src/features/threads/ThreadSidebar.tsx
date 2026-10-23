import { ThreadList } from '../../design-system/components/ThreadList';
import { formatRelativeDay } from '../../lib/format';
import { threadPath, useThreadIndex } from './threadIndex';

interface ThreadSidebarProps {
  activeId?: string;
  onNew: () => void;
}

/** Conversas deste navegador. Abrir uma muda o hash da URL, e o App carrega o histórico. */
export function ThreadSidebar({ activeId, onNew }: ThreadSidebarProps) {
  const entries = useThreadIndex();
  return (
    <ThreadList
      threads={entries.map(({ id, title, lastActivity }) => ({
        id,
        title,
        lastActivity: formatRelativeDay(lastActivity),
      }))}
      activeId={activeId}
      onSelect={(id) => {
        window.location.hash = threadPath(id);
      }}
      onNew={onNew}
      footnote="Conversas sem atividade por 30 dias são apagadas."
    />
  );
}
