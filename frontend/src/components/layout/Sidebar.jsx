import { useState, useEffect } from 'react';
import { THEME, ROLE_STYLES } from '../../config/theme';
import { BRAND } from '../../config/constants';
import { fetchMyDocuments } from '../../services/api';
import hmLogo from '../../assets/hm_logo.png';

function generateQuestions(docs) {
  const questions = [];

  for (const doc of docs) {
    const name = doc.display_name;
    if (name.includes('Syllabus')) {
      questions.push(`What topics are in ${name}?`);
    } else if (name.includes('Minutes')) {
      questions.push(`What was discussed in ${name}?`);
    } else if (name.includes('Manual')) {
      questions.push(`What does ${name} cover?`);
    } else if (name.includes('Protocol')) {
      questions.push(`What is the ${name}?`);
    } else if (name.includes('Blueprint')) {
      questions.push(`What is the process in ${name}?`);
    } else {
      questions.push(`What is in ${name}?`);
    }
    if (questions.length >= 5) return questions.slice(0, 5);
  }

  // 2nd pass: Summarize
  for (const doc of docs) {
    questions.push(`Summarize ${doc.display_name}`);
    if (questions.length >= 5) return questions.slice(0, 5);
  }

  // 3rd pass: Key points
  for (const doc of docs) {
    questions.push(`What are the key points in ${doc.display_name}?`);
    if (questions.length >= 5) return questions.slice(0, 5);
  }

  return questions.slice(0, 5);
}

export default function Sidebar({ auth, onNewChat, onLogout, onAskQuestion }) {
  const roleStyle = ROLE_STYLES[auth?.role] || ROLE_STYLES.student;
  const [questions, setQuestions] = useState([]);

  useEffect(() => {
    if (!auth?.token) return;
    fetchMyDocuments(auth.token)
      .then(docs => setQuestions(generateQuestions(docs)))
      .catch(() => setQuestions([]));
  }, [auth?.token]);

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
          marginBottom: 16, fontFamily: THEME.fontBase,
        }}
      >+ New Chat</button>

      {/* Sample Questions */}
      {questions.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <p style={{ fontSize: 11, fontWeight: 600, color: '#009797', marginBottom: 8 }}>
            Try asking...
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {questions.map((q, i) => (
              <button
                key={i}
                onClick={() => onAskQuestion(q)}
                style={{
                  padding: '7px 10px',
                  background: '#F0FAF0',
                  color: '#009797',
                  border: '1px solid #39B54A',
                  borderRadius: 8,
                  fontSize: 11,
                  lineHeight: 1.3,
                  textAlign: 'left',
                  cursor: 'pointer',
                  fontFamily: THEME.fontBase,
                }}
              >{q}</button>
            ))}
          </div>
        </div>
      )}

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

      {/* Logo */}
      <div style={{ marginTop: 12, textAlign: 'center' }}>
        <img src={hmLogo} alt="Happiest Minds" style={{ maxHeight: 40, objectFit: 'contain' }} />
      </div>
    </div>
  );
}
