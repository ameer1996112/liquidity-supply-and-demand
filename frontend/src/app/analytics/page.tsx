'use client';

import { useState } from 'react';
import { useAnalytics } from '@/hooks/useAnalytics';
import {
  useBreakdown,
  useStreaks,
  useDrawdown,
  useSummary,
} from '@/hooks/usePerformanceAnalytics';
import { TradingMode } from '@/types/trading';
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
import {
  Target,
  TrendingUp,
  BarChart3,
  Hash,
} from 'lucide-react';

type ModeFilter = 'LIVE' | 'PAPER' | 'ALL';
type AnalyticsTab = 'overview' | 'breakdown' | 'drawdown' | 'streaks';

const TABS: { key: AnalyticsTab; label: string }[] = [
  { key: 'overview', label: 'Overview' },
  { key: 'breakdown', label: 'Breakdown' },
  { key: 'drawdown', label: 'Drawdown' },
  { key: 'streaks', label: 'Streaks' },
];

const PERIODS = ['24h', '7d', '30d', 'all'] as const;

const HOUR_LABELS = Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2, '0')}:00`);

export default function AnalyticsPage() {
  const [modeFilter, setModeFilter] = useState<ModeFilter>('ALL');
  const [activeTab, setActiveTab] = useState<AnalyticsTab>('overview');
  const [period, setPeriod] = useState<string>('7d');

  const mode = modeFilter === 'ALL' ? undefined : modeFilter;
  const apiMode = modeFilter === 'ALL' ? 'LIVE' : modeFilter;

  // Overview tab data
  const { data: analytics, isLoading } = useAnalytics(mode);

  // Performance Intelligence tab data (only fetch when tab active)
  const { data: breakdown, isLoading: breakdownLoading } = useBreakdown(period, apiMode);
  const { data: streaksData, isLoading: streaksLoading } = useStreaks(apiMode);
  const { data: drawdownData, isLoading: drawdownLoading } = useDrawdown(apiMode);
  const { data: summaryData, isLoading: summaryLoading } = useSummary(apiMode);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-zinc-100">Analytics</h1>

        <div className="flex items-center gap-3">
          {/* Period selector (for breakdown tab) */}
          {activeTab === 'breakdown' && (
            <div className="flex items-center gap-1 bg-[#1e222d] border border-[#2a2e39] rounded-md p-1">
              {PERIODS.map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={cn(
                    'font-mono text-[11px] px-2.5 py-1 rounded transition-colors',
                    period === p
                      ? 'bg-[#2a2e39] text-zinc-200'
                      : 'text-zinc-500 hover:text-zinc-300',
                  )}
                >
                  {p}
                </button>
              ))}
            </div>
          )}

          {/* Mode Filter */}
          <div className="flex items-center gap-1 bg-[#1e222d] border border-[#2a2e39] rounded-md p-1">
            {(['ALL', 'LIVE', 'PAPER'] as ModeFilter[]).map((m) => (
              <button
                key={m}
                onClick={() => setModeFilter(m)}
                className={cn(
                  'font-mono text-[11px] px-3 py-1 rounded transition-colors',
                  modeFilter === m
                    ? 'bg-[#2a2e39] text-zinc-200'
                    : 'text-zinc-500 hover:text-zinc-300',
                )}
              >
                {m}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 bg-[#1e222d] border border-[#2a2e39] rounded-md p-1 w-fit">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'font-mono text-[11px] px-4 py-1.5 rounded transition-colors',
              activeTab === tab.key
                ? 'bg-[#2a2e39] text-zinc-200'
                : 'text-zinc-500 hover:text-zinc-300',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ══════ OVERVIEW TAB ══════ */}
      {activeTab === 'overview' && (
        <>
          {isLoading ? (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-28 rounded-lg bg-[#1e222d]" />
              ))}
            </div>
          ) : analytics ? (
            <>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <MetricCard
                  label="Win Rate"
                  value={`${analytics.winRate.toFixed(1)}%`}
                  icon={<Target className="w-4 h-4" />}
                  trend={analytics.winRate >= 50 ? 'up' : 'down'}
                  subtitle={`${analytics.outcomeDistribution.wins}W / ${analytics.outcomeDistribution.losses}L`}
                />
                <MetricCard
                  label="Profit Factor"
                  value={analytics.profitFactor >= 999 ? 'Inf' : analytics.profitFactor.toFixed(2)}
                  icon={<TrendingUp className="w-4 h-4" />}
                  trend={analytics.profitFactor >= 1 ? 'up' : 'down'}
                  subtitle={`Avg Win: $${analytics.avgWin.toFixed(2)}`}
                />
                <MetricCard
                  label="Avg R:R"
                  value={`1:${analytics.avgRR.toFixed(1)}`}
                  icon={<BarChart3 className="w-4 h-4" />}
                  subtitle={`Avg Loss: $${analytics.avgLoss.toFixed(2)}`}
                />
                <MetricCard
                  label="Total Trades"
                  value={analytics.closedTrades}
                  icon={<Hash className="w-4 h-4" />}
                  subtitle={`${analytics.totalTrades} signals total`}
                />
              </div>

              <EquityCurveChart data={analytics.equityCurve} />

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <WinRateDonut
                  wins={analytics.outcomeDistribution.wins}
                  losses={analytics.outcomeDistribution.losses}
                  breakeven={analytics.outcomeDistribution.breakeven}
                />
                <PnlBySymbolChart data={analytics.pnlBySymbol} />
              </div>

              <DailyPnlChart data={analytics.pnlByDay} />
            </>
          ) : (
            <div className="tv-card p-12 flex flex-col items-center justify-center">
              <BarChart3 className="w-10 h-10 text-zinc-700 mb-3" />
              <span className="text-sm text-zinc-500">No analytics data available</span>
            </div>
          )}
        </>
      )}

      {/* ══════ BREAKDOWN TAB ══════ */}
      {activeTab === 'breakdown' && (
        <>
          {breakdownLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-64 rounded-lg bg-[#1e222d]" />
              <Skeleton className="h-48 rounded-lg bg-[#1e222d]" />
            </div>
          ) : breakdown ? (
            <div className="space-y-6">
              <HeatmapChart
                title="PnL by Hour of Day"
                rows={['PnL']}
                columns={HOUR_LABELS.filter((_, i) => i % 3 === 0)}
                data={[
                  HOUR_LABELS.filter((_, i) => i % 3 === 0).map(
                    (h) => breakdown.pnl_by_hour[h]?.pnl ?? 0,
                  ),
                ]}
              />

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <BreakdownTable title="By Symbol" data={breakdown.pnl_by_symbol} />
                <BreakdownTable title="By Day of Week" data={breakdown.pnl_by_day_of_week} />
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <BreakdownTable title="By Zone Type" data={breakdown.pnl_by_zone_type} />
                <BreakdownTable title="By Entry Model" data={breakdown.pnl_by_entry_model} />
              </div>

              <BreakdownTable
                title="By AI Confidence"
                data={breakdown.win_rate_by_ai_confidence}
              />
            </div>
          ) : (
            <div className="tv-card p-12 flex flex-col items-center justify-center">
              <BarChart3 className="w-10 h-10 text-zinc-700 mb-3" />
              <span className="text-sm text-zinc-500">No breakdown data available</span>
            </div>
          )}
        </>
      )}

      {/* ══════ DRAWDOWN TAB ══════ */}
      {activeTab === 'drawdown' && (
        <>
          {drawdownLoading || summaryLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-80 rounded-lg bg-[#1e222d]" />
              <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
                {[...Array(6)].map((_, i) => (
                  <Skeleton key={i} className="h-24 rounded-lg bg-[#1e222d]" />
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-6">
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
            <Skeleton className="h-96 rounded-lg bg-[#1e222d]" />
          ) : streaksData ? (
            <StreakTimeline
              streaks={streaksData.streaks}
              maxWinStreak={streaksData.max_win_streak}
              maxLossStreak={streaksData.max_loss_streak}
              currentStreak={streaksData.current_streak}
              currentStreakType={streaksData.current_streak_type}
            />
          ) : (
            <div className="tv-card p-12 flex flex-col items-center justify-center">
              <BarChart3 className="w-10 h-10 text-zinc-700 mb-3" />
              <span className="text-sm text-zinc-500">No streak data available</span>
            </div>
          )}
        </>
      )}
    </div>
  );
}
