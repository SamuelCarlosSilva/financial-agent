import { useEffect } from 'react';

import { AppLayout } from './AppLayout';
import { Composer } from './design-system/components/Composer';
import { ErrorBanner } from './design-system/components/ErrorBanner';
import { ChatView } from './features/chat/ChatView';
import { useConversation } from './features/chat/useConversation';
import { useServiceHealth } from './features/chat/useServiceHealth';
import { ThreadSidebar } from './features/threads/ThreadSidebar';
import {
  threadFromHash,
  threadPath,
  titleFrom,
  useThreadIndex,
} from './features/threads/threadIndex';

function replaceHash(hash: string) {
  if (window.location.hash !== hash) window.history.replaceState(null, '', hash);
}

export function App() {
  const {
    threadId,
    turns,
    status,
    expired,
    loadError,
    submit,
    retry,
    openThread,
    newConversation,
  } = useConversation();
  const entries = useThreadIndex();
  const health = useServiceHealth();

  // A URL segue a conversa: `#/t/<id>` quando ela ganha id, `#/` quando expira.
  useEffect(() => {
    if (threadId) replaceHash(threadPath(threadId));
    else if (expired) replaceHash(threadPath());
  }, [threadId, expired]);

  // E a conversa segue a URL: na carga, no Voltar/Avançar e ao escolher na lista.
  useEffect(() => {
    function sync() {
      const id = threadFromHash(window.location.hash);
      if (id) {
        void openThread(id);
        return;
      }
      newConversation();
      replaceHash(threadPath());
    }
    sync();
    window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, [openThread, newConversation]);

  const title =
    entries.find((entry) => entry.id === threadId)?.title ?? titleFrom(turns[0]?.question);

  return (
    <AppLayout
      sidebar={
        <ThreadSidebar
          activeId={threadId}
          onNew={() => {
            newConversation();
            window.location.hash = threadPath();
          }}
        />
      }
      title={title}
      threadId={threadId}
      composer={<Composer busy={status !== 'idle'} onSubmit={(m) => void submit(m)} />}
    >
      {/* Fica no topo enquanto o serviço estiver fora; o composer continua usável. */}
      {health.down ? <ErrorBanner {...health.down} onRetry={() => void health.recheck()} /> : null}
      <ChatView
        turns={turns}
        status={status}
        expired={expired}
        loadError={loadError}
        onRetry={(id) => void retry(id)}
        onReloadThread={() => {
          if (threadId) void openThread(threadId);
        }}
      />
    </AppLayout>
  );
}
