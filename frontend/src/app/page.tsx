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
import { TradingSignal } from '@/types/trading';
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

export default function DashboardPage() {
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(
    null,
  );
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [logEntries, setLogEntries] = useState<LogEntry[]>([]);
  const logIdRef = useRef(0);

  useEffect(() => {
    setMounted(true);
  }, []);

  const { mode: activeMode } = useTradingMode();
  const { data: stats } = useSignalStats();
  const { data: risk } = useRiskStatus();
  const { data: signals = [] } = useTradingSignals(activeMode);

  const { data: health } = useQuery({
    queryKey: ['dashboard-health'],
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) return { status: 'offline' as const };
      const res = await fetch(`${base}/health`, {
        signal: AbortSignal.timeout(3000),
      });
      if (!res.ok) return { status: 'offline' as const };
      return res.json() as Promise<{
        status: 'healthy' | 'degraded' | 'offline';
      }>;
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
    ? new Date(
        latestSignal.updated_at ?? latestSignal.created_at,
      ).toLocaleTimeString()
    : new Date().toLocaleTimeString();

  const displayLastUpdated = mounted ? lastUpdated : 'Loading...';

  const strategyName =
    latestSignal?.entry_model || latestSignal?.zone_type || 'Liquidity S&D';
  const timeframe = '5M';

  const todayPnl =
    activeMode === 'PAPER'
      ? (stats?.paper_daily_pnl ?? stats?.paper_pnl_24h)
      : (stats?.live_daily_pnl ?? stats?.live_pnl_24h);
  const totalPnl =
    activeMode === 'PAPER'
      ? (stats?.paper_total_pnl ?? stats?.paper_pnl_24h)
      : (stats?.live_total_pnl ?? stats?.total_pnl);

  // Generate live log entries from signal activity
  const prevSignalCountRef = useRef(signals.length);
  useEffect(() => {
    if (!mounted) return;
    if (signals.length > prevSignalCountRef.current) {
      const newSignals = signals.slice(
        0,
        signals.length - prevSignalCountRef.current,
      );
      const newEntries: LogEntry[] = newSignals.map((s) => ({
        id: String(++logIdRef.current),
        timestamp: s.created_at,
        level: s.status === 'active' || s.status === 'executed' ? 'success' : s.status === 'filtered' || s.status === 'ai_rejected' ? 'warn' : 'info',
        message: `${s.symbol} ${s.side.toUpperCase()} @ ${s.entry ?? s.price ?? '?'} — ${s.status}`,
        source: 'SIGNAL',
      }));
      setLogEntries((prev) => [...prev, ...newEntries]);
    }
    prevSignalCountRef.current = signals.length;
  }, [signals, mounted]);

  // Seed initial log entries on mount
  useEffect(() => {
    if (!mounted) return;
    const now = new Date().toISOString();
    setLogEntries([
      {
        id: String(++logIdRef.current),
        timestamp: now,
        level: 'info',
        message: `Dashboard initialized — mode: ${activeMode}`,
        source: 'SYSTEM',
      },
      {
        id: String(++logIdRef.current),
        timestamp: now,
        level: isConnected ? 'success' : 'error',
        message: isConnected
          ? 'API connection established'
          : 'API unreachable — signals via Supabase only',
        source: 'HEALTH',
      },
      {
        id: String(++logIdRef.current),
        timestamp: now,
        level: 'info',
        message: `Strategy: ${strategyName} | Timeframe: ${timeframe}`,
        source: 'CONFIG',
      },
    ]);
    // Only run once on mount
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
      <div className='flex shrink-0 items-center justify-between gap-3'>
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
          <span
            className={
              activeMode === 'LIVE'
                ? 'flex items-center gap-1.5 rounded border border-[var(--to-long)]/20 bg-[var(--to-long)]/8 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--to-long)]'
                : 'flex items-center gap-1.5 rounded border border-[var(--to-warning)]/20 bg-[var(--to-warning)]/8 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--to-warning)]'
            }
          >
            <span className='status-dot status-dot-active pulse-active' />
            {activeMode}
          </span>
        </div>
      </div>

      {/* ── KPI Bar ─────────────────────────────────────────────── */}
      <section className='shrink-0'>
        <div className='mb-1.5 flex items-center justify-between px-0.5'>
          <p
            className='text-[9px] font-semibold uppercase tracking-[0.14em] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            Session KPIs
          </p>
          <p
            className='text-[9px] tabular-nums text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {displayLastUpdated}
          </p>
        </div>
        <div className='grid grid-cols-2 gap-1.5 md:grid-cols-3 xl:grid-cols-6'>
          <StatCard
            label='Today PnL'
            value={mounted ? formatCurrency(todayPnl, { signed: true }) : '—'}
            icon={Wallet}
          />
          <StatCard
            label='Total PnL'
            value={mounted ? formatCurrency(totalPnl, { signed: true }) : '—'}
            icon={TrendingUp}
          />
          <StatCard
            label='Drawdown'
            value={mounted ? formatPercent(risk?.drawdown_pct) : '—'}
            icon={Activity}
            variant='loss'
          />
          <StatCard
            label='Daily DD'
            value={mounted ? formatPercent(stats?.daily_drawdown_pct) : '—'}
            icon={BarChart3}
          />
          <StatCard
            label='Active Positions'
            value={
              mounted
                ? formatNumber(activePositionsCount, { decimals: 0, empty: '0' })
                : '—'
            }
            icon={Crosshair}
          />
          <StatCard
            label='Trades Today'
            value={
              mounted
                ? formatNumber(tradesToday, { decimals: 0, empty: '0' })
                : '—'
            }
            icon={Clock}
          />
        </div>
      </section>

      {noData && (
        <section className='to-panel shrink-0 border-[var(--to-warning)]/15 bg-[var(--to-warning)]/5 p-3'>
          <h2 className='text-sm font-semibold text-[var(--to-warning)]'>
            Bot is waiting for…
          </h2>
          <div className='mt-2 grid gap-3 md:grid-cols-2'>
            <div className='space-y-1 text-xs text-[var(--to-text-secondary)]'>
              <p>
                <span className='text-[var(--to-text-dim)]'>Strategy:</span>{' '}
                {strategyName}
              </p>
              <p>
                <span className='text-[var(--to-text-dim)]'>Timeframe:</span>{' '}
                {timeframe}
              </p>
              <p>
                <span className='text-[var(--to-text-dim)]'>Last signal:</span>{' '}
                <span>
                  {mounted
                    ? latestSignal
                      ? new Date(latestSignal.created_at).toLocaleString()
                      : EMPTY_VALUE
                    : 'Loading...'}
                </span>
              </p>
              <p>
                <span className='text-[var(--to-text-dim)]'>
                  Last reject reason:
                </span>{' '}
                {lastRejectSignal?.filter_reason ||
                  lastRejectSignal?.notes ||
                  EMPTY_VALUE}
              </p>
            </div>
            <div className='rounded border border-[var(--to-border)] bg-[var(--to-surface)] p-3 text-xs text-[var(--to-text-secondary)]'>
              <p>
                Connected{' '}
                {isConnected ? (
                  <span className='text-[var(--to-long)]'>●</span>
                ) : (
                  <span className='text-[var(--to-short)]'>●</span>
                )}
              </p>
              <p>
                Config loaded{' '}
                {stats ? (
                  <span className='text-[var(--to-long)]'>●</span>
                ) : (
                  <span className='text-[var(--to-short)]'>●</span>
                )}
              </p>
              <p>
                Risk guard{' '}
                {risk ? (
                  <span className='text-[var(--to-long)]'>●</span>
                ) : (
                  <span className='text-[var(--to-short)]'>●</span>
                )}
              </p>
              <p>
                Market open{' '}
                {isConnected ? (
                  <span className='text-[var(--to-long)]'>●</span>
                ) : (
                  <span className='text-[var(--to-text-dim)]'>—</span>
                )}
              </p>
            </div>
          </div>
        </section>
      )}

      {/* ── Main grid: 50 / 25 / 25 ─────────────────────────────── */}
      <div className='grid min-h-0 flex-1 grid-cols-1 gap-2 xl:grid-cols-4'>
        {/* ── Col 1-2: Charts + Signal Table (50%) ──────────────── */}
        <section
          className={`to-panel col-span-1 flex min-h-0 flex-col overflow-hidden xl:col-span-2 ${
            noData ? 'max-h-[220px]' : ''
          }`}
        >
          <div className='to-panel-header'>
            <div className='flex items-center gap-2'>
              <CandlestickChart className='h-3.5 w-3.5 text-[var(--to-accent-blue)]' />
              <span className='panel-label'>Technical Analysis</span>
            </div>
            <div className='flex items-center gap-1.5'>
              <span className='status-dot status-dot-active pulse-active' />
              <span
                className='text-[9px] text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                LIVE FEED
              </span>
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

                {/* Signal Table — sortable data grid */}
                <div className='to-panel'>
                  <div className='to-panel-header'>
                    <span className='panel-label'>Signal Book</span>
                    <span
                      className='text-[9px] tabular-nums text-[var(--to-text-dim)]'
                      style={{ fontFamily: 'var(--font-mono)' }}
                    >
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

        {/* ── Col 3: Active Positions (25%) ─────────────────────── */}
        <section className='col-span-1 min-h-0 overflow-hidden'>
          <ActiveTradesPanel
            mode={activeMode}
            onSelectSignal={handleSelectSignal}
            compact={noData}
          />
        </section>

        {/* ── Col 4: Bot Config + Signal Log + Live Log (25%) ──── */}
        <section className='col-span-1 flex min-h-0 flex-col gap-2 overflow-hidden'>
          {/* Bot Runtime panel */}
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

          {/* Recent Signals */}
          <div className='min-h-0 flex-1 overflow-hidden'>
            <RecentSignalsPanel
              mode={activeMode}
              onSelectSignal={handleSelectSignal}
            />
          </div>

          {/* Live Log terminal */}
          <LiveLog
            entries={logEntries}
            onClear={handleClearLog}
            className='h-[200px] shrink-0'
          />
        </section>
      </div>

      {/* Signal Inspector Sheet */}
      <SignalInspector
        signal={selectedSignal}
        open={inspectorOpen}
        onOpenChange={setInspectorOpen}
      />
    </div>
  );
}
