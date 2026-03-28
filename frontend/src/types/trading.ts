// Trading Signal Types - Mapped to Supabase `trading_signals` table
// CRITICAL: These field names must match the database schema exactly

export type SignalSide = 'buy' | 'sell' | 'BUY' | 'SELL';

// High-level action coming from TradingView / backend
export type SignalActionType =
  | 'entry'
  | 'exit'
  | 'close_all'
  | 'modify'
  | 'cancel';
export type SignalStatus =
  | 'active' // Live trade
  | 'closed' // Trade completed
  | 'filtered' // Pre-execution filter
  | 'ai_rejected' // AI veto
  | 'model_error' // ML model unavailable/invalid inference
  | 'executed' // Legacy: filled
  | 'pending' // Awaiting execution
  | 'failed' // Execution failed
  | 'PENDING'
  | 'OPEN'
  | 'CLOSED'
  | 'CANCELLED'
  | 'ERROR';

export type TradingMode = 'LIVE' | 'PAPER';

// AI Reasoning - structured JSON from the AI model
export interface AIReasoning {
  zone_id?: number;
  zone_type?: 'demand' | 'supply';
  zone_grade?: string;
  zone_score?: number;
  entry_model?: string;
  liquidity_swept?: boolean;
  target_swept?: boolean;
  caused_sweep?: boolean;
  is_accuracy?: boolean;
  session?: number;
  trend?: number;
  htf_trend?: number;
  rsi?: number;
  rvol?: number;
  adx?: number;
  atr_ratio?: number;
  base_quality?: number;
  departure_strength?: number;
  liquidity_distance?: number;
  liquidity_spread?: number;
  liquidity_distance_pips?: number;
  liquidity_spread_pips?: number;
  return_strength?: number;
  guardian_liq_sweep?: boolean;
  guardian_arrival?: string;
  guardian_structure_break?: boolean;
  // v9.1 Ensemble Brain – must match backend worker ai_result (src/worker.py, src/ai/brain.py)
  decision?: string; // "GO" | "NO_GO"
  reason?: string;
  rf_prob?: number; // 0–1 from RF model
  rf_threshold?: number; // 0-1 effective threshold used by RF gate
  rf_note?: string;
  narrative?: string; // Market narrative from adapters/market_data
  rules?: string[]; // RAG-retrieved rule strings
  llm_status?: 'ok' | 'skipped' | 'error';
  llm_model_used?: string | null;
  llm_error_code?: string | null;
  llm_error_message_short?: string | null;
  llm_error_raw?: string | null;
  decision_trace?: {
    rf_probability_raw?: number;
    rf_probability_pct?: number;
    threshold_raw?: number;
    threshold_pct?: number;
    predicted_class?: string | number;
    class_mapping?: Record<string, unknown>;
    features_snapshot?: Record<string, unknown>;
    rules?: Array<{
      rule_id?: string;
      passed?: boolean;
      status?: string;
      non_blocking?: boolean;
      message?: string;
      [key: string]: unknown;
    }>;
    rejected_rule?: Record<string, unknown> | null;
    [key: string]: unknown;
  };
  // Allow arbitrary additional fields
  [key: string]: unknown;
}

// Main Trading Signal Interface - matches `trading_signals` table
export interface TradingSignal {
  id: string;
  created_at: string;
  updated_at?: string;

  // Asset identification
  symbol: string; // e.g., "BTCUSD", "XAUUSD"
  ticker?: string; // Legacy alias for symbol

  // Direction
  side: SignalSide; // "buy" or "sell"
  action?: SignalSide; // Legacy alias for side (backwards-compatible)

  // High-level intent & execution hints (Sprint 6.2)
  /**
   * Normalized webhook / DB action: entry|exit|close_all|modify|cancel.
   * Stored in trading_signals.signal_action (see migrations/037_signal_actions.sql).
   */
  signal_action?: SignalActionType | string | null;
  /**
   * Order type hint from webhook: market|limit|stop.
   */
  order_type?: 'market' | 'limit' | 'stop' | string | null;
  /**
   * Optional trailing stop configuration emitted by strategy.
   * May be a simple flag, distance in pips, or structured JSON (frontend treats as opaque metadata).
   */
  trailing_stop?: unknown;
  /**
   * Optional additional TP levels (prices) provided by strategy.
   */
  multi_tp?: number[] | null;
  /**
   * Optional partial close percentage requested by strategy (0-100).
   */
  partial_close_percent?: number | null;

  // Entry parameters
  price?: number; // Entry price
  entry?: number; // Alternative entry field
  stop_loss?: number;
  sl?: number; // Alternative SL field
  take_profit?: number;
  tp?: number; // Alternative TP field
  position_size?: number;

