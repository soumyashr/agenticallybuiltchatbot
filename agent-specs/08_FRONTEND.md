# 08 — FRONTEND.md
# For Claude Code: WRITE ALL CODE IN THIS FILE.
# Build the complete React frontend with HM branding.
# Prerequisites: 07_ADMIN_API.md must be COMPLETE and VERIFIED.

---

## STEP 1 — Scaffold Frontend

Run these commands exactly:
```bash
cd /Users/soumya.shrivastava/AgenticallyBuiltChatBot
npm create vite@latest frontend -- --template react
cd frontend
npm install
```

---

## STEP 2 — vite.config.js

Overwrite `frontend/vite.config.js`:
```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/auth': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    }
  }
})
```

---

## STEP 3 — index.html

Overwrite `frontend/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="icon" type="image/png" href="/favicon.png" />
    <title>Happiest Minds Knowledge Hub</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Montserrat:wght@700&display=swap" rel="stylesheet" />
    <style>
      *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
      html, body, #root { height: 100%; width: 100%; overflow: hidden; }
      body { font-family: 'Inter', sans-serif; background: #1A1A2E; color: #FFFFFF; }
    </style>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

---

## STEP 4 — src/config/theme.js

Write to `frontend/src/config/theme.js`:
```js
export const THEME = {
  // ── HM Brand Colors ──────────────────────────
  green:         '#3AB54A',
  greenHover:    '#2E9640',
  greenLight:    '#E8F8EA',
  greenDim:      '#E8F8EA',

  // ── Light Surfaces ───────────────────────────
  bgDeep:        '#FFFFFF',   // page background
  bgCard:        '#F8F9FA',   // cards, panels
  bgMid:         '#E8F8EA',   // secondary panels, hover
  bgBorder:      '#E2E8F0',   // borders

  // ── Sidebar (light, HM brand) ────────────────
  sidebarBg:     '#FFFFFF',
  sidebarText:   '#1A1A2E',
  sidebarMuted:  '#666666',
  sidebarBorder: '#E2E8F0',

  // ── Text ─────────────────────────────────────
  textLight:     '#1A1A2E',   // primary body text (dark on light bg)
  textMuted:     '#666666',
  textDark:      '#1A1A2E',
  textBody:      '#334155',

  // ── Buttons ──────────────────────────────────
  buttonText:    '#FFFFFF',

  // ── Status ───────────────────────────────────
  error:         '#EF4444',
  errorBg:       '#FEF2F2',
  warning:       '#F59E0B',
  info:          '#3B82F6',

  // ── Fonts ────────────────────────────────────
  fontBase:      "'Inter', sans-serif",
  fontMono:      "'JetBrains Mono', 'Fira Code', monospace",

  // ── Sizing ───────────────────────────────────
  sidebarWidth:  '260px',
  headerHeight:  '56px',
  borderRadius:  '8px',
  borderRadiusLg:'12px',

  // ── Shadows ──────────────────────────────────
  shadowSm:      '0 1px 3px rgba(0,0,0,0.08)',
  shadowMd:      '0 4px 12px rgba(0,0,0,0.1)',
  shadowLg:      '0 8px 24px rgba(0,0,0,0.12)',
};

export const ROLE_STYLES = {
  admin: {
    bg:     '#3AB54A',
    text:   '#0A1A0A',
    label:  '⚙ ADMIN',
  },
  faculty: {
    bg:     '#0F3460',
    text:   '#FFFFFF',
    label:  '👤 FACULTY',
  },
  student: {
    bg:     'transparent',
    text:   '#3AB54A',
    border: '1px solid #3AB54A',
    label:  '📚 STUDENT',
  },
};
```

---

## STEP 5 — src/config/constants.js

Write to `frontend/src/config/constants.js`:
```js
export const BRAND = {
  name:    'Happiest Minds Knowledge Hub',
  tagline: 'The Mindful IT Company · AI-powered',
  company: 'Happiest Minds Technologies',
  version: '1.0',
};

export const API_BASE = import.meta.env.VITE_API_URL || '';
// Empty in dev (Vite proxy handles routing)
// Set VITE_API_URL at build time for Docker/AWS deployments

export const CHAT_CONFIG = {
  maxChars:        1000,
  typingDelayMs:   400,
  sessionIdPrefix: 'hm-session-',
};

export const ADMIN_POLL_INTERVAL_MS = 2000;  // Status poll during ingest
```

---

## STEP 6 — src/services/api.js

Write to `frontend/src/services/api.js`:
```js
import { API_BASE } from '../config/constants';

function authHeaders(token) {
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
  };
}

