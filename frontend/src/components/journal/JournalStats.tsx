'use client';

import { useMemo } from 'react';
import { TradingSignal, getPnl } from '@/types/trading';
import { cn } from '@/lib/utils';
import {
  TrendingUp,
  TrendingDown,
  Target,
  BarChart2,
  Activity,
  DollarSign,
} from 'lucide-react';

interface JournalStatsProps {
  signals: TradingSignal[];
}

interface StatCell {
  label: string;
  value: string;
  sub?: string;
  color?: string;
  icon: React.ReactNode;
}

export function JournalStats({ signals }: JournalStatsProps) {
  const stats = useMemo(() => {
    const closed = signals.filter((s) => {
      const st = (s.status || '').toLowerCase();
      return (st === 'closed' || st === 'executed') && getPnl(s) != null;
    });

    const totalPnl = closed.reduce((sum, s) => sum + (getPnl(s) ?? 0), 0);

    let wins = 0;
    let losses = 0;
    let totalWin = 0;
    let totalLoss = 0;
    let rrSum = 0;
    let rrCount = 0;

    for (const s of closed) {
      const pnl = getPnl(s) ?? 0;
      if (pnl > 0) { wins++; totalWin += pnl; }
      else if (pnl < 0) { losses++; totalLoss += Math.abs(pnl); }
      if (s.rr_ratio != null && s.rr_ratio > 0) {
        rrSum += s.rr_ratio;
        rrCount++;
      }
    }

    const winRate = closed.length > 0 ? (wins / closed.length) * 100 : null;
    const profitFactor = totalLoss > 0 ? totalWin / totalLoss : totalWin > 0 ? Infinity : null;
    const avgRR = rrCount > 0 ? rrSum / rrCount : null;
    const avgWin = wins > 0 ? totalWin / wins : null;
    const avgLoss = losses > 0 ? totalLoss / losses : null;
    const expectancy = closed.length > 0
      ? ((winRate ?? 0) / 100) * (avgWin ?? 0) - ((1 - (winRate ?? 0) / 100)) * (avgLoss ?? 0)
      : null;

    return {
      totalPnl,
      winRate,
      profitFactor,
      avgRR,
      expectancy,
      closedCount: closed.length,
      totalCount: signals.length,
    };
  }, [signals]);

  const pnlPositive = stats.totalPnl >= 0;
  const wrGood = stats.winRate != null && stats.winRate >= 50;

  const cells: StatCell[] = [
    {
      label: 'Total PnL',
      value: stats.closedCount === 0
        ? '--'
        : `${pnlPositive ? '+' : ''}$${Math.abs(stats.totalPnl).toFixed(2)}`,
      color: stats.closedCount === 0 ? undefined : pnlPositive ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]',
      icon: <DollarSign className='w-3.5 h-3.5' />,
    },
    {
      label: 'Win Rate',
      value: stats.winRate != null ? `${stats.winRate.toFixed(1)}%` : '--',
      color: stats.winRate == null ? undefined : wrGood ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]',
      icon: <Target className='w-3.5 h-3.5' />,
    },
    {
      label: 'Profit Factor',
      value: stats.profitFactor == null
        ? '--'
        : stats.profitFactor === Infinity
        ? '∞'
        : stats.profitFactor.toFixed(2),
      color: stats.profitFactor == null
        ? undefined
        : stats.profitFactor >= 1.5
        ? 'text-[var(--to-long)]'
        : stats.profitFactor >= 1
        ? 'text-amber-400'
        : 'text-[var(--to-short)]',
      icon: <BarChart2 className='w-3.5 h-3.5' />,
    },
    {
      label: 'Avg R:R',
      value: stats.avgRR != null ? `1:${stats.avgRR.toFixed(2)}` : '--',
      color: stats.avgRR != null ? (stats.avgRR >= 1.5 ? 'text-[var(--to-long)]' : 'text-amber-400') : undefined,
      icon: <Activity className='w-3.5 h-3.5' />,
    },
    {
      label: 'Expectancy',
      value: stats.expectancy != null
        ? `${stats.expectancy >= 0 ? '+' : ''}$${stats.expectancy.toFixed(2)}`
        : '--',
      sub: 'per trade',
      color: stats.expectancy == null ? undefined : stats.expectancy >= 0 ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]',
      icon: stats.expectancy != null && stats.expectancy >= 0
        ? <TrendingUp className='w-3.5 h-3.5' />
        : <TrendingDown className='w-3.5 h-3.5' />,
    },
    {
      label: 'Closed',
      value: `${stats.closedCount}`,
      sub: `of ${stats.totalCount} total`,
      color: 'text-[var(--to-text-secondary)]',
      icon: <Target className='w-3.5 h-3.5' />,
    },
  ];

  if (stats.totalCount === 0) return null;

  return (
    <div className='grid grid-cols-3 sm:grid-cols-6 gap-px bg-[#2a2e39] rounded-xl overflow-hidden border border-[#2a2e39]'>
      {cells.map((cell) => (
        <div
          key={cell.label}
          className='flex flex-col gap-1 px-3 py-3 bg-[#0d1117]'
        >
          <div className='flex items-center gap-1.5 text-[var(--to-text-dim)]'>
            <span className='opacity-60'>{cell.icon}</span>
            <span className='font-mono text-[9px] uppercase tracking-wider'>{cell.label}</span>
          </div>
          <span
            className={cn(
              'font-mono text-[15px] font-semibold leading-tight',
              cell.color ?? 'text-[var(--to-text-primary)]',
            )}
          >
            {cell.value}
          </span>
          {cell.sub && (
            <span className='font-mono text-[9px] text-[var(--to-text-dim)]'>{cell.sub}</span>
          )}
        </div>
      ))}
    </div>
  );
}
