'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import { useAnalytics } from '@/hooks/useAnalytics';
import {
  useBreakdown,
  useStreaks,
  useDrawdown,
  useSummary,
} from '@/hooks/usePerformanceAnalytics';
import { MetricCard } from '@/components/analytics/MetricCard';
import { BreakdownTable } from '@/components/analytics/BreakdownTable';
import { SummaryCards } from '@/components/analytics/SummaryCards';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
  Target,
  TrendingUp,
  BarChart3,
  Hash,
  Download,
  TrendingDown,
  Zap,
  Clock,
} from 'lucide-react';
import { PanelEmptyState } from '@/components/shared/PanelEmptyState';

const EquityCurveChart = dynamic(
  () =>
    import('@/components/analytics/EquityCurveChart').then(
      (m) => m.EquityCurveChart
    ),
  {
    loading: () => (
      <Skeleton className='h-full min-h-[360px] rounded-lg bg-slate-800/60' />
    ),
  }
);
const WinRateDonut = dynamic(
  () =>
    import('@/components/analytics/WinRateDonut').then((m) => m.WinRateDonut),
  { loading: () => <Skeleton className='h-64 rounded-lg bg-slate-800/60' /> }
);
const PnlBySymbolChart = dynamic(
  () =>
    import('@/components/analytics/PnlBySymbolChart').then(
      (m) => m.PnlBySymbolChart
    ),
  { loading: () => <Skeleton className='h-64 rounded-lg bg-slate-800/60' /> }
);
const DailyPnlChart = dynamic(
  () =>
    import('@/components/analytics/DailyPnlChart').then((m) => m.DailyPnlChart),
  { loading: () => <Skeleton className='h-64 rounded-lg bg-slate-800/60' /> }
);
const HeatmapChart = dynamic(
  () =>
    import('@/components/analytics/HeatmapChart').then((m) => m.HeatmapChart),
  { loading: () => <Skeleton className='h-64 rounded-lg bg-slate-800/60' /> }
);
const DrawdownChart = dynamic(
  () =>
    import('@/components/analytics/DrawdownChart').then((m) => m.DrawdownChart),
  { loading: () => <Skeleton className='h-64 rounded-lg bg-slate-800/60' /> }
);
const StreakTimeline = dynamic(
  () =>
    import('@/components/analytics/StreakTimeline').then(
      (m) => m.StreakTimeline
    ),
  { loading: () => <Skeleton className='h-80 rounded-lg bg-slate-800/60' /> }
);
const RollingMetricsChart = dynamic(
  () =>
    import('@/components/analytics/RollingMetricsChart').then(
      (m) => m.RollingMetricsChart
    ),
  { loading: () => <Skeleton className='h-80 rounded-lg bg-slate-800/60' /> }
);

type ModeFilter = 'LIVE' | 'PAPER' | 'ALL';
type AnalyticsTab =
  | 'overview'
  | 'breakdown'
  | 'drawdown'
  | 'streaks'
  | 'rolling';

const TABS: { key: AnalyticsTab; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'breakdown', label: 'Breakdown' },
  { key: 'drawdown', label: 'Drawdown' },
  { key: 'streaks', label: 'Streaks' },
  { key: 'rolling', label: 'Rolling' },
];

const PERIODS = ['24h', '7d', '30d', 'all'] as const;

const HOUR_LABELS = Array.from(
  { length: 24 },
  (_, i) => `${String(i).padStart(2, '0')}:00`
);

