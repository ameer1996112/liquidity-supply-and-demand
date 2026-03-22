'use client';

import { useCallback, useMemo, useState, useEffect } from 'react';
import { SignalInspector } from '@/components/SignalInspector';
import { ActiveTradesPanel } from '@/components/dashboard/ActiveTradesPanel';
import { StatCard } from '@/components/dashboard/StatCard';
import { SignalTable } from '@/components/dashboard/SignalTable';
import { LiveLog } from '@/components/dashboard/LiveLog';
import { RiskBar } from '@/components/risk/RiskBar';
import { ConnectionPill } from '@/components/dashboard/ConnectionPill';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { useTradingMode } from '@/providers/TradingModeProvider';
import {
  useSignalStats,
  useTradingSignals,
  useCouncilSummaries,
} from '@/hooks/useTradingSignals';
import { useRiskStatus } from '@/hooks/useRiskStatus';
import { useConnectionHealth } from '@/hooks/useConnectionHealth';
import { useActivePositions, useAccountStatus } from '@/hooks/usePositions';
import { useDashboardLog } from '@/hooks/useDashboardLog';
import { MarketSessionBanner } from '@/components/dashboard/MarketSessionBanner';
import { PageStatusBanner } from '@/components/shared/PageStatusBanner';
import { TableSkeleton } from '@/components/shared/TableStates';
import { SessionRing } from '@/components/dashboard/SessionRing';
import { LivePnlTicker } from '@/components/dashboard/LivePnlTicker';
import { BestSetupCard } from '@/components/dashboard/BestSetupCard';
import {
  formatCurrency,
  formatNumber,
  formatPercent,
  EMPTY_VALUE,
} from '@/lib/formatters';
import type { TradingSignal, TradingMode } from '@/types/trading';
import {
  Radio,
  Wallet,
  TrendingUp,
  Activity,
  BarChart3,
  Crosshair,
  Clock,
  Target,
  Percent,
} from 'lucide-react';
import {
  isSignalOpen,
  isSignalRejected,
} from '@/domain/metrics/tradingMetrics';
import { getScore } from '@/types/trading';

// ── Sub-components ────────────────────────────────────────────────────────────

function ModeBadge({ mode }: { mode: TradingMode }) {
  return (
    <span
      className={
        mode === 'LIVE'
          ? 'mode-badge mode-badge-live'
          : 'mode-badge mode-badge-paper'
      }
    >
      <span className='status-dot status-dot-active pulse-active' />
      {mode}
    </span>
  );
}

interface WaitingBannerProps {
  strategyName: string;
  timeframe: string;
  latestSignalTime: string | null;
  lastRejectReason: string;
  isConnected: boolean;
  hasStats: boolean;
  hasRisk: boolean;
  mounted: boolean;
}

const STATUS_CHECKS = [
  'Connected',
  'Config loaded',
  'Risk guard',
  'Market open',
] as const;

