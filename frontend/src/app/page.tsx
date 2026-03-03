'use client';

import { useCallback, useMemo, useState, useEffect } from 'react';
import { SignalInspector } from '@/components/SignalInspector';
import { ActiveTradesPanel } from '@/components/dashboard/ActiveTradesPanel';
import { RecentSignalsPanel } from '@/components/dashboard/RecentSignalsPanel';
import { MiniEquityChart } from '@/components/dashboard/MiniEquityChart';
import { ExecutionQualityWidget } from '@/components/dashboard/ExecutionQualityWidget';
import { PortfolioRiskWidget } from '@/components/dashboard/PortfolioRiskWidget';
import { EvaluationDashboard } from '@/components/evaluation/EvaluationDashboard';
import { PineConfigStatus } from '@/components/dashboard/PineConfigStatus';
import { StatCard } from '@/components/dashboard/StatCard';
import { SignalTable } from '@/components/dashboard/SignalTable';
import { LiveLog } from '@/components/dashboard/LiveLog';
import { useTradingMode } from '@/providers/TradingModeProvider';
import { useSignalStats, useTradingSignals } from '@/hooks/useTradingSignals';
import { useRiskStatus } from '@/hooks/useRiskStatus';
import { useConnectionHealth } from '@/hooks/useConnectionHealth';
import { useDashboardLog } from '@/hooks/useDashboardLog';
import {
  formatCurrency,
  formatNumber,
  formatPercent,
  EMPTY_VALUE,
} from '@/lib/formatters';
import type { TradingSignal, TradingMode } from '@/types/trading';
import {
  CandlestickChart,
  Server,
  Radio,
  Wallet,
  TrendingUp,
  Activity,
  BarChart3,
  Crosshair,
  Clock,
} from 'lucide-react';
import { isSignalOpen, isSignalRejected } from '@/domain/metrics/tradingMetrics';

// ── Sub-components ────────────────────────────────────────────────────────────

