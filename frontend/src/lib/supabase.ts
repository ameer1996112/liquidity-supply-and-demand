import { createClient, SupabaseClient } from '@supabase/supabase-js';
import { TradingSignal, SignalStats, normalizeSignal } from '@/types/trading';

// Database types for Supabase
// Note: Only trading_signals is typed here. Other tables (symbol_risk_rules,
// documents) are accessed via untyped .from() calls with explicit casts.
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
    mode?: 'LIVE' | 'PAPER' | 'BACKTEST';
    limit?: number;
    offset?: number;
    runId?: string;
  } = {}
): Promise<TradingSignal[]> {
  if (!supabase) {
    return getMockSignals(
      options.mode === 'BACKTEST' ? undefined : options.mode
    );
  }

  const { mode, limit = 50, offset = 0, runId } = options;

  let query = supabase
    .from('trading_signals')
    .select('*')
    .order('created_at', { ascending: false })
    .range(offset, offset + limit - 1);

  // DB uses run_mode for LIVE/PAPER/BACKTEST (backend writes run_mode)
  if (mode) {
    query = query.eq('run_mode', mode);
  }

  if (runId) {
    query = query.eq('run_id', runId);
  }

  const { data, error } = await query;

  if (error) {
    console.error('Error fetching signals:', error);
    throw error;
  }

  // Normalize signals to handle both old and new field names
  return (data || []).map((row) =>
    normalizeSignal(row as Partial<TradingSignal>)
  );
}

