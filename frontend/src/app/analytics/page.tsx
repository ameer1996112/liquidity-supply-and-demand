'use client';

import { useState } from 'react';
import { useAnalytics } from '@/hooks/useAnalytics';
import {
  useBreakdown,
  useStreaks,
  useDrawdown,
  useSummary,
} from '@/hooks/usePerformanceAnalytics';
import { MetricCard } from '@/components/analytics/MetricCard';
import { EquityCurveChart } from '@/components/analytics/EquityCurveChart';
import { WinRateDonut } from '@/components/analytics/WinRateDonut';
import { PnlBySymbolChart } from '@/components/analytics/PnlBySymbolChart';
import { DailyPnlChart } from '@/components/analytics/DailyPnlChart';
import { HeatmapChart } from '@/components/analytics/HeatmapChart';
import { DrawdownChart } from '@/components/analytics/DrawdownChart';
import { BreakdownTable } from '@/components/analytics/BreakdownTable';
import { StreakTimeline } from '@/components/analytics/StreakTimeline';
import { SummaryCards } from '@/components/analytics/SummaryCards';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { Target, TrendingUp, BarChart3, Hash } from 'lucide-react';

type ModeFilter = 'LIVE' | 'PAPER' | 'ALL';
type AnalyticsTab = 'overview' | 'breakdown' | 'drawdown' | 'streaks';

const TABS: { key: AnalyticsTab; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'breakdown', label: 'Breakdown' },
  { key: 'drawdown', label: 'Drawdown' },
  { key: 'streaks', label: 'Streaks' },
];

const PERIODS = ['24h', '7d', '30d', 'all'] as const;

const HOUR_LABELS = Array.from(
  { length: 24 },
  (_, i) => `${String(i).padStart(2, '0')}:00`
);