function ModeBadge({ mode }: { mode: TradingMode }) {
  return (
    <span className={mode === 'LIVE' ? 'mode-badge mode-badge-live' : 'mode-badge mode-badge-paper'}>
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

const STATUS_CHECKS = ['Connected', 'Config loaded', 'Risk guard', 'Market open'] as const;

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
          {([
            ['Strategy', strategyName],
            ['Timeframe', timeframe],
          ] as [string, string][]).map(([label, val]) => (
            <div key={label} className='flex gap-1.5'>
              <dt className='text-text-dim'>{label}:</dt>
              <dd>{val}</dd>
            </div>
          ))}
          <div className='flex gap-1.5'>
            <dt className='text-text-dim'>Last signal:</dt>
            <dd className='font-mono tabular-nums'>
              {mounted ? (latestSignalTime ?? EMPTY_VALUE) : 'Loading…'}
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
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  const { mode: activeMode } = useTradingMode();
  const { data: stats } = useSignalStats();
  const { data: risk } = useRiskStatus();
  const { data: signals = [] } = useTradingSignals(activeMode);
  const { isConnected } = useConnectionHealth();

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

  const lastUpdated = useMemo(
    () =>
      latestSignal
        ? new Date(latestSignal.updated_at ?? latestSignal.created_at).toLocaleTimeString()
        : new Date().toLocaleTimeString(),
    // Recompute only when the latest signal changes, not on every render tick
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [latestSignal?.id],
  );

  const noData = signals.length === 0 && activePositionsCount === 0;
  const strategyName = latestSignal?.entry_model ?? latestSignal?.zone_type ?? 'Liquidity S&D';
  const timeframe = '5M';

  const todayPnl =
    activeMode === 'PAPER'
      ? (stats?.paper_daily_pnl ?? stats?.paper_pnl_24h)
      : (stats?.live_daily_pnl ?? stats?.live_pnl_24h);

  const totalPnl =
    activeMode === 'PAPER'
      ? (stats?.paper_total_pnl ?? stats?.paper_pnl_24h)
      : (stats?.live_total_pnl ?? stats?.total_pnl);

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
            Live command center · market orders · 5-minute zones
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

      {/* ── KPI Bar ─────────────────────────────────────────────── */}
      <section className='shrink-0'>
        <div className='mb-1.5 flex items-center justify-between px-0.5'>
          <p className='kpi-meta'>Session KPIs</p>
          <p className='kpi-meta font-mono tabular-nums'>
            {mounted ? lastUpdated : '—'}
          </p>
        </div>
        <div className='grid grid-cols-2 gap-1.5 md:grid-cols-3 xl:grid-cols-6'>
          <StatCard label='Today PnL'        value={mounted ? formatCurrency(todayPnl, { signed: true }) : '—'} icon={Wallet} />
          <StatCard label='Total PnL'        value={mounted ? formatCurrency(totalPnl, { signed: true }) : '—'} icon={TrendingUp} />
          <StatCard label='Drawdown'         value={mounted ? formatPercent(risk?.drawdown_pct) : '—'} icon={Activity} variant='loss' />
          <StatCard label='Daily DD'         value={mounted ? formatPercent(stats?.daily_drawdown_pct) : '—'} icon={BarChart3} />
          <StatCard label='Active Positions' value={mounted ? formatNumber(activePositionsCount, { decimals: 0, empty: '0' }) : '—'} icon={Crosshair} />
          <StatCard label='Trades Today'     value={mounted ? formatNumber(tradesToday, { decimals: 0, empty: '0' }) : '—'} icon={Clock} />
        </div>
      </section>

      {/* ── Waiting banner (no data) ─────────────────────────────── */}
      {noData && (
        <WaitingBanner
          strategyName={strategyName}
          timeframe={timeframe}
          latestSignalTime={
            latestSignal ? new Date(latestSignal.created_at).toLocaleString() : null
          }
          lastRejectReason={lastRejectSignal?.filter_reason ?? lastRejectSignal?.notes ?? ''}
          isConnected={isConnected}
          hasStats={!!stats}
          hasRisk={!!risk}
          mounted={mounted}
        />
      )}

      {/* ── Main grid: [50%] [25%] [25%] ────────────────────────── */}
      <div className='grid min-h-0 flex-1 grid-cols-1 gap-2 xl:grid-cols-4'>

        {/* Col 1–2 · Charts + Signal Table */}
        <section
          className={[
            'to-panel col-span-1 flex min-h-0 flex-col overflow-hidden xl:col-span-2',
            noData ? 'max-h-[220px]' : '',
          ].join(' ')}
        >
          <div className='to-panel-header'>
            <div className='flex items-center gap-2'>
              <CandlestickChart className='h-3.5 w-3.5 text-blue-accent' />
              <span className='panel-label'>Technical Analysis</span>
            </div>
            <div className='flex items-center gap-1.5'>
              <span className='status-dot status-dot-active pulse-active' />
              <span className='kpi-meta'>LIVE FEED</span>
            </div>
          </div>

          <div className='scrollbar-thin flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-2'>
            <div className={noData ? 'min-h-[120px]' : 'min-h-[180px]'}>
              <MiniEquityChart mode={activeMode} />
            </div>

            {!noData && (
              <>
                <div className='grid grid-cols-1 gap-2 lg:grid-cols-2'>
                  <ExecutionQualityWidget />
                  <PortfolioRiskWidget />
                </div>

                <div className='to-panel'>
                  <div className='to-panel-header'>
                    <span className='panel-label'>Signal Book</span>
                    <span className='kpi-meta font-mono tabular-nums'>
                      {signals.length} signals
                    </span>
                  </div>
                  <SignalTable
                    signals={signals}
                    onSelectSignal={handleSelectSignal}
                    maxRows={30}
                    className='max-h-[280px]'
                  />
                </div>

                <EvaluationDashboard />
              </>
            )}
          </div>
        </section>

        {/* Col 3 · Active Positions */}
        <section className='col-span-1 min-h-0 overflow-hidden'>
          <ActiveTradesPanel
            mode={activeMode}
            onSelectSignal={handleSelectSignal}
            compact={noData}
          />
        </section>

        {/* Col 4 · Bot Runtime + Signal Log + Live Log */}
        <section className='col-span-1 flex min-h-0 flex-col gap-2 overflow-hidden'>
          <div className='to-panel shrink-0'>
            <div className='to-panel-header'>
              <div className='flex items-center gap-2'>
                <Server className='h-3.5 w-3.5 text-blue-accent' />
                <span className='panel-label'>Bot Runtime</span>
              </div>
              <span className='status-dot status-dot-active pulse-active' />
            </div>
            <div className='p-2'>
              <PineConfigStatus />
            </div>
          </div>

          <div className='min-h-0 flex-1 overflow-hidden'>
            <RecentSignalsPanel mode={activeMode} onSelectSignal={handleSelectSignal} />
          </div>

          <LiveLog
            entries={logEntries}
            onClear={clearLog}
            className='h-[200px] shrink-0'
          />
        </section>
      </div>

      <SignalInspector
        signal={selectedSignal}
        open={inspectorOpen}
        onOpenChange={setInspectorOpen}
      />
    </div>
  );
}
