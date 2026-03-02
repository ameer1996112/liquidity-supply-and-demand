'use client';

import { useCallback, useMemo, useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
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
import { LiveLog, type LogEntry } from '@/components/dashboard/LiveLog';
import { useTradingMode } from '@/providers/TradingModeProvider';
import { useSignalStats, useTradingSignals } from '@/hooks/useTradingSignals';
import { useRiskStatus } from '@/hooks/useRiskStatus';
import { getApiUrl } from '@/lib/api';
import {
  formatCurrency,
  formatNumber,
  formatPercent,
  EMPTY_VALUE,
} from '@/lib/formatters';
import { TradingSignal, TradingMode } from '@/types/trading';
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
import {
  isSignalOpen,
  isSignalRejected,
} from '@/domain/metrics/tradingMetrics';

// ── Local sub-components ──────────────────────────────────────────────────────

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
  return (
    <section className='to-panel shrink-0 border-[var(--to-warning)]/15 bg-[var(--to-warning)]/5 p-3'>
      <h2 className='text-sm font-semibold text-[var(--to-warning)]'>
        Bot is waiting for…
      </h2>
      <div className='mt-2 grid gap-3 md:grid-cols-2'>
        <dl className='space-y-1 text-xs text-[var(--to-text-secondary)]'>
          <div className='flex gap-1.5'>
            <dt className='text-[var(--to-text-dim)]'>Strategy:</dt>
            <dd>{strategyName}</dd>
          </div>
          <div className='flex gap-1.5'>
            <dt className='text-[var(--to-text-dim)]'>Timeframe:</dt>
            <dd>{timeframe}</dd>
          </div>
          <div className='flex gap-1.5'>
            <dt className='text-[var(--to-text-dim)]'>Last signal:</dt>
            <dd className='font-mono tabular-nums'>
              {mounted ? (latestSignalTime ?? EMPTY_VALUE) : 'Loading…'}
            </dd>
          </div>
          <div className='flex gap-1.5'>
            <dt className='text-[var(--to-text-dim)]'>Last reject:</dt>
            <dd>{lastRejectReason || EMPTY_VALUE}</dd>
          </div>
        </dl>

        <div className='rounded border border-[var(--to-border)] bg-[var(--to-surface)] p-3'>
          <ul className='space-y-1 text-xs text-[var(--to-text-secondary)]'>
            {(
              [
                ['Connected', isConnected],
                ['Config loaded', hasStats],
                ['Risk guard', hasRisk],
                ['Market open', isConnected],
              ] as [string, boolean][]
            ).map(([label, ok]) => (
              <li key={label} className='flex items-center justify-between'>
                <span>{label}</span>
                <span className={ok ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]'}>●</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

// ── Dashboard page ────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [logEntries, setLogEntries] = useState<LogEntry[]>([]);
  const logIdRef = useRef(0);

  useEffect(() => { setMounted(true); }, []);

  const { mode: activeMode } = useTradingMode();
  const { data: stats } = useSignalStats();
  const { data: risk } = useRiskStatus();
  const { data: signals = [] } = useTradingSignals(activeMode);

  const { data: health } = useQuery({
    queryKey: ['dashboard-health'],
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) return { status: 'offline' as const };
      const res = await fetch(`${base}/health`, { signal: AbortSignal.timeout(3000) });
      if (!res.ok) return { status: 'offline' as const };
      return res.json() as Promise<{ status: 'healthy' | 'degraded' | 'offline' }>;
    },
    refetchInterval: 30_000,
  });

  const isConnected = health?.status != null && health.status !== 'offline';

  const activePositionsCount = useMemo(
    () => signals.filter(isSignalOpen).length,
    [signals],
  );

  const tradesToday = useMemo(() => {
    if (!mounted) return 0;
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    return signals.filter((s) => new Date(s.created_at) >= start).length;
  }, [signals, mounted]);

  const latestSignal = signals[0] ?? null;
  const lastRejectSignal = useMemo(
    () => signals.find((s) => isSignalRejected(s)),
    [signals],
  );
  const noData = signals.length === 0 && activePositionsCount === 0;

  const lastUpdated = latestSignal
    ? new Date(latestSignal.updated_at ?? latestSignal.created_at).toLocaleTimeString()
    : new Date().toLocaleTimeString();

  const strategyName = latestSignal?.entry_model || latestSignal?.zone_type || 'Liquidity S&D';
  const timeframe = '5M';

  const todayPnl = activeMode === 'PAPER'
    ? (stats?.paper_daily_pnl ?? stats?.paper_pnl_24h)
    : (stats?.live_daily_pnl ?? stats?.live_pnl_24h);
  const totalPnl = activeMode === 'PAPER'
    ? (stats?.paper_total_pnl ?? stats?.paper_pnl_24h)
    : (stats?.live_total_pnl ?? stats?.total_pnl);

  // Append live-log entries when new signals arrive
  const prevSignalCountRef = useRef(signals.length);
  useEffect(() => {
    if (!mounted) return;
    if (signals.length > prevSignalCountRef.current) {
      const newSignals = signals.slice(0, signals.length - prevSignalCountRef.current);
      setLogEntries((prev) => [
        ...prev,
        ...newSignals.map((s) => ({
          id: String(++logIdRef.current),
          timestamp: s.created_at,
          level: (
            s.status === 'active' || s.status === 'executed' ? 'success' :
            s.status === 'filtered' || s.status === 'ai_rejected' ? 'warn' : 'info'
          ) as LogEntry['level'],
          message: `${s.symbol} ${s.side.toUpperCase()} @ ${s.entry ?? s.price ?? '?'} — ${s.status}`,
          source: 'SIGNAL',
        })),
      ]);
    }
    prevSignalCountRef.current = signals.length;
  }, [signals, mounted]);

  // Seed initial log entries on first mount
  useEffect(() => {
    if (!mounted) return;
    const now = new Date().toISOString();
    setLogEntries([
      { id: String(++logIdRef.current), timestamp: now, level: 'info', message: `Dashboard initialized — mode: ${activeMode}`, source: 'SYSTEM' },
      { id: String(++logIdRef.current), timestamp: now, level: isConnected ? 'success' : 'error', message: isConnected ? 'API connection established' : 'API unreachable — signals via Supabase only', source: 'HEALTH' },
      { id: String(++logIdRef.current), timestamp: now, level: 'info', message: `Strategy: ${strategyName} | Timeframe: ${timeframe}`, source: 'CONFIG' },
    ]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted]);

  const handleSelectSignal = useCallback((signal: TradingSignal) => {
    setSelectedSignal(signal);
    setInspectorOpen(true);
  }, []);

  const handleClearLog = useCallback(() => setLogEntries([]), []);

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
          <StatCard label='Today PnL'         value={mounted ? formatCurrency(todayPnl, { signed: true }) : '—'} icon={Wallet} />
          <StatCard label='Total PnL'         value={mounted ? formatCurrency(totalPnl, { signed: true }) : '—'} icon={TrendingUp} />
          <StatCard label='Drawdown'          value={mounted ? formatPercent(risk?.drawdown_pct) : '—'} icon={Activity} variant='loss' />
          <StatCard label='Daily DD'          value={mounted ? formatPercent(stats?.daily_drawdown_pct) : '—'} icon={BarChart3} />
          <StatCard label='Active Positions'  value={mounted ? formatNumber(activePositionsCount, { decimals: 0, empty: '0' }) : '—'} icon={Crosshair} />
          <StatCard label='Trades Today'      value={mounted ? formatNumber(tradesToday, { decimals: 0, empty: '0' }) : '—'} icon={Clock} />
        </div>
      </section>

      {/* ── Waiting banner (no data) ─────────────────────────────── */}
      {noData && (
        <WaitingBanner
          strategyName={strategyName}
          timeframe={timeframe}
          latestSignalTime={latestSignal ? new Date(latestSignal.created_at).toLocaleString() : null}
          lastRejectReason={lastRejectSignal?.filter_reason || lastRejectSignal?.notes || ''}
          isConnected={isConnected}
          hasStats={!!stats}
          hasRisk={!!risk}
          mounted={mounted}
        />
      )}

      {/* ── Main grid: 50 / 25 / 25 ─────────────────────────────── */}
      <div className='grid min-h-0 flex-1 grid-cols-1 gap-2 xl:grid-cols-4'>

        {/* Col 1–2: Charts + Signal Table (50%) */}
        <section className={`to-panel col-span-1 flex min-h-0 flex-col overflow-hidden xl:col-span-2 ${noData ? 'max-h-[220px]' : ''}`}>
          <div className='to-panel-header'>
            <div className='flex items-center gap-2'>
              <CandlestickChart className='h-3.5 w-3.5 text-[var(--to-accent-blue)]' />
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

        {/* Col 3: Active Positions (25%) */}
        <section className='col-span-1 min-h-0 overflow-hidden'>
          <ActiveTradesPanel
            mode={activeMode}
            onSelectSignal={handleSelectSignal}
            compact={noData}
          />
        </section>

        {/* Col 4: Bot Config + Signal Log + Live Log (25%) */}
        <section className='col-span-1 flex min-h-0 flex-col gap-2 overflow-hidden'>
          <div className='to-panel shrink-0'>
            <div className='to-panel-header'>
              <div className='flex items-center gap-2'>
                <Server className='h-3.5 w-3.5 text-[var(--to-accent-blue)]' />
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
            onClear={handleClearLog}
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
