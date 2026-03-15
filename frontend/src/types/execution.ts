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
  alert_type: 'high_slippage' | 'high_latency' | 'unknown' | 'high_bot_latency' | 'high_broker_latency';
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

// ── Pipeline Traces (Sprint 2.1 / 2.4) ────────────────────────────────────

/** Timestamps for each hop in the execution pipeline */
export interface TraceHops {
  received_at?: string | null;
  enqueued_at?: string | null;
  dequeued_at?: string | null;
  validated_at?: string | null;
  risk_started_at?: string | null;
  risk_finished_at?: string | null;
  exec_started_at?: string | null;
  exec_submitted_at?: string | null;
  broker_ack_at?: string | null;
  broker_confirmed_at?: string | null;
  reconciled_at?: string | null;
  error_at?: string | null;
}

/** Lightweight row returned by GET /api/traces */
export interface TraceSummary {
  trace_id?: string | null;
  correlation_id: string;
  signal_id?: number | null;
  account_id?: string | null;
  symbol?: string | null;
  run_mode?: string | null;
  received_at?: string | null;
  total_ms?: number | null;
  error_type?: string | null;
  created_at?: string | null;
}

/** Full detail returned by GET /api/traces/{correlation_id} */
export interface TraceDetail extends TraceSummary {
  hops: TraceHops;
  error_message?: string | null;
}

/** Derived badge status for a single trace */
export interface TraceBrokerStatus {
  broker_connected: boolean;  // has broker_ack_at
  broker_confirmed: boolean;  // has broker_confirmed_at
  missing_on_broker: boolean; // submitted but no broker_ack, no error
}

/** Account row from GET /api/accounts */
export interface AccountRow {
  account_id: string;
  name: string;
  broker_type: string;
  status: string;
  queue_key?: string | null;
}
