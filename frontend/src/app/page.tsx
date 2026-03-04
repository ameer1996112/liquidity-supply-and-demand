'use client';

import { useCallback, useMemo, useState, useEffect } from 'react';
import { SignalInspector } from '@/components/SignalInspector';
import { ActiveTradesPanel } from '@/components/dashboard/ActiveTradesPanel';
import { StatCard } from '@/components/dashboard/StatCard';
import { SignalTable } from '@/components/dashboard/SignalTable';
import { LiveLog } from '@/components/dashboard/LiveLog';
import { RiskBar } from '@/components/risk/RiskBar';
import { Skeleton } from '@/components/ui/skeleton';
import { useTradingMode } from '@/providers/TradingModeProvider';
import {
  useSignalStats,
  useTradingSignals,
  useCouncilSummaries,
} from '@/hooks/useTradingSignals';
import { useRiskStatus } from '@/hooks/useRiskStatus';
import { useConnectionHealth } from '@/hooks/useConnectionHealth';
import { useDashboardLog } from '@/hooks/useDashboardLog';
import { PageStatusBanner } from '@/components/shared/PageStatusBanner';
import { TableSkeleton } from '@/components/shared/TableStates';
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
} from 'lucide-react';
import {
  isSignalOpen,
  isSignalRejected,
} from '@/domain/metrics/tradingMetrics';

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
    <section className='to-panel shrink-0 border-amber/15 bg-amber/5 p-3'>
      <h2 className='text-sm font-semibold text-amber'>Bot is waiting for…</h2>
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
                (latestSignalTime ?? EMPTY_VALUE)
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
                <span className={ok ? 'text-long' : 'text-short'}>●</span>
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
    null,
  );
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

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

  // ── Derived values ──────────────────────────────────────────────────────────

  const activePositionsCount = useMemo(
    () => signals.filter(isSignalOpen).length,
    [signals],
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
    [signals],
  );

  const [lastUpdated, setLastUpdated] = useState('—');
  useEffect(() => {
    setLastUpdated(
      latestSignal
        ? new Date(
            latestSignal.updated_at ?? latestSignal.created_at,
          ).toLocaleTimeString()
        : new Date().toLocaleTimeString(),
    );
  // Recompute only when the latest signal changes, not on every render tick
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [latestSignal?.id]);

  const noData = signals.length === 0 && activePositionsCount === 0;
  const strategyName =
    latestSignal?.entry_model ?? latestSignal?.zone_type ?? 'Liquidity S&D';
  const timeframe = '5M';

  const todayPnl =
    activeMode === 'PAPER'
      ? (stats?.paper_daily_pnl ?? stats?.paper_pnl_24h)
      : (stats?.live_daily_pnl ?? stats?.live_pnl_24h);

  const totalPnl =
    activeMode === 'PAPER'
      ? (stats?.paper_total_pnl ?? stats?.paper_pnl_24h)
      : (stats?.live_total_pnl ?? stats?.total_pnl);

  // Deltas: approximate today vs prior 24h window
  const baseDailyPnl =
    activeMode === 'PAPER'
      ? (stats?.paper_daily_pnl ?? stats?.daily_pnl)
      : (stats?.live_daily_pnl ?? stats?.daily_pnl);

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
        <div className='flex items-center gap-2'>
          <span className='tf-badge'>
            <Radio className='h-3 w-3' />
            5M
          </span>
          <ModeBadge mode={activeMode} />
        </div>
      </header>

      {/* ── Page-level health banner ────────────────────────────── */}
      <PageStatusBanner status={status} surfaceLabel='Dashboard' />

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
          <div className='grid grid-cols-2 gap-1.5 md:grid-cols-3 xl:grid-cols-6'>
            {Array.from({ length: 6 }).map((_, idx) => (
              <Skeleton
                // eslint-disable-next-line react/no-array-index-key
                key={idx}
                className='h-[60px] rounded border border-[var(--to-border)] bg-[var(--to-surface-raised)]'
              />
            ))}
          </div>
        ) : (
          <div className='grid grid-cols-2 gap-1.5 md:grid-cols-3 xl:grid-cols-6'>
            <StatCard
              label='Today PnL'
              value={formatCurrency(todayPnl, { signed: true })}
              subValue={
                todayPnlDelta != null
                  ? `Δ vs prev 24h ${formatCurrency(todayPnlDelta, { signed: true })}`
                  : EMPTY_VALUE
              }
              icon={Wallet}
            />
            <StatCard
              label='Total PnL'
              value={formatCurrency(totalPnl, { signed: true })}
              subValue={
                stats?.total_pnl_24h != null
                  ? `24h ${formatCurrency(stats.total_pnl_24h, { signed: true })}`
                  : EMPTY_VALUE
              }
              icon={TrendingUp}
            />
            <StatCard
              label='Drawdown'
              value={formatPercent(risk?.drawdown_pct)}
              subValue={
                risk?.max_drawdown_pct != null
                  ? `Max ${formatPercent(risk.max_drawdown_pct)}`
                  : EMPTY_VALUE
              }
              icon={Activity}
              variant='loss'
            />
            <StatCard
              label='Daily DD'
              value={formatPercent(stats?.daily_drawdown_pct)}
              subValue={
                risk?.max_daily_loss_pct != null
                  ? `Limit ${formatPercent(risk.max_daily_loss_pct)}`
                  : EMPTY_VALUE
              }
              icon={BarChart3}
            />
            <StatCard
              label='Active Positions'
              value={formatNumber(activePositionsCount, {
                decimals: 0,
                empty: '0',
              })}
              subValue={
                risk?.max_positions != null
                  ? `Max ${formatNumber(risk.max_positions, { decimals: 0 })}`
                  : EMPTY_VALUE
              }
              icon={Crosshair}
            />
            <StatCard
              label='Trades Today'
              value={formatNumber(tradesToday, { decimals: 0, empty: '0' })}
              subValue={
                stats?.total_signals_24h != null
                  ? `24h ${formatNumber(stats.total_signals_24h, { decimals: 0 })}`
                  : EMPTY_VALUE
              }
              icon={Clock}
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
        <section className='to-panel flex min-h-0 flex-1 flex-col overflow-hidden'>
          <div className='to-panel-header'>
            <div className='flex items-center gap-2'>
              <span className='panel-label'>Latest Signals</span>
              <span
                className='kpi-meta font-mono text-[10px] tabular-nums'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {signals.length} total
              </span>
            </div>
            <span
              className='kpi-meta font-mono text-[10px] tabular-nums text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              Last updated&nbsp;{mounted ? lastUpdated : '—'}
            </span>
          </div>

          <div className='scrollbar-thin min-h-0 flex-1 overflow-y-auto p-2'>
            {signalsLoading && signals.length === 0 ? (
              <TableSkeleton rowCount={8} columnCount={6} />
            ) : (
              <SignalTable
                signals={signals}
                councilMap={councilMap}
                onSelectSignal={handleSelectSignal}
                maxRows={30}
                className='max-h-[320px]'
              />
            )}
          </div>
        </section>

        {/* Side rail · Risk status + Live log */}
        <aside className='flex min-h-0 w-full flex-col gap-2 xl:w-[360px]'>
          <section className='to-panel shrink-0'>
            <div className='to-panel-header'>
              <div className='flex items-center gap-2'>
                <span className='panel-label'>Risk status</span>
              </div>
              <span
                className='kpi-meta font-mono text-[10px] tabular-nums text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                Last updated&nbsp;{mounted ? lastUpdated : '—'}
              </span>
            </div>
            <div className='p-2'>
              {riskLoading ? (
                <div className='space-y-2'>
                  <Skeleton className='h-4 w-full rounded bg-[var(--to-surface-raised)]' />
                  <Skeleton className='h-4 w-4/5 rounded bg-[var(--to-surface-raised)]' />
                </div>
              ) : (
                <RiskBar />
              )}
            </div>
          </section>

          <section className='min-h-0 flex-1 overflow-hidden'>
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
