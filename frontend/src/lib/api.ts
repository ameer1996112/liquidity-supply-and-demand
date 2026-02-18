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
  options?: RequestInit,
): Promise<T> {
  // Ensure endpoint starts with / and construct clean URL
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const url = `${API_BASE_URL}${cleanEndpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API Error (${response.status}): ${error}`);
  }

  return response.json();
}

/**
 * Backtest API client
 */
export const backtestAPI = {
  /**
   * Run a backtest
   */
  async runBacktest(request: {
    symbol: string;
    start_date: string;
    end_date: string;
    timeframe: string;
    initial_cash: number;
    commission: number;
    risk_percent: number;
    min_rr_ratio: number;
    require_liquidity_sweep?: boolean;
    reject_compression_arrival?: boolean;
    require_structure_break?: boolean;
  }) {
    return apiFetch<any>('/api/backtest/run', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  /**
   * Validate strategy before deploying to live bot
   */
  async validateStrategy(request: {
    symbol: string;
    days_to_test: number;
    timeframe: string;
    risk_percent: number;
    min_rr_ratio: number;
    reject_compression_arrival: boolean;
    min_trades: number;
    min_win_rate: number;
    min_profit_factor: number;
    max_drawdown: number;
  }) {
    return apiFetch<any>('/api/bot/validate-strategy', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  /**
   * Health check
   */
  async healthCheck() {
    return apiFetch<{ status: string }>('/api/backtest/health');
  },
};

/**
 * Portfolio Control - Account Management
 */
export async function fetchAccountsComparison(): Promise<AccountDetailApi[]> {
  const response = await apiFetch<AccountComparisonResponse>(
    '/api/portfolio-control/accounts/comparison',
  );
  return response.accounts || [];
}

export async function fetchAccountDetail(accountName: string) {
  return apiFetch<any>(
    `/api/portfolio-control/accounts/${encodeURIComponent(accountName)}`,
  );
}

export async function syncAccount(accountName: string) {
  return apiFetch<any>(
    `/api/portfolio-control/accounts/${encodeURIComponent(accountName)}/sync`,
    {
      method: 'POST',
    },
  );
}

export async function fetchAllocationSuggest(
  totalCapital: number,
  goal: string = 'maximize_sharpe',
) {
  return apiFetch<any>(
    `/api/portfolio-control/accounts/allocation-suggest?total_capital=${totalCapital}&goal=${goal}`,
  );
}

export async function executeAllocation(
  accountName: string,
  allocationUsd: number,
) {
  return apiFetch<any>(
    `/api/portfolio-control/accounts/${encodeURIComponent(accountName)}/allocate`,
    {
      method: 'POST',
      body: JSON.stringify({ allocation_usd: allocationUsd }),
    },
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
    },
  );
}

export async function fetchTradeCopyLog(limit: number = 50) {
  return apiFetch<any>(
    `/api/portfolio-control/accounts/trade-copy-log?limit=${limit}`,
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
    '/api/portfolio-control/optimizer/hedge-suggestions',
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
    },
  );
}

export async function rejectHedgeSuggestion(suggestionId: number) {
  return apiFetch<any>(
    `/api/portfolio-control/optimizer/hedge-suggestions/${suggestionId}/reject`,
    {
      method: 'POST',
    },
  );
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
    },
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
    },
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
    `/api/portfolio-control/accounts/${encodeURIComponent(accountName)}/positions`,
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

export function getAlertsActiveUrl(): string {
  return `${API_BASE_URL}/api/alerts/active`;
}

export function getAlertAcknowledgeUrl(alertId: number): string {
  return `${API_BASE_URL}/api/alerts/${alertId}/acknowledge`;
}

export function getAlertAcknowledgeAllUrl(): string {
  return `${API_BASE_URL}/api/alerts/acknowledge_all`;
}

/**
 * Type Definitions
 */
export interface AccountDetailApi {
  account_name: string;
  account_number?: string;
  account_type?: string;
  balance: number;
  equity: number;
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
  changeReason?: string,
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
  rule: Omit<SymbolRiskRuleApi, 'id' | 'created_at' | 'updated_at'>,
) {
  // TODO: Backend needs to implement this endpoint
  console.warn('createSymbolRiskRule not implemented');
  return {};
}

export async function updateSymbolRiskRule(
  symbol: string,
  updates: Partial<SymbolRiskRuleApi>,
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
