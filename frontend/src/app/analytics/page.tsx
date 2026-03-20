'use client';

import { useState, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { useAnalytics } from '@/hooks/useAnalytics';
import {
  useBreakdown,
  useStreaks,
  useDrawdown,
  useSummary,
  type BucketStats,
} from '@/hooks/usePerformanceAnalytics';
import { PerformanceScoreCard } from '@/components/analytics/PerformanceScoreCard';
import {
  InsightCard,
  type InsightData,
} from '@/components/analytics/InsightCard';
import { AIConfidenceChart } from '@/components/analytics/AIConfidenceChart';
import { SymbolPerformanceTable } from '@/components/analytics/SymbolPerformanceTable';
import { DayOfWeekChart } from '@/components/analytics/DayOfWeekChart';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { Download, BarChart3 } from 'lucide-react';
import { PanelEmptyState } from '@/components/shared/PanelEmptyState';

// ── Dynamic imports (heavy chart components) ─────────────────────────────────

const EquityCurveChart = dynamic(
  () =>
    import('@/components/analytics/EquityCurveChart').then(
      (m) => m.EquityCurveChart
    ),
  {
    loading: () => (
      <Skeleton className='h-[280px] w-full rounded-lg bg-[var(--to-surface-raised)]/60' />
    ),
  }
);
const DrawdownChart = dynamic(
  () =>
    import('@/components/analytics/DrawdownChart').then((m) => m.DrawdownChart),
  {
    loading: () => (
      <Skeleton className='h-[220px] w-full rounded-lg bg-[var(--to-surface-raised)]/60' />
    ),
  }
);
const HeatmapChart = dynamic(
  () =>
    import('@/components/analytics/HeatmapChart').then((m) => m.HeatmapChart),
  {
    loading: () => (
      <Skeleton className='h-[200px] w-full rounded-lg bg-[var(--to-surface-raised)]/60' />
    ),
  }
);
const StreakTimeline = dynamic(
  () =>
    import('@/components/analytics/StreakTimeline').then(
      (m) => m.StreakTimeline
    ),
  {
    loading: () => (
      <Skeleton className='h-[280px] w-full rounded-lg bg-[var(--to-surface-raised)]/60' />
    ),
  }
);
const RollingMetricsChart = dynamic(
  () =>
    import('@/components/analytics/RollingMetricsChart').then(
      (m) => m.RollingMetricsChart
    ),
  {
    loading: () => (
      <Skeleton className='h-[360px] w-full rounded-lg bg-[var(--to-surface-raised)]/60' />
    ),
  }
);

// ── Types ─────────────────────────────────────────────────────────────────────

type ModeFilter = 'LIVE' | 'PAPER' | 'ALL';
const PERIODS = ['7d', '30d', '90d', 'all'] as const;
type Period = (typeof PERIODS)[number];

const HOUR_LABELS = Array.from(
  { length: 24 },
  (_, i) => `${String(i).padStart(2, '0')}:00`
);

// ── Helpers ───────────────────────────────────────────────────────────────────

function getBestBucket(
  data: Record<string, BucketStats>,
  minTrades = 3
): { key: string; stats: BucketStats } | null {
  const entries = Object.entries(data).filter(([, b]) => b.count >= minTrades);
  if (entries.length === 0) return null;
  const best = entries.reduce((a, b) =>
    b[1].win_rate > a[1].win_rate ? b : a
  );
  return { key: best[0], stats: best[1] };
}

function toInsightData(
  key: string,
  stats: BucketStats,
  type: InsightData['type'],
  subValue?: string
): InsightData {
  return {
    label: key,
    value: key,
    subValue,
    winRate: stats.win_rate,
    trades: stats.count,
    pnl: stats.pnl,
    type,
  };
}

function exportAnalyticsCsv(
  analytics: ReturnType<typeof useAnalytics>['data'],
  summaryData: ReturnType<typeof useSummary>['data']
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

// ── Section wrapper ───────────────────────────────────────────────────────────

function Section({
  title,
  subtitle,
  children,
  className,
}: {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn('flex flex-col gap-2', className)}>
      {title && (
        <div>
          <h2
            className='text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {title}
          </h2>
          {subtitle && (
            <p
              className='mt-0.5 text-[10px] text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-sans)' }}
            >
              {subtitle}
            </p>
          )}
        </div>
      )}
      {children}
    </section>
  );
}

