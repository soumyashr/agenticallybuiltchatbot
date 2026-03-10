import { useState, useRef, useCallback, useEffect } from 'react';
import { sendMessage, clearSession } from '../services/api';
import { CHAT_CONFIG } from '../config/constants';

function newSessionId() {
  return CHAT_CONFIG.sessionIdPrefix + Date.now();
}

export function useChat(token) {
  const [messages,  setMessages]  = useState([]);
  const [loading,   setLoading]   = useState(false);
  const [sessionId, setSessionId] = useState(newSessionId);
  const bottomRef = useRef(null);

  // Reset chat state whenever auth token changes (new login / logout)
  useEffect(() => {
    setMessages([]);
    setLoading(false);
    setSessionId(newSessionId());
  }, [token]);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
  }, []);

  const send = useCallback(async (text) => {
    if (!text.trim() || loading) return;

    const userMsg = { id: Date.now(), role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);
    scrollToBottom();

    try {
      const data = await sendMessage(token, text, sessionId);
      const aiMsg = {
        id:             Date.now() + 1,
        role:           'assistant',
        content:        data.answer,
        sources:        data.sources        || [],
        reasoningSteps: data.reasoning_steps ?? 0,
        userQuery:      text,
      };
      setMessages(prev => [...prev, aiMsg]);
    } catch (err) {
      setMessages(prev => [...prev, {
        id:      Date.now() + 1,
        role:    'error',
        content: 'Something went wrong. Please try again.',
      }]);
    } finally {
      setLoading(false);
      scrollToBottom();
    }
  }, [token, sessionId, loading, scrollToBottom]);

  const newChat = useCallback(async () => {
    await clearSession(token, sessionId).catch(() => {});
    setMessages([]);
    setSessionId(newSessionId());
  }, [token, sessionId]);

  return { messages, loading, send, newChat, bottomRef, sessionId };
}