  // AI Analysis
  score?: number; // AI confidence 0-100
  ai_confidence?: number; // Legacy alias for score
  notes?: string | null; // AI reasoning text
  ai_reasoning?: AIReasoning | string | null; // Structured or stringified JSON
  filter_reason?: string | null; // Why signal was filtered/rejected

  // Status & Outcome
  status: SignalStatus;
  mode?: TradingMode;
  /** DB column run_mode (LIVE/PAPER); use with mode for stats. */
  run_mode?: string;

  // Zone / signal context (top-level DB columns from TradingView webhook)
  zone_id?: number;
  zone_type?: 'demand' | 'supply' | string;
  zone_grade?: string;
  entry_model?: string;
  liq_swept?: boolean;
  target_swept?: boolean;
  caused_sweep?: boolean;
  is_accuracy?: boolean;
  session?: number;
  trend?: number;
  htf_trend?: number;
  rsi?: number;
  rvol?: number;
  adx?: number;
  atr_ratio?: number;
  base_quality?: number;
  departure_strength?: number;
  liquidity_distance?: number;
  liquidity_spread?: number;
  liquidity_distance_pips?: number;
  liquidity_spread_pips?: number;
  return_strength?: number;

  // Trade metrics
  rr_ratio?: number;
  sl_pips?: number;
  pnl?: number;
  pnl_usd?: number; // Alternative PnL field
  pnl_percentage?: number;

  // Broker execution info (LIVE)
  broker_order_id?: string;
  close_broker_order_id?: string;
  /** Broker account name at execution (MetaApi or config). */
  account_name?: string | null;

  // Exit information
  closed_at?: string;
  exit_price?: number;
  exit_type?: 'TP_HIT' | 'SL_HIT' | 'MANUAL' | 'TIME_STOP' | string;

  // New execution source and timestamps
  execution_source?: 'metaapi' | 'paper' | 'signal_only';
  broker_position_id?: string;
  opened_at?: string;
  last_broker_sync_at?: string;
}

export interface SignalStats {
  total_signals_24h: number;
  executed_count: number;
  filtered_count: number;
  failed_count: number;
  win_rate: number; // Backwards-compatible overall win rate (defaults to live)
  live_win_rate?: number; // Live-only win rate
  /** Number of closed trades that contribute to win_rate calculation */
  closed_trade_count?: number;
  ai_reject_rate: number;
  active_trades: number;
  total_pnl_24h: number; // Backwards-compatible PnL (defaults to live)
  live_pnl_24h?: number;
  paper_pnl_24h?: number;
  /** PnL for today only (resets at midnight UTC) - mixed LIVE+PAPER for backward compat */
  daily_pnl: number;
  /** LIVE-only PnL for today (resets at midnight UTC) */
  live_daily_pnl?: number;
  /** PAPER-only PnL for today (resets at midnight UTC) */
  paper_daily_pnl?: number;
  /** All-time cumulative PnL - mixed LIVE+PAPER for backward compat */
  total_pnl: number;
  /** All-time LIVE-only PnL */
  live_total_pnl?: number;
  /** All-time PAPER-only PnL */
  paper_total_pnl?: number;
  /** Daily drawdown % (today's loss relative to starting equity) */
  daily_drawdown_pct: number;
  /** Data source for PnL values: broker snapshot (most accurate) or signal records (fallback) */
  pnl_source?: 'broker_snapshot' | 'signal_records';
}

// Filter types for queries
export interface SignalFilter {
  mode?: TradingMode;
  status?: SignalStatus;
  symbol?: string;
  side?: SignalSide;
  from_date?: string;
  to_date?: string;
  limit?: number;
}

// Real-time event types
export type RealtimeEventType = 'INSERT' | 'UPDATE' | 'DELETE';

export interface RealtimePayload<T> {
  eventType: RealtimeEventType;
  new: T;
  old: T | null;
}

