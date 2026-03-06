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
