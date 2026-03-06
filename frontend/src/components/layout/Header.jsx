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
