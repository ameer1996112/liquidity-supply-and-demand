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

// ---------------------------------------------------------------------------
// Alerts API helpers
// ---------------------------------------------------------------------------

export function getAlertsActiveUrl(): string {
  const base = getBase();
  return base ? `${base}/alerts/active` : '';
}

export function getAlertAcknowledgeUrl(id: number | string): string {
  const base = getBase();
  return base ? `${base}/alerts/${id}/acknowledge` : '';
}

export function getAlertAcknowledgeAllUrl(): string {
  const base = getBase();
  return base ? `${base}/alerts/acknowledge_all` : '';
}

// ---------------------------------------------------------------------------
// Portfolio Command Center (V2.0)
// ---------------------------------------------------------------------------

export function getPortfolioControlUrl(path = ''): string {
  const base = getBase();
  const p = path.startsWith('/') ? path : `/${path}`;
  return base ? `${base}/portfolio-control${p}` : '';
}

/** GET /portfolio-control/risk/settings */
export function getRiskSettingsUrl(): string {
  return getPortfolioControlUrl('/risk/settings');
}

/** PATCH /portfolio-control/risk/settings/{key} */
export function getRiskSettingUpdateUrl(settingKey: string): string {
  return getPortfolioControlUrl(`/risk/settings/${encodeURIComponent(settingKey)}`);
}

export interface RiskSettingsResponse {
  settings: Record<string, number | boolean | string | Record<string, unknown>>;
  overrides_count: number;
}

export async function fetchRiskSettings(): Promise<RiskSettingsResponse> {
  const url = getRiskSettingsUrl();
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function updateRiskSetting(
  settingKey: string,
  value: number | boolean | string | Record<string, unknown>,
  changeReason?: string
): Promise<{ status: string; setting: string; value: unknown }> {
  const url = getRiskSettingUpdateUrl(settingKey);
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value, change_reason: changeReason ?? undefined }),
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Rules API (symbol risk rules for Risk Control Center)
// ---------------------------------------------------------------------------

export function getRulesSymbolsUrl(): string {
  const base = getBase();
  return base ? `${base}/rules/symbols` : '';
}

export function getRulesSymbolUrl(symbol: string): string {
  const base = getBase();
  return base ? `${base}/rules/symbols/${encodeURIComponent(symbol)}` : '';
}

export interface SymbolRiskRuleApi {
  id?: string;
  symbol: string;
  max_lot_size: number;
  risk_percent: number;
  pip_size: number;
  pip_value_per_lot: number;
  max_positions: number;
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
}

export async function fetchSymbolRiskRules(): Promise<SymbolRiskRuleApi[]> {
  const url = getRulesSymbolsUrl();
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return (data.rules ?? []) as SymbolRiskRuleApi[];
}

export async function createSymbolRiskRule(rule: Omit<SymbolRiskRuleApi, 'id' | 'created_at' | 'updated_at'>): Promise<SymbolRiskRuleApi> {
  const url = getRulesSymbolsUrl();
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rule),
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.rule as SymbolRiskRuleApi;
}

export async function updateSymbolRiskRule(symbol: string, updates: Partial<SymbolRiskRuleApi>): Promise<SymbolRiskRuleApi> {
  const url = getRulesSymbolUrl(symbol);
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.rule as SymbolRiskRuleApi;
}

export async function deleteSymbolRiskRule(symbol: string): Promise<void> {
  const url = getRulesSymbolUrl(symbol);
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, { method: 'DELETE', signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}
