export const THEME = {
  // ── HM Brand Colors ──────────────────────────
  green:         '#3AB54A',
  greenHover:    '#2E9640',
  greenLight:    '#E8F8EA',
  greenDim:      '#E8F8EA',
  teal:          '#009797',

  // ── Light Surfaces ───────────────────────────
  bgDeep:        '#FFFFFF',   // page background
  bgCard:        '#F8F9FA',   // cards, panels
  bgMid:         '#E8F8EA',   // secondary panels, hover
  bgBorder:      '#E2E8F0',   // borders

  // ── Sidebar (light, HM brand) ────────────────
  sidebarBg:     '#FFFFFF',
  sidebarText:   '#1A1A2E',
  sidebarMuted:  '#666666',
  sidebarBorder: '#E2E8F0',

  // ── Text ─────────────────────────────────────
  textLight:     '#1A1A2E',   // primary body text (dark on light bg)
  textMuted:     '#666666',
  textDark:      '#1A1A2E',
  textBody:      '#334155',

  // ── Buttons ──────────────────────────────────
  buttonText:    '#FFFFFF',

  // ── Status ───────────────────────────────────
  error:         '#EF4444',
  errorBg:       '#FEF2F2',
  warning:       '#F59E0B',
  info:          '#3B82F6',

  // ── Fonts ────────────────────────────────────
  fontBase:      "'Inter', sans-serif",
  fontMono:      "'JetBrains Mono', 'Fira Code', monospace",

  // ── Sizing ───────────────────────────────────
  sidebarWidth:  '260px',
  headerHeight:  '56px',
  borderRadius:  '8px',
  borderRadiusLg:'12px',

  // ── Shadows ──────────────────────────────────
  shadowSm:      '0 1px 3px rgba(0,0,0,0.08)',
  shadowMd:      '0 4px 12px rgba(0,0,0,0.1)',
  shadowLg:      '0 8px 24px rgba(0,0,0,0.12)',
};

export const ROLE_STYLES = {
  admin: {
    bg:     '#3AB54A',
    text:   '#0A1A0A',
    label:  '⚙ ADMIN',
  },
  faculty: {
    bg:     '#0F3460',
    text:   '#FFFFFF',
    label:  '👤 FACULTY',
  },
  student: {
    bg:     'transparent',
    text:   '#3AB54A',
    border: '1px solid #3AB54A',
    label:  '📚 STUDENT',
  },
};
