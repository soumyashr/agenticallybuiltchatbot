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
