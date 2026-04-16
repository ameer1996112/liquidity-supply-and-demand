/**
 * API Client Configuration for Railway Deployment
 *
 * Automatically uses Railway backend URL in production,
 * localhost in development.
 */

// Get API base URL from environment or default to localhost
// Remove trailing slash to prevent double slashes in URLs
const rawApiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
export const API_BASE_URL = rawApiUrl.endsWith('/')
  ? rawApiUrl.slice(0, -1)
  : rawApiUrl;

/**
 * Fetch wrapper with automatic Railway URL handling
 */
export async function apiFetch<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  // Ensure endpoint starts with / and construct clean URL
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const url = `${API_BASE_URL}${cleanEndpoint}`;

  const adminApiKey = process.env.NEXT_PUBLIC_ADMIN_API_KEY || '';

  const response = await fetch(url, {
    ...options,
    cache: 'no-store', // Fix: Force Next.js App Router to never cache API responses
    headers: {
      'Content-Type': 'application/json',
      ...(adminApiKey ? { 'X-Admin-API-Key': adminApiKey } : {}),
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API Error (${response.status}): ${error}`);
  }

  // Some endpoints legitimately return no body (e.g. DELETE 204).
  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get('content-type') || '';
  const text = await response.text();
  if (!text) {
    return undefined as T;
  }

  if (contentType.includes('application/json')) {
    return JSON.parse(text) as T;
  }

  // Fallback for non-JSON responses (should be rare in this app).
  return text as unknown as T;
}

/**
 * Portfolio Control - Account Management
 */
export async function fetchAccountsComparison(): Promise<AccountDetailApi[]> {
  const response = await apiFetch<AccountComparisonResponse>(
    '/api/portfolio-control/accounts/comparison'
  );
  return response.accounts || [];
}

export interface LiveBrokerBalance {
  balance: number;
  equity: number;
  free_margin: number;
  margin_used: number;
  margin_level_pct: number;
  active_positions_count: number;
}

export async function fetchLiveBrokerBalance(): Promise<LiveBrokerBalance> {
  return apiFetch<LiveBrokerBalance>('/positions/account');
}

export async function fetchAccountDetail(accountName: string) {
  return apiFetch<any>(
    `/api/portfolio-control/accounts/${encodeURIComponent(accountName)}`
  );
}

export async function syncAccount(accountName: string) {
  return apiFetch<any>(
    `/api/portfolio-control/accounts/${encodeURIComponent(accountName)}/sync`,
    {
      method: 'POST',
    }
  );
}

export async function syncAllAccounts() {
  return apiFetch<any>('/api/portfolio-control/accounts/sync-all', {
    method: 'POST',
  });
}

export async function fetchAllocationSuggest(
  totalCapital: number,
  goal: string = 'maximize_sharpe'
) {
  return apiFetch<any>(
    `/api/portfolio-control/accounts/allocation-suggest?total_capital=${totalCapital}&goal=${goal}`
  );
}

export async function executeAllocation(
  accountName: string,
  allocationUsd: number
) {
  return apiFetch<any>(
    `/api/portfolio-control/accounts/${encodeURIComponent(
      accountName
    )}/allocate`,
    {
      method: 'POST',
      body: JSON.stringify({ allocation_usd: allocationUsd }),
    }
  );
}

/**
 * Portfolio Control - Trade Copy
 */
export async function fetchTradeCopyRules() {
  return apiFetch<any>('/api/portfolio-control/accounts/trade-copy-rules');
}

export async function createTradeCopyRule(rule: {
  rule_name?: string;
  master_account_name: string;
  slave_account_names: string[];
  copy_ratio?: number;
  scale_by_balance?: boolean;
  risk_multiplier?: number;
  copy_sl_tp?: boolean;
  enabled?: boolean;
  filter_symbols?: string[];
  filter_strategies?: string[];
}) {
  return apiFetch<any>('/api/portfolio-control/accounts/trade-copy-rules', {
    method: 'POST',
    body: JSON.stringify(rule),
  });
}

export async function toggleTradeCopyRule(ruleId: number, enabled: boolean) {
  return apiFetch<any>(
    `/api/portfolio-control/accounts/trade-copy-rules/${ruleId}/toggle?enabled=${enabled}`,
    {
      method: 'PATCH',
    }
  );
}

export async function fetchTradeCopyLog(limit: number = 50) {
  return apiFetch<any>(
    `/api/portfolio-control/accounts/trade-copy-log?limit=${limit}`
  );
}

/**
 * Portfolio Control - Optimizer & Hedge Suggestions
 */
export interface HedgeSuggestionApi {
  id: number;
  status: string;
  suggested_symbol: string;
  suggested_direction: string;
  suggested_size_lots: number;
  reason: string;
  created_at: string;
}

export async function fetchHedgeSuggestions() {
  return apiFetch<HedgeSuggestionApi[]>(
    '/api/portfolio-control/optimizer/hedge-suggestions'
  );
}

export async function generateHedgeSuggestion() {
  return apiFetch<any>('/api/portfolio-control/optimizer/hedge-suggestions', {
    method: 'POST',
  });
}

export async function acceptHedgeSuggestion(suggestionId: number) {
  return apiFetch<any>(
    `/api/portfolio-control/optimizer/hedge-suggestions/${suggestionId}/accept`,
    {
      method: 'POST',
    }
  );
}

export async function rejectHedgeSuggestion(suggestionId: number) {
  return apiFetch<any>(
    `/api/portfolio-control/optimizer/hedge-suggestions/${suggestionId}/reject`,
    {
      method: 'POST',
    }
  );
}

export interface OptimizerRunSummaryApi {
  total_pairs: number;
  running_pairs: number;
  completed_pairs: number;
  failed_pairs: number;
  best_symbol?: string;
  best_score?: number;
  output_paths?: Record<string, string>;
  error_message?: string;
}

export interface OptimizerRunApi {
  id: string;
  strategy_id?: string | null;
  strategy_version?: string | null;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'interrupted';
  mode: string;
  workers: number;
  pairs: string[];
  n_trials: number;
  dd_limit: number;
  dry_run: boolean;
  created_by?: string | null;
  summary: OptimizerRunSummaryApi;
  started_at?: string | null;
  finished_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface OptimizerRunResultApi {
  symbol: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  params?: Record<string, unknown>;
  metrics?: {
    score?: number;
    net_profit?: number;
    win_rate?: number;
    profit_factor?: number;
    max_drawdown_pct?: number;
    total_trades?: number;
  };
  error_message?: string | null;
}

export interface OptimizerRunEventApi {
  event_type: string;
  run_id: string;
  worker_id?: number | null;
  symbol?: string | null;
  payload?: Record<string, any>;
  created_at?: string;
}

export interface OptimizerRunCreateApi {
  strategy_id: string;
  strategy_version: string;
  mode: string;
  workers: number;
  pairs: string[];
  n_trials: number;
  dd_limit: number;
  dry_run: boolean;
}

export async function fetchOptimizerRuns() {
  const response = await apiFetch<{ runs: OptimizerRunApi[] }>('/api/optimizer/runs');
  return response.runs || [];
}

export async function fetchOptimizerRun(runId: string) {
  return apiFetch<OptimizerRunApi>(`/api/optimizer/runs/${runId}`);
}

export async function fetchOptimizerRunResults(runId: string) {
  const response = await apiFetch<{ results: OptimizerRunResultApi[] }>(
    `/api/optimizer/runs/${runId}/results`
  );
  return response.results || [];
}

export async function fetchOptimizerRunEvents(runId: string) {
  const response = await apiFetch<{ events: OptimizerRunEventApi[] }>(
    `/api/optimizer/runs/${runId}/events`
  );
  return response.events || [];
}

export async function createOptimizerRun(payload: OptimizerRunCreateApi) {
  return apiFetch<OptimizerRunApi>('/api/optimizer/runs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function cancelOptimizerRun(runId: string) {
  return apiFetch<OptimizerRunApi>(`/api/optimizer/runs/${runId}/cancel`, {
    method: 'POST',
  });
}

export interface AgentStatusApi {
  agent_online: boolean;
  chrome_ready: boolean;
  agent_version: string | null;
  last_heartbeat: number | null;
}

export async function fetchAgentStatus() {
  return apiFetch<AgentStatusApi>('/api/optimizer/agent/status');
}

/**
 * Alert Setup
 */
export type AlertSetupPresetMode = 'top3' | 'top5' | 'approved' | 'custom';

export interface AlertApprovedConfigApi {
  pair: string;
  timeframe: string;
  status: 'candidate' | 'approved' | 'archived';
  rank?: number | null;
  risk_weight?: number | null;
  score?: number | null;
  profit_factor?: number | null;
  max_drawdown_pct?: number | null;
  total_trades?: number | null;
  source_run_id?: string | null;
  params?: Record<string, unknown> | null;
  notes?: string | null;
  updated_at?: string | null;
}

export interface AlertBatchSummaryApi {
  total_pairs: number;
  pending_pairs?: number;
  running_pairs: number;
  completed_pairs: number;
  failed_pairs: number;
  cancelled_pairs?: number;
  skipped_pairs?: number;
  created_alerts?: number;
  best_pair?: string;
  best_score?: number;
  error_message?: string;
}

export interface AlertBatchApi {
  id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'interrupted';
  source_mode: AlertSetupPresetMode;
  timeframe: string;
  pairs: string[];
  alert_name_prefix?: string | null;
  webhook_url?: string | null;
  use_approved_weights?: boolean | null;
  pair_risk_weights?: Record<string, number> | null;
  created_by?: string | null;
  summary: AlertBatchSummaryApi;
  started_at?: string | null;
  finished_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AlertBatchResultApi {
  pair: string;
  status: 'pending' | 'running' | 'completed' | 'created' | 'skipped' | 'failed' | 'cancelled';
  timeframe?: string | null;
  risk_weight?: number | null;
  alert_name?: string | null;
  alert_id?: string | null;
  params?: Record<string, unknown> | null;
  error_message?: string | null;
  created_at?: string | null;
}

export interface AlertBatchEventApi {
  batch_id: string;
  event_type: string;
  pair?: string | null;
  worker_id?: number | null;
  payload?: Record<string, any>;
  created_at?: string;
}

export interface AlertBatchCreateApi {
  source_mode: AlertSetupPresetMode;
  pairs: string[];
  timeframe: string;
  alert_name_prefix?: string;
  webhook_url?: string;
  use_approved_weights?: boolean;
  pair_risk_weights?: Record<string, number>;
  notes?: string;
}

export async function fetchAlertApprovedConfigs() {
  const response = await apiFetch<{ configs: AlertApprovedConfigApi[] }>(
    '/api/alert-setup/approved-configs'
  );
  return response.configs || [];
}

export async function fetchAlertBatches() {
  const response = await apiFetch<{ batches: AlertBatchApi[] }>('/api/alert-setup/batches');
  return response.batches || [];
}

export async function fetchAlertBatch(batchId: string) {
  return apiFetch<AlertBatchApi>(`/api/alert-setup/batches/${batchId}`);
}

export async function fetchAlertBatchResults(batchId: string) {
  const response = await apiFetch<{ results: AlertBatchResultApi[] }>(
    `/api/alert-setup/batches/${batchId}/results`
  );
  return response.results || [];
}

export async function fetchAlertBatchEvents(batchId: string) {
  const response = await apiFetch<{ events: AlertBatchEventApi[] }>(
    `/api/alert-setup/batches/${batchId}/events`
  );
  return response.events || [];
}

export async function createAlertBatch(payload: AlertBatchCreateApi) {
  return apiFetch<AlertBatchApi>('/api/alert-setup/batches', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function cancelAlertBatch(batchId: string) {
  return apiFetch<AlertBatchApi>(`/api/alert-setup/batches/${batchId}/cancel`, {
    method: 'POST',
  });
}

/**
 * Portfolio Control - Trailing Stops
 */
export async function fetchTrailingStops() {
  return apiFetch<any>('/api/portfolio-control/optimizer/trailing-stops');
}

export async function addTrailingStop(payload: {
  signal_id: number;
  trail_distance_pips: number;
  activation_price?: number;
  wait_for_breakeven?: boolean;
}) {
  return apiFetch<any>('/api/portfolio-control/optimizer/trailing-stop', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function removeTrailingStop(trailingStopId: number) {
  return apiFetch<any>(
    `/api/portfolio-control/optimizer/trailing-stops/${trailingStopId}`,
    {
      method: 'DELETE',
    }
  );
}

/**
 * Portfolio Control - Batch Position Actions
 */
export async function batchPositionAction(payload: {
  signal_ids: number[];
  action: 'close' | 'scale_out' | 'move_sl_breakeven' | 'add_trailing';
  action_params?: { trail_distance_pips?: number };
}) {
  return apiFetch<any>(
    '/api/portfolio-control/optimizer/batch-position-action',
    {
      method: 'POST',
      body: JSON.stringify(payload),
    }
  );
}

/**
 * Account Positions - Fetch reconciled positions for an account
 */
export interface Position {
  reconciliation_status?: 'matched' | 'orphaned' | 'pending';
  [key: string]: any;
}

export async function fetchAccountPositions(accountName: string): Promise<{
  broker: Position[];
  db: Position[];
  reconciliation_summary: {
    matched: number;
    orphaned: number;
    pending: number;
  };
}> {
  return apiFetch(
    `/api/portfolio-control/accounts/${encodeURIComponent(
      accountName
    )}/positions`
  );
}

export interface ReconcileStatusAccount {
  account_name: string;
  last_reconcile_time?: string | null;
  last_reconcile_drift_count: number;
  connection_status?: string | null;
  last_sync_time?: string | null;
}

export interface ReconcileStatusResponse {
  accounts: ReconcileStatusAccount[];
}

export async function fetchReconcileStatus(): Promise<ReconcileStatusResponse> {
  return apiFetch<ReconcileStatusResponse>(
    '/api/portfolio-control/reconcile/status'
  );
}

/**
 * AI Configuration
 */
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
    ai_enabled?: boolean;
    ai_mode?: 'shadow' | 'enforce';
    ai_quick_model?: string;
    ai_deep_model?: string;
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
  };
}

export async function fetchAiConfig(): Promise<AiConfigResponse> {
  return apiFetch<AiConfigResponse>('/config/ai');
}

/**
 * Sprint 3.4: Strategy graduation — shadow vs actual metrics + readiness
 */
export interface GraduationReadiness {
  ready: boolean;
  reason: string;
  metrics: {
    sample_size: number;
    sample_size_ai_blocked: number;
    sample_size_ai_allowed: number;
    win_rate_actual: number;
    win_rate_if_blocked: number;
    win_rate_if_allowed: number;
    edge_pct: number;
    pnl_edge_usd: number;
  };
  thresholds: {
    min_sample_size: number;
    min_edge_pct: number;
  };
}

export async function fetchGraduationStatus(): Promise<GraduationReadiness> {
  return apiFetch<GraduationReadiness>('/config/ai/graduation');
}

export async function setAiMode(
  mode: 'shadow' | 'enforce',
  reason?: string
): Promise<{ status: string; mode: string }> {
  return apiFetch<{ status: string; mode: string }>('/config/ai/mode', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode, reason: reason || 'ui' }),
  });
}

export interface AiModeToggle {
  id: number;
  from_mode: string;
  to_mode: string;
  reason: string | null;
  created_at: string;
  created_by: string | null;
}

export async function fetchAiModeToggles(
  limit?: number
): Promise<{ toggles: AiModeToggle[] }> {
  const q = limit != null ? `?limit=${limit}` : '';
  return apiFetch<{ toggles: AiModeToggle[] }>(`/config/ai/mode-toggles${q}`);
}

export interface KillSwitchLogEntry {
  id: number;
  action: 'engage' | 'reset';
  reason: string | null;
  toggled_by: string | null;
  created_at: string;
}

export async function fetchKillSwitchLog(
  limit?: number
): Promise<{ events: KillSwitchLogEntry[] }> {
  const q = limit != null ? `?limit=${limit}` : '';
  return apiFetch<{ events: KillSwitchLogEntry[] }>(
    `/risk/kill-switch/log${q}`
  );
}

/**
 * Sprint 3.3: AI Run (Debate transcript + votes) for a signal
 */
export interface AiRunResponse {
  id: number;
  correlation_id?: string;
  signal_id?: number;
  run_type: string;
  recommendation: 'allow' | 'block';
  confidence: number;
  reason_codes: string[];
  memo: string;
  votes: Record<string, string>;
  transcript: Array<{ role: string; content: string }>;
  created_at?: string;
}

export async function fetchAiRunBySignal(
  signalId: number
): Promise<AiRunResponse | null> {
  const res = await apiFetch<AiRunResponse | { data: null }>(
    `/api/ai-runs?signal_id=${signalId}`
  );
  if (res && 'data' in res && res.data === null) return null;
  return res as AiRunResponse;
}

/** Lightweight council summary for a single signal (from bulk endpoint) */
export interface CouncilSummary {
  recommendation: 'allow' | 'block';
  confidence: number;
  votes: Record<string, string>;
}

/**
 * Fetch council summaries for multiple signals at once.
 * Returns a map of signal_id (string) → CouncilSummary.
 */
export async function fetchAiRunsBulk(
  signalIds: (string | number)[]
): Promise<Record<string, CouncilSummary>> {
  if (signalIds.length === 0) return {};
  const ids = signalIds.join(',');
  const resp = await apiFetch<{ runs: Record<string, CouncilSummary> }>(
    `/api/ai-runs/bulk?signal_ids=${ids}`
  );
  return resp.runs ?? {};
}

/**
 * URL Helper Functions
 */
export function getApiUrl(): string {
  return API_BASE_URL;
}

export function getHealthUrl(): string {
  return `${API_BASE_URL}/health`;
}

export function getPortfolioControlUrl(path: string = ''): string {
  return `${API_BASE_URL}/api/portfolio-control${path}`;
}

export function getRulesStrategyUrl(): string {
  return `${API_BASE_URL}/api/rules/strategy`;
}

// Sprint 4.4: Strategy Studio API helpers

export function getStrategiesUrl(): string {
  return `${API_BASE_URL}/api/strategies`;
}

export function getStrategyDetailUrl(id: number): string {
  return `${API_BASE_URL}/api/strategies/${id}`;
}

export function getStrategyActivateUrl(id: number, active: boolean): string {
  return `${API_BASE_URL}/api/strategies/${id}/activate?active=${active}`;
}

export function getAlertsActiveUrl(): string {
  return `${API_BASE_URL}/api/alerts/active`;
}

export function getAlertAcknowledgeUrl(alertId: number): string {
  return `${API_BASE_URL}/api/alerts/${alertId}/acknowledge`;
}

export function getAlertAcknowledgeAllUrl(): string {
  return `${API_BASE_URL}/api/alerts/acknowledge_all`;
}

export function getAlertSnoozeUrl(alertId: number): string {
  return `${API_BASE_URL}/api/alerts/${alertId}/snooze`;
}

export function getAlertRulePatchUrl(ruleId: number): string {
  return `${API_BASE_URL}/api/alerts/rules/${ruleId}`;
}

/**
 * Type Definitions
 */
export interface AccountDetailApi {
  account_name: string;
  account_number?: string;
  account_type?: string;
  balance: number | null;
  equity: number | null;
  margin_used: number;
  margin_free: number;
  free_margin?: number;
  margin_level?: number;
  margin_level_pct?: number;
  open_positions: number;
  active_positions?: number;
  floating_pnl: number;
  realized_pnl_today: number;
  daily_pnl?: number;
  daily_pnl_pct?: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  avg_win_usd?: number;
  avg_loss_usd?: number;
  profit_factor?: number;
  max_drawdown?: number;
  max_drawdown_pct?: number;
  sharpe_ratio?: number;
  last_sync?: string;
  last_sync_time?: string;
  leverage?: number;
  broker_profile_id?: number;
  broker_name?: string;
  mt_version?: string;
  server_name?: string;
  platform_type?: string;
  status: string;
  connection_status?: string;
  strategy_type?: string;
  provider?: string;
  allocated_capital_usd?: number;
  risk_percent?: number;
  min_rr_ratio?: number;
  max_lot_size?: number;
  max_positions?: number;
  pause_trading?: boolean;
  created_at?: string;
  is_archived?: boolean;
}

// AccountComparisonApi is used for individual accounts in cards/tables
// It's the same as AccountDetailApi
export type AccountComparisonApi = AccountDetailApi;

export interface AccountComparisonResponse {
  accounts: AccountDetailApi[];
  portfolio_summary?: {
    total_balance: number;
    total_equity: number;
    total_floating_pnl: number;
    total_realized_pnl_today: number;
    total_open_positions: number;
    avg_win_rate: number;
  };
}

export interface SymbolRiskRuleApi {
  id: number;
  symbol: string;
  pip_size?: number;
  risk_percent?: number;
  max_lot_size?: number;
  sl_buffer_pips?: number;
  created_at: string;
  updated_at: string;
}

/**
 * Risk Settings - TODO: Backend needs to implement these endpoints
 */
export async function fetchRiskSettings() {
  // TODO: Backend needs to implement this endpoint
  console.warn('fetchRiskSettings not implemented');
  return {};
}

export async function updateRiskSetting(
  settingKey: string,
  value: number | boolean | string | Record<string, unknown>,
  changeReason?: string
) {
  // TODO: Backend needs to implement this endpoint
  console.warn(`updateRiskSetting not implemented for ${settingKey}`);
  return {};
}

export async function fetchSymbolRiskRules() {
  // TODO: Backend needs to implement this endpoint
  console.warn('fetchSymbolRiskRules not implemented');
  return [];
}

export async function createSymbolRiskRule(
  rule: Omit<SymbolRiskRuleApi, 'id' | 'created_at' | 'updated_at'>
) {
  // TODO: Backend needs to implement this endpoint
  console.warn('createSymbolRiskRule not implemented');
  return {};
}

export async function updateSymbolRiskRule(
  symbol: string,
  updates: Partial<SymbolRiskRuleApi>
) {
  // TODO: Backend needs to implement this endpoint
  console.warn(`updateSymbolRiskRule not implemented for ${symbol}`);
  return {};
}

export async function deleteSymbolRiskRule(symbol: string) {
  // TODO: Backend needs to implement this endpoint
  console.warn(`deleteSymbolRiskRule not implemented for ${symbol}`);
  return {};
}

// ── Challenge Settings API ────────────────────────────────────────────────

export interface ChallengeSettings {
  account_name: string;
  broker_profile_id: number | null;
  evaluation_mode: boolean;
  evaluation_phase: 'phase1' | 'phase2' | 'funded';
  starting_balance: number;
  profit_target: number;
  max_daily_loss_pct: number;
  max_drawdown_pct: number;
  min_trading_days: number;
  consistency_limit_pct: number;
  consistency_enabled: boolean | null;  // null = use global setting
  evaluation_start_date: string | null;
}

export async function fetchChallengeSettings(accountName: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/api/v1/prop-firm/challenge-status/${encodeURIComponent(accountName)}`, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Failed to fetch challenge settings: ${res.statusText}`);
  return res.json();
}

export async function updateChallengeSettings(
  accountName: string,
  settings: any
): Promise<any> {
  // Map legacy payload properties to new backend structure
  let challenge_type = settings.challenge_type || settings.evaluation_phase;
  if (challenge_type === 'phase1') challenge_type = 'phase_1';
  if (challenge_type === 'phase2') challenge_type = 'phase_2';
  
  const payload = {
    challenge_type: challenge_type || 'phase_1',
    ...settings
  };

  const res = await fetch(`${API_BASE_URL}/api/v1/prop-firm/challenge-config/${encodeURIComponent(accountName)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to update challenge settings: ${res.statusText}`);
  }
  return res.json();
}

// ── Prop Firm API ──────────────────────────────────────────────────────────

export interface PropFirmEquity {
  daily_start_balance: number;
  current_equity: number;
  daily_high_water_mark: number;
}

export interface PropFirmDailyPnl {
  closed: number;
  floating: number;
  total: number;
}

export interface PropFirmDrawdown {
  daily_pct: number;
  daily_limit_pct: number;
  daily_remaining_usd: number;
  trailing_pct: number;
  trailing_limit_pct: number;
}

export interface PropFirmStatus {
  daily_loss_breach: boolean;
  drawdown_breach: boolean;
  safe_to_trade: boolean;
  consistency_ok: boolean;
}

export interface PropFirmConsistency {
  best_day_pct: number;
  limit_pct: number | null;  // null when consistency rule is disabled for this account
  status: 'safe' | 'warning' | 'danger' | 'violated' | null;
}

export interface PropFirmMetrics {
  equity: PropFirmEquity;
  daily_pnl: PropFirmDailyPnl;
  drawdown: PropFirmDrawdown;
  status: PropFirmStatus;
  consistency: PropFirmConsistency;
  days_remaining: number | null;
}

export interface PropFirmMetricsResponse {
  status: string;
  account_name: string;
  evaluation_phase: string;
  metrics: PropFirmMetrics;
}

export interface PropFirmSnapshot {
  snapshot_time: string;
  daily_drawdown_pct: number;
  trailing_drawdown_pct: number;
  daily_pnl_total: number;
  current_equity: number;
  daily_loss_breach: boolean;
  drawdown_breach: boolean;
}

export interface PropFirmHistoryResponse {
  account_name: string;
  days: number;
  snapshots: PropFirmSnapshot[];
}

export interface ConsistencyDetail {
  net_profit: number;
  best_day_pct: number;
  limit_pct: number;
  consistency_ok: boolean;
  daily_profits: Record<string, number>;
}

export interface MtmPosition {
  symbol: string;
  side: string;
  lots: number;
  open_price: number;
  current_price: number;
  floating_pnl: number;
  pct_to_sl?: number;
  at_risk?: boolean;
}

export interface MtmResponse {
  current_equity: number;
  starting_balance: number;
  closed_pnl: number;
  floating_pnl: number;
  daily_drawdown_pct: number;
  positions: MtmPosition[];
}

export async function fetchPropFirmMetrics(
  accountName = 'default'
): Promise<PropFirmMetricsResponse> {
  return apiFetch<PropFirmMetricsResponse>(
    `/api/prop-firm/metrics?account_name=${encodeURIComponent(accountName)}`
  );
}

export async function fetchPropFirmHistory(
  accountName = 'default',
  days = 7
): Promise<PropFirmHistoryResponse> {
  return apiFetch<PropFirmHistoryResponse>(
    `/api/prop-firm/history?account_name=${encodeURIComponent(
      accountName
    )}&days=${days}`
  );
}

export async function fetchPropFirmConsistency(
  accountName = 'default'
): Promise<ConsistencyDetail> {
  return apiFetch<ConsistencyDetail>(
    `/api/prop-firm/consistency?account_name=${encodeURIComponent(accountName)}`
  );
}

export async function fetchPropFirmMtm(
  accountName = 'default'
): Promise<MtmResponse> {
  return apiFetch<MtmResponse>(
    `/api/prop-firm/mtm?account_name=${encodeURIComponent(accountName)}`
  );
}

export async function resetPropFirmDaily(
  accountName = 'default'
): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(
    `/api/prop-firm/reset?account_name=${encodeURIComponent(accountName)}`,
    { method: 'POST' }
  );
}

// ── Account Trade History (DB + MetaAPI merged) ────────────────────────────

export interface TradeHistoryTrade {
  id: string | number;
  symbol: string;
  side: string;
  size: number;
  entry: number;
  exit: number;
  pnl_usd: number;
  entry_time: string | null;
  exit_time: string | null;
  outcome: 'win' | 'loss';
  source: 'database' | 'metaapi';
}

export interface TradeHistoryResponse {
  trades: TradeHistoryTrade[];
  total: number;
  sources: { database: number; metaapi: number };
}

export async function fetchAccountTradeHistory(
  accountName: string,
  days?: number
): Promise<TradeHistoryResponse> {
  const params = new URLSearchParams();
  if (days) params.set('days', String(days));
  return apiFetch<TradeHistoryResponse>(
    `/api/portfolio-control/accounts/${encodeURIComponent(
      accountName
    )}/history?${params}`
  );
}

// ── AI Copilot API ─────────────────────────────────────────────────────────

export interface CopilotHistoryMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface CopilotChatResponse {
  answer: string;
  context_used: string[];
  model_used?: string;
}

export async function fetchCopilotAnswer(
  question: string,
  history: CopilotHistoryMessage[] = []
): Promise<CopilotChatResponse> {
  return apiFetch<CopilotChatResponse>('/api/copilot/chat', {
    method: 'POST',
    body: JSON.stringify({ question, history }),
  });
}
