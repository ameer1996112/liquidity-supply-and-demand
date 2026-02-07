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

// ---------------------------------------------------------------------------
// Portfolio Optimizer (batch actions, hedging, trailing stops)
// ---------------------------------------------------------------------------

export async function batchPositionAction(payload: {
  signal_ids: number[];
  action: 'close' | 'scale_out' | 'move_sl_breakeven' | 'add_trailing';
  action_params?: { trail_distance_pips?: number };
}): Promise<{
  status: string;
  action: string;
  total: number;
  success: number;
  failed: number;
  results: Array<{ signal_id: number; success: boolean; error?: string; trailing_stop_id?: number }>;
}> {
  const url = getPortfolioControlUrl('/optimizer/batch-action');
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(15000),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export interface HedgeSuggestionApi {
  id: number;
  suggested_symbol: string;
  suggested_side: string;
  suggested_size: number;
  expected_var_reduction_pct: number;
  hedge_reason: string;
  currency_exposure: Record<string, number>;
  total_exposure_usd: number;
  current_var: number;
}

export async function fetchHedgeSuggestions(): Promise<HedgeSuggestionApi[]> {
  const url = getPortfolioControlUrl('/optimizer/hedge-suggestions');
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return (data.suggestions ?? []).map((s: Record<string, unknown>) => ({
    id: s.id,
    suggested_symbol: s.suggested_symbol ?? s.symbol,
    suggested_side: s.suggested_side ?? s.side,
    suggested_size: s.suggested_size ?? s.size,
    expected_var_reduction_pct: s.expected_var_reduction_pct ?? 0,
    hedge_reason: s.hedge_reason ?? s.reason ?? '',
    currency_exposure: (s.currency_exposure as Record<string, number>) ?? {},
    total_exposure_usd: s.total_exposure_usd ?? 0,
    current_var: s.current_var ?? 0,
  })) as HedgeSuggestionApi[];
}

export async function generateHedgeSuggestion(): Promise<{
  status: string;
  suggestion_id?: number;
  suggestion?: {
    symbol: string;
    side: string;
    size: number;
    expected_var_reduction_pct: number;
    reason: string;
    currency_exposure: Record<string, number>;
  };
  message?: string;
}> {
  const url = getPortfolioControlUrl('/optimizer/generate-hedge');
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, { method: 'POST', signal: AbortSignal.timeout(15000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function acceptHedgeSuggestion(suggestionId: number): Promise<{ status: string; suggestion_id: number }> {
  const url = getPortfolioControlUrl(`/optimizer/hedge-suggestions/${suggestionId}/accept`);
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, { method: 'POST', signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function rejectHedgeSuggestion(suggestionId: number): Promise<{ status: string; suggestion_id: number }> {
  const url = getPortfolioControlUrl(`/optimizer/hedge-suggestions/${suggestionId}/reject`);
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, { method: 'POST', signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export interface TrailingStopApi {
  id: number;
  signal_id: number;
  symbol: string;
  side: string;
  trail_distance_pips: number;
  current_sl: number | null;
  is_activated: boolean;
  times_moved: number;
}

export async function fetchTrailingStops(): Promise<TrailingStopApi[]> {
  const url = getPortfolioControlUrl('/optimizer/trailing-stops');
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return (data.trailing_stops ?? []) as TrailingStopApi[];
}

export async function addTrailingStop(payload: {
  signal_id: number;
  trail_distance_pips: number;
  activation_price?: number;
  wait_for_breakeven?: boolean;
}): Promise<{ status: string; trailing_stop_id: number }> {
  const url = getPortfolioControlUrl('/optimizer/trailing-stop');
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function removeTrailingStop(trailingStopId: number): Promise<{ status: string }> {
  const url = getPortfolioControlUrl(`/optimizer/trailing-stops/${trailingStopId}`);
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, { method: 'DELETE', signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// Multi-Account Manager
// ---------------------------------------------------------------------------

export interface AccountComparisonApi {
  account_name: string;
  strategy_type?: string;
  balance: number;
  daily_pnl: number;
  daily_pnl_pct: number;
  win_rate: number;
  sharpe_ratio: number;
  active_positions: number;
  total_trades?: number;
}

export interface AllocationRecommendationApi {
  account_name: string;
  current_balance: number;
  suggested_allocation_usd: number;
  change_usd: number;
  change_pct: number;
  reason: string;
}

export interface AllocationPlanApi {
  total_capital: number;
  total_allocated: number;
  unallocated: number;
  recommendations: AllocationRecommendationApi[];
  expected_portfolio_sharpe: number;
}

export interface TradeCopyRuleApi {
  id: number;
  rule_name: string;
  master_account_name: string;
  slave_account_names: string[];
  scale_by_balance: boolean;
  risk_multiplier: number;
  copy_sl_tp: boolean;
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface TradeCopyLogApi {
  id: number;
  rule_id: number;
  master_signal_id: number;
  master_account: string;
  slave_signal_id: number;
  slave_account: string;
  master_size: number;
  slave_size: number;
  copied_at: string;
  success: boolean;
}

export async function fetchAccountsComparison(): Promise<AccountComparisonApi[]> {
  const url = getPortfolioControlUrl('/accounts/comparison');
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return (data.accounts ?? []) as AccountComparisonApi[];
}

export async function fetchAllocationSuggest(
  totalCapital: number,
  goal = 'maximize_sharpe'
): Promise<AllocationPlanApi> {
  const url = getPortfolioControlUrl(`/accounts/allocation/suggest?total_capital=${totalCapital}&optimization_goal=${goal}`);
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, { method: 'POST', signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function executeAllocation(
  accountName: string,
  allocationUsd: number
): Promise<{ status: string; account_name: string; new_allocation: number }> {
  const url = getPortfolioControlUrl(`/accounts/allocation/execute/${encodeURIComponent(accountName)}?allocation_usd=${allocationUsd}`);
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, { method: 'POST', signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchTradeCopyRules(): Promise<TradeCopyRuleApi[]> {
  const url = getPortfolioControlUrl('/accounts/trade-copy-rules');
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return (data.rules ?? []) as TradeCopyRuleApi[];
}

export async function createTradeCopyRule(rule: {
  rule_name: string;
  master_account_name: string;
  slave_account_names: string[];
  scale_by_balance?: boolean;
  risk_multiplier?: number;
  copy_sl_tp?: boolean;
  enabled?: boolean;
}): Promise<{ status: string; rule: TradeCopyRuleApi }> {
  const url = getPortfolioControlUrl('/accounts/trade-copy-rules');
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rule),
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function toggleTradeCopyRule(
  ruleId: number,
  enabled: boolean
): Promise<{ status: string; rule_id: number; enabled: boolean }> {
  const url = getPortfolioControlUrl(`/accounts/trade-copy-rules/${ruleId}/toggle?enabled=${enabled}`);
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, {
    method: 'PATCH',
    signal: AbortSignal.timeout(10000),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchTradeCopyLog(limit = 50): Promise<TradeCopyLogApi[]> {
  const url = getPortfolioControlUrl(`/accounts/trade-copy-log?limit=${limit}`);
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return (data.log ?? []) as TradeCopyLogApi[];
}
