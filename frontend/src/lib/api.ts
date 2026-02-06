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

/** e.g. "http://backend:8000/config/ai" */
export function getAiConfigUrl(): string {
  const base = getBase();
  return base ? `${base}/config/ai` : '';
}

/** AI/ML configuration shape returned by GET /config/ai */
export interface AiConfigResponse {
  ai: {
    ai_filter_enabled: boolean;
    ai_provider: string;
    ai_model: string;
    ai_base_url: string;
    ai_min_confidence: number;
    ai_timeout_seconds: number;
    ai_api_key_set: boolean;
  };
  ml: {
    ml_guardian_enabled: boolean;
    ml_min_confidence: number;
  };
  ensemble: {
    enable_llm_filter: boolean;
    run_shadow_mode: boolean;
  };
  execution: {
    execution_mode: string;
    run_mode: string;
    live_trading_enabled: boolean;
    live_shadow: boolean;
    trading_kill_switch: boolean;
    meta_api_configured: boolean;
    meta_api_region: string;
  };
  risk: {
    trinity_enabled: boolean;
    trinity_max_daily_loss_pct: number;
    trinity_max_drawdown_pct: number;
    trinity_max_risk_per_trade_pct: number;
    trinity_max_positions: number;
    risk_percent: number;
    account_balance: number;
    enable_risk_scaling: boolean;
    risk_mode: string;
  };
}

export async function fetchAiConfig(): Promise<AiConfigResponse> {
  const url = getAiConfigUrl();
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/** e.g. "http://backend:8000/rules/strategy" */
export function getRulesStrategyUrl(): string {
  const base = getBase();
  return base ? `${base}/rules/strategy` : '';
}
