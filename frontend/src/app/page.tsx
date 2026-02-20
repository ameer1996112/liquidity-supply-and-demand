'use client';

import { useCallback, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { SignalInspector } from '@/components/SignalInspector';
import { ActiveTradesPanel } from '@/components/dashboard/ActiveTradesPanel';
import { RecentSignalsPanel } from '@/components/dashboard/RecentSignalsPanel';
import { MiniEquityChart } from '@/components/dashboard/MiniEquityChart';
import { ExecutionQualityWidget } from '@/components/dashboard/ExecutionQualityWidget';
import { PortfolioRiskWidget } from '@/components/dashboard/PortfolioRiskWidget';
import { EvaluationDashboard } from '@/components/evaluation/EvaluationDashboard';
import { PineConfigStatus } from '@/components/dashboard/PineConfigStatus';
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
import { CandlestickChart, Server, Radio } from 'lucide-react';
import { isSignalRejected } from '@/domain/metrics/tradingMetrics';

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className='rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2'>
      <p className='text-[10px] uppercase tracking-wider text-slate-500'>
        {label}
      </p>
      <p className='mt-1 text-sm font-semibold tabular-nums text-slate-100'>
        {value}
      </p>
    </div>
  );
}

export default function DashboardPage() {
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(
    null
  );
  const [inspectorOpen, setInspectorOpen] = useState(false);
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
  const activePositionsCount =
    risk?.active_positions ?? stats?.active_trades ?? 0;
  const tradesToday = useMemo(() => {
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    return signals.filter((s) => new Date(s.created_at) >= start).length;
  }, [signals]);

  const latestSignal = signals[0] ?? null;
  const lastRejectSignal = useMemo(
    () => signals.find((s) => isSignalRejected(s)),
    [signals]
  );
  const noData = signals.length === 0 && activePositionsCount === 0;

  const lastUpdated = latestSignal
    ? new Date(
        latestSignal.updated_at ?? latestSignal.created_at
      ).toLocaleTimeString()
    : new Date().toLocaleTimeString();

  const strategyName =
    latestSignal?.entry_model || latestSignal?.zone_type || 'Liquidity S&D';
  const timeframe = '5M';

  const todayPnl =
    activeMode === 'PAPER'
      ? stats?.paper_daily_pnl ?? stats?.paper_pnl_24h
      : stats?.live_daily_pnl ?? stats?.live_pnl_24h;
  const totalPnl =
    activeMode === 'PAPER'
      ? stats?.paper_total_pnl ?? stats?.paper_pnl_24h
      : stats?.live_total_pnl ?? stats?.total_pnl;

  const kpis = [
    { label: 'Today PnL', value: formatCurrency(todayPnl, { signed: true }) },
    { label: 'Total PnL', value: formatCurrency(totalPnl, { signed: true }) },
    { label: 'Drawdown', value: formatPercent(risk?.drawdown_pct) },
    { label: 'Daily DD', value: formatPercent(stats?.daily_drawdown_pct) },
    {
      label: 'Active Positions',
      value: formatNumber(activePositionsCount, { decimals: 0, empty: '0' }),
    },
    {
      label: 'Trades Today',
      value: formatNumber(tradesToday, { decimals: 0, empty: '0' }),
    },
  ];

  const handleSelectSignal = useCallback((signal: TradingSignal) => {
    setSelectedSignal(signal);
    setInspectorOpen(true);
  }, []);

  return (
    <div className='flex h-full min-h-0 flex-col gap-3'>
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className='flex shrink-0 items-center justify-between gap-3'>
        <div>
          <h1 className='page-title text-lg font-semibold'>Dashboard</h1>
          <p className='page-subtitle text-xs'>
            Live command center · market orders · 5-minute zones
          </p>
        </div>

        {/* 5m Timeframe badge — always visible */}
        <div className='flex items-center gap-2'>
          <span className='tf-badge'>
            <Radio className='h-3 w-3' />
            5M
          </span>
          <span
            className={
              activeMode === 'LIVE'
                ? 'flex items-center gap-1.5 rounded-md border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 font-mono text-[10px] font-semibold uppercase tracking-wider text-emerald-400'
                : 'flex items-center gap-1.5 rounded-md border border-amber-500/20 bg-amber-500/10 px-2.5 py-1 font-mono text-[10px] font-semibold uppercase tracking-wider text-amber-400'
            }
          >
            <span className='status-dot status-dot-active pulse-active' />
            {activeMode}
          </span>
        </div>
      </div>

      <section className='tv-card shrink-0 p-3'>
        <div className='mb-2 flex items-center justify-between'>
          <p className='text-[11px] font-medium uppercase tracking-[0.12em] text-slate-500'>
            Session KPIs
          </p>
          <p className='text-[10px] text-slate-500'>
            Last updated {lastUpdated}
          </p>
        </div>
        <div className='grid grid-cols-2 gap-2 lg:grid-cols-6'>
          {kpis.map((kpi) => (
            <StatCard key={kpi.label} label={kpi.label} value={kpi.value} />
          ))}
        </div>
      </section>

      {noData && (
        <section className='tv-card shrink-0 border border-indigo-500/25 bg-indigo-950/20 p-4'>
          <h2 className='text-sm font-semibold text-indigo-200'>
            Bot is waiting for…
          </h2>
          <div className='mt-3 grid gap-3 md:grid-cols-2'>
            <div className='space-y-1 text-xs text-slate-300'>
              <p>
                <span className='text-slate-500'>Strategy:</span> {strategyName}
              </p>
              <p>
                <span className='text-slate-500'>Timeframe:</span> {timeframe}
              </p>
              <p>
                <span className='text-slate-500'>Last signal:</span>{' '}
                {latestSignal
                  ? new Date(latestSignal.created_at).toLocaleString()
                  : EMPTY_VALUE}
              </p>
              <p>
                <span className='text-slate-500'>Last reject reason:</span>{' '}
                {lastRejectSignal?.filter_reason ||
                  lastRejectSignal?.notes ||
                  EMPTY_VALUE}
              </p>
            </div>
            <div className='rounded-lg border border-slate-800 bg-slate-900/70 p-3 text-xs text-slate-300'>
              <p>Connected {isConnected ? '✅' : '❌'}</p>
              <p>Config loaded {stats ? '✅' : '❌'}</p>
              <p>Risk guard {risk ? '✅' : '❌'}</p>
              <p>Market open {isConnected ? '✅' : '—'}</p>
            </div>
          </div>
        </section>
      )}

      {/* ── Main grid: 50 / 25 / 25 ─────────────────────────────── */}
      <div className='grid min-h-0 flex-1 grid-cols-1 gap-3 xl:grid-cols-4'>
        {/* ── Col 1-2: Technical Analysis (50%) ─────────────────── */}
        <section
          className={`tv-card col-span-1 flex min-h-0 flex-col overflow-hidden xl:col-span-2 ${
            noData ? 'max-h-[220px]' : ''
          }`}
        >
          <div className='tv-divider flex shrink-0 items-center justify-between border-b px-3 py-2'>
            <div className='flex items-center gap-2'>
              <CandlestickChart className='h-3.5 w-3.5 text-indigo-400' />
              <span
                className='panel-label'
                style={{ fontFamily: 'var(--font-sans)' }}
              >
                Technical Analysis
              </span>
            </div>
            <div className='flex items-center gap-1.5'>
              <span className='status-dot status-dot-active pulse-active' />
              <span
                className='text-[9px] text-slate-500'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                LIVE FEED
              </span>
            </div>
          </div>

          <div className='scrollbar-thin flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3'>
            <div className={noData ? 'min-h-[120px]' : 'min-h-[180px]'}>
              <MiniEquityChart mode={activeMode} />
            </div>
            {!noData && (
              <>
                <div className='grid grid-cols-1 gap-3 lg:grid-cols-2'>
                  <ExecutionQualityWidget />
                  <PortfolioRiskWidget />
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

        {/* ── Col 4: Bot Config + Signal Log (25%) ──────────────── */}
        <section className='col-span-1 flex min-h-0 flex-col gap-3 overflow-hidden'>
          {/* Bot Runtime panel */}
          <div className='tv-card shrink-0'>
            <div className='tv-divider flex items-center justify-between border-b px-3 py-2'>
              <div className='flex items-center gap-2'>
                <Server className='h-3.5 w-3.5 text-indigo-400' />
                <span
                  className='panel-label'
                  style={{ fontFamily: 'var(--font-sans)' }}
                >
                  Bot Runtime
                </span>
              </div>
              <span className='status-dot status-dot-active pulse-active' />
            </div>
            <div className='p-3'>
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
