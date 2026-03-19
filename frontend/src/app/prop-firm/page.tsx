'use client';

import { useMemo } from 'react';
import { AlertTriangle, DollarSign, Activity, Calendar } from 'lucide-react';
import { CalendarPnlView } from '@/components/journal/CalendarPnlView';
import {
  usePropFirmMetrics,
  usePropFirmHistory,
  usePropFirmMtm,
  useResetPropFirmDaily,
  usePrefetchPropFirmAccounts,
} from '@/hooks/usePropFirm';
import {
  useAccountsComparison,
  useAccountTradeHistory,
} from '@/hooks/useAccounts';
import { fetchSignals } from '@/lib/supabase';
import { useQuery } from '@tanstack/react-query';
import { format, subDays, startOfDay } from 'date-fns';
import { getPnl, getSymbol, TradingSignal } from '@/types/trading';
import { StatCard } from '@/components/dashboard/StatCard';
import type { PropFirmMetricsResponse } from '@/lib/api';
import { ChallengeHeader } from '@/components/prop-firm/ChallengeHeader';
import { HealthScoreGauge } from '@/components/prop-firm/HealthScoreGauge';
import { ChallengeMetrics } from '@/components/prop-firm/ChallengeMetrics';
import { ChallengeRules } from '@/components/prop-firm/ChallengeRules';
import { PerformanceSummary } from '@/components/prop-firm/PerformanceSummary';
import { usePropFirmChallenge } from '@/hooks/usePropFirmChallenge';
import {
  getSignalSession,
  getSignalAccount,
  isClosedSignal,
} from '@/components/prop-firm/propFirmUtils';

const MOCK_METRICS: PropFirmMetricsResponse = {
  status: 'ok',
  account_name: 'Demo Account',
  evaluation_phase: 'phase1',
  metrics: {
    equity: {
      daily_start_balance: 100000,
      current_equity: 101850,
      daily_high_water_mark: 102100,
    },
    daily_pnl: { closed: 1200, floating: 650, total: 1850 },
    drawdown: {
      daily_pct: 0.8,
      daily_limit_pct: 5,
      daily_remaining_usd: 4200,
      trailing_pct: 1.2,
      trailing_limit_pct: 10,
    },
    status: {
      daily_loss_breach: false,
      drawdown_breach: false,
      safe_to_trade: true,
      consistency_ok: true,
    },
    consistency: { best_day_pct: 18, limit_pct: 30, status: 'safe' },
    days_remaining: 22,
  },
};

