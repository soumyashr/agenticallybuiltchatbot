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
