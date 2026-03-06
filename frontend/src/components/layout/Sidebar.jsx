import { THEME, ROLE_STYLES } from '../../config/theme';
import { BRAND } from '../../config/constants';

export default function Sidebar({ auth, onNewChat, onLogout }) {
  const roleStyle = ROLE_STYLES[auth?.role] || ROLE_STYLES.student;

  return (
    <div style={{
      width: THEME.sidebarWidth, height: '100%',
      background: THEME.sidebarBg,
      borderRight: `1px solid ${THEME.sidebarBorder}`,
      display: 'flex', flexDirection: 'column',
      padding: '20px 16px', flexShrink: 0,
    }}>
      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 28 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 7,
          background: THEME.green, display: 'flex',
          alignItems: 'center', justifyContent: 'center',
          fontSize: 16, fontWeight: 700, color: '#0A1A0A', flexShrink: 0,
        }}>H</div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: THEME.sidebarText, lineHeight: 1.2 }}>
            {BRAND.name}
          </div>
          <div style={{ fontSize: 10, color: THEME.sidebarMuted, lineHeight: 1.2 }}>
            {BRAND.company}
          </div>
        </div>
      </div>

      {/* New Chat */}
      <button
        onClick={onNewChat}
        style={{
          width: '100%', padding: '10px',
          background: THEME.green, color: THEME.buttonText,
          border: 'none', borderRadius: THEME.borderRadius,
          fontSize: 13, fontWeight: 600, cursor: 'pointer',
          marginBottom: 24, fontFamily: THEME.fontBase,
        }}
      >+ New Chat</button>

      <div style={{ flex: 1 }} />

      {/* Role badge + user */}
      <div style={{
        padding: '12px', background: THEME.bgCard,
        borderRadius: THEME.borderRadius,
        border: `1px solid ${THEME.sidebarBorder}`,
      }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center',
          padding: '3px 10px', borderRadius: 20,
          background: roleStyle.bg,
          border: roleStyle.border || 'none',
          marginBottom: 8,
        }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: roleStyle.text, letterSpacing: '0.05em' }}>
            {roleStyle.label}
          </span>
        </div>
        <p style={{ fontSize: 13, fontWeight: 600, color: THEME.sidebarText, marginBottom: 2 }}>
          {auth?.username}
        </p>
        <p style={{ fontSize: 11, color: THEME.sidebarMuted }}>{BRAND.company}</p>
        <button
          onClick={onLogout}
          style={{
            marginTop: 10, width: '100%', padding: '7px',
            background: '#FFFFFF', border: `1px solid ${THEME.sidebarText}`,
            borderRadius: 6, color: THEME.sidebarText, fontSize: 12,
            cursor: 'pointer', fontFamily: THEME.fontBase,
          }}
        >Sign out</button>
      </div>

      <p style={{ marginTop: 12, textAlign: 'center', fontSize: 10, color: THEME.sidebarMuted }}>
        {BRAND.tagline}
      </p>
    </div>
  );
}
