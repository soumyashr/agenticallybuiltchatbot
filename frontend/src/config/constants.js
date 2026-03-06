export const BRAND = {
  name:    'Happiest Minds Knowledge Hub',
  tagline: 'The Mindful IT Company · AI-powered',
  company: 'Happiest Minds Technologies',
  version: '1.0',
};

export const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const CHAT_CONFIG = {
  maxChars:        1000,
  typingDelayMs:   400,
  sessionIdPrefix: 'hm-session-',
};

export const ADMIN_POLL_INTERVAL_MS = 2000;  // Status poll during ingest
