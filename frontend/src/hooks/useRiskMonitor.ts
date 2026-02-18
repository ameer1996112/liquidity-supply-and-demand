import { useQuery } from '@tanstack/react-query';

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
).replace(/\/$/, '');

export interface DailyRiskStatus {
  loss_used_usd: number;
  loss_limit_usd: number;
  loss_pct: number;
  remaining_usd: number;
  profit_target_usd: number;
  profit_current_usd: number;
  is_profit_target_hit: boolean;
  is_loss_limit_hit: boolean;
}

export interface PositionLimitsStatus {
  open_positions: number;
  max_positions: number;
  trades_today: number;
  max_trades_today: number;
  warning: string | null;
}

export interface DrawdownStatus {
  current_dd_pct: number;
  max_dd_allowed_pct: number;
  dd_utilization_pct: number;
  remaining_dd_pct: number;
  peak_equity_usd: number;
  current_equity_usd: number;
}

export interface ActiveSettings {
  risk_per_trade_pct: number;
  min_rr_ratio: number;
  stop_loss_buffer_pips: number;
  trading_hours_utc: string;
  max_trades_per_day: number;
  dead_zone_block_enabled: boolean;
  account_balance_usd: number;
}

export interface GuardRailStatus {
  name: string;
  status: 'passed' | 'warning' | 'critical' | 'unknown';
  severity: 'success' | 'warning' | 'critical' | 'info';
  message: string;
}

export interface SymbolOverride {
  symbol: string;
  risk_pct: number;
  max_lots: number;
  sl_buffer_pips: number;
  pip_size: number;
}

export interface RiskMonitorData {
  daily_risk: DailyRiskStatus;
  position_limits: PositionLimitsStatus;
  drawdown: DrawdownStatus;
  active_settings: ActiveSettings;
  guard_rails: GuardRailStatus[];
  symbol_overrides: SymbolOverride[];
  last_updated: string;
  data_source: string;
}

async function fetchRiskMonitor(): Promise<RiskMonitorData> {
  const res = await fetch(`${API_URL}/api/risk/monitor`);
  if (!res.ok) {
    throw new Error(`Risk monitor API error: ${res.status}`);
  }
  return res.json();
}

export function useRiskMonitor() {
  return useQuery({
    queryKey: ['risk-monitor'],
    queryFn: fetchRiskMonitor,
    refetchInterval: 30000, // Auto-refresh every 30 seconds
    staleTime: 20000, // Consider data stale after 20 seconds
  });
}