// ── Skeleton helpers ──────────────────────────────────────────────────────────

function CardSkeleton({ h = 'h-28' }: { h?: string }) {
  return <Skeleton className={cn(h, 'rounded-lg bg-[var(--to-surface-raised)]/60')} />;
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const [modeFilter, setModeFilter] = useState<ModeFilter>('ALL');
  const [period, setPeriod] = useState<Period>('30d');

  const mode = modeFilter === 'ALL' ? undefined : modeFilter;
  // Pass 'ALL' to backend when user selects ALL — backend supports it and returns
  // all trades regardless of run_mode. Previously hardcoded 'LIVE' here which meant
  // breakdown/streaks/drawdown always showed LIVE-only data even when ALL was selected.
  const analyticsMode = modeFilter;

  // ── Data hooks ──────────────────────────────────────────────────────────────
  const { data: analytics, isLoading: analyticsLoading } = useAnalytics(mode);
  const { data: breakdown, isLoading: breakdownLoading } = useBreakdown(
    period,
    analyticsMode
  );
  const { data: streaksData, isLoading: streaksLoading } =
    useStreaks(analyticsMode);
  const { data: drawdownData, isLoading: drawdownLoading } =
    useDrawdown(analyticsMode);
  const { data: summaryData, isLoading: summaryLoading } =
    useSummary(analyticsMode);

  const isLoading = analyticsLoading || summaryLoading;

  // ── Derived insights ────────────────────────────────────────────────────────
  const insights = useMemo(() => {
    if (!breakdown) return { symbol: null, hour: null, day: null, model: null };

    const bestSymbol = getBestBucket(breakdown.pnl_by_symbol);
    const bestHour = getBestBucket(breakdown.pnl_by_hour);
    const bestDay = getBestBucket(breakdown.pnl_by_day_of_week);
    const bestModel = getBestBucket(breakdown.pnl_by_entry_model);

    return {
      symbol: bestSymbol
        ? toInsightData(
            bestSymbol.key,
            bestSymbol.stats,
            'symbol',
            `${bestSymbol.stats.count} trades`
          )
        : null,
      hour: bestHour
        ? toInsightData(bestHour.key, bestHour.stats, 'hour', 'UTC time')
        : null,
      day: bestDay
        ? toInsightData(bestDay.key, bestDay.stats, 'day', 'day of week')
        : null,
      model: bestModel
        ? toInsightData(bestModel.key, bestModel.stats, 'model', 'entry model')
        : null,
    };
  }, [breakdown]);

  const hasData = !!analytics;
  const hasBreakdown = !!breakdown;
  const hasDrawdown = !!drawdownData && drawdownData.data.length > 0;
  const hasStreaks = !!streaksData && streaksData.streaks.length > 0;

  return (
    <div className='flex flex-col gap-6 pb-8 animate-fade-in-up'>
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className='flex flex-wrap items-start justify-between gap-3'>
        <div className='flex items-center gap-3'>
          <div className='flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--to-accent-blue)]/12 border border-[var(--to-accent-blue)]/25'>
            <BarChart3 className='h-[18px] w-[18px] text-[var(--to-accent-blue)]' />
          </div>
          <div>
            <h1 className='page-title text-lg font-bold'>
              Performance Intelligence
            </h1>
            <p className='page-subtitle mt-0.5 text-xs'>
              Deep-dive analytics · patterns · risk-adjusted metrics
            </p>
          </div>
        </div>

        <div className='flex flex-wrap items-center gap-2'>
          {/* Export CSV */}
          <button
            onClick={() => exportAnalyticsCsv(analytics, summaryData)}
            disabled={!analytics && !summaryData}
            className='flex items-center gap-1.5 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-1.5 text-[10px] font-medium text-[var(--to-text-secondary)] transition-colors hover:border-[var(--to-accent-blue)]/50 hover:text-[var(--to-accent-blue)] disabled:opacity-40'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            <Download className='h-3 w-3' />
            Export CSV
          </button>

          {/* Period selector */}
          <div className='surface-soft flex items-center gap-0.5 rounded-lg p-0.5'>
            {PERIODS.map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={cn(
                  'rounded-md px-2.5 py-1 text-[10px] font-medium transition-colors',
                  period === p
                    ? 'bg-[var(--to-accent-blue)]/20 text-[var(--to-accent-blue)]'
                    : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]'
                )}
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {p}
              </button>
            ))}
          </div>

          {/* Mode filter */}
          <div className='surface-soft flex items-center gap-0.5 rounded-lg p-0.5'>
            {(['ALL', 'LIVE', 'PAPER'] as ModeFilter[]).map((m) => (
              <button
                key={m}
                onClick={() => setModeFilter(m)}
                className={cn(
                  'rounded-md px-3 py-1 text-[10px] font-medium transition-colors',
                  modeFilter === m
                    ? 'bg-[var(--to-long)]/15 text-[var(--to-long)]'
                    : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]'
                )}
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {m}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── No data state ────────────────────────────────────────────────────── */}
      {!isLoading && !hasData && (
        <div className='glow-card p-8'>
          <PanelEmptyState
            title='No performance data'
            description='Execute and close trades to generate analytics.'
          />
        </div>
      )}

      {/* ── Performance Score (Hero) ─────────────────────────────────────────── */}
      <Section
        title='Performance Score'
        subtitle='Composite score across win rate, profit factor, risk-adjusted returns, and drawdown'
      >
        {isLoading ? (
          <div aria-label="Loading analytics"><CardSkeleton h='h-36' /></div>
        ) : analytics && summaryData ? (
          <PerformanceScoreCard
            winRate={analytics.winRate}
            profitFactor={analytics.profitFactor}
            expectancy={summaryData.expectancy}
            sharpeRatio={summaryData.sharpe_ratio}
            sortinoRatio={summaryData.sortino_ratio}
            maxDrawdownPct={drawdownData?.max_drawdown_pct ?? 0}
            totalTrades={summaryData.total_trades}
          />
        ) : null}
      </Section>

      {/* ── Equity Curve ─────────────────────────────────────────────────────── */}
      {hasData && (
        <Section
          title='Equity Curve'
          subtitle='Cumulative PnL over all closed trades'
        >
          <div className='glow-card p-4'>
            <EquityCurveChart data={analytics!.equityCurve} />
          </div>
        </Section>
      )}

      {/* ── Drawdown ─────────────────────────────────────────────────────────── */}
      {(drawdownLoading || hasDrawdown) && (
        <Section
          title='Drawdown Analysis'
          subtitle='Underwater equity curve — how deep and how long'
        >
          {drawdownLoading ? (
            <CardSkeleton h='h-[220px]' />
          ) : (
            <DrawdownChart
              data={drawdownData!.data}
              maxDrawdownPct={drawdownData!.max_drawdown_pct}
              maxDrawdownAmount={drawdownData!.max_drawdown_amount}
            />
          )}
        </Section>
      )}

      {/* ── Intelligence Insights ─────────────────────────────────────────────── */}
      <Section
        title='Intelligence Insights'
        subtitle={`Best-performing patterns from the last ${period} · min 3 trades`}
      >
        {breakdownLoading ? (
          <div className='grid grid-cols-2 gap-3 lg:grid-cols-4'>
            {[...Array(4)].map((_, i) => (
              <CardSkeleton key={i} h='h-32' />
            ))}
          </div>
        ) : (
          <div className='grid grid-cols-2 gap-3 lg:grid-cols-4'>
            <InsightCard data={insights.symbol} type='symbol' />
            <InsightCard data={insights.hour} type='hour' />
            <InsightCard data={insights.day} type='day' />
            <InsightCard data={insights.model} type='model' />
          </div>
        )}
      </Section>

      {/* ── Symbol Performance + AI Confidence ───────────────────────────────── */}
      {(breakdownLoading || hasBreakdown) && (
        <Section
          title='Breakdown Analysis'
          subtitle='Symbol performance and AI confidence correlation'
        >
          {breakdownLoading ? (
            <div className='grid grid-cols-1 gap-3 lg:grid-cols-2'>
              <CardSkeleton h='h-64' />
              <CardSkeleton h='h-64' />
            </div>
          ) : (
            <div className='grid grid-cols-1 gap-3 lg:grid-cols-2'>
              <SymbolPerformanceTable data={breakdown!.pnl_by_symbol} />
              <AIConfidenceChart data={breakdown!.win_rate_by_ai_confidence} />
            </div>
          )}
        </Section>
      )}

      {/* ── Hour Heatmap ─────────────────────────────────────────────────────── */}
      {(breakdownLoading || hasBreakdown) && (
        <Section
          title='Time-of-Day Analysis'
          subtitle='PnL distribution across trading hours (UTC)'
        >
          {breakdownLoading ? (
            <CardSkeleton h='h-[200px]' />
          ) : (
            <HeatmapChart
              title='PnL by Hour of Day (UTC)'
              rows={['PnL']}
              columns={HOUR_LABELS.filter((_, i) => i % 2 === 0)}
              data={[
                HOUR_LABELS.filter((_, i) => i % 2 === 0).map(
                  (h) => breakdown!.pnl_by_hour[h]?.pnl ?? 0
                ),
              ]}
            />
          )}
        </Section>
      )}

      {/* ── Day-of-Week + Entry Model ─────────────────────────────────────────── */}
      {(breakdownLoading || hasBreakdown) && (
        <Section
          title='Pattern Analysis'
          subtitle='Day-of-week performance and entry model breakdown'
        >
          {breakdownLoading ? (
            <div className='grid grid-cols-1 gap-3 lg:grid-cols-2'>
              <CardSkeleton h='h-56' />
              <CardSkeleton h='h-56' />
            </div>
          ) : (
            <div className='grid grid-cols-1 gap-3 lg:grid-cols-2'>
              <DayOfWeekChart data={breakdown!.pnl_by_day_of_week} />
              <EntryModelBreakdown data={breakdown!.pnl_by_entry_model} />
            </div>
          )}
        </Section>
      )}

      {/* ── Rolling Metrics ───────────────────────────────────────────────────── */}
      {(drawdownLoading || hasDrawdown) && (
        <Section
          title='Rolling Metrics'
          subtitle='10-trade rolling window — Win Rate, Profit Factor, Avg R:R'
        >
          {drawdownLoading ? (
            <CardSkeleton h='h-[360px]' />
          ) : (
            <RollingMetricsChart
              drawdownData={drawdownData!.data}
              windowSize={10}
            />
          )}
        </Section>
      )}

      {/* ── Streak Timeline ───────────────────────────────────────────────────── */}
      {(streaksLoading || hasStreaks) && (
        <Section
          title='Streak Analysis'
          subtitle='Win/loss streak history and current momentum'
        >
          {streaksLoading ? (
            <CardSkeleton h='h-[280px]' />
          ) : (
            <StreakTimeline
              streaks={streaksData!.streaks}
              maxWinStreak={streaksData!.max_win_streak}
              maxLossStreak={streaksData!.max_loss_streak}
              currentStreak={streaksData!.current_streak}
              currentStreakType={streaksData!.current_streak_type}
            />
          )}
        </Section>
      )}

      {/* ── Zone Type Breakdown ───────────────────────────────────────────────── */}
      {(breakdownLoading || hasBreakdown) && (
        <Section
          title='Zone & Setup Analysis'
          subtitle='Performance by zone type and setup quality'
        >
          {breakdownLoading ? (
            <CardSkeleton h='h-48' />
          ) : (
            <ZoneTypeBreakdown data={breakdown!.pnl_by_zone_type} />
          )}
        </Section>
      )}
    </div>
  );
}