export async function fetchSignalStats(): Promise<SignalStats> {
  if (!supabase) {
    return getMockStats();
  }

  // Get signals from last 24 hours
  const twentyFourHoursAgo = new Date(
    Date.now() - 24 * 60 * 60 * 1000
  ).toISOString();

  const { data, error } = await supabase
    .from('trading_signals')
    .select('*')
    .gte('created_at', twentyFourHoursAgo);

  if (error) {
    console.error('Error fetching stats:', error);
    throw error;
  }

  const signals: TradingSignal[] = (data || []).map((row) =>
    normalizeSignal(row as Partial<TradingSignal>)
  );

  const normalizeStatus = (status: string | undefined) => status?.toLowerCase();
  const normalizeMode = (mode: string | undefined) =>
    mode ? String(mode).toUpperCase() : undefined;
  /** Treat as LIVE if run_mode is LIVE or missing (default = live when not paper).
   *  IMPORTANT: Use run_mode as source of truth (backend writes run_mode column). */
  const isLive = (s: TradingSignal) => {
    // Prioritize run_mode over mode since backend uses run_mode as the canonical field
    const m = normalizeMode(s.run_mode ?? s.mode);
    return m === 'LIVE' || m === undefined;
  };
  /** Only PAPER when explicitly set in run_mode. */
  const isPaper = (s: TradingSignal) =>
    normalizeMode(s.run_mode ?? s.mode) === 'PAPER';

  const executed = signals.filter(
    (s) => normalizeStatus(s.status) === 'executed'
  );
  const filtered = signals.filter(
    (s) =>
      normalizeStatus(s.status) === 'filtered' ||
      normalizeStatus(s.status) === 'ai_rejected'
  );
  const failed = signals.filter((s) => normalizeStatus(s.status) === 'failed');
  const activeSignals = signals.filter(
    (s) => normalizeStatus(s.status) === 'active'
  );

  // Helper to get a consistent PnL in USD for a signal
  const getPnlUsd = (s: TradingSignal): number => {
    const direct = s.pnl_usd ?? s.pnl;
    if (direct != null) return direct;

    const entry = s.entry ?? s.price;
    const exit = s.exit_price;
    if (entry == null || exit == null) return 0;

    const size = s.position_size ?? 0;
    if (!size) return 0;

    const side = String(s.side || 'buy').toLowerCase();
    const diff = side === 'buy' ? exit - entry : entry - exit;
    // NOTE: Contract size is broker-specific; we assume 1 here as a fallback.
    return diff * size;
  };

  // More aggressive PnL eligibility:
  // - status 'closed' OR 'executed'
  // - AND has explicit PnL (pnl or pnl_usd)
  const eligibleForPnl = signals.filter((s) => {
    const st = normalizeStatus(s.status);
    const hasPnl = s.pnl_usd != null || s.pnl != null;
    return (
      hasPnl &&
      (st === 'closed' ||
        st === 'executed' ||
        st === 'CLOSED' ||
        st === 'EXECUTED')
    );
  });

  const liveClosed = eligibleForPnl.filter(isLive);
  const paperClosed = eligibleForPnl.filter(isPaper);

  const liveWins = liveClosed.filter((s) => getPnlUsd(s) > 0);
  const _liveLosses = liveClosed.filter((s) => getPnlUsd(s) <= 0);
  const liveWinRate =
    liveClosed.length > 0 ? (liveWins.length / liveClosed.length) * 100 : 0;

  const livePnl = liveClosed.reduce((sum, s) => sum + getPnlUsd(s), 0);
  const paperPnl = paperClosed.reduce((sum, s) => sum + getPnlUsd(s), 0);

  if (process.env.NODE_ENV === 'development' && eligibleForPnl.length > 0) {
    console.log(
      'Stats 24h: liveClosed=',
      liveClosed.length,
      'livePnl=',
      livePnl.toFixed(2),
      'paperClosed=',
      paperClosed.length,
      'paperPnl=',
      paperPnl.toFixed(2)
    );
  }

  // Active trades are either 'active' status or executed without closed_at
  const active = [...activeSignals, ...executed.filter((s) => !s.closed_at)];

  const aiRejected = signals.filter(
    (s) => normalizeStatus(s.status) === 'ai_rejected'
  );

  // ── Daily PnL (today only, resets at midnight UTC) ──────────────────
  const todayMidnight = new Date();
  todayMidnight.setUTCHours(0, 0, 0, 0);
  const todayISO = todayMidnight.toISOString();

  const todaySignals = eligibleForPnl.filter((s) => s.created_at >= todayISO);
  const dailyPnl = todaySignals.reduce((sum, s) => sum + getPnlUsd(s), 0);

  // Mode-specific daily PnL
  const liveTodaySignals = todaySignals.filter(isLive);
  const paperTodaySignals = todaySignals.filter(isPaper);
  const liveDailyPnl = liveTodaySignals.reduce(
    (sum, s) => sum + getPnlUsd(s),
    0
  );
  const paperDailyPnl = paperTodaySignals.reduce(
    (sum, s) => sum + getPnlUsd(s),
    0
  );

  // ── Total PnL (all-time) ────────────────────────────────────────────
  let totalPnl = 0;
  let liveTotalPnl = 0;
  let paperTotalPnl = 0;
  try {
    if (supabase) {
      // Type for the partial signal row returned by this query
      interface ClosedSignalRow {
        pnl?: number | null;
        pnl_usd?: number | null;
        entry?: number | null;
        exit_fill_price?: number | null;
        exit_price?: number | null;
        size?: number | null;
        position_size?: number | null;
        side?: string | null;
        run_mode?: string | null;
        mode?: string | null;
      }

      const { data: allClosed } = await supabase
        .from('trading_signals')
        .select(
          'pnl, pnl_usd, entry, exit_fill_price, size, side, run_mode, status'
        )
        .or(
          'status.eq.closed,status.eq.executed,status.eq.CLOSED,status.eq.EXECUTED'
        );

      if (allClosed) {
        totalPnl = (allClosed as ClosedSignalRow[]).reduce((sum, s) => {
          // Try pnl_usd first, then pnl, then calculate from entry/exit
          const pnlUsd = s.pnl_usd ?? s.pnl;
          if (pnlUsd != null) {
            return sum + pnlUsd;
          }

          // Fallback: calculate from entry/exit (DB columns: entry, exit_fill_price, size)
          const entry = s.entry;
          const exit = s.exit_fill_price ?? s.exit_price;
          const size = s.size ?? s.position_size;
          if (entry != null && exit != null && size) {
            const side = String(s.side || 'buy').toLowerCase();
            const diff = side === 'buy' ? exit - entry : entry - exit;
            return sum + diff * size;
          }

          return sum;
        }, 0);

        // Calculate mode-specific totals
        liveTotalPnl = (allClosed as ClosedSignalRow[])
          .filter((s) => {
            const m = normalizeMode(s.run_mode ?? s.mode ?? undefined);
            return m === 'LIVE' || m === undefined;
          })
          .reduce((sum, s) => {
            const pnlUsd = s.pnl_usd ?? s.pnl;
            if (pnlUsd != null) {
              return sum + pnlUsd;
            }
            const entry = s.entry;
            const exit = s.exit_fill_price ?? s.exit_price;
            const size = s.size ?? s.position_size;
            if (entry != null && exit != null && size) {
              const side = String(s.side || 'buy').toLowerCase();
              const diff = side === 'buy' ? exit - entry : entry - exit;
              return sum + diff * size;
            }
            return sum;
          }, 0);

        paperTotalPnl = (allClosed as ClosedSignalRow[])
          .filter(
            (s) => normalizeMode(s.run_mode ?? s.mode ?? undefined) === 'PAPER'
          )
          .reduce((sum, s) => {
            const pnlUsd = s.pnl_usd ?? s.pnl;
            if (pnlUsd != null) {
              return sum + pnlUsd;
            }
            const entry = s.entry;
            const exit = s.exit_fill_price ?? s.exit_price;
            const size = s.size ?? s.position_size;
            if (entry != null && exit != null && size) {
              const side = String(s.side || 'buy').toLowerCase();
              const diff = side === 'buy' ? exit - entry : entry - exit;
              return sum + diff * size;
            }
            return sum;
          }, 0);
      }
    }
  } catch (e) {
    console.error('Failed to fetch total PnL:', e);
  }

  // ── MetaTrader-aligned PnL from account_status_snapshots ───────────
  // Use broker balance snapshots so dashboard matches real account PnL.
  let brokerDailyPnl: number | null = null;
  let brokerTotalPnl: number | null = null;
  try {
    if (supabase) {
      // Get all active accounts
      const { data: accounts } = await supabase
        .from('account_strategies')
        .select('account_name, allocated_capital_usd')
        .eq('is_active', true);

      const todayStart = new Date();
      todayStart.setUTCHours(0, 0, 0, 0);
      const todayISO = todayStart.toISOString();

      let dailySum = 0;
      let totalAllocated = 0;
      let currentBalanceSum = 0;

      for (const acct of accounts ?? []) {
        const name = (acct as { account_name?: string }).account_name;
        if (!name) continue;

        const allocated =
          Number(
            (acct as { allocated_capital_usd?: number | null })
              .allocated_capital_usd ?? 0
          ) || 0;
        totalAllocated += allocated;

        // Balance just before today (start-of-day baseline)
        const { data: startSnap } = await supabase
          .from('account_status_snapshots')
          .select('balance')
          .eq('account_name', name)
          .lt('snapshot_time', todayISO)
          .order('snapshot_time', { ascending: false })
          .limit(1);

        // Latest balance for this account
        const { data: currentSnap } = await supabase
          .from('account_status_snapshots')
          .select('balance')
          .eq('account_name', name)
          .order('snapshot_time', { ascending: false })
          .limit(1);

        if (startSnap && startSnap.length && currentSnap && currentSnap.length) {
          const startBal = Number(
            (startSnap[0] as { balance: number }).balance ?? 0
          );
          const currBal = Number(
            (currentSnap[0] as { balance: number }).balance ?? 0
          );
          dailySum += currBal - startBal;
          currentBalanceSum += currBal;
        }
      }

      if (currentBalanceSum !== 0) {
        brokerDailyPnl = dailySum;
        // Total PnL = current balance minus allocated capital (initial deposit)
        if (totalAllocated > 0) {
          brokerTotalPnl = currentBalanceSum - totalAllocated;
        }
      }
    }
  } catch (e) {
    console.warn('Failed to compute broker-based PnL from snapshots:', e);
  }

  // Override signal-based PnL with broker-based PnL when available
  if (brokerDailyPnl != null) {
    dailyPnl = brokerDailyPnl;
    liveDailyPnl = brokerDailyPnl;
  }
  if (brokerTotalPnl != null) {
    totalPnl = brokerTotalPnl;
    liveTotalPnl = brokerTotalPnl;
  }

  // ── Daily Drawdown % ───────────────────────────────────────────────
  // Use account balance from closed signals if available, fallback to 50000
  const balanceSamples = eligibleForPnl
    .map(
      (s) => (s as TradingSignal & { account_balance?: number }).account_balance
    )
    .filter((v): v is number => typeof v === 'number' && v > 0);
  const accountBalance =
    balanceSamples.length > 0
      ? balanceSamples[balanceSamples.length - 1]
      : 50000;
  const dailyDrawdownPct =
    dailyPnl < 0 ? (Math.abs(dailyPnl) / accountBalance) * 100 : 0;

  return {
    total_signals_24h: signals.length,
    executed_count: executed.length + activeSignals.length,
    filtered_count: filtered.length,
    failed_count: failed.length,
    win_rate: liveWinRate,
    live_win_rate: liveWinRate,
    ai_reject_rate:
      signals.length > 0 ? (aiRejected.length / signals.length) * 100 : 0,
    active_trades: active.length,
    total_pnl_24h: livePnl,
    live_pnl_24h: livePnl,
    paper_pnl_24h: paperPnl,
    daily_pnl: dailyPnl,
    live_daily_pnl: liveDailyPnl,
    paper_daily_pnl: paperDailyPnl,
    total_pnl: totalPnl,
    live_total_pnl: liveTotalPnl,
    paper_total_pnl: paperTotalPnl,
    daily_drawdown_pct: dailyDrawdownPct,
  };
}

