import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { TradingSignal, SignalStats } from '@/types/trading';

// Database types for Supabase
export interface Database {
  public: {
    Tables: {
      trading_signals: {
        Row: TradingSignal;
        Insert: Omit<TradingSignal, 'id' | 'created_at' | 'updated_at'>;
        Update: Partial<Omit<TradingSignal, 'id' | 'created_at'>>;
      };
    };
  };
}

// Environment validation
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn(
    '⚠️ Supabase credentials not found. Using mock data mode. ' +
    'Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY to connect.'
  );
}

// Create Supabase client
export const supabase: SupabaseClient<Database> | null =
  supabaseUrl && supabaseAnonKey
    ? createClient<Database>(supabaseUrl, supabaseAnonKey, {
        realtime: {
          params: {
            eventsPerSecond: 10,
          },
        },
      })
    : null;

// Helper to check if Supabase is available
export const isSupabaseAvailable = (): boolean => supabase !== null;

// Query helpers
export async function fetchSignals(
  options: {
    mode?: 'LIVE' | 'PAPER';
    limit?: number;
    offset?: number;
  } = {}
): Promise<TradingSignal[]> {
  if (!supabase) {
    return getMockSignals(options.mode);
  }

  const { mode, limit = 50, offset = 0 } = options;

  let query = supabase
    .from('trading_signals')
    .select('*')
    .order('created_at', { ascending: false })
    .range(offset, offset + limit - 1);

  if (mode) {
    query = query.eq('mode', mode);
  }

  const { data, error } = await query;

  if (error) {
    console.error('Error fetching signals:', error);
    throw error;
  }

  return data || [];
}

export async function fetchSignalStats(): Promise<SignalStats> {
  if (!supabase) {
    return getMockStats();
  }

  // Get signals from last 24 hours
  const twentyFourHoursAgo = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();

  const { data, error } = await supabase
    .from('trading_signals')
    .select('*')
    .gte('created_at', twentyFourHoursAgo);

  if (error) {
    console.error('Error fetching stats:', error);
    throw error;
  }

  const signals: TradingSignal[] = data || [];
  // Normalize status comparison to handle both uppercase and lowercase
  const normalizeStatus = (status: string | undefined) => status?.toLowerCase();
  const executed = signals.filter(s => normalizeStatus(s.status) === 'executed');
  const filtered = signals.filter(s =>
    normalizeStatus(s.status) === 'filtered' || normalizeStatus(s.status) === 'ai_rejected'
  );
  const failed = signals.filter(s => normalizeStatus(s.status) === 'failed');
  const activeSignals = signals.filter(s => normalizeStatus(s.status) === 'active');
  const closed = executed.filter(s => s.closed_at);
  const wins = closed.filter(s => (s.pnl || 0) > 0);
  // Active trades are either 'active' status or executed without closed_at
  const active = [...activeSignals, ...executed.filter(s => !s.closed_at)];

  // Count AI rejected signals separately
  const aiRejected = signals.filter(s => normalizeStatus(s.status) === 'ai_rejected');

  return {
    total_signals_24h: signals.length,
    executed_count: executed.length + activeSignals.length,
    filtered_count: filtered.length,
    failed_count: failed.length,
    win_rate: closed.length > 0 ? (wins.length / closed.length) * 100 : 0,
    ai_reject_rate: signals.length > 0
      ? (aiRejected.length / signals.length) * 100
      : 0,
    active_trades: active.length,
    total_pnl_24h: closed.reduce((sum, s) => sum + (s.pnl || 0), 0),
  };
}

