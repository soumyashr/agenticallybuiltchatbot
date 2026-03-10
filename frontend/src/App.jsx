import { useState } from 'react';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './hooks/useAuth';
import { useChat } from './hooks/useChat';
import { THEME } from './config/theme';

import LoginScreen  from './components/auth/LoginScreen';
import Sidebar      from './components/layout/Sidebar';
import Header       from './components/layout/Header';
import MessageList  from './components/chat/MessageList';
import ChatInput    from './components/input/ChatInput';
import AdminPanel   from './components/admin/AdminPanel';

function AppShell() {
  const { auth, loading, error, handleLogin, logout, isAdmin } = useAuth();
  const { messages, loading: chatLoading, send, newChat, bottomRef, sessionId } = useChat(auth?.token);
  const [activeTab, setActiveTab] = useState('chat');

  function handleLogout() {
    newChat();
    logout();
  }

  if (!auth) {
    return <LoginScreen onLogin={handleLogin} loading={loading} error={error} />;
  }

  return (
    <div style={{
      display: 'flex', height: '100vh', width: '100%',
      background: THEME.bgDeep, fontFamily: THEME.fontBase, overflow: 'hidden',
    }}>
      <Sidebar auth={auth} onNewChat={newChat} onLogout={handleLogout} onAskQuestion={send} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Header activeTab={activeTab} onTabChange={setActiveTab} isAdmin={isAdmin} />
        {activeTab === 'chat' ? (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <MessageList messages={messages} loading={chatLoading} bottomRef={bottomRef} auth={auth} sessionId={sessionId} token={auth.token} />
            <ChatInput onSend={send} disabled={chatLoading} />
          </div>
        ) : (
          <AdminPanel token={auth.token} />
        )}
      </div>
    </div>
  );
}

export default function App() {
  return <AuthProvider><AppShell /></AuthProvider>;
}
