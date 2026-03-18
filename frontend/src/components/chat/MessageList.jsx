import MessageBubble from './MessageBubble';
import TypingIndicator from './TypingIndicator';
import WelcomeScreen from './WelcomeScreen';

export default function MessageList({ messages, loading, bottomRef, auth, sessionId, token, onSend }) {
  const initial = auth?.username?.[0]?.toUpperCase() ?? 'U';

  return (
    <div style={{
      flex: 1,
      overflowY: 'auto',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {messages.length === 0 && !loading
        ? <WelcomeScreen username={auth?.username} role={auth?.role} />
        : (
          <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 16 }}>
            {messages.map(msg => (
              <MessageBubble key={msg.id} message={msg} userInitial={initial} sessionId={sessionId} token={token} onSend={onSend} />
            ))}
            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>
        )
      }
    </div>
  );
}
