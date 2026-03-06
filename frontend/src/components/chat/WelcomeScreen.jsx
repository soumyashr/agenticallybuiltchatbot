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
