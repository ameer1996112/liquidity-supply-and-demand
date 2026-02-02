/**
 * Backend API base URL for health checks, webhook proxy, etc.
 * Set NEXT_PUBLIC_API_URL (e.g. http://backend:8000 in Docker, http://localhost:8000 locally).
 */
function getBase(): string {
  if (typeof process === 'undefined') return '';
  const url = (process.env.NEXT_PUBLIC_API_URL || '').trim().replace(/\/$/, '');
  if (url) return url;
  return typeof window === 'undefined' ? 'http://localhost:8000' : '';
}

export function getApiUrl(): string {
  return getBase();
}

/** e.g. "http://backend:8000/health" */
export function getHealthUrl(): string {
  const base = getBase();
  return base ? `${base}/health` : '';
}

/** e.g. "http://backend:8000/webhook" - for future webhook proxy or test UI */
export function getWebhookUrl(): string {
  const base = getBase();
  return base ? `${base}/webhook` : '';
}