// Mock data for development without Supabase
// Uses the CORRECT field names: symbol, side, score, notes
function getMockSignals(mode?: 'LIVE' | 'PAPER'): TradingSignal[] {
  const mockSignals: TradingSignal[] = [
    {
      id: '1',
      created_at: new Date(Date.now() - 1000 * 60 * 2).toISOString(), // 2 mins ago
      updated_at: new Date(Date.now() - 1000 * 60 * 2).toISOString(),
      symbol: 'BTCUSD',
      side: 'buy',
      price: 97245.5,
      stop_loss: 96800.0,
      take_profit: 98500.0,
      position_size: 0.15,
      score: 92,
      notes:
        'Strong momentum breakout detected. Volume surge confirmed with RSI divergence on 4H timeframe. Institutional accumulation pattern visible.',
      ai_reasoning: {
        zone_id: 142,
        zone_type: 'demand',
        zone_grade: 'A+',
        zone_score: 92,
        entry_model: 'BREAKOUT',
        liquidity_swept: true,
        target_swept: true,
        caused_sweep: true,
        is_accuracy: true,
        session: 2,
        trend: 1,
        htf_trend: 1,
        rsi: 58.5,
        rvol: 2.15,
        adx: 38.4,
        atr_ratio: 0.85,
        base_quality: 88.5,
        departure_strength: 92.3,
        liquidity_distance: 8.5,
        liquidity_spread: 12.2,
        return_strength: 85.8,
        guardian_liq_sweep: true,
        guardian_arrival: 'aggressive',
        guardian_structure_break: true,
      },
      status: 'active',
      filter_reason: null,
      mode: 'LIVE',
      rr_ratio: 2.8,
      sl_pips: 445,
    },
    {
      id: '2',
      created_at: new Date(Date.now() - 1000 * 60 * 8).toISOString(), // 8 mins ago
      updated_at: new Date(Date.now() - 1000 * 60 * 8).toISOString(),
      symbol: 'XAUUSD',
      side: 'sell',
      price: 2645.5,
      stop_loss: 2652.0,
      take_profit: 2628.0,
      position_size: 0.5,
      score: 87,
      notes:
        'Supply zone rejection at key resistance. Multiple timeframe confluence with bearish engulfing on H1.',
      ai_reasoning: {
        zone_id: 89,
        zone_type: 'supply',
        zone_grade: 'A',
        zone_score: 87,
        entry_model: 'FLIP',
        liquidity_swept: true,
        target_swept: true,
        caused_sweep: false,
        is_accuracy: true,
        session: 2,
        trend: 0,
        htf_trend: 0,
        rsi: 68.2,
        rvol: 1.45,
        adx: 28.1,
        atr_ratio: 0.55,
        base_quality: 82.0,
        departure_strength: 78.2,
        liquidity_distance: 6.5,
        liquidity_spread: 10.8,
        return_strength: 75.5,
        guardian_liq_sweep: true,
        guardian_arrival: 'gradual',
        guardian_structure_break: true,
      },
      status: 'executed',
      filter_reason: null,
      mode: 'LIVE',
      rr_ratio: 2.7,
      sl_pips: 65,
      pnl: 325.5,
      pnl_percentage: 2.17,
      closed_at: new Date(Date.now() - 1000 * 60 * 3).toISOString(),
      exit_price: 2628.0,
      exit_type: 'TP_HIT',
    },
    {
      id: '3',
      created_at: new Date(Date.now() - 1000 * 60 * 15).toISOString(), // 15 mins ago
      updated_at: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
      symbol: 'EURUSD',
      side: 'buy',
      price: 1.0845,
      stop_loss: 1.0825,
      take_profit: 1.0895,
      position_size: 1.0,
      score: 54,
      notes:
        'Demand zone touch but lacking confirmation. HTF trend opposing, session timing suboptimal.',
      ai_reasoning: {
        zone_id: 203,
        zone_type: 'demand',
        zone_grade: 'C+',
        zone_score: 54,
        entry_model: 'DIR_CLOSE',
        liquidity_swept: false,
        target_swept: false,
        caused_sweep: false,
        is_accuracy: false,
        session: 3,
        trend: 1,
        htf_trend: 0,
        rsi: 42.5,
        rvol: 0.72,
        adx: 15.5,
        atr_ratio: 0.88,
        base_quality: 52.0,
        departure_strength: 48.1,
        liquidity_distance: 28.0,
        liquidity_spread: 35.5,
        return_strength: 45.3,
        guardian_liq_sweep: false,
        guardian_arrival: 'gradual',
        guardian_structure_break: false,
      },
      status: 'ai_rejected',
      filter_reason:
        'AI Quality Score 54 below 60 threshold. Liquidity not swept. HTF trend mismatch.',
      mode: 'LIVE',
      rr_ratio: 2.5,
      sl_pips: 20,
    },
    {
      id: '4',
      created_at: new Date(Date.now() - 1000 * 60 * 25).toISOString(), // 25 mins ago
      updated_at: new Date(Date.now() - 1000 * 60 * 25).toISOString(),
      symbol: 'GBPJPY',
      side: 'sell',
      price: 188.45,
      stop_loss: 188.95,
      take_profit: 186.95,
      position_size: 0.3,
      score: 78,
      notes:
        'Clean supply zone with aggressive departure. Session timing optimal for JPY pairs.',
      ai_reasoning: {
        zone_id: 156,
        zone_type: 'supply',
        zone_grade: 'B+',
        zone_score: 78,
        entry_model: 'BREAK_CANDLE',
        liquidity_swept: true,
        target_swept: true,
        caused_sweep: true,
        is_accuracy: false,
        session: 1,
        trend: 0,
        htf_trend: 0,
        rsi: 72.8,
        rvol: 1.25,
        adx: 32.1,
        atr_ratio: 0.62,
        base_quality: 75.0,
        departure_strength: 78.5,
        liquidity_distance: 12.5,
        liquidity_spread: 18.2,
        return_strength: 72.2,
        guardian_liq_sweep: true,
        guardian_arrival: 'aggressive',
        guardian_structure_break: false,
      },
      status: 'executed',
      filter_reason: null,
      mode: 'LIVE',
      rr_ratio: 3.0,
      sl_pips: 50,
      pnl: -150.0,
      pnl_percentage: -1.0,
      closed_at: new Date(Date.now() - 1000 * 60 * 10).toISOString(),
      exit_price: 188.95,
      exit_type: 'SL_HIT',
    },
    {
      id: '5',
      created_at: new Date(Date.now() - 1000 * 60 * 35).toISOString(), // 35 mins ago
      updated_at: new Date(Date.now() - 1000 * 60 * 35).toISOString(),
      symbol: 'USDJPY',
      side: 'buy',
      price: 149.85,
      stop_loss: 149.45,
      take_profit: 150.85,
      position_size: 0.8,
      score: 81,
      notes:
        'Demand zone flip confirmed. Strong institutional footprint with order flow alignment.',
      ai_reasoning: {
        zone_id: 178,
        zone_type: 'demand',
        zone_grade: 'A-',
        zone_score: 81,
        entry_model: 'FLIP',
        liquidity_swept: true,
        target_swept: true,
        caused_sweep: true,
        is_accuracy: true,
        session: 2,
        trend: 1,
        htf_trend: 1,
        rsi: 45.2,
        rvol: 1.85,
        adx: 25.2,
        atr_ratio: 0.48,
        base_quality: 78.0,
        departure_strength: 82.5,
        liquidity_distance: 5.5,
        liquidity_spread: 8.2,
        return_strength: 80.2,
        guardian_liq_sweep: true,
        guardian_arrival: 'aggressive',
        guardian_structure_break: true,
      },
      status: 'active',
      filter_reason: null,
      mode: 'LIVE',
      rr_ratio: 2.5,
      sl_pips: 40,
    },
    {
      id: '6',
      created_at: new Date(Date.now() - 1000 * 60 * 45).toISOString(), // 45 mins ago
      updated_at: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
      symbol: 'ETHUSD',
      side: 'sell',
      price: 3245.0,
      stop_loss: 3295.0,
      take_profit: 3145.0,
      position_size: 0.25,
      score: 45,
      notes:
        'Weak supply zone. Low volume, no clear institutional interest. Risk/reward unfavorable.',
      ai_reasoning: {
        zone_id: 221,
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
        rvol: 0.62,
        adx: 12.2,
        atr_ratio: 0.92,
        base_quality: 42.0,
        departure_strength: 38.5,
        liquidity_distance: 42.0,
        liquidity_spread: 55.5,
        return_strength: 35.2,
        guardian_liq_sweep: false,
        guardian_arrival: 'gradual',
        guardian_structure_break: false,
      },
      status: 'filtered',
      filter_reason:
        'Low zone score (45). No liquidity swept. Trend opposing on all timeframes.',
      mode: 'PAPER',
      rr_ratio: 2.0,
      sl_pips: 50,
    },
    {
      id: '7',
      created_at: new Date(Date.now() - 1000 * 60 * 55).toISOString(), // 55 mins ago
      updated_at: new Date(Date.now() - 1000 * 60 * 55).toISOString(),
      symbol: 'AUDCAD',
      side: 'buy',
      price: 0.9125,
      stop_loss: 0.9095,
      take_profit: 0.9185,
      position_size: 0.6,
      score: 68,
      notes:
        'Moderate demand zone. Volume picking up but HTF structure still developing.',
      ai_reasoning: {
        zone_id: 334,
        zone_type: 'demand',
        zone_grade: 'B',
        zone_score: 68,
        entry_model: 'BREAK_CANDLE',
        liquidity_swept: true,
        target_swept: false,
        caused_sweep: false,
        is_accuracy: false,
        session: 1,
        trend: 1,
        htf_trend: 0,
        rsi: 38.5,
        rvol: 1.12,
        adx: 22.5,
        atr_ratio: 0.72,
        base_quality: 65.0,
        departure_strength: 62.1,
        liquidity_distance: 18.0,
        liquidity_spread: 22.5,
        return_strength: 58.3,
        guardian_liq_sweep: true,
        guardian_arrival: 'gradual',
        guardian_structure_break: false,
      },
      status: 'executed',
      filter_reason: null,
      mode: 'PAPER',
      rr_ratio: 2.0,
      sl_pips: 30,
      pnl: 180.0,
      pnl_percentage: 1.2,
      closed_at: new Date(Date.now() - 1000 * 60 * 20).toISOString(),
      exit_price: 0.9185,
      exit_type: 'TP_HIT',
    },
    {
      id: '8',
      created_at: new Date(Date.now() - 1000 * 60 * 72).toISOString(), // 72 mins ago
      updated_at: new Date(Date.now() - 1000 * 60 * 72).toISOString(),
      symbol: 'NZDUSD',
      side: 'sell',
      price: 0.5845,
      stop_loss: 0.5875,
      take_profit: 0.5785,
      position_size: 0.4,
      score: 52,
      notes:
        'Supply zone test but RVOL too low. Waiting for better confirmation.',
      ai_reasoning: {
        zone_id: 445,
        zone_type: 'supply',
        zone_grade: 'C+',
        zone_score: 52,
        entry_model: 'DIR_CLOSE',
        liquidity_swept: false,
        target_swept: false,
        caused_sweep: false,
        is_accuracy: false,
        session: 0,
        trend: 0,
        htf_trend: 1,
        rsi: 62.5,
        rvol: 0.58,
        adx: 14.8,
        atr_ratio: 0.82,
        base_quality: 48.0,
        departure_strength: 52.1,
        liquidity_distance: 32.0,
        liquidity_spread: 38.5,
        return_strength: 45.3,
        guardian_liq_sweep: false,
        guardian_arrival: 'gradual',
        guardian_structure_break: false,
      },
      status: 'ai_rejected',
      filter_reason:
        'AI Score 52 below threshold. RVOL 0.58 indicates low participation. Asian session - suboptimal for USD pairs.',
      mode: 'PAPER',
      rr_ratio: 2.0,
      sl_pips: 30,
    },
  ];

  if (mode) {
    return mockSignals.filter((s) => s.mode === mode);
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
    live_win_rate: 66.7,
    ai_reject_rate: 68.1,
    active_trades: 2,
    total_pnl_24h: 458.25,
    live_pnl_24h: 458.25,
    paper_pnl_24h: 85.5,
    daily_pnl: 125.5,
    live_daily_pnl: 125.5,
    paper_daily_pnl: 32.2,
    total_pnl: 1245.8,
    live_total_pnl: 1245.8,
    paper_total_pnl: 342.15,
    daily_drawdown_pct: 0,
  };
}
