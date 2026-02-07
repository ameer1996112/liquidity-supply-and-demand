/**
 * TypeScript types for Transaction Cost Analysis (TCA) and Execution Quality
 */

export interface TCAMetrics {
  total_trades: number;
  avg_slippage_pips: number;
  avg_slippage_bps: number;
  total_slippage_cost_usd: number;
  avg_spread_cost_usd: number;
  avg_execution_time_ms: number;
  worst_slippage_pips: number;
  best_slippage_pips: number;
  median_slippage_pips: number;
  total_spread_cost_usd: number;
}

export interface SlippageBySymbol {
  symbol: string;
  avg_slippage_pips: number;
  trade_count: number;
  total_cost_usd: number;
  worst_slippage_pips: number;
}

export interface SlippageByHour {
  hour: number;
  avg_slippage_pips: number;
}

export interface LatencyBreakdown {
  avg_signal_to_submit_ms: number;
  avg_submit_to_fill_ms: number;
  avg_total_execution_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  median_latency_ms: number;
}

export interface TCAAlert {
  id: number;
  signal_id: number;
  alert_type: 'high_slippage' | 'high_latency' | 'unknown';
  slippage_pips?: number;
  total_execution_ms?: number;
  exceeds_slippage_threshold: boolean;
  exceeds_latency_threshold: boolean;
  created_at: string;
}

export interface TCASettings {
  tca_enabled: boolean;
  slippage_threshold_pips: number;
  latency_threshold_ms: number;
  spread_threshold_pips: number;
}
