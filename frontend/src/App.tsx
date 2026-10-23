import { AppLayout } from './AppLayout';
import { Composer } from './design-system/components/Composer';
import { ChatView } from './features/chat/ChatView';
import { useConversation } from './features/chat/useConversation';

const TITLE_MAX = 60;

/** Título da conversa: a primeira pergunta, cortada em 60 caracteres com "…". */
function conversationTitle(question: string | undefined): string | undefined {
  const text = question?.trim().replace(/\s+/g, ' ');
  if (!text) return undefined;
  return text.length > TITLE_MAX ? `${text.slice(0, TITLE_MAX - 1).trimEnd()}…` : text;
}

export function App() {
  const { threadId, turns, status, submit } = useConversation();

  return (
    <AppLayout
      title={conversationTitle(turns[0]?.question)}
      threadId={threadId}
      composer={<Composer busy={status === 'sending'} onSubmit={(m) => void submit(m)} />}
    >
      <ChatView turns={turns} />
    </AppLayout>
  );
}
