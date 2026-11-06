declare global {
  interface Window { __API_BASE__?: string }
}

export function getApiBase(): string {
  // Prefer explicit override set via index.html script (?api=...) or env
  const envBase = (window as any).__API_BASE__ || import.meta.env.VITE_API_BASE;
  if (envBase) return envBase;
  // Fallback: if served on 43123 (static UI), default backend to 54123 on loopback
  if (location.hostname === 'localhost' || location.hostname === '127.0.0.1') {
    if (location.port === '43123') return 'http://127.0.0.1:54123';
  }
  // Otherwise same origin (works behind reverse proxy)
  return `${location.protocol}//${location.host}`;
}

export function getRunsBase(): string {
  return getApiBase();
}