/** Export analytics summary to CSV */
function exportAnalyticsCsv(
  analytics: {
    winRate: number;
    profitFactor: number;
    avgRR: number;
    closedTrades: number;
    totalTrades: number;
    avgWin: number;
    avgLoss: number;
    outcomeDistribution: { wins: number; losses: number; breakeven: number };
  } | null,
  summaryData: {
    sharpe_ratio: number;
    sortino_ratio: number;
    expectancy: number;
    avg_hold_time_hours: number;
    total_r_won: number;
    total_r_lost: number;
  } | null
) {
  const rows: string[][] = [
    ['Metric', 'Value'],
    ['Win Rate (%)', analytics ? analytics.winRate.toFixed(2) : ''],
    ['Profit Factor', analytics ? analytics.profitFactor.toFixed(2) : ''],
    ['Avg R:R', analytics ? analytics.avgRR.toFixed(2) : ''],
    ['Total Trades', analytics ? String(analytics.closedTrades) : ''],
    ['Wins', analytics ? String(analytics.outcomeDistribution.wins) : ''],
    ['Losses', analytics ? String(analytics.outcomeDistribution.losses) : ''],
    ['Avg Win ($)', analytics ? analytics.avgWin.toFixed(2) : ''],
    ['Avg Loss ($)', analytics ? analytics.avgLoss.toFixed(2) : ''],
    ['Sharpe Ratio', summaryData ? summaryData.sharpe_ratio.toFixed(2) : ''],
    ['Sortino Ratio', summaryData ? summaryData.sortino_ratio.toFixed(2) : ''],
    ['Expectancy ($)', summaryData ? summaryData.expectancy.toFixed(2) : ''],
    [
      'Avg Hold Time (h)',
      summaryData ? summaryData.avg_hold_time_hours.toFixed(1) : '',
    ],
    ['Total R Won', summaryData ? summaryData.total_r_won.toFixed(2) : ''],
    ['Total R Lost', summaryData ? summaryData.total_r_lost.toFixed(2) : ''],
  ];

  const csv = rows.map((r) => r.join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `analytics_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function AnalyticsPage() {
  const [modeFilter, setModeFilter] = useState<ModeFilter>('ALL');
  const [activeTab, setActiveTab] = useState<AnalyticsTab>('overview');
  const [period, setPeriod] = useState<string>('7d');

  const mode = modeFilter === 'ALL' ? undefined : modeFilter;
  const analyticsMode = modeFilter === 'ALL' ? 'LIVE' : modeFilter;

  const { data: analytics, isLoading } = useAnalytics(mode);
  const {
    data: breakdown,
    isLoading: breakdownLoading,
    isError: breakdownError,
    error: breakdownErrorObj,
  } = useBreakdown(period, analyticsMode);
  const { data: streaksData, isLoading: streaksLoading } =
    useStreaks(analyticsMode);
  const { data: drawdownData, isLoading: drawdownLoading } =
    useDrawdown(analyticsMode);
  const { data: summaryData, isLoading: summaryLoading } =
    useSummary(analyticsMode);

  return (
    <div className='flex h-full min-h-0 flex-col gap-3'>
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className='shrink-0 flex flex-wrap items-start justify-between gap-3'>
        <div>
          <h1 className='page-title text-lg font-semibold'>Analytics</h1>
          <p className='page-subtitle mt-0.5 text-xs'>
            Performance insights across trades, risk, and consistency.
          </p>
        </div>

        <div className='flex flex-wrap items-center gap-2'>
          {/* Export CSV button */}
          <button
            onClick={() =>
              exportAnalyticsCsv(analytics ?? null, summaryData ?? null)
            }
            disabled={!analytics && !summaryData}
            className='flex items-center gap-1.5 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-1.5 text-[10px] font-medium text-[var(--to-text-secondary)] transition-colors hover:border-[var(--to-accent-blue)]/50 hover:text-[var(--to-accent-blue)] disabled:opacity-40'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            <Download className='h-3 w-3' />
            Export CSV
          </button>

          {/* Period selector */}
          {activeTab === 'breakdown' && (
            <div className='surface-soft flex items-center gap-0.5 rounded-lg p-0.5'>
              {PERIODS.map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={cn(
                    'rounded-md px-2.5 py-1 text-[10px] transition-colors',
                    period === p
                      ? 'bg-indigo-600/20 text-indigo-300'
                      : 'text-slate-500 hover:text-slate-300'
                  )}
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {p}
                </button>
              ))}
            </div>
          )}

          {/* Mode filter */}
          <div className='surface-soft flex items-center gap-0.5 rounded-lg p-0.5'>
            {(['ALL', 'LIVE', 'PAPER'] as ModeFilter[]).map((m) => (
              <button
                key={m}
                onClick={() => setModeFilter(m)}
                className={cn(
                  'rounded-md px-3 py-1 text-[10px] transition-colors',
                  modeFilter === m
                    ? 'bg-emerald-500/15 text-emerald-400'
                    : 'text-slate-500 hover:text-slate-300'
                )}
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {m}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Tab bar ─────────────────────────────────────────────── */}
      <div className='surface-soft flex w-fit shrink-0 items-center gap-0.5 rounded-lg p-0.5'>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'rounded-md px-4 py-1.5 text-[11px] font-medium transition-colors',
              activeTab === tab.key
                ? 'bg-indigo-600/20 text-indigo-300'
                : 'text-slate-500 hover:text-slate-300'
            )}
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Tab content ─────────────────────────────────────────── */}
      <div className='min-h-0 flex-1 overflow-y-auto scrollbar-thin'>
        {/* ══ OVERVIEW ══ */}
        {activeTab === 'overview' && (
          <div className='flex h-full min-h-0 flex-col gap-4'>
            {isLoading ? (
              <div className='grid shrink-0 grid-cols-2 gap-3 lg:grid-cols-4'>
                {[...Array(4)].map((_, i) => (
                  <Skeleton
                    key={i}
                    className='h-24 rounded-lg bg-slate-800/60'
                  />
                ))}
              </div>
            ) : analytics ? (
              <>
                {/* Primary KPI row */}
                <div className='grid shrink-0 grid-cols-2 gap-3 lg:grid-cols-4'>
                  <MetricCard
                    label='Win Rate'
                    value={`${analytics.winRate.toFixed(1)}%`}
                    icon={<Target className='w-4 h-4' />}
                    trend={analytics.winRate >= 50 ? 'up' : 'down'}
                    subtitle={`${analytics.outcomeDistribution.wins}W / ${analytics.outcomeDistribution.losses}L`}
                  />
                  <MetricCard
                    label='Profit Factor'
                    value={
                      analytics.profitFactor >= 999
                        ? 'Inf'
                        : analytics.profitFactor.toFixed(2)
                    }
                    icon={<TrendingUp className='w-4 h-4' />}
                    trend={analytics.profitFactor >= 1 ? 'up' : 'down'}
                    subtitle={`Avg Win: $${analytics.avgWin.toFixed(2)}`}
                  />
                  <MetricCard
                    label='Avg R:R'
                    value={`1:${analytics.avgRR.toFixed(1)}`}
                    icon={<BarChart3 className='w-4 h-4' />}
                    subtitle={`Avg Loss: $${analytics.avgLoss.toFixed(2)}`}
                  />
                  <MetricCard
                    label='Total Trades'
                    value={analytics.closedTrades}
                    icon={<Hash className='w-4 h-4' />}
                    subtitle={`${analytics.totalTrades} signals total`}
                  />
                </div>

                {/* Advanced risk-adjusted metrics row */}
                {summaryLoading ? (
                  <div className='grid shrink-0 grid-cols-2 gap-3 lg:grid-cols-4'>
                    {[...Array(4)].map((_, i) => (
                      <Skeleton
                        key={i}
                        className='h-20 rounded-lg bg-slate-800/60'
                      />
                    ))}
                  </div>
                ) : (
                  summaryData && (
                    <div className='grid shrink-0 grid-cols-2 gap-3 lg:grid-cols-4'>
                      <div className='tv-card flex items-start gap-3 p-4'>
                        <div className='flex h-8 w-8 shrink-0 items-center justify-center rounded bg-[#1e222d] text-zinc-500'>
                          <TrendingUp className='h-4 w-4' />
                        </div>
                        <div>
                          <p className='text-[10px] uppercase tracking-wider text-zinc-500 font-mono'>
                            Sharpe Ratio
                          </p>
                          <p
                            className={cn(
                              'font-mono text-lg font-bold tabular-nums',
                              summaryData.sharpe_ratio > 0
                                ? 'text-[#0ecb81]'
                                : 'text-[#f6465d]'
                            )}
                          >
                            {summaryData.sharpe_ratio.toFixed(2)}
                          </p>
                        </div>
                      </div>
                      <div className='tv-card flex items-start gap-3 p-4'>
                        <div className='flex h-8 w-8 shrink-0 items-center justify-center rounded bg-[#1e222d] text-zinc-500'>
                          <TrendingDown className='h-4 w-4' />
                        </div>
                        <div>
                          <p className='text-[10px] uppercase tracking-wider text-zinc-500 font-mono'>
                            Sortino Ratio
                          </p>
                          <p
                            className={cn(
                              'font-mono text-lg font-bold tabular-nums',
                              summaryData.sortino_ratio > 0
                                ? 'text-[#0ecb81]'
                                : 'text-[#f6465d]'
                            )}
                          >
                            {summaryData.sortino_ratio.toFixed(2)}
                          </p>
                        </div>
                      </div>
                      <div className='tv-card flex items-start gap-3 p-4'>
                        <div className='flex h-8 w-8 shrink-0 items-center justify-center rounded bg-[#1e222d] text-zinc-500'>
                          <Zap className='h-4 w-4' />
                        </div>
                        <div>
                          <p className='text-[10px] uppercase tracking-wider text-zinc-500 font-mono'>
                            Expectancy
                          </p>
                          <p
                            className={cn(
                              'font-mono text-lg font-bold tabular-nums',
                              summaryData.expectancy > 0
                                ? 'text-[#0ecb81]'
                                : 'text-[#f6465d]'
                            )}
                          >
                            ${summaryData.expectancy.toFixed(2)}
                          </p>
                        </div>
                      </div>
                      <div className='tv-card flex items-start gap-3 p-4'>
                        <div className='flex h-8 w-8 shrink-0 items-center justify-center rounded bg-[#1e222d] text-zinc-500'>
                          <Clock className='h-4 w-4' />
                        </div>
                        <div>
                          <p className='text-[10px] uppercase tracking-wider text-zinc-500 font-mono'>
                            Avg Hold
                          </p>
                          <p className='font-mono text-lg font-bold tabular-nums text-zinc-200'>
                            {summaryData.avg_hold_time_hours.toFixed(1)}h
                          </p>
                        </div>
                      </div>
                    </div>
                  )
                )}

                {/* Equity curve */}
                <div className='flex-1 min-h-[360px]'>
                  <EquityCurveChart data={analytics.equityCurve} />
                </div>

                {/* Secondary charts */}
                <div className='grid grid-cols-1 lg:grid-cols-2 gap-3 shrink-0'>
                  <WinRateDonut
                    wins={analytics.outcomeDistribution.wins}
                    losses={analytics.outcomeDistribution.losses}
                    breakeven={analytics.outcomeDistribution.breakeven}
                  />
                  <PnlBySymbolChart data={analytics.pnlBySymbol} />
                </div>

                <div className='shrink-0'>
                  <DailyPnlChart data={analytics.pnlByDay} />
                </div>
              </>
            ) : (
              <div className='tv-card flex-1 p-4'>
                <PanelEmptyState
                  title='No analytics data'
                  description='Execute trades to generate performance data.'
                />
              </div>
            )}
          </div>
        )}

        {/* ══ BREAKDOWN ══ */}
        {activeTab === 'breakdown' && (
          <>
            {breakdownLoading ? (
              <div className='space-y-3'>
                <Skeleton className='h-56 rounded-lg bg-slate-800/60' />
                <Skeleton className='h-44 rounded-lg bg-slate-800/60' />
              </div>
            ) : breakdownError ? (
              <div className='tv-card p-4'>
                <PanelEmptyState
                  title='Failed to load breakdown'
                  description={
                    breakdownErrorObj instanceof Error
                      ? breakdownErrorObj.message
                      : 'Unable to fetch breakdown analytics.'
                  }
                />
              </div>
            ) : breakdown ? (
              <div className='space-y-4'>
                <div className='min-h-[280px]'>
                  <HeatmapChart
                    title='PnL by Hour of Day'
                    rows={['PnL']}
                    columns={HOUR_LABELS.filter((_, i) => i % 3 === 0)}
                    data={[
                      HOUR_LABELS.filter((_, i) => i % 3 === 0).map(
                        (h) => breakdown.pnl_by_hour[h]?.pnl ?? 0
                      ),
                    ]}
                  />
                </div>

                <div className='grid grid-cols-1 lg:grid-cols-2 gap-3'>
                  <BreakdownTable
                    title='By Symbol'
                    data={breakdown.pnl_by_symbol}
                  />
                  <BreakdownTable
                    title='By Day of Week'
                    data={breakdown.pnl_by_day_of_week}
                  />
                </div>

                <div className='grid grid-cols-1 lg:grid-cols-2 gap-3'>
                  <BreakdownTable
                    title='By Zone Type'
                    data={breakdown.pnl_by_zone_type}
                  />
                  <BreakdownTable
                    title='By Entry Model'
                    data={breakdown.pnl_by_entry_model}
                  />
                </div>

                <BreakdownTable
                  title='By AI Confidence'
                  data={breakdown.win_rate_by_ai_confidence}
                />
              </div>
            ) : (
              <div className='tv-card p-4'>
                <PanelEmptyState
                  title='No breakdown data'
                  description='Not enough trades yet to compute breakdown analytics.'
                />
              </div>
            )}
          </>
        )}

        {/* ══ DRAWDOWN ══ */}
        {activeTab === 'drawdown' && (
          <>
            {drawdownLoading || summaryLoading ? (
              <div className='space-y-3'>
                <Skeleton className='h-72 rounded-lg bg-slate-800/60' />
                <div className='grid grid-cols-2 gap-3 lg:grid-cols-3'>
                  {[...Array(6)].map((_, i) => (
                    <Skeleton
                      key={i}
                      className='h-20 rounded-lg bg-slate-800/60'
                    />
                  ))}
                </div>
              </div>
            ) : (
              <div className='space-y-4'>
                {drawdownData && (
                  <DrawdownChart
                    data={drawdownData.data}
                    maxDrawdownPct={drawdownData.max_drawdown_pct}
                    maxDrawdownAmount={drawdownData.max_drawdown_amount}
                  />
                )}
                {summaryData && <SummaryCards data={summaryData} />}
              </div>
            )}
          </>
        )}

        {/* ══ STREAKS ══ */}
        {activeTab === 'streaks' && (
          <>
            {streaksLoading ? (
              <Skeleton className='h-80 rounded-lg bg-slate-800/60' />
            ) : streaksData ? (
              <StreakTimeline
                streaks={streaksData.streaks}
                maxWinStreak={streaksData.max_win_streak}
                maxLossStreak={streaksData.max_loss_streak}
                currentStreak={streaksData.current_streak}
                currentStreakType={streaksData.current_streak_type}
              />
            ) : (
              <div className='tv-card p-4'>
                <PanelEmptyState
                  title='No streak data'
                  description='Execute more trades to see win/loss streaks.'
                />
              </div>
            )}
          </>
        )}

        {/* ══ ROLLING ══ */}
        {activeTab === 'rolling' && (
          <>
            {drawdownLoading ? (
              <div className='space-y-3'>
                <Skeleton className='h-56 rounded-lg bg-slate-800/60' />
                <Skeleton className='h-56 rounded-lg bg-slate-800/60' />
              </div>
            ) : drawdownData && drawdownData.data.length > 0 ? (
              <div className='space-y-4'>
                <div className='flex items-center justify-between'>
                  <div>
                    <p className='page-title text-sm font-semibold'>
                      Rolling Metrics
                    </p>
                    <p className='page-subtitle text-[11px]'>
                      10-trade rolling window · Win Rate, Profit Factor, Avg R:R
                    </p>
                  </div>
                </div>
                <RollingMetricsChart
                  drawdownData={drawdownData.data}
                  windowSize={10}
                />
              </div>
            ) : (
              <div className='tv-card p-4'>
                <PanelEmptyState
                  title='No rolling data'
                  description='Execute more trades to see rolling performance metrics.'
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