// Mock data for development without Supabase
function getMockSignals(mode?: 'LIVE' | 'PAPER'): TradingSignal[] {
  const mockSignals: TradingSignal[] = [
    {
      id: '1',
      created_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
      updated_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
      ticker: 'XAUUSD',
      action: 'BUY',
      price: 2645.50,
      stop_loss: 2640.00,
      take_profit: 2660.00,
      position_size: 0.5,
      ai_confidence: 87,
      ai_reasoning: {
        zone_id: 142,
        zone_type: 'demand',
        zone_grade: 'A',
        zone_score: 85,
        entry_model: 'FLIP',
        liquidity_swept: true,
        target_swept: true,
        caused_sweep: true,
        is_accuracy: true,
        session: 2,
        trend: 1,
        htf_trend: 1,
        rsi: 42.5,
        rvol: 1.35,
        adx: 28.4,
        atr_ratio: 0.65,
        base_quality: 78.5,
        departure_strength: 82.3,
        liquidity_distance: 12.5,
        liquidity_spread: 18.2,
        return_strength: 75.8,
        guardian_liq_sweep: true,
        guardian_arrival: 'aggressive',
        guardian_structure_break: true,
      },
      status: 'EXECUTED',
      filter_reason: null,
      mode: 'LIVE',
      rr_ratio: 2.7,
      sl_pips: 55,
      pnl: 245.50,
      pnl_percentage: 2.45,
    },
    {
      id: '2',
      created_at: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
      updated_at: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
      ticker: 'EURUSD',
      action: 'SELL',
      price: 1.0845,
      stop_loss: 1.0865,
      take_profit: 1.0800,
      position_size: 1.0,
      ai_confidence: 72,
      ai_reasoning: {
        zone_id: 89,
        zone_type: 'supply',
        zone_grade: 'B+',
        zone_score: 72,
        entry_model: 'DIR_CLOSE',
        liquidity_swept: true,
        target_swept: true,
        caused_sweep: false,
        is_accuracy: false,
        session: 2,
        trend: 0,
        htf_trend: 0,
        rsi: 68.2,
        rvol: 0.95,
        adx: 22.1,
        atr_ratio: 0.45,
        base_quality: 65.0,
        departure_strength: 70.2,
        liquidity_distance: 8.5,
        liquidity_spread: 12.8,
        return_strength: 68.5,
        guardian_liq_sweep: true,
        guardian_arrival: 'gradual',
        guardian_structure_break: false,
      },
      status: 'EXECUTED',
      filter_reason: null,
      mode: 'LIVE',
      rr_ratio: 2.25,
      sl_pips: 20,
    },
    {
      id: '3',
      created_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
      updated_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
      ticker: 'GBPJPY',
      action: 'BUY',
      price: 188.450,
      stop_loss: 187.950,
      take_profit: 189.900,
      position_size: 0.3,
      ai_confidence: 58,
      ai_reasoning: {
        zone_id: 203,
        zone_type: 'demand',
        zone_grade: 'C+',
        zone_score: 58,
        entry_model: 'BREAK_CANDLE',
        liquidity_swept: true,
        target_swept: false,
        caused_sweep: true,
        is_accuracy: false,
        session: 1,
        trend: 1,
        htf_trend: 0,
        rsi: 38.5,
        rvol: 1.12,
        adx: 18.5,
        atr_ratio: 0.78,
        base_quality: 55.0,
        departure_strength: 62.1,
        liquidity_distance: 22.0,
        liquidity_spread: 28.5,
        return_strength: 52.3,
        guardian_liq_sweep: false,
        guardian_arrival: 'gradual',
        guardian_structure_break: false,
      },
      status: 'FILTERED',
      filter_reason: 'AI Quality: 58 < 60 threshold',
      mode: 'PAPER',
      rr_ratio: 2.9,
      sl_pips: 50,
    },
    {
      id: '4',
      created_at: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
      updated_at: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
      ticker: 'USDJPY',
      action: 'SELL',
      price: 149.850,
      stop_loss: 150.200,
      take_profit: 149.000,
      position_size: 0.8,
      ai_confidence: 81,
      ai_reasoning: {
        zone_id: 156,
        zone_type: 'supply',
        zone_grade: 'A-',
        zone_score: 81,
        entry_model: 'FLIP',
        liquidity_swept: true,
        target_swept: true,
        caused_sweep: true,
        is_accuracy: true,
        session: 2,
        trend: 0,
        htf_trend: 0,
        rsi: 72.8,
        rvol: 1.45,
        adx: 32.1,
        atr_ratio: 0.52,
        base_quality: 82.0,
        departure_strength: 78.5,
        liquidity_distance: 5.5,
        liquidity_spread: 10.2,
        return_strength: 85.2,
        guardian_liq_sweep: true,
        guardian_arrival: 'aggressive',
        guardian_structure_break: true,
      },
      status: 'EXECUTED',
      filter_reason: null,
      mode: 'LIVE',
      rr_ratio: 2.43,
      sl_pips: 35,
      pnl: -87.50,
      pnl_percentage: -0.88,
      closed_at: new Date(Date.now() - 1000 * 60 * 20).toISOString(),
      exit_price: 150.200,
      exit_type: 'SL_HIT',
    },
    {
      id: '5',
      created_at: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
      updated_at: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
      ticker: 'XAUUSD',
      action: 'SELL',
      price: 2638.00,
      stop_loss: 2645.00,
      take_profit: 2620.00,
      position_size: 0.4,
      ai_confidence: 45,
      ai_reasoning: {
        zone_id: 178,
        zone_type: 'supply',
        zone_grade: 'C',
        zone_score: 45,
        entry_model: 'DIR_CLOSE',
        liquidity_swept: false,
        target_swept: false,
        caused_sweep: false,
        is_accuracy: false,
        session: 3,
        trend: 1,
        htf_trend: 1,
        rsi: 55.2,
        rvol: 0.72,
        adx: 15.2,
        atr_ratio: 0.88,
        base_quality: 42.0,
        departure_strength: 48.5,
        liquidity_distance: 35.0,
        liquidity_spread: 42.5,
        return_strength: 38.2,
        guardian_liq_sweep: false,
        guardian_arrival: 'gradual',
        guardian_structure_break: false,
      },
      status: 'FILTERED',
      filter_reason: 'Liquidity not swept',
      mode: 'PAPER',
      rr_ratio: 2.57,
      sl_pips: 70,
    },
  ];

  if (mode) {
    return mockSignals.filter(s => s.mode === mode);
  }

  return mockSignals;
}

function getMockStats(): SignalStats {
  return {
    total_signals_24h: 47,
    executed_count: 12,
    filtered_count: 32,
    failed_count: 3,
    win_rate: 66.7,
    ai_reject_rate: 68.1,
    active_trades: 2,
    total_pnl_24h: 458.25,
  };
}