export default function AnalyticsPage() {
  const [modeFilter, setModeFilter] = useState<ModeFilter>('ALL');
  const [activeTab, setActiveTab] = useState<AnalyticsTab>('overview');
  const [period, setPeriod] = useState<string>('7d');

  const mode = modeFilter === 'ALL' ? undefined : modeFilter;
  const apiMode = modeFilter === 'ALL' ? 'LIVE' : modeFilter;

  const { data: analytics, isLoading } = useAnalytics(mode);
  const { data: breakdown, isLoading: breakdownLoading } = useBreakdown(
    period,
    apiMode
  );
  const { data: streaksData, isLoading: streaksLoading } = useStreaks(apiMode);
  const { data: drawdownData, isLoading: drawdownLoading } =
    useDrawdown(apiMode);
  const { data: summaryData, isLoading: summaryLoading } = useSummary(apiMode);

  return (
    // Full-height flex column — fills the `main` flex-1 area
    <div className='flex h-full min-h-0 flex-col gap-4'>
      {/* ── Sticky Header Row ─────────────────────────────── */}
      <div className='shrink-0 flex flex-wrap items-start justify-between gap-3'>
        <div>
          <h1 className='page-title text-xl font-semibold'>Analytics</h1>
          <p className='page-subtitle mt-1 text-sm'>
            Performance insights across trades, risk, and consistency.
          </p>
        </div>

        <div className='flex flex-wrap items-center gap-2'>
          {/* Period selector (breakdown tab only) */}
          {activeTab === 'breakdown' && (
            <div className='surface-soft flex items-center gap-1 rounded-xl border border-[rgba(95,119,163,0.34)] p-1'>
              {PERIODS.map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={cn(
                    'font-mono text-[11px] rounded-lg px-2.5 py-1 transition-colors',
                    period === p
                      ? 'bg-[rgba(95,131,255,0.2)] text-[#cfe0ff]'
                      : 'text-[#9cafd4] hover:text-[#ecf2ff]'
                  )}
                >
                  {p}
                </button>
              ))}
            </div>
          )}

          {/* Mode Filter */}
          <div className='surface-soft flex items-center gap-1 rounded-xl border border-[rgba(95,119,163,0.34)] p-1'>
            {(['ALL', 'LIVE', 'PAPER'] as ModeFilter[]).map((m) => (
              <button
                key={m}
                onClick={() => setModeFilter(m)}
                className={cn(
                  'font-mono text-[11px] rounded-lg px-3 py-1 transition-colors',
                  modeFilter === m
                    ? 'bg-[rgba(46,201,170,0.18)] text-[#c9faef]'
                    : 'text-[#9cafd4] hover:text-[#ecf2ff]'
                )}
              >
                {m}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Tab Bar ───────────────────────────────────────── */}
      <div className='surface-soft flex w-fit shrink-0 items-center gap-1 rounded-xl border border-[rgba(95,119,163,0.34)] p-1'>
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'font-mono text-[11px] rounded-lg px-4 py-1.5 transition-colors',
              activeTab === tab.key
                ? 'bg-[rgba(95,131,255,0.2)] text-[#d8e5ff]'
                : 'text-[#9cafd4] hover:text-[#ecf2ff]'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Tab Content — scrollable, fills remaining height ─ */}
      <div className='flex-1 min-h-0 overflow-y-auto scrollbar-thin'>
        {/* ══════ OVERVIEW TAB ══════ */}
        {activeTab === 'overview' && (
          <div className='flex h-full min-h-0 flex-col gap-4'>
            {isLoading ? (
              <div className='grid shrink-0 grid-cols-2 gap-4 lg:grid-cols-4'>
                {[...Array(4)].map((_, i) => (
                  <Skeleton
                    key={i}
                    className='h-28 rounded-xl bg-[rgba(30,45,72,0.72)]'
                  />
                ))}
              </div>
            ) : analytics ? (
              <>
                {/* KPI Row — natural height, never shrinks */}
                <div className='grid shrink-0 grid-cols-2 gap-4 lg:grid-cols-4'>
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

                {/* Equity Curve — grows to fill remaining space */}
                <div className='flex-1 min-h-[400px]'>
                  <EquityCurveChart data={analytics.equityCurve} />
                </div>

                {/* Secondary charts below */}
                <div className='grid grid-cols-1 lg:grid-cols-2 gap-4 shrink-0'>
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
              <div className='tv-card p-12 flex flex-col items-center justify-center flex-1'>
                <BarChart3 className='mb-3 h-10 w-10 text-[#7588b0]' />
                <span className='text-sm text-[#9aabd1]'>
                  No analytics data available
                </span>
              </div>
            )}
          </div>
        )}

        {/* ══════ BREAKDOWN TAB ══════ */}
        {activeTab === 'breakdown' && (
          <>
            {breakdownLoading ? (
              <div className='space-y-4'>
                <Skeleton className='h-64 rounded-xl bg-[rgba(30,45,72,0.72)]' />
                <Skeleton className='h-48 rounded-xl bg-[rgba(30,45,72,0.72)]' />
              </div>
            ) : breakdown ? (
              <div className='space-y-6'>
                <div className='min-h-[300px]'>
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

                <div className='grid grid-cols-1 lg:grid-cols-2 gap-4'>
                  <BreakdownTable
                    title='By Symbol'
                    data={breakdown.pnl_by_symbol}
                  />
                  <BreakdownTable
                    title='By Day of Week'
                    data={breakdown.pnl_by_day_of_week}
                  />
                </div>

                <div className='grid grid-cols-1 lg:grid-cols-2 gap-4'>
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
              <div className='tv-card p-12 flex flex-col items-center justify-center'>
                <BarChart3 className='mb-3 h-10 w-10 text-[#7588b0]' />
                <span className='text-sm text-[#9aabd1]'>
                  No breakdown data available
                </span>
              </div>
            )}
          </>
        )}

        {/* ══════ DRAWDOWN TAB ══════ */}
        {activeTab === 'drawdown' && (
          <>
            {drawdownLoading || summaryLoading ? (
              <div className='space-y-4'>
                <Skeleton className='h-80 rounded-xl bg-[rgba(30,45,72,0.72)]' />
                <div className='grid grid-cols-2 gap-4 lg:grid-cols-3'>
                  {[...Array(6)].map((_, i) => (
                    <Skeleton
                      key={i}
                      className='h-24 rounded-xl bg-[rgba(30,45,72,0.72)]'
                    />
                  ))}
                </div>
              </div>
            ) : (
              <div className='space-y-6'>
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

        {/* ══════ STREAKS TAB ══════ */}
        {activeTab === 'streaks' && (
          <>
            {streaksLoading ? (
              <Skeleton className='h-96 rounded-xl bg-[rgba(30,45,72,0.72)]' />
            ) : streaksData ? (
              <StreakTimeline
                streaks={streaksData.streaks}
                maxWinStreak={streaksData.max_win_streak}
                maxLossStreak={streaksData.max_loss_streak}
                currentStreak={streaksData.current_streak}
                currentStreakType={streaksData.current_streak_type}
              />
            ) : (
              <div className='tv-card p-12 flex flex-col items-center justify-center'>
                <BarChart3 className='mb-3 h-10 w-10 text-[#7588b0]' />
                <span className='text-sm text-[#9aabd1]'>
                  No streak data available
                </span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
