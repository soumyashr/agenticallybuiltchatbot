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
