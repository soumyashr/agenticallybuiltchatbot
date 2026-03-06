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