export default function PropFirmPage() {
  const historyDays = 30;
  const analyticsRange = 14;
  const symbolFilter = 'ALL';
  const sessionFilter = 'ALL';
  const dowFilter = 'ALL';

  const { data: accounts = [] } = useAccountsComparison();

  const accountOptions = useMemo(() => {
    const safeAccounts = Array.isArray(accounts) ? accounts : [];
    const names = safeAccounts.map((a) => a?.account_name).filter(Boolean);
    return names.length > 0 ? names : ['default'];
  }, [accounts]);

  const selectedAccount = 'default';
  const resolvedAccount = accountOptions.includes(selectedAccount)
    ? selectedAccount
    : accountOptions[0] ?? 'default';

  // Prefetch metrics for ALL accounts so switching is instant
  usePrefetchPropFirmAccounts(accountOptions);

  const {
    data: metricsData,
    isLoading: metricsLoading,
    isError: metricsIsError,
    error: metricsError,
    dataUpdatedAt,
  } = usePropFirmMetrics(resolvedAccount);

  usePropFirmHistory(resolvedAccount, historyDays);
  usePropFirmMtm(resolvedAccount);
  const resetMutation = useResetPropFirmDaily(resolvedAccount);

  // Get firm-specific info for rules display
  const { data: challengeData } = usePropFirmChallenge(resolvedAccount);
  const firmInfo = challengeData?.firm_info;

  const { data: allSignals = [] } = useQuery({
    queryKey: ['prop-firm-analytics-signals', resolvedAccount, analyticsRange],
    queryFn: () => fetchSignals({ limit: 1200, mode: 'LIVE' }),
    staleTime: 60_000,
  });

  const { data: metaApiHistory } = useAccountTradeHistory(resolvedAccount, 90);

  // Transform MetaAPI trades into TradingSignal-compatible shape for CalendarPnlView
  const metaApiSignals = useMemo((): TradingSignal[] => {
    if (!metaApiHistory?.trades?.length) return [];
    return metaApiHistory.trades.map(
      (trade) =>
        ({
          id: `metaapi-${trade.id}`,
          created_at:
            trade.exit_time || trade.entry_time || new Date().toISOString(),
          updated_at:
            trade.exit_time || trade.entry_time || new Date().toISOString(),
          symbol: trade.symbol,
          side: (trade.side?.toLowerCase() ?? 'buy') as TradingSignal['side'],
          price: trade.entry ?? 0,
          stop_loss: null,
          take_profit: null,
          position_size: trade.size ?? 0,
          score: null,
          notes: null,
          ai_reasoning: null,
          status: 'closed' as TradingSignal['status'],
          filter_reason: null,
          mode: 'LIVE' as TradingSignal['mode'],
          rr_ratio: null,
          sl_pips: null,
          pnl: trade.pnl_usd ?? null,
          pnl_usd: trade.pnl_usd ?? null,
          pnl_percentage: null,
          closed_at: trade.exit_time ?? null,
          exit_price: trade.exit ?? null,
          exit_type: null,
          account_name: resolvedAccount,
          ticker: trade.symbol,
          action: null,
          signal_action: null,
          order_type: null,
          trailing_stop: null,
          multi_tp: null,
          partial_close_percent: null,
          broker_order_id: null,
          close_broker_order_id: null,
          run_mode: 'LIVE',
          zone_id: null,
          zone_type: null,
          zone_grade: null,
          entry_model: null,
          liq_swept: null,
          target_swept: null,
          caused_sweep: null,
          is_accuracy: null,
          session: null,
          trend: null,
          htf_trend: null,
          rsi: null,
          rvol: null,
          adx: null,
          atr_ratio: null,
          base_quality: null,
          departure_strength: null,
          liquidity_distance: null,
          liquidity_spread: null,
          liquidity_distance_pips: null,
          liquidity_spread_pips: null,
          return_strength: null,
          ai_confidence: null,
          outcome: trade.outcome ?? null,
        } as unknown as TradingSignal)
    );
  }, [metaApiHistory, resolvedAccount]);

  const safeAllSignals = useMemo(
    () => (Array.isArray(allSignals) ? allSignals : []),
    [allSignals]
  );

  const brokerConfirmedSignals = useMemo(
    () =>
      safeAllSignals.filter(
        (s) =>
          (s as TradingSignal & { broker_order_id?: string | null })
            .broker_order_id != null
      ),
    [safeAllSignals]
  );

  const mergedSignals = useMemo(() => {
    if (metaApiSignals.length > 0) return metaApiSignals;
    return brokerConfirmedSignals;
  }, [brokerConfirmedSignals, metaApiSignals]);

  const cutoff = useMemo(
    () => startOfDay(subDays(new Date(), analyticsRange - 1)),
    [analyticsRange]
  );

  const safeMergedSignals = useMemo(
    () => (Array.isArray(mergedSignals) ? mergedSignals : []),
    [mergedSignals]
  );

  const filteredSignals = useMemo(() => {
    return safeMergedSignals
      .filter((s) => new Date(s.closed_at || s.created_at) >= cutoff)
      .filter((s) =>
        resolvedAccount === 'default'
          ? true
          : getSignalAccount(s) === resolvedAccount
      )
      .filter((s) =>
        symbolFilter === 'ALL' ? true : getSymbol(s) === symbolFilter
      )
      .filter((s) =>
        sessionFilter === 'ALL' ? true : getSignalSession(s) === sessionFilter
      )
      .filter((s) => {
        if (dowFilter === 'ALL') return true;
        const dow = new Date(s.created_at).toLocaleDateString('en-US', {
          weekday: 'short',
        });
        return dow === dowFilter;
      });
  }, [
    safeMergedSignals,
    cutoff,
    resolvedAccount,
    symbolFilter,
    sessionFilter,
    dowFilter,
  ]);

  const analyticsDaily = useMemo(() => {
    const map = new Map<
      string,
      {
        date: string;
        positions: number;
        wins: number;
        losses: number;
        pnl: number;
      }
    >();
    for (const s of filteredSignals) {
      const dateStr = s.closed_at || s.created_at;
      const d = format(new Date(dateStr), 'MMM dd');
      if (!map.has(d))
        map.set(d, { date: d, positions: 0, wins: 0, losses: 0, pnl: 0 });
      const row = map.get(d)!;
      row.positions += 1;
      if (isClosedSignal(s)) {
        const pnl = getPnl(s) ?? 0;
        if (pnl === 0) continue;
        row.pnl += pnl;
        if (pnl > 0) row.wins += 1;
        else row.losses += 1;
      }
    }
    return Array.from(map.values()).map((r) => ({
      ...r,
      winRate: r.wins + r.losses > 0 ? (r.wins / (r.wins + r.losses)) * 100 : 0,
    }));
  }, [filteredSignals]);

  const summary = useMemo(() => {
    const closed = filteredSignals.filter(isClosedSignal);
    const open = filteredSignals.filter((s) => {
      const st = String(s.status || '').toLowerCase();
      return st === 'active' || st === 'open' || st === 'pending';
    });
    const pnl = closed.reduce((acc, s) => acc + (getPnl(s) ?? 0), 0);
    const wins = closed.filter((s) => (getPnl(s) ?? 0) > 0).length;
    const wr = closed.length ? (wins / closed.length) * 100 : 0;

    let bestDay = { date: '—', pnl: -Infinity };
    let worstDay = { date: '—', pnl: Infinity };
    for (const d of analyticsDaily) {
      if (d.pnl > bestDay.pnl) bestDay = { date: d.date, pnl: d.pnl };
      if (d.pnl < worstDay.pnl) worstDay = { date: d.date, pnl: d.pnl };
    }

    return {
      openPositions: open.length,
      closedTrades: closed.length,
      winRate: wr,
      totalPnl: pnl,
      bestDay: bestDay.pnl === -Infinity ? { date: '—', pnl: 0 } : bestDay,
      worstDay: worstDay.pnl === Infinity ? { date: '—', pnl: 0 } : worstDay,
    };
  }, [filteredSignals, analyticsDaily]);

  // Show skeleton only on initial load with no data — fall through on error
  if (metricsLoading && !metricsIsError) {
    return (
      <div className='flex flex-col gap-3 p-2'>
        <div className='h-16 rounded-xl bg-[var(--to-surface-raised)]/60 animate-pulse' />
        <div className='grid grid-cols-1 lg:grid-cols-3 gap-4'>
          <div className='h-48 rounded-xl bg-[var(--to-surface-raised)]/60 animate-pulse' />
          <div className='h-48 lg:col-span-2 rounded-xl bg-[var(--to-surface-raised)]/60 animate-pulse' />
        </div>
        <div className='h-32 rounded-xl bg-[var(--to-surface-raised)]/60 animate-pulse' />
      </div>
    );
  }

  const isDemo = metricsError || !metricsData;
  const resolvedMetrics = isDemo ? MOCK_METRICS : metricsData!;

  const { metrics, evaluation_phase, account_name } = resolvedMetrics;
  const { equity, daily_pnl, drawdown, status, consistency } = metrics;

  const safeEquity = {
    daily_start_balance: equity?.daily_start_balance ?? 0,
    current_equity: equity?.current_equity ?? 0,
  };
  const safeDailyPnl = {
    closed: daily_pnl?.closed ?? 0,
    floating: daily_pnl?.floating ?? 0,
    total: daily_pnl?.total ?? 0,
  };
  const safeDrawdown = {
    daily_pct: drawdown?.daily_pct ?? 0,
    daily_limit_pct: drawdown?.daily_limit_pct ?? 0,
    trailing_pct: drawdown?.trailing_pct ?? 0,
    trailing_limit_pct: drawdown?.trailing_limit_pct ?? 0,
  };
  const safeConsistency = {
    best_day_pct: consistency?.best_day_pct ?? 0,
    limit_pct: consistency?.limit_pct ?? 0,
  };

  const currentProfitPct =
    safeEquity.current_equity > safeEquity.daily_start_balance
      ? ((safeEquity.current_equity - safeEquity.daily_start_balance) /
          Math.max(safeEquity.daily_start_balance, 1)) *
        100
      : 0;

  const accountGrowthPct =
    safeEquity.daily_start_balance > 0
      ? ((safeEquity.current_equity - safeEquity.daily_start_balance) /
          safeEquity.daily_start_balance) *
        100
      : 0;

  return (
    <div className='flex-1 space-y-4 animate-fade-in-up'>
      {/* Demo banner */}
      {isDemo && (
        <div className='rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 flex items-center gap-2 text-xs text-amber-300 font-mono'>
          <AlertTriangle className='h-4 w-4 shrink-0' />
          Backend offline — showing demo data. Connect your backend to see live
          metrics.
        </div>
      )}

      {/* Header Section */}
      <ChallengeHeader
        accountName={account_name}
        evaluationPhase={evaluation_phase}
        daysRemaining={metrics.days_remaining}
        accountOptions={accountOptions}
        selectedAccount={resolvedAccount}
        onSelectAccount={() => {}}
        dataUpdatedAt={dataUpdatedAt}
        onReset={() => resetMutation.mutate()}
        isResetting={resetMutation.isPending}
      />

      {/* Challenge Health Score & Account Overview */}
      <div className='grid grid-cols-1 lg:grid-cols-3 gap-4'>
        <div className='lg:col-span-1'>
          <HealthScoreGauge
            dailyPct={safeDrawdown.daily_pct}
            dailyLimitPct={safeDrawdown.daily_limit_pct}
            trailingPct={safeDrawdown.trailing_pct}
            trailingLimitPct={safeDrawdown.trailing_limit_pct}
            consistencyPct={safeConsistency.best_day_pct}
            consistencyLimitPct={safeConsistency.limit_pct}
            safeToTrade={status.safe_to_trade}
            currentProfitPct={currentProfitPct}
          />
        </div>

        <div className='tv-card p-6 lg:col-span-2'>
          <h3 className='text-[13px] font-bold text-[var(--to-text-dim)] uppercase tracking-widest font-mono mb-4'>
            Account Overview
          </h3>

          <div className='grid grid-cols-2 md:grid-cols-4 gap-4'>
            <StatCard
              label='Starting Balance'
              value={`$${safeEquity.daily_start_balance.toLocaleString()}`}
              icon={DollarSign}
              variant='default'
              numericValue={safeEquity.daily_start_balance}
              numericFormat={(v) => `$${v.toLocaleString(undefined, { minimumFractionDigits: 0 })}`}
            />

            <StatCard
              label='Current Equity'
              value={`$${safeEquity.current_equity.toLocaleString()}`}
              icon={DollarSign}
              variant={accountGrowthPct >= 0 ? 'profit' : 'loss'}
              numericValue={safeEquity.current_equity}
              numericFormat={(v) => `$${v.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
              subValue={`${
                accountGrowthPct >= 0 ? '+' : ''
              }${accountGrowthPct.toFixed(2)}%`}
              trend={accountGrowthPct >= 0 ? 'up' : accountGrowthPct < 0 ? 'down' : 'neutral'}
            />

            <StatCard
              label='Daily P&L'
              value={`${
                safeDailyPnl.total >= 0 ? '+' : ''
              }$${safeDailyPnl.total.toLocaleString()}`}
              icon={Activity}
              variant={safeDailyPnl.total >= 0 ? 'profit' : 'loss'}
              numericValue={safeDailyPnl.total}
              numericFormat={(v) => `${v >= 0 ? '+' : ''}$${v.toLocaleString()}`}
              subValue={`Closed: ${
                safeDailyPnl.closed >= 0 ? '+' : ''
              }$${safeDailyPnl.closed.toLocaleString()}`}
              trend={safeDailyPnl.total >= 0 ? 'up' : safeDailyPnl.total < 0 ? 'down' : 'neutral'}
            />

            <StatCard
              label='Floating P&L'
              value={`${
                safeDailyPnl.floating >= 0 ? '+' : ''
              }$${safeDailyPnl.floating.toLocaleString()}`}
              icon={Activity}
              variant={safeDailyPnl.floating >= 0 ? 'profit' : 'loss'}
              numericValue={safeDailyPnl.floating}
              numericFormat={(v) => `${v >= 0 ? '+' : ''}$${v.toLocaleString()}`}
              trend={safeDailyPnl.floating > 0 ? 'up' : safeDailyPnl.floating < 0 ? 'down' : 'neutral'}
            />
          </div>
        </div>
      </div>

      {/* Challenge Metrics */}
      <ChallengeMetrics
        dailyPct={safeDrawdown.daily_pct}
        dailyLimitPct={safeDrawdown.daily_limit_pct}
        trailingPct={safeDrawdown.trailing_pct}
        trailingLimitPct={safeDrawdown.trailing_limit_pct}
        consistencyPct={safeConsistency.best_day_pct}
        consistencyLimitPct={safeConsistency.limit_pct}
      />

      {/* Challenge Rules */}
      <ChallengeRules
        dailyLimitPct={safeDrawdown.daily_limit_pct}
        maxDrawdownPct={safeDrawdown.trailing_limit_pct}
        consistencyLimitPct={safeConsistency.limit_pct}
        profitTargetPct={firmInfo?.profit_target_pct ?? 0}
        minTradingDays={firmInfo?.min_trading_days ?? undefined}
        maxTradingDays={firmInfo?.max_trading_days ?? undefined}
        daysRemaining={metrics.days_remaining ?? undefined}
        currentDailyPct={safeDrawdown.daily_pct}
        currentTrailingPct={safeDrawdown.trailing_pct}
        currentConsistencyPct={safeConsistency.best_day_pct}
        currentProfitPct={currentProfitPct}
      />

      {/* Performance Summary */}
      <PerformanceSummary
        openPositions={summary.openPositions}
        closedTrades={summary.closedTrades}
        winRate={summary.winRate}
        totalPnl={summary.totalPnl}
        bestDay={summary.bestDay}
        worstDay={summary.worstDay}
      />

      {/* Calendar View */}
      <div className='tv-card p-6'>
        <h3 className='text-[13px] font-bold text-[var(--to-text-dim)] uppercase tracking-widest font-mono mb-4 flex items-center gap-2'>
          <Calendar className='h-4 w-4 text-amber-400' />
          Daily Performance Calendar
        </h3>

        <CalendarPnlView
          signals={safeMergedSignals
            .filter(isClosedSignal)
            .filter((s) =>
              resolvedAccount === 'default'
                ? true
                : getSignalAccount(s) === resolvedAccount
            )}
        />
      </div>
    </div>
  );
}