function WaitingBanner({
  strategyName,
  timeframe,
  latestSignalTime,
  lastRejectReason,
  isConnected,
  hasStats,
  hasRisk,
  mounted,
}: WaitingBannerProps) {
  const checks: [string, boolean][] = [
    ['Connected', isConnected],
    ['Config loaded', hasStats],
    ['Risk guard', hasRisk],
    ['Market open', isConnected],
  ];

  return (
    <section className='glass-panel shrink-0 border-[var(--to-warning)]/30 bg-[var(--to-warning)]/5 p-4'>
      <h2 className='text-sm font-semibold text-[var(--to-warning)]'>Bot is waiting for…</h2>
      <div className='mt-2 grid gap-3 md:grid-cols-2'>
        <dl className='space-y-1 text-xs text-text-secondary'>
          {(
            [
              ['Strategy', strategyName],
              ['Timeframe', timeframe],
            ] as [string, string][]
          ).map(([label, val]) => (
            <div key={label} className='flex gap-1.5'>
              <dt className='text-text-dim'>{label}:</dt>
              <dd>{val}</dd>
            </div>
          ))}
          <div className='flex gap-1.5'>
            <dt className='text-text-dim'>Last signal:</dt>
            <dd className='font-mono tabular-nums'>
              {mounted ? (
                latestSignalTime ?? EMPTY_VALUE
              ) : (
                <Skeleton className='h-3 w-28 bg-[var(--to-surface-raised)]' />
              )}
            </dd>
          </div>
          <div className='flex gap-1.5'>
            <dt className='text-text-dim'>Last reject:</dt>
            <dd>{lastRejectReason || EMPTY_VALUE}</dd>
          </div>
        </dl>

        <div className='rounded border border-panel-border bg-surface p-3'>
          <ul className='space-y-1 text-xs text-text-secondary'>
            {checks.map(([label, ok]) => (
              <li key={label} className='flex items-center justify-between'>
                <span>{label}</span>
                <span
                  className={cn(
                    'h-2 w-2 rounded-full inline-block',
                    ok ? 'bg-[var(--to-long)]' : 'bg-[var(--to-short)]'
                  )}
                />
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

// Silence unused import warning — STATUS_CHECKS is a typed constant for future use
void STATUS_CHECKS;

// ── Dashboard page ────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(
    null
  );
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [showLog, setShowLog] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const { mode: activeMode } = useTradingMode();
  const { data: stats, isLoading: statsLoading } = useSignalStats();
  const { data: risk, isLoading: riskLoading } = useRiskStatus();
  const { data: signals = [], isLoading: signalsLoading } =
    useTradingSignals(activeMode);
  const { status, isConnected } = useConnectionHealth();

  const signalIds = useMemo(() => signals.map((s) => s.id), [signals]);
  const councilMap = useCouncilSummaries(signalIds);

  // Broker live positions — map by signal ID for overlay in SignalTable
  const { data: positionsData } = useActivePositions();
  const { data: accountStatus } = useAccountStatus();
  const brokerMap = useMemo(() => {
    const map: Record<string, import('@/hooks/usePositions').ActivePosition> = {};
    for (const pos of positionsData?.positions ?? []) {
      map[String(pos.id)] = pos;
    }
    return map;
  }, [positionsData]);

  // ── Derived values ──────────────────────────────────────────────────────────

  const activePositionsCount = useMemo(
    () => signals.filter(isSignalOpen).length,
    [signals]
  );

  const tradesToday = useMemo(() => {
    if (!mounted) return 0;
    const dayStart = new Date();
    dayStart.setHours(0, 0, 0, 0);
    return signals.filter((s) => new Date(s.created_at) >= dayStart).length;
  }, [signals, mounted]);

  const latestSignal = signals[0] ?? null;

  const lastRejectSignal = useMemo(
    () => signals.find(isSignalRejected),
    [signals]
  );

  const [lastUpdated, setLastUpdated] = useState('—');
  useEffect(() => {
    setLastUpdated(
      latestSignal
        ? new Date(
            latestSignal.updated_at ?? latestSignal.created_at
          ).toLocaleTimeString()
        : new Date().toLocaleTimeString()
    );
    // Recompute only when the latest signal changes, not on every render tick
  }, [latestSignal?.id, latestSignal?.updated_at, latestSignal?.created_at]);

  // ── Sparkline data (derived from recent signals) ────────────────────────────

  const recentClosed = useMemo(
    () =>
      signals
        .filter((s) => s.pnl != null || s.pnl_usd != null)
        .slice(0, 14)
        .reverse(),
    [signals]
  );

  const pnlSparkline = useMemo(
    () => recentClosed.map((s) => s.pnl ?? s.pnl_usd ?? 0),
    [recentClosed]
  );

  const winRateSparkline = useMemo(() => {
    const closed = recentClosed;
    if (closed.length < 2) return [];
    return closed.map((_, i) => {
      const slice = closed.slice(0, i + 1);
      const wins = slice.filter((s) => (s.pnl ?? s.pnl_usd ?? 0) > 0).length;
      return (wins / slice.length) * 100;
    });
  }, [recentClosed]);

  const scoreSparkline = useMemo(
    () =>
      signals
        .slice(0, 14)
        .reverse()
        .map((s) => getScore(s) ?? 50),
    [signals]
  );

  // Today's win/loss counts for SessionRing
  const { todayWins, todayLosses } = useMemo(() => {
    if (!mounted) return { todayWins: 0, todayLosses: 0 };
    const dayStart = new Date();
    dayStart.setHours(0, 0, 0, 0);
    const todayClosedSignals = signals.filter(
      (s) =>
        new Date(s.created_at) >= dayStart &&
        (s.pnl != null || s.pnl_usd != null)
    );
    const wins = todayClosedSignals.filter(
      (s) => (s.pnl ?? s.pnl_usd ?? 0) > 0
    ).length;
    const losses = todayClosedSignals.filter(
      (s) => (s.pnl ?? s.pnl_usd ?? 0) < 0
    ).length;
    return { todayWins: wins, todayLosses: losses };
  }, [signals, mounted]);

  // Best setup: highest AI score signal from today
  const bestSetupSignal = useMemo(() => {
    const dayStart = new Date();
    dayStart.setHours(0, 0, 0, 0);
    const todaySignals = signals.filter(
      (s) => new Date(s.created_at) >= dayStart
    );
    if (todaySignals.length === 0) return null;
    return todaySignals.reduce((best, s) => {
      const bScore = getScore(best) ?? 0;
      const sScore = getScore(s) ?? 0;
      return sScore > bScore ? s : best;
    });
  }, [signals, mounted]);

  const noData = signals.length === 0 && activePositionsCount === 0;
  const strategyName =
    latestSignal?.entry_model ?? latestSignal?.zone_type ?? 'Liquidity S&D';
  const timeframe = '5M';

  const todayPnl =
    activeMode === 'PAPER'
      ? stats?.paper_daily_pnl ?? stats?.paper_pnl_24h
      : stats?.live_daily_pnl ?? stats?.live_pnl_24h;

  const totalPnl =
    activeMode === 'PAPER'
      ? stats?.paper_total_pnl ?? stats?.paper_pnl_24h
      : stats?.live_total_pnl ?? stats?.total_pnl;

  // Deltas: approximate today vs prior 24h window
  const baseDailyPnl =
    activeMode === 'PAPER'
      ? stats?.paper_daily_pnl ?? stats?.daily_pnl
      : stats?.live_daily_pnl ?? stats?.daily_pnl;

  const priorWindowPnl =
    activeMode === 'PAPER'
      ? stats && stats.paper_pnl_24h != null
        ? stats.paper_pnl_24h - (stats.paper_daily_pnl ?? 0)
        : null
      : stats && stats.live_pnl_24h != null
      ? stats.live_pnl_24h - (stats.live_daily_pnl ?? 0)
      : null;

  const todayPnlDelta =
    baseDailyPnl != null && priorWindowPnl != null
      ? baseDailyPnl - priorWindowPnl
      : null;

  // ── Live log ────────────────────────────────────────────────────────────────

  const { entries: logEntries, clear: clearLog } = useDashboardLog({
    signals,
    activeMode,
    isConnected,
    strategyName,
    timeframe,
    mounted,
  });

  // ── Handlers ────────────────────────────────────────────────────────────────

  const handleSelectSignal = useCallback((signal: TradingSignal) => {
    setSelectedSignal(signal);
    setInspectorOpen(true);
  }, []);

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className='flex h-full min-h-0 flex-col gap-2'>
      {/* ── Header ──────────────────────────────────────────────── */}
      <header className='flex shrink-0 items-center justify-between gap-3'>
        <div>
          <h1 className='page-title text-base font-semibold'>Dashboard</h1>
          <p className='page-subtitle text-[11px]'>
            Live command center · telemetry first · 5-minute zones
          </p>
        </div>
        <div className='flex items-center gap-2 flex-wrap justify-end'>
          {mounted && todayPnl != null && (
            <SessionRing
              todayPnl={todayPnl}
              dailyTarget={200}
              winCount={todayWins}
              lossCount={todayLosses}
            />
          )}
          <ConnectionPill />
          <span className='tf-badge'>
            <Radio className='h-3 w-3' />
            5M
          </span>
          <ModeBadge mode={activeMode} />
        </div>
      </header>

      {/* ── Page-level health banner ────────────────────────────── */}
      <PageStatusBanner status={status} surfaceLabel='Dashboard' />

      {/* ── Market Session Banner ───────────────────────────────── */}
      <MarketSessionBanner />

      {/* ── Live P&L Ticker (open positions) ────────────────────── */}
      {mounted && <LivePnlTicker signals={signals} />}

      {/* ── Top row · Stat bento ───────────────────────────────── */}
      <section className='shrink-0'>
        <div className='mb-1.5 flex items-center justify-between px-0.5'>
          <p className='kpi-meta'>Session KPIs</p>
          <p
            className='kpi-meta font-mono tabular-nums'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            Last updated&nbsp;{mounted ? lastUpdated : '—'}
          </p>
        </div>
        {!mounted || statsLoading || riskLoading || signalsLoading ? (
          <div aria-label="Loading dashboard metrics" className='grid grid-cols-2 gap-1.5 md:grid-cols-4 xl:grid-cols-7'>
            {Array.from({ length: 7 }).map((_, idx) => (
              <Skeleton
                key={idx}
                className='h-[72px] rounded-xl border border-[var(--to-border)] skeleton-shimmer'
              />
            ))}
          </div>
        ) : (
          <div className='grid grid-cols-2 gap-1.5 md:grid-cols-4 xl:grid-cols-8 stagger-children'>
            <StatCard
              label='Today PnL'
              value={formatCurrency(todayPnl, { signed: true })}
              numericValue={todayPnl ?? undefined}
              numericFormat={(v) => formatCurrency(v, { signed: true })}
              trend={
                todayPnl != null ? (todayPnl >= 0 ? 'up' : 'down') : 'neutral'
              }
              subValue={
                activeMode === 'LIVE' && accountStatus?.equity != null
                  ? `Equity ${formatCurrency(accountStatus.equity)}`
                  : todayPnlDelta != null
                  ? `Δ ${formatCurrency(todayPnlDelta, { signed: true })}`
                  : EMPTY_VALUE
              }
              icon={Wallet}
              sparklineData={pnlSparkline}
              hero={true}
              className='col-span-1 xl:col-span-2 animate-fade-in-up'
            />
            <StatCard
              label='Total PnL'
              value={formatCurrency(totalPnl, { signed: true })}
              numericValue={totalPnl ?? undefined}
              numericFormat={(v) => formatCurrency(v, { signed: true })}
              trend={
                totalPnl != null ? (totalPnl >= 0 ? 'up' : 'down') : 'neutral'
              }
              subValue={
                stats?.total_pnl_24h != null
                  ? `24h ${formatCurrency(stats.total_pnl_24h, {
                      signed: true,
                    })}`
                  : EMPTY_VALUE
              }
              icon={TrendingUp}
              sparklineData={pnlSparkline}
              className='animate-fade-in-up'
            />
            <StatCard
              label='Win Rate'
              value={formatPercent(stats?.win_rate)}
              numericValue={stats?.win_rate ?? undefined}
              numericFormat={(v) => formatPercent(v)}
              trend={
                stats?.win_rate != null
                  ? stats.win_rate >= 50
                    ? 'up'
                    : 'down'
                  : 'neutral'
              }
              subValue={
                stats?.closed_trade_count != null
                  ? `${stats.closed_trade_count} trades`
                  : EMPTY_VALUE
              }
              icon={Target}
              sparklineData={winRateSparkline}
              className='animate-fade-in-up'
            />
            <StatCard
              label='Drawdown'
              value={formatPercent(risk?.drawdown_pct)}
              numericValue={risk?.drawdown_pct ?? undefined}
              numericFormat={(v) => formatPercent(v)}
              trend={
                risk?.drawdown_pct != null
                  ? risk.drawdown_pct > 3
                    ? 'down'
                    : 'neutral'
                  : 'neutral'
              }
              subValue={
                risk?.max_drawdown_pct != null
                  ? `Max ${formatPercent(risk.max_drawdown_pct)}`
                  : EMPTY_VALUE
              }
              icon={Activity}
              variant='loss'
              className='animate-fade-in-up'
            />
            <StatCard
              label='Daily DD'
              value={formatPercent(stats?.daily_drawdown_pct)}
              numericValue={stats?.daily_drawdown_pct ?? undefined}
              numericFormat={(v) => formatPercent(v)}
              subValue={
                risk?.max_daily_loss_pct != null
                  ? `Limit ${formatPercent(risk.max_daily_loss_pct)}`
                  : EMPTY_VALUE
              }
              icon={BarChart3}
              className='animate-fade-in-up'
            />
            <StatCard
              label='Positions'
              value={formatNumber(activePositionsCount, {
                decimals: 0,
                empty: '0',
              })}
              numericValue={activePositionsCount}
              numericFormat={(v) => String(Math.round(v))}
              subValue={
                risk?.max_positions != null
                  ? `Max ${formatNumber(risk.max_positions, { decimals: 0 })}`
                  : EMPTY_VALUE
              }
              icon={Crosshair}
              className='animate-fade-in-up'
            />
            <StatCard
              label='Trades Today'
              value={formatNumber(tradesToday, { decimals: 0, empty: '0' })}
              numericValue={tradesToday}
              numericFormat={(v) => String(Math.round(v))}
              subValue={
                stats?.total_signals_24h != null
                  ? `24h ${formatNumber(stats.total_signals_24h, {
                      decimals: 0,
                    })}`
                  : EMPTY_VALUE
              }
              icon={Clock}
              sparklineData={scoreSparkline}
              className='animate-fade-in-up'
            />
            <StatCard
              label='Effective Risk'
              value={
                risk?.risk_multiplier != null && risk.risk_multiplier !== 1
                  ? `${formatPercent(0.5 * risk.risk_multiplier)}`
                  : formatPercent(0.5)
              }
              numericValue={
                risk != null
                  ? 0.5 * (risk.risk_multiplier ?? 1)
                  : undefined
              }
              numericFormat={(v) => formatPercent(v)}
              trend={
                risk?.risk_multiplier != null
                  ? risk.risk_multiplier > 1
                    ? 'up'
                    : risk.risk_multiplier < 1
                    ? 'down'
                    : 'neutral'
                  : 'neutral'
              }
              subValue={
                risk?.risk_multiplier != null
                  ? `${risk.risk_multiplier.toFixed(2)}× (${risk.risk_mode ?? 'step_up'})`
                  : EMPTY_VALUE
              }
              icon={Percent}
              className='animate-fade-in-up'
            />
          </div>
        )}
      </section>

      {/* ── Waiting banner (no data) ─────────────────────────────── */}
      {noData && (
        <WaitingBanner
          strategyName={strategyName}
          timeframe={timeframe}
          latestSignalTime={
            latestSignal
              ? new Date(latestSignal.created_at).toLocaleString()
              : null
          }
          lastRejectReason={
            lastRejectSignal?.filter_reason ?? lastRejectSignal?.notes ?? ''
          }
          isConnected={isConnected}
          hasStats={!!stats}
          hasRisk={!!risk}
          mounted={mounted}
        />
      )}

      {/* ── Middle · Bento grid: latest signals + risk side rail ── */}
      <div className='flex min-h-0 flex-1 flex-col gap-2 xl:flex-row'>
        {/* Middle · Latest Signals table */}
        <section className='glow-card flex min-h-0 flex-1 flex-col overflow-hidden'>
          <div className='to-panel-header'>
            <div className='flex items-center gap-2'>
              <span className='panel-label'>Latest Signals</span>
              <span
                className='rounded-full bg-[var(--to-surface-raised)] border border-[var(--to-border)] px-2 py-0.5 font-mono text-[9px] tabular-nums text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {signals.length}
              </span>
            </div>
            <span
              className='kpi-meta font-mono text-[10px] tabular-nums text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {mounted ? lastUpdated : '—'}
            </span>
          </div>

          <div className='min-h-0 flex-1 overflow-hidden p-2'>
            {signalsLoading && signals.length === 0 ? (
              <TableSkeleton rowCount={8} columnCount={6} />
            ) : (
              <SignalTable
                signals={signals}
                councilMap={councilMap}
                brokerMap={brokerMap}
                onSelectSignal={handleSelectSignal}
                maxRows={150}
              />
            )}
          </div>
        </section>

        {/* Side rail · Best Setup + Risk status + Live log */}
        <aside className='flex min-h-0 w-full flex-col gap-2 xl:w-[360px]'>
          {bestSetupSignal && (
            <BestSetupCard signal={bestSetupSignal} className='shrink-0' />
          )}
          <section className='glow-card shrink-0'>
            <div className='to-panel-header'>
              <div className='flex items-center gap-2'>
                <span className='panel-label'>Risk Status</span>
                {risk?.kill_switch_active && (
                  <span className='rounded-full bg-[var(--to-short)]/15 border border-[var(--to-short)]/30 px-2 py-0.5 text-[9px] font-bold uppercase tracking-widest text-[var(--to-short)]'>
                    KILL ON
                  </span>
                )}
              </div>
              <span
                className='kpi-meta font-mono text-[10px] tabular-nums text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {mounted ? lastUpdated : '—'}
              </span>
            </div>
            <div className='p-2'>
              {riskLoading ? (
                <div className='space-y-2'>
                  <Skeleton className='h-4 w-full rounded skeleton-shimmer' />
                  <Skeleton className='h-4 w-4/5 rounded skeleton-shimmer' />
                </div>
              ) : (
                <RiskBar />
              )}
            </div>
          </section>

          {/* Log toggle button — mobile/tablet only */}
          <button
            className='xl:hidden text-[11px] text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] transition-colors py-1 px-0.5 text-left'
            onClick={() => setShowLog((prev) => !prev)}
          >
            {showLog ? 'Hide Live Log ▲' : 'Show Live Log ▼'}
          </button>

          <section className={cn('min-h-0 flex-1 overflow-hidden', !showLog && 'hidden xl:block')}>
            <LiveLog
              entries={logEntries}
              onClear={clearLog}
              className='h-full'
            />
          </section>
        </aside>
      </div>

      {/* ── Bottom · Open positions snapshot ────────────────────── */}
      <section className='mt-1 min-h-[180px]'>
        <ActiveTradesPanel
          mode={activeMode}
          onSelectSignal={handleSelectSignal}
          compact
        />
      </section>

      <SignalInspector
        signal={selectedSignal}
        open={inspectorOpen}
        onOpenChange={setInspectorOpen}
      />
    </div>
  );
}