// ── Inline sub-components ─────────────────────────────────────────────────────

function EntryModelBreakdown({ data }: { data: Record<string, BucketStats> }) {
  const rows = useMemo(
    () =>
      Object.entries(data)
        .filter(([, b]) => b.count >= 1)
        .map(([model, b]) => ({ model, ...b }))
        .sort((a, b) => b.pnl - a.pnl),
    [data]
  );

  if (rows.length === 0) {
    return (
      <div className='glow-card p-4'>
        <PanelEmptyState
          title='No entry model data'
          description='More trades needed.'
        />
      </div>
    );
  }

  const maxAbsPnl = Math.max(...rows.map((r) => Math.abs(r.pnl)), 1);

  return (
    <div className='glow-card'>
      <div className='border-b border-[var(--to-border)] px-4 py-3'>
        <p className='panel-label'>Entry Model Performance</p>
        <p
          className='mt-0.5 text-[10px] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          Which entry models generate the best results?
        </p>
      </div>
      <div className='divide-y divide-[var(--to-border)]/50'>
        {rows.map((row) => {
          const winRateColor =
            row.win_rate >= 60
              ? 'var(--to-long)'
              : row.win_rate >= 50
              ? 'var(--to-warning)'
              : 'var(--to-short)';
          const barWidth = (Math.abs(row.pnl) / maxAbsPnl) * 100;
          return (
            <div
              key={row.model}
              className='flex items-center gap-3 px-4 py-2.5 hover:bg-[var(--to-surface-raised)]/30 transition-colors'
            >
              <span
                className='w-28 truncate text-[11px] font-medium text-[var(--to-text-secondary)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {row.model}
              </span>
              <span
                className='w-8 text-[10px] tabular-nums'
                style={{ color: winRateColor, fontFamily: 'var(--font-mono)' }}
              >
                {row.win_rate.toFixed(0)}%
              </span>
              <div className='flex flex-1 items-center gap-2'>
                <div className='h-1.5 flex-1 overflow-hidden rounded-full bg-[var(--to-surface)]'>
                  <div
                    className='h-full rounded-full transition-all duration-500'
                    style={{
                      width: `${barWidth}%`,
                      backgroundColor: row.pnl >= 0 ? 'var(--to-long)' : 'var(--to-short)',
                      opacity: 0.75,
                    }}
                  />
                </div>
                <span
                  className='w-20 text-right text-[10px] font-bold tabular-nums'
                  style={{
                    color: row.pnl >= 0 ? 'var(--to-long)' : 'var(--to-short)',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {row.pnl >= 0 ? '+' : ''}${row.pnl.toFixed(2)}
                </span>
              </div>
              <span
                className='w-8 text-right text-[10px] text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {row.count}t
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ZoneTypeBreakdown({ data }: { data: Record<string, BucketStats> }) {
  const rows = useMemo(
    () =>
      Object.entries(data)
        .filter(([, b]) => b.count >= 1)
        .map(([zone, b]) => ({ zone, ...b }))
        .sort((a, b) => b.win_rate - a.win_rate),
    [data]
  );

  if (rows.length === 0) {
    return (
      <div className='glow-card p-4'>
        <PanelEmptyState
          title='No zone data'
          description='More trades needed.'
        />
      </div>
    );
  }

  return (
    <div className='glow-card'>
      <div className='border-b border-[var(--to-border)] px-4 py-3'>
        <p className='panel-label'>Zone Type Performance</p>
        <p
          className='mt-0.5 text-[10px] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          Supply & demand zone quality breakdown
        </p>
      </div>
      <div className='grid grid-cols-2 gap-3 p-4 sm:grid-cols-3 lg:grid-cols-4'>
        {rows.map((row) => {
          const winRateColor =
            row.win_rate >= 60
              ? '#0ecb81'
              : row.win_rate >= 50
              ? '#f0b90b'
              : '#f6465d';
          return (
            <div
              key={row.zone}
              className='flex flex-col gap-1.5 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)]/40 p-3'
            >
              <span
                className='truncate text-[10px] font-bold text-[var(--to-text-secondary)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {row.zone}
              </span>
              <span
                className='text-lg font-black tabular-nums'
                style={{ color: winRateColor, fontFamily: 'var(--font-mono)' }}
              >
                {row.win_rate.toFixed(0)}%
              </span>
              <div className='flex items-center justify-between'>
                <span
                  className='text-[9px] text-[var(--to-text-dim)]'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {row.count} trades
                </span>
                <span
                  className='text-[10px] font-bold tabular-nums'
                  style={{
                    color: row.pnl >= 0 ? 'var(--to-long)' : 'var(--to-short)',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {row.pnl >= 0 ? '+' : ''}${row.pnl.toFixed(0)}
                </span>
              </div>
              {/* Win rate bar */}
              <div className='h-1 overflow-hidden rounded-full bg-[var(--to-surface)]'>
                <div
                  className='h-full rounded-full'
                  style={{
                    width: `${Math.min(row.win_rate, 100)}%`,
                    backgroundColor: winRateColor,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
