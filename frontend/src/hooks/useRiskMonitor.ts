import { useQuery } from '@tanstack/react-query';

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
).replace(/\/$/, '');

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

export interface RiskMonitorSummary {
  total_accounts: number;
  active_accounts: number;
  total_equity_usd: number;
  total_starting_balance_usd: number;
  total_daily_pnl_usd: number;
  total_open_positions: number;
  accounts_in_warning: number;
  accounts_blocked: number;
  global_kill_switch_active: boolean;
}

export interface AccountGuardCard {
  account_name: string;
  broker_profile_id?: number | null;
  account_type: string;
  evaluation_phase?: string | null;
  prop_firm_name?: string | null;
  run_mode: string;
  connection_status?: string | null;
  starting_balance_usd: number;
  current_equity_usd: number;
  daily_pnl_usd: number;
  daily_pnl_pct: number;
  peak_equity_usd: number;
  current_drawdown_pct: number;
  max_drawdown_allowed_pct: number;
  drawdown_utilization_pct: number;
  daily_loss_used_usd: number;
  daily_loss_limit_usd: number;
  open_positions: number;
  max_positions: number;
  trades_today: number;
  max_trades_today: number;
  risk_multiplier: number;
  risk_label: string;
  effective_risk_pct: number;
  base_risk_pct: number;
  kill_switch_active: boolean;
  blocked: boolean;
  warning_message?: string | null;
  blocked_reason?: string | null;
  guard_rails: GuardRailStatus[];
}

export interface RiskMonitorData {
  summary: RiskMonitorSummary;
  accounts: AccountGuardCard[];
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
    refetchInterval: 30000,
    staleTime: 20000,
  });
}
