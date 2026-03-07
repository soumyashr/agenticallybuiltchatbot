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
        justifyContent: 'center', padding: '60px 50px',
        borderRight: `1px solid ${THEME.bgBorder}`,
      }}>
        <div style={{ marginBottom: 40 }}>
          <img src={hmLogo} alt="Happiest Minds" style={{ height: 48, objectFit: 'contain' }} />
        </div>
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
