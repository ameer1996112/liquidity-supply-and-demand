'use client';

import { cn } from '@/lib/utils';
import type { SummaryData } from '@/hooks/usePerformanceAnalytics';
import {
  TrendingUp,
  TrendingDown,
  Clock,
  Target,
  BarChart3,
  Zap,
} from 'lucide-react';

interface SummaryCardsProps {
  data: SummaryData;
}

function SummaryMetric({
  label,
  value,
  icon,
  colored,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  colored?: 'green' | 'red';
}) {
  return (
    <div className="tv-card p-4 flex items-start gap-3">
      <div className="flex items-center justify-center w-8 h-8 rounded bg-[#1e222d] text-zinc-500 shrink-0">
        {icon}
      </div>
      <div className="flex flex-col">
        <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-mono">
          {label}
        </span>
        <span
          className={cn(
            'font-mono text-lg font-bold tabular-nums',
            colored === 'green' && 'text-[#26a69a]',
            colored === 'red' && 'text-[#ef5350]',
            !colored && 'text-zinc-200',
          )}
        >
          {value}
        </span>
      </div>
    </div>
  );
}

export function SummaryCards({ data }: SummaryCardsProps) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
      <SummaryMetric
        label="Sharpe Ratio"
        value={data.sharpe_ratio.toFixed(2)}
        icon={<TrendingUp className="w-4 h-4" />}
        colored={data.sharpe_ratio > 0 ? 'green' : data.sharpe_ratio < 0 ? 'red' : undefined}
      />
      <SummaryMetric
        label="Sortino Ratio"
        value={data.sortino_ratio.toFixed(2)}
        icon={<TrendingDown className="w-4 h-4" />}
        colored={data.sortino_ratio > 0 ? 'green' : data.sortino_ratio < 0 ? 'red' : undefined}
      />
      <SummaryMetric
        label="Expectancy"
        value={`$${data.expectancy.toFixed(2)}`}
        icon={<Zap className="w-4 h-4" />}
        colored={data.expectancy > 0 ? 'green' : data.expectancy < 0 ? 'red' : undefined}
      />
      <SummaryMetric
        label="Avg Hold Time"
        value={`${data.avg_hold_time_hours.toFixed(1)}h`}
        icon={<Clock className="w-4 h-4" />}
      />
      <SummaryMetric
        label="Total R Won"
        value={data.total_r_won.toFixed(2)}
        icon={<Target className="w-4 h-4" />}
        colored="green"
      />
      <SummaryMetric
        label="Total R Lost"
        value={data.total_r_lost.toFixed(2)}
        icon={<BarChart3 className="w-4 h-4" />}
        colored="red"
      />
    </div>
  );
}