// Helper type guards and normalizers
export function normalizeSignal(
  raw: Partial<TradingSignal> & { run_mode?: string },
): TradingSignal {
  // IMPORTANT: Prioritize run_mode over mode since backend uses run_mode as the canonical field
  const rawMode = (raw as { run_mode?: string }).run_mode ?? raw.mode;
  const rawStatus = raw.status || 'pending';

  // Normalize high-level action when present, but keep unknown values for debugging.
  const rawSignalAction = (raw as { signal_action?: string }).signal_action;
  const normalizedSignalAction =
    typeof rawSignalAction === 'string'
      ? (rawSignalAction.toLowerCase() as SignalActionType | string)
      : rawSignalAction ?? undefined;
  return {
    id: raw.id || '',
    created_at: raw.created_at || new Date().toISOString(),
    updated_at: raw.updated_at,
    symbol: raw.symbol || raw.ticker || 'UNKNOWN',
    ticker: raw.ticker || raw.symbol,
    side: raw.side || raw.action || 'buy',
    action: raw.action || raw.side,
    price: raw.price ?? raw.entry,
    entry: raw.entry ?? raw.price,
    stop_loss: raw.stop_loss ?? raw.sl,
    sl: raw.sl ?? raw.stop_loss,
    take_profit: raw.take_profit ?? raw.tp,
    tp: raw.tp ?? raw.take_profit,
    position_size: raw.position_size,
    score: raw.score ?? raw.ai_confidence,
    ai_confidence: raw.ai_confidence ?? raw.score,
    notes: raw.notes,
    ai_reasoning: raw.ai_reasoning,
    filter_reason: raw.filter_reason,
    status: (typeof rawStatus === 'string'
      ? rawStatus.toLowerCase()
      : 'pending') as SignalStatus,
    mode: (typeof rawMode === 'string' ? rawMode.toUpperCase() : rawMode) as
      | TradingMode
      | undefined,
    run_mode: (raw as { run_mode?: string }).run_mode,
    zone_id: raw.zone_id,
    zone_type: raw.zone_type,
    zone_grade: raw.zone_grade,
    entry_model: raw.entry_model,
    liq_swept: raw.liq_swept,
    target_swept: raw.target_swept,
    caused_sweep: raw.caused_sweep,
    is_accuracy: raw.is_accuracy,
    session: raw.session,
    trend: raw.trend,
    htf_trend: raw.htf_trend,
    rsi: raw.rsi,
    rvol: raw.rvol,
    adx: raw.adx,
    atr_ratio: raw.atr_ratio,
    base_quality: raw.base_quality,
    departure_strength: raw.departure_strength,
    liquidity_distance: raw.liquidity_distance,
    liquidity_spread: raw.liquidity_spread,
    liquidity_distance_pips: raw.liquidity_distance_pips,
    liquidity_spread_pips: raw.liquidity_spread_pips,
    return_strength: raw.return_strength,
    rr_ratio: raw.rr_ratio,
    sl_pips: raw.sl_pips,
    pnl: raw.pnl ?? raw.pnl_usd,
    pnl_usd: raw.pnl_usd ?? raw.pnl,
    pnl_percentage: raw.pnl_percentage,
    broker_order_id: raw.broker_order_id,
    close_broker_order_id: raw.close_broker_order_id,
    account_name: raw.account_name ?? null,
    closed_at: raw.closed_at,
    exit_price: raw.exit_price,
    exit_type: raw.exit_type,
    signal_action: normalizedSignalAction,
    order_type: raw.order_type,
    trailing_stop: raw.trailing_stop,
    multi_tp: (raw.multi_tp as number[] | null) ?? null,
    partial_close_percent: raw.partial_close_percent ?? null,
  };
}

// Get the display ticker (symbol) from a signal
export function getSymbol(signal: Partial<TradingSignal>): string {
  return signal.symbol || signal.ticker || 'UNKNOWN';
}

// Get the direction (buy/sell) from a signal
export function getSide(signal: Partial<TradingSignal>): 'buy' | 'sell' {
  const side = signal.side || signal.action || 'buy';
  return side.toLowerCase() as 'buy' | 'sell';
}

// Get the AI confidence score from a signal
export function getScore(signal: Partial<TradingSignal>): number | null {
  return signal.score ?? signal.ai_confidence ?? null;
}

// Get the PnL from a signal
export function getPnl(signal: Partial<TradingSignal>): number | null {
  return signal.pnl ?? signal.pnl_usd ?? null;
}

// Get AI reasoning text from a signal
export function getNotes(signal: Partial<TradingSignal>): string | null {
  if (signal.notes) return signal.notes;
  if (signal.filter_reason) return signal.filter_reason;
  if (typeof signal.ai_reasoning === 'string') return signal.ai_reasoning;
  return null;
}

export interface AccountSummaryItem {
  id: number
  name: string
  account_type: 'funded' | 'evaluation' | 'personal'
  run_mode: 'LIVE' | 'PAPER'
  connection_status: 'connected' | 'error' | 'unknown'
  pnl_today: number
  pnl_total: number
  positions_count: number
  win_rate: number
  trades_today: number
}

export interface DashboardSummary {
  total_pnl_today: number
  total_pnl_all_time: number
  total_win_rate: number
  total_active_positions: number
  total_trades_today: number
  max_drawdown_pct: number
  accounts: AccountSummaryItem[]
}
