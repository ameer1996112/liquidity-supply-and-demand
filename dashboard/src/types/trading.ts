// Trading Signal Types - Strictly typed for Supabase

export type SignalAction = 'BUY' | 'SELL';
export type SignalStatus = 'EXECUTED' | 'FILTERED' | 'FAILED' | 'PENDING';
export type TradingMode = 'LIVE' | 'PAPER';

export interface AIReasoning {
  zone_id: number;
  zone_type: 'demand' | 'supply';
  zone_grade: string;
  zone_score: number;
  entry_model: string;
  liquidity_swept: boolean;
  target_swept: boolean;
  caused_sweep: boolean;
  is_accuracy: boolean;
  session: number;
  trend: number;
  htf_trend: number;
  rsi: number;
  rvol: number;
  adx: number;
  atr_ratio: number;
  base_quality: number;
  departure_strength: number;
  liquidity_distance: number;
  liquidity_spread: number;
  return_strength: number;
  // AI Guardian metrics
  guardian_liq_sweep?: boolean;
  guardian_arrival?: string;
  guardian_structure_break?: boolean;
}

export interface TradingSignal {
  id: string;
  created_at: string;
  updated_at: string;
  ticker: string;
  action: SignalAction;
  price: number;
  stop_loss: number;
  take_profit: number;
  position_size: number;
  ai_confidence: number;
  ai_reasoning: AIReasoning;
  status: SignalStatus;
  filter_reason: string | null;
  mode: TradingMode;
  // Calculated fields (from backend)
  rr_ratio?: number;
  sl_pips?: number;
  pnl?: number;
  pnl_percentage?: number;
  closed_at?: string;
  exit_price?: number;
  exit_type?: 'TP_HIT' | 'SL_HIT' | 'MANUAL' | 'TIME_STOP';
}

export interface SignalStats {
  total_signals_24h: number;
  executed_count: number;
  filtered_count: number;
  failed_count: number;
  win_rate: number;
  ai_reject_rate: number;
  active_trades: number;
  total_pnl_24h: number;
}

// Filter types for queries
export interface SignalFilter {
  mode?: TradingMode;
  status?: SignalStatus;
  ticker?: string;
  action?: SignalAction;
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
