'use client';

import { useState } from 'react';
import { useAnalytics } from '@/hooks/useAnalytics';
import { TradingMode } from '@/types/trading';
import { MetricCard } from '@/components/analytics/MetricCard';
import { EquityCurveChart } from '@/components/analytics/EquityCurveChart';
import { WinRateDonut } from '@/components/analytics/WinRateDonut';
import { PnlBySymbolChart } from '@/components/analytics/PnlBySymbolChart';
import { DailyPnlChart } from '@/components/analytics/DailyPnlChart';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
  Target,
  TrendingUp,
  BarChart3,
  Hash,
} from 'lucide-react';

type ModeFilter = 'LIVE' | 'PAPER' | 'ALL';

export default function AnalyticsPage() {
  const [modeFilter, setModeFilter] = useState<ModeFilter>('ALL');

  const mode: TradingMode | undefined = modeFilter === 'ALL' ? undefined : modeFilter;
  const { data: analytics, isLoading } = useAnalytics(mode);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-zinc-100">Analytics</h1>

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
                  : 'text-zinc-500 hover:text-zinc-300'
              )}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      {/* KPI Cards */}
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

          {/* Equity Curve */}
          <EquityCurveChart data={analytics.equityCurve} />

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <WinRateDonut
              wins={analytics.outcomeDistribution.wins}
              losses={analytics.outcomeDistribution.losses}
              breakeven={analytics.outcomeDistribution.breakeven}
            />
            <PnlBySymbolChart data={analytics.pnlBySymbol} />
          </div>

          {/* Daily PnL */}
          <DailyPnlChart data={analytics.pnlByDay} />
        </>
      ) : (
        <div className="tv-card p-12 flex flex-col items-center justify-center">
          <BarChart3 className="w-10 h-10 text-zinc-700 mb-3" />
          <span className="text-sm text-zinc-500">No analytics data available</span>
        </div>
      )}
    </div>
  );
}
