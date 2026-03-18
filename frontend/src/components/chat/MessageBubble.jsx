import { useState } from 'react';
import { THEME } from '../../config/theme';
import { submitFeedback } from '../../services/api';

export default function MessageBubble({ message, userInitial, sessionId, token, onSend }) {
  const [showSources, setShowSources] = useState(false);
  const [feedbackState, setFeedbackState] = useState('idle'); // idle | selected | submitted
  const [selectedRating, setSelectedRating] = useState(null);
  const [comment, setComment] = useState('');
  const [hovered, setHovered] = useState(null); // 'up' | 'down'
  const [chipsVisible, setChipsVisible] = useState(true);

  const isUser      = message.role === 'user';
  const isError     = message.role === 'error';
  const isAssistant = message.role === 'assistant';
  const hasSources  = message.sources?.length > 0;
  const hasSteps    = message.reasoningSteps > 0;

  function handleRatingClick(rating) {
    setSelectedRating(rating);
    setFeedbackState('selected');
  }

  async function handleSubmit() {
    try {
      await submitFeedback(token, {
        sessionId,
        message: message.userQuery || '',
        responsePreview: (message.content || '').slice(0, 200),
        rating: selectedRating,
        comment,
      });
      setFeedbackState('submitted');
    } catch {
      setFeedbackState('submitted');
    }
  }

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

        {/* Clarification chips (UC-08) */}
        {message.isClarification && chipsVisible && message.clarificationOptions?.length >= 2 && (
          <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
            {message.clarificationOptions.map((option, i) => (
              <button
                key={i}
                onClick={() => { setChipsVisible(false); onSend?.(option); }}
                style={{
                  background: '#009797',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 16,
                  padding: '6px 14px',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontFamily: 'inherit',
                  fontWeight: 500,
                  transition: 'opacity 0.15s',
                }}
                onMouseEnter={e => e.currentTarget.style.opacity = '0.85'}
                onMouseLeave={e => e.currentTarget.style.opacity = '1'}
              >{option}</button>
            ))}
          </div>
        )}

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
                  📄 {src.display_name || src.source}{src.page != null ? ` · Page ${src.page}` : ''}
                </p>
                {src.uploaded_at && (
                  <p style={{ fontSize: 10, color: THEME.textMuted, marginBottom: 2 }}>
                    Uploaded: {new Date(src.uploaded_at).toLocaleDateString()}
                  </p>
                )}
                {src.snippet && (
                  <p style={{ fontSize: 11, color: THEME.textMuted, lineHeight: 1.5 }}>
                    {src.snippet}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Feedback row — assistant messages only */}
        {isAssistant && feedbackState === 'idle' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6 }}>
            <button
              onClick={() => handleRatingClick('positive')}
              onMouseEnter={() => setHovered('up')}
              onMouseLeave={() => setHovered(null)}
              style={{
                background: 'transparent', border: 'none', cursor: 'pointer',
                fontSize: 14, padding: '2px 6px', borderRadius: 4,
                color: hovered === 'up' ? THEME.teal : THEME.textMuted,
                transition: 'color 0.15s',
              }}
              title="Helpful"
            >👍</button>
            <button
              onClick={() => handleRatingClick('negative')}
              onMouseEnter={() => setHovered('down')}
              onMouseLeave={() => setHovered(null)}
              style={{
                background: 'transparent', border: 'none', cursor: 'pointer',
                fontSize: 14, padding: '2px 6px', borderRadius: 4,
                color: hovered === 'down' ? '#e74c3c' : THEME.textMuted,
                transition: 'color 0.15s',
              }}
              title="Not helpful"
            >👎</button>
          </div>
        )}

        {isAssistant && feedbackState === 'selected' && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8, marginTop: 6,
            flexWrap: 'wrap',
          }}>
            <span style={{ fontSize: 12, color: THEME.textMuted }}>
              {selectedRating === 'positive' ? '👍' : '👎'}
            </span>
            <input
              type="text"
              value={comment}
              onChange={e => setComment(e.target.value)}
              placeholder="Comment (optional)"
              style={{
                fontSize: 12, padding: '4px 8px', borderRadius: 6,
                border: `1px solid ${THEME.bgBorder}`, background: THEME.bgMid,
                color: THEME.textLight, outline: 'none', flex: 1, minWidth: 120,
                fontFamily: THEME.fontBase,
              }}
            />
            <button
              onClick={handleSubmit}
              style={{
                fontSize: 11, padding: '4px 12px', borderRadius: 6,
                border: 'none', cursor: 'pointer',
                background: THEME.teal, color: '#fff',
                fontFamily: THEME.fontBase, fontWeight: 600,
              }}
            >Submit</button>
          </div>
        )}

        {isAssistant && feedbackState === 'submitted' && (
          <p style={{ fontSize: 11, color: THEME.teal, marginTop: 6 }}>
            Thanks for your feedback!
          </p>
        )}
      </div>
    </div>
  );
}