// ── Auth ──────────────────────────────────────────────────────
export async function login(username, password) {
  const form = new FormData();
  form.append('username', username);
  form.append('password', password);
  const res = await fetch(`${API_BASE}/auth/token`, { method: 'POST', body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Login failed');
  }
  return res.json();   // { access_token, username, role }
}

// ── Chat ──────────────────────────────────────────────────────
export async function sendMessage(token, message, sessionId) {
  const res = await fetch(`${API_BASE}/chat`, {
    method:  'POST',
    headers: authHeaders(token),
    body:    JSON.stringify({ message, session_id: sessionId }),
  });
  if (!res.ok) throw new Error('Chat request failed');
  return res.json();   // { answer, sources, reasoning_steps, session_id, role }
}

export async function clearSession(token, sessionId) {
  await fetch(`${API_BASE}/chat/clear`, {
    method:  'POST',
    headers: authHeaders(token),
    body:    JSON.stringify({ message: '', session_id: sessionId }),
  });
}

// ── Admin ─────────────────────────────────────────────────────
export async function fetchDocuments(token) {
  const res = await fetch(`${API_BASE}/admin/documents`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Failed to fetch documents');
  return res.json();
}

// ── User Documents (any role) ────────────────────────────────
export async function fetchMyDocuments(token) {
  const res = await fetch(`${API_BASE}/documents/my`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Failed to fetch my documents');
  return res.json();   // [{ id, display_name, allowed_roles, chunk_count }]
}

export async function uploadDocument(token, file, displayName, allowedRoles) {
  const form = new FormData();
  form.append('file', file);
  form.append('display_name', displayName);
  form.append('allowed_roles', JSON.stringify(allowedRoles));
  const res = await fetch(`${API_BASE}/admin/documents/upload`, {
    method:  'POST',
    headers: { Authorization: `Bearer ${token}` },
    body:    form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Upload failed');
  }
  return res.json();
}

export async function ingestDocuments(token) {
  const res = await fetch(`${API_BASE}/admin/documents/ingest`, {
    method:  'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Ingest failed');
  return res.json();
}

export async function deleteDocument(token, docId) {
  const res = await fetch(`${API_BASE}/admin/documents/${docId}`, {
    method:  'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Delete failed');
  return res.json();
}

export async function pollDocumentStatus(token, docId) {
  const res = await fetch(`${API_BASE}/admin/documents/${docId}/status`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Status poll failed');
  return res.json();
}
```

---

## STEP 7 — src/context/AuthContext.jsx

Write to `frontend/src/context/AuthContext.jsx`:
```jsx
import { createContext, useContext, useState, useCallback } from 'react';
import { login as apiLogin } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(() => {
    const stored = sessionStorage.getItem('hm_auth');
    return stored ? JSON.parse(stored) : null;
  });

  const login = useCallback(async (username, password) => {
    const data = await apiLogin(username, password);
    const authData = {
      token:    data.access_token,
      username: data.username,
      role:     data.role,
    };
    sessionStorage.setItem('hm_auth', JSON.stringify(authData));
    setAuth(authData);
    return authData;
  }, []);

  const logout = useCallback(() => {
    sessionStorage.removeItem('hm_auth');
    setAuth(null);
  }, []);

  return (
    <AuthContext.Provider value={{ auth, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuthContext() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuthContext must be used inside AuthProvider');
  return ctx;
}
```

---

## STEP 8 — src/hooks/useAuth.js

Write to `frontend/src/hooks/useAuth.js`:
```js
import { useState } from 'react';
import { useAuthContext } from '../context/AuthContext';

export function useAuth() {
  const { auth, login, logout } = useAuthContext();
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState('');

  async function handleLogin(username, password) {
    setLoading(true);
    setError('');
    try {
      await login(username, password);
    } catch (err) {
      setError(err.message || 'Login failed. Check your credentials.');
    } finally {
      setLoading(false);
    }
  }

  return {
    auth,
    loading,
    error,
    handleLogin,
    logout,
    isAdmin:   auth?.role === 'admin',
    isFaculty: auth?.role === 'faculty',
    isStudent: auth?.role === 'student',
    initial:   auth?.username?.[0]?.toUpperCase() ?? 'U',
  };
}
```

---

## STEP 9 — src/hooks/useChat.js

Write to `frontend/src/hooks/useChat.js`:
```js
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

  return { messages, loading, send, newChat, bottomRef };
}
```

---

## STEP 10 — src/hooks/useDocuments.js

Write to `frontend/src/hooks/useDocuments.js`:
```js
import { useState, useCallback } from 'react';
import {
  fetchDocuments, uploadDocument,
  ingestDocuments, deleteDocument,
} from '../services/api';

export function useDocuments(token) {
  const [docs,    setDocs]    = useState({ pending: [], ingested: [], failed: [], total: 0 });
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState('');
  const [success, setSuccess] = useState('');

  const refresh = useCallback(async () => {
    try {
      const data = await fetchDocuments(token);
      setDocs(data);
    } catch { /* ignore poll errors */ }
  }, [token]);

  const upload = useCallback(async (file, displayName, allowedRoles) => {
    setLoading(true); setError(''); setSuccess('');
    try {
      await uploadDocument(token, file, displayName, allowedRoles);
      setSuccess(`"${displayName}" uploaded. Click Ingest Now to make it searchable.`);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, refresh]);

  const ingest = useCallback(async () => {
    setLoading(true); setError(''); setSuccess('');
    try {
      const result = await ingestDocuments(token);
      setSuccess(result.message);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, refresh]);

  const remove = useCallback(async (docId) => {
    setLoading(true); setError(''); setSuccess('');
    try {
      const result = await deleteDocument(token, docId);
      setSuccess(`"${result.filename}" deleted.`);
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, refresh]);

  return { docs, loading, error, success, refresh, upload, ingest, remove };
}
```

---

## STEP 11 — Components (write each file exactly)

### src/components/auth/LoginScreen.jsx
```jsx
import { useState } from 'react';
import { THEME } from '../../config/theme';
import { BRAND } from '../../config/constants';
import hmLogo from '../../assets/hm_logo.png';

export default function LoginScreen({ onLogin, loading, error }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  function handleSubmit(e) {
    e.preventDefault();
    onLogin(username, password);
  }

  return (
    <div style={{
      display: 'flex', height: '100vh', width: '100%',
      background: THEME.bgDeep, fontFamily: THEME.fontBase,
    }}>
      {/* Left panel */}
      <div style={{
        width: '45%', background: THEME.bgCard,
        display: 'flex', flexDirection: 'column',
        padding: '24px 50px',
        borderRight: `1px solid ${THEME.bgBorder}`,
      }}>
        <div style={{ marginBottom: 40 }}>
          <img src={hmLogo} alt="Happiest Minds" style={{ height: 48, objectFit: 'contain' }} />
        </div>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
        <h1 style={{
          fontSize: 36, fontWeight: 700, color: THEME.textLight,
          lineHeight: 1.2, marginBottom: 16,
        }}>
          Happiest Minds Knowledge<br />
          <span style={{ color: THEME.green }}>Hub</span>
        </h1>
        <p style={{ color: THEME.textMuted, fontSize: 15, lineHeight: 1.7, marginBottom: 40 }}>
          Ask questions. Get grounded answers from internal documents — with sources cited and access controlled by your role.
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[
            { icon: '🔒', text: 'Role-based document access' },
            { icon: '📄', text: 'Cited answers with page references' },
            { icon: '🤖', text: 'Powered by GPT-4o + LangChain' },
          ].map(f => (
            <div key={f.text} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 16 }}>{f.icon}</span>
              <span style={{ color: THEME.textMuted, fontSize: 13 }}>{f.text}</span>
            </div>
          ))}
        </div>
        </div>
      </div>

      {/* Right panel — login form */}
      <div style={{
        flex: 1, display: 'flex', alignItems: 'center',
        justifyContent: 'center', padding: '40px',
      }}>
        <div style={{ width: '100%', maxWidth: 400 }}>
          <h2 style={{
            fontSize: 24, fontWeight: 600,
            color: THEME.textLight, marginBottom: 8,
          }}>Sign in</h2>
          <p style={{ color: THEME.textMuted, fontSize: 14, marginBottom: 32 }}>
            Use your Happiest Minds credentials
          </p>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label style={{ display: 'block', color: THEME.textMuted, fontSize: 12, fontWeight: 500, marginBottom: 6, letterSpacing: '0.05em' }}>
                USERNAME
              </label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="e.g. admin"
                required
                style={{
                  width: '100%', padding: '12px 14px',
                  background: THEME.bgCard, border: `1px solid ${THEME.bgBorder}`,
                  borderRadius: THEME.borderRadius, color: THEME.textLight,
                  fontSize: 14, outline: 'none', fontFamily: THEME.fontBase,
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', color: THEME.textMuted, fontSize: 12, fontWeight: 500, marginBottom: 6, letterSpacing: '0.05em' }}>
                PASSWORD
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                style={{
                  width: '100%', padding: '12px 14px',
                  background: THEME.bgCard, border: `1px solid ${THEME.bgBorder}`,
                  borderRadius: THEME.borderRadius, color: THEME.textLight,
                  fontSize: 14, outline: 'none', fontFamily: THEME.fontBase,
                }}
              />
            </div>

            {error && (
              <div style={{
                background: THEME.errorBg, border: `1px solid ${THEME.error}`,
                borderRadius: THEME.borderRadius, padding: '10px 14px',
                color: THEME.error, fontSize: 13,
              }}>{error}</div>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%', padding: '13px',
                background: loading ? THEME.bgMid : THEME.green,
                color: loading ? THEME.textMuted : THEME.buttonText,
                border: 'none', borderRadius: THEME.borderRadius,
                fontSize: 14, fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer',
                fontFamily: THEME.fontBase, transition: 'background 0.2s',
              }}
            >
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>

          <div style={{
            marginTop: 32, padding: 16,
            background: THEME.bgCard, borderRadius: THEME.borderRadius,
            border: `1px solid ${THEME.bgBorder}`,
          }}>
            <p style={{ color: THEME.textMuted, fontSize: 11, marginBottom: 8 }}>TEST CREDENTIALS</p>
            {[
              { u: 'admin',    p: 'HMAdmin@2024',   r: 'admin'   },
              { u: 'faculty1', p: 'HMFaculty@2024', r: 'faculty' },
              { u: 'student1', p: 'HMStudent@2024', r: 'student' },
            ].map(c => (
              <p key={c.u} style={{ color: THEME.textMuted, fontSize: 11, marginBottom: 2 }}>
                <span style={{ color: THEME.green, fontWeight: 600 }}>{c.u}</span> / {c.p}
                <span style={{ color: THEME.textMuted, marginLeft: 6 }}>({c.r})</span>
              </p>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
```

### src/components/layout/Sidebar.jsx

**Current implementation** uses the HM logo image, fetches accessible documents via
`GET /documents/my`, and generates dynamic "Try asking..." questions based on document names.

Key features:
- **Header**: HM logo image (36px) + "Happiest Minds" / "Knowledge Hub" in Montserrat bold white 13px
- **Dynamic questions**: Fetches `/documents/my` on mount, generates questions via keyword matching
  (Syllabus, Minutes, Manual, Protocol, Blueprint → contextual question templates)
- **"Try asking..." label**: 10px, uppercase, bold, teal #009797
- **Question cards**: #F0FAF0 bg, #009797 text, #39B54A border, 8px radius
- **No tagline at bottom** (removed)
- Accepts `onAskQuestion` prop from App.jsx (sends question to chat)

```jsx
import { useState, useEffect } from 'react';
import { THEME, ROLE_STYLES } from '../../config/theme';
import { BRAND } from '../../config/constants';
import { fetchMyDocuments } from '../../services/api';
import hmLogo from '../../assets/hm_logo.png';

// (see full source in frontend/src/components/layout/Sidebar.jsx)
export default function Sidebar({ auth, onNewChat, onLogout, onAskQuestion }) {
  // ... fetches documents, generates questions, renders sidebar
}
```

### src/components/layout/Header.jsx
```jsx
import { THEME } from '../../config/theme';

export default function Header({ activeTab, onTabChange, isAdmin }) {
  return (
    <div style={{
      height: THEME.headerHeight, background: THEME.bgCard,
      borderBottom: `1px solid ${THEME.bgBorder}`,
      display: 'flex', alignItems: 'center',
      padding: '0 20px', gap: 4, flexShrink: 0,
    }}>
      {['chat', isAdmin && 'documents'].filter(Boolean).map(tab => (
        <button
          key={tab}
          onClick={() => onTabChange(tab)}
          style={{
            padding: '6px 16px',
            background: activeTab === tab ? THEME.bgMid : 'transparent',
            color: activeTab === tab ? THEME.textLight : THEME.textMuted,
            border: activeTab === tab ? `1px solid ${THEME.bgBorder}` : '1px solid transparent',
            borderRadius: 6, fontSize: 13, fontWeight: 500,
            cursor: 'pointer', fontFamily: THEME.fontBase,
            textTransform: 'capitalize',
          }}
        >
          {tab === 'chat' ? '💬 Chat' : '📁 Documents'}
        </button>
      ))}
    </div>
  );
}
```

### src/components/chat/WelcomeScreen.jsx
```jsx
import { THEME } from '../../config/theme';
import { BRAND } from '../../config/constants';

export default function WelcomeScreen({ username, role }) {
  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: '40px 20px', textAlign: 'center',
    }}>
      <div style={{
        width: 64, height: 64, borderRadius: 16,
        background: THEME.greenDim, border: `2px solid ${THEME.green}`,
        display: 'flex', alignItems: 'center',
        justifyContent: 'center', fontSize: 28, marginBottom: 20,
      }}>🤖</div>

      <h2 style={{ fontSize: 22, fontWeight: 700, color: THEME.textLight, marginBottom: 8 }}>
        Welcome back, {username}
      </h2>
      <p style={{ color: THEME.textMuted, fontSize: 14, maxWidth: 420, lineHeight: 1.6, marginBottom: 28 }}>
        Ask any question about Happiest Minds internal documents. Answers are grounded in documents accessible to your <strong style={{ color: THEME.green }}>{role}</strong> role.
      </p>

      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '6px 14px', background: THEME.bgCard,
        border: `1px solid ${THEME.bgBorder}`, borderRadius: 20,
      }}>
        <span style={{ fontSize: 11, color: THEME.textMuted }}>
          Responses are sourced from internal documents only
        </span>
      </div>
    </div>
  );
}
```

### src/components/chat/TypingIndicator.jsx
```jsx
import { THEME } from '../../config/theme';

export default function TypingIndicator() {
  return (
    <div style={{ display: 'flex', gap: 12, padding: '4px 0', alignItems: 'flex-start' }}>
      <div style={{
        width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
        background: THEME.greenDim, border: `1px solid ${THEME.green}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 14,
      }}>🤖</div>
      <div style={{
        padding: '12px 16px', background: THEME.bgCard,
        borderRadius: '4px 12px 12px 12px',
        border: `1px solid ${THEME.bgBorder}`,
        display: 'flex', gap: 5, alignItems: 'center',
      }}>
        {[0, 1, 2].map(i => (
          <div key={i} style={{
            width: 7, height: 7, borderRadius: '50%',
            background: THEME.green, opacity: 0.7,
            animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
          }} />
        ))}
        <style>{`@keyframes bounce { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-6px)} }`}</style>
      </div>
    </div>
  );
}
```

### src/components/chat/MessageBubble.jsx
```jsx
import { useState } from 'react';
import { THEME } from '../../config/theme';

export default function MessageBubble({ message, userInitial }) {
  const [showSources, setShowSources] = useState(false);
  const isUser      = message.role === 'user';
  const isError     = message.role === 'error';
  const hasSources  = message.sources?.length > 0;
  const hasSteps    = message.reasoningSteps > 0;

  if (isUser) {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, alignItems: 'flex-end' }}>
        <div style={{
          maxWidth: '70%', padding: '12px 16px',
          background: THEME.bgMid, borderRadius: '12px 4px 12px 12px',
          border: `1px solid ${THEME.bgBorder}`,
          color: THEME.textLight, fontSize: 14, lineHeight: 1.6,
        }}>{message.content}</div>
        <div style={{
          width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
          background: THEME.green, color: '#0A1A0A',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 13, fontWeight: 700,
        }}>{userInitial}</div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
      <div style={{
        width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
        background: THEME.greenDim, border: `1px solid ${THEME.green}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14,
      }}>🤖</div>
      <div style={{ flex: 1, maxWidth: '80%' }}>
        <div style={{
          padding: '14px 16px',
          background: isError ? THEME.errorBg : THEME.bgCard,
          border: `1px solid ${isError ? THEME.error : THEME.bgBorder}`,
          borderRadius: '4px 12px 12px 12px',
          color: isError ? THEME.error : THEME.textLight,
          fontSize: 14, lineHeight: 1.7,
          whiteSpace: 'pre-wrap', wordBreak: 'break-word',
        }}>{message.content}</div>

        {/* Footer bar */}
        {(hasSources || hasSteps) && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 6 }}>
            {hasSteps && (
              <span style={{
                fontSize: 11, color: THEME.textMuted,
                background: THEME.bgCard, padding: '2px 8px',
                borderRadius: 10, border: `1px solid ${THEME.bgBorder}`,
              }}>⚡ {message.reasoningSteps} step{message.reasoningSteps !== 1 ? 's' : ''}</span>
            )}
            {hasSources && (
              <button
                onClick={() => setShowSources(s => !s)}
                style={{
                  fontSize: 11, color: THEME.green, background: 'transparent',
                  border: 'none', cursor: 'pointer', padding: 0,
                  fontFamily: THEME.fontBase,
                }}
              >
                {showSources ? '▲' : '▼'} {message.sources.length} source{message.sources.length !== 1 ? 's' : ''}
              </button>
            )}
          </div>
        )}

        {/* Sources panel */}
        {showSources && hasSources && (
          <div style={{
            marginTop: 6, padding: 12,
            background: THEME.bgDeep,
            border: `1px solid ${THEME.bgBorder}`,
            borderRadius: THEME.borderRadius,
            display: 'flex', flexDirection: 'column', gap: 8,
          }}>
            {message.sources.map((src, i) => (
              <div key={i} style={{
                padding: '8px 10px', background: THEME.bgCard,
                borderRadius: 6, borderLeft: `3px solid ${THEME.green}`,
              }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: THEME.green, marginBottom: 2 }}>
                  📄 {src.source}{src.page != null ? ` · Page ${src.page}` : ''}
                </p>
                {src.snippet && (
                  <p style={{ fontSize: 11, color: THEME.textMuted, lineHeight: 1.5 }}>
                    {src.snippet}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

### src/components/chat/MessageList.jsx
```jsx
import MessageBubble from './MessageBubble';
import TypingIndicator from './TypingIndicator';
import WelcomeScreen from './WelcomeScreen';

export default function MessageList({ messages, loading, bottomRef, auth }) {
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
              <MessageBubble key={msg.id} message={msg} userInitial={initial} />
            ))}
            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>
        )
      }
    </div>
  );
}
```

### src/components/input/ChatInput.jsx
```jsx
import { useState, useRef } from 'react';
import { THEME } from '../../config/theme';
import { CHAT_CONFIG } from '../../config/constants';

export default function ChatInput({ onSend, disabled }) {
  const [value, setValue] = useState('');
  const textareaRef = useRef(null);

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function submit() {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue('');
    if (textareaRef.current) textareaRef.current.style.height = '24px';
  }

  const remaining = CHAT_CONFIG.maxChars - value.length;

  return (
    <div style={{
      padding: '12px 16px',
      background: THEME.bgCard,
      borderTop: `1px solid ${THEME.bgBorder}`,
    }}>
      <div style={{
        display: 'flex', gap: 10, alignItems: 'flex-end',
        background: THEME.bgDeep, borderRadius: 10,
        border: `1px solid ${THEME.bgBorder}`, padding: '8px 12px',
      }}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => {
            setValue(e.target.value.slice(0, CHAT_CONFIG.maxChars));
            const el = textareaRef.current;
            if (el) {
              el.style.height = 'auto';
              el.style.height = Math.min(el.scrollHeight, 120) + 'px';
            }
          }}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="Ask about any internal document…"
          rows={1}
          style={{
            flex: 1, background: 'transparent', border: 'none', outline: 'none',
            color: THEME.textLight, fontSize: 14, fontFamily: THEME.fontBase,
            resize: 'none', lineHeight: 1.6, height: '24px', maxHeight: 120, overflowY: 'hidden',
          }}
        />
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
          <span style={{ fontSize: 10, color: remaining < 100 ? THEME.warning : THEME.textMuted }}>
            {remaining}
          </span>
          <button
            onClick={submit}
            disabled={disabled || !value.trim()}
            style={{
              width: 34, height: 34, borderRadius: 8, border: 'none',
              background: disabled || !value.trim() ? THEME.bgMid : THEME.green,
              color: disabled || !value.trim() ? THEME.textMuted : THEME.buttonText,
              cursor: disabled || !value.trim() ? 'not-allowed' : 'pointer',
              fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >↑</button>
        </div>
      </div>
      <p style={{ textAlign: 'center', fontSize: 10, color: THEME.textMuted, marginTop: 6 }}>
        Answers are sourced from internal documents only · Enter to send
      </p>
    </div>
  );
}
```

### src/components/admin/DocumentUpload.jsx
```jsx
import { useState } from 'react';
import { THEME } from '../../config/theme';

const ALL_ROLES = ['admin', 'faculty', 'student'];

export default function DocumentUpload({ onUpload, loading }) {
  const [file,         setFile]        = useState(null);
  const [displayName,  setDisplayName] = useState('');
  const [roles,        setRoles]       = useState(['admin']);

  function toggleRole(role) {
    setRoles(prev =>
      prev.includes(role) ? prev.filter(r => r !== role) : [...prev, role]
    );
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!file || !displayName || roles.length === 0) return;
    onUpload(file, displayName, roles);
    setFile(null); setDisplayName(''); setRoles(['admin']);
  }

  return (
    <div style={{ padding: 20, background: THEME.bgCard, borderRadius: THEME.borderRadiusLg, border: `1px solid ${THEME.bgBorder}`, marginBottom: 20 }}>
      <h3 style={{ color: THEME.textLight, fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Upload Document</h3>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div>
          <label style={{ fontSize: 11, color: THEME.textMuted, fontWeight: 600, letterSpacing: '0.05em', display: 'block', marginBottom: 6 }}>PDF FILE</label>
          <input type="file" accept=".pdf" onChange={e => setFile(e.target.files[0])}
            style={{ color: THEME.textMuted, fontSize: 13, width: '100%' }} />
        </div>
        <div>
          <label style={{ fontSize: 11, color: THEME.textMuted, fontWeight: 600, letterSpacing: '0.05em', display: 'block', marginBottom: 6 }}>DISPLAY NAME</label>
          <input type="text" value={displayName} onChange={e => setDisplayName(e.target.value)}
            placeholder="e.g. HR Policies 2024" required
            style={{ width: '100%', padding: '10px 12px', background: THEME.bgDeep, border: `1px solid ${THEME.bgBorder}`, borderRadius: 6, color: THEME.textLight, fontSize: 13, outline: 'none', fontFamily: THEME.fontBase }} />
        </div>
        <div>
          <label style={{ fontSize: 11, color: THEME.textMuted, fontWeight: 600, letterSpacing: '0.05em', display: 'block', marginBottom: 8 }}>ACCESS ROLES</label>
          <div style={{ display: 'flex', gap: 8 }}>
            {ALL_ROLES.map(role => (
              <button key={role} type="button" onClick={() => toggleRole(role)}
                style={{
                  padding: '6px 14px', borderRadius: 20, fontSize: 12, fontWeight: 500, cursor: 'pointer', fontFamily: THEME.fontBase,
                  background: roles.includes(role) ? THEME.green : THEME.bgDeep,
                  color: roles.includes(role) ? THEME.buttonText : THEME.textMuted,
                  border: `1px solid ${roles.includes(role) ? THEME.green : THEME.bgBorder}`,
                }}>{role}</button>
            ))}
          </div>
        </div>
        <button type="submit" disabled={loading || !file || !displayName || roles.length === 0}
          style={{
            padding: '10px', background: loading ? THEME.bgMid : THEME.green,
            color: THEME.buttonText, border: 'none', borderRadius: 6,
            fontSize: 13, fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer', fontFamily: THEME.fontBase,
          }}>
          {loading ? 'Uploading…' : 'Upload PDF'}
        </button>
      </form>
    </div>
  );
}
```

### src/components/admin/DocumentList.jsx
```jsx
import { THEME } from '../../config/theme';

const STATUS_COLORS = {
  UPLOADED:  THEME.info,
  INGESTING: THEME.warning,
  INGESTED:  THEME.green,
  FAILED:    THEME.error,
};

export default function DocumentList({ docs, onIngest, onDelete, loading }) {
  const all = [...(docs.pending || []), ...(docs.ingested || []), ...(docs.failed || [])];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <h3 style={{ color: THEME.textLight, fontSize: 15, fontWeight: 600 }}>
          Documents ({docs.total || 0})
        </h3>
        {(docs.pending || []).length > 0 && (
          <button onClick={onIngest} disabled={loading}
            style={{
              padding: '7px 16px', background: THEME.green, color: THEME.buttonText,
              border: 'none', borderRadius: 6, fontSize: 12, fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer', fontFamily: THEME.fontBase,
            }}>
            {loading ? 'Ingesting…' : `Ingest Now (${(docs.pending || []).length})`}
          </button>
        )}
      </div>
      {all.length === 0 ? (
        <p style={{ color: THEME.textMuted, fontSize: 13, textAlign: 'center', padding: '30px 0' }}>
          No documents yet. Upload a PDF to get started.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {all.map(doc => (
            <div key={doc.id} style={{
              padding: '12px 14px', background: THEME.bgCard,
              borderRadius: 8, border: `1px solid ${THEME.bgBorder}`,
              display: 'flex', alignItems: 'center', gap: 12,
            }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: 13, fontWeight: 600, color: THEME.textLight, marginBottom: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  📄 {doc.display_name}
                </p>
                <p style={{ fontSize: 11, color: THEME.textMuted }}>
                  Roles: {doc.allowed_roles?.join(', ')}
                  {doc.chunk_count > 0 && ` · ${doc.chunk_count} chunks`}
                </p>
              </div>
              <span style={{
                fontSize: 10, fontWeight: 600, padding: '3px 9px', borderRadius: 10,
                background: 'transparent', border: `1px solid ${STATUS_COLORS[doc.status] || THEME.bgBorder}`,
                color: STATUS_COLORS[doc.status] || THEME.textMuted,
                whiteSpace: 'nowrap',
              }}>{doc.status}</span>
              <button onClick={() => onDelete(doc.id)} disabled={loading}
                style={{
                  background: 'transparent', border: 'none', color: THEME.textMuted,
                  cursor: loading ? 'not-allowed' : 'pointer', fontSize: 15, padding: '2px 6px',
                }}>✕</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

### src/components/admin/AdminPanel.jsx
```jsx
import { useEffect } from 'react';
import { THEME } from '../../config/theme';
import { useDocuments } from '../../hooks/useDocuments';
import DocumentUpload from './DocumentUpload';
import DocumentList from './DocumentList';

export default function AdminPanel({ token }) {
  const { docs, loading, error, success, refresh, upload, ingest, remove } = useDocuments(token);

  useEffect(() => { refresh(); }, []);

  return (
    <div style={{
      flex: 1, overflowY: 'auto', padding: '24px',
      background: THEME.bgDeep,
    }}>
      <h2 style={{ color: THEME.textLight, fontSize: 20, fontWeight: 700, marginBottom: 20 }}>
        Document Management
      </h2>

      {error && (
        <div style={{ padding: '10px 14px', background: THEME.errorBg, border: `1px solid ${THEME.error}`, borderRadius: 8, color: THEME.error, fontSize: 13, marginBottom: 16 }}>
          {error}
        </div>
      )}
      {success && (
        <div style={{ padding: '10px 14px', background: THEME.greenDim, border: `1px solid ${THEME.green}`, borderRadius: 8, color: THEME.green, fontSize: 13, marginBottom: 16 }}>
          {success}
        </div>
      )}

      <DocumentUpload onUpload={upload} loading={loading} />
      <DocumentList docs={docs} onIngest={ingest} onDelete={remove} loading={loading} />
    </div>
  );
}
```

---

## STEP 12 — src/App.jsx

Write to `frontend/src/App.jsx`:
```jsx
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
  const { messages, loading: chatLoading, send, newChat, bottomRef } = useChat(auth?.token);
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
      <Sidebar auth={auth} onNewChat={newChat} onLogout={handleLogout} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <Header activeTab={activeTab} onTabChange={setActiveTab} isAdmin={isAdmin} />
        {activeTab === 'chat' ? (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <MessageList messages={messages} loading={chatLoading} bottomRef={bottomRef} auth={auth} />
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
```

---

## STEP 13 — src/main.jsx

Overwrite `frontend/src/main.jsx`:
```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

---

## STEP 14 — Start Frontend

```bash
cd /Users/soumya.shrivastava/AgenticallyBuiltChatBot/frontend
npm run dev
```

---

## VERIFICATION CHECKLIST
# Run each check. Report PASS or FAIL. Fix all FAILs before moving to 09.

- [ ] Login page renders with two-panel layout — left info panel, right form
- [ ] HM logo image (from `assets/hm_logo.png`) appears in login page top-left and sidebar header
- [ ] Favicon (from `public/favicon.png`) is visible in browser tab
- [ ] Montserrat font loads (used in sidebar brand text)
- [ ] HM green #3AB54A is used for Sign In button and brand accents
- [ ] Background is clean white #FFFFFF with light green accents #E8F8EA
- [ ] Login with admin / HMAdmin@2024 → enters app showing ⚙ ADMIN badge (green bg, white text)
- [ ] Login with faculty1 / HMFaculty@2024 → 👤 FACULTY badge (dark blue bg, white text)
- [ ] Login with student1 / HMStudent@2024 → 📚 STUDENT badge (transparent bg, green text, green border)
- [ ] Admin sees "💬 Chat" and "📁 Documents" tabs in header
- [ ] Faculty sees only "💬 Chat" tab — no Documents tab
- [ ] Student sees only "💬 Chat" tab — no Documents tab
- [ ] Welcome screen shows username and role
- [ ] Sending a message shows user bubble (right side) and AI bubble (left side)
- [ ] AI bubble shows ⚡ N steps badge
- [ ] AI bubble shows sources count — click expands source panel with filename + page
- [ ] Typing indicator (3 bouncing dots) appears while waiting for response
- [ ] New Chat button clears messages
- [ ] Admin Documents tab: upload a PDF, click Ingest Now, status changes to INGESTED
- [ ] Character counter turns orange below 100 chars remaining
- [ ] Sign out clears chat history and returns to login screen
- [ ] Sidebar has white background with HM green accents and #E2E8F0 borders
- [ ] All text readable — dark text on light backgrounds, proper contrast throughout
- [ ] Chat input auto-resizes as user types (max 120px), resets to single line on send
- [ ] Sidebar shows dynamic "Try asking..." questions based on user's accessible documents
- [ ] Clicking a suggested question sends it to the chat
- [ ] `fetchMyDocuments` in api.js calls `GET /documents/my` and returns filtered document list

## Jira Mapping

**Covers:** UC-01, UC-15

| Story ID | Title | AC | Implementation Status |
|----------|-------|----|-----------------------|
| UIB-1 | Access chatbot widget from approved internal systems | 0 | ✅ Implemented |
| UIB-14 | Start chatbot interaction on user trigger | 0 | ✅ Implemented |
| UIB-179 | Allow users to rate chatbot responses | 0 | ✅ Implemented |
| UIB-183 | Capture optional free-text feedback | 0 | ✅ Implemented |

### Source of Truth Rules
- Jira AC = WHAT (behavior) — wins on conflicts
- This .md = HOW (implementation) — wins on design decisions
- Conflicts must be flagged in docs/CONFLICTS.md, never silently overridden
