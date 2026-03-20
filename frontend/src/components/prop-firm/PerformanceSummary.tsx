'use client';

import { StatCard } from '@/components/dashboard/StatCard';

interface PerformanceSummaryProps {
  openPositions: number;
  closedTrades: number;
  winRate: number;
  totalPnl: number;
  bestDay: { date: string; pnl: number };
  worstDay: { date: string; pnl: number };
}

export function PerformanceSummary({
  openPositions,
  closedTrades,
  winRate,
  totalPnl,
  bestDay,
  worstDay,
}: PerformanceSummaryProps) {
  return (
    <div className='glow-card p-6'>
      <h3 className='text-[13px] font-bold text-[var(--to-text-dim)] uppercase tracking-widest font-mono mb-4'>
        Performance Summary
      </h3>

      <div className='grid grid-cols-2 md:grid-cols-5 gap-3'>
        <StatCard
          label='Open Positions'
          value={`${openPositions}`}
          variant='default'
        />

        <StatCard
          label='Closed Trades'
          value={`${closedTrades}`}
          variant='default'
        />

        <StatCard
          label='Win Rate'
          value={`${winRate.toFixed(1)}%`}
          variant={winRate >= 50 ? 'profit' : 'loss'}
        />

        <StatCard
          label='Total PnL'
          value={`${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}`}
          variant={totalPnl >= 0 ? 'profit' : 'loss'}
        />

        <StatCard
          label='Best / Worst Day'
          value={`${bestDay.date} / ${worstDay.date}`}
          variant='warning'
        />
      </div>
    </div>
  );
}
