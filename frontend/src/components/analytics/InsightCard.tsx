'use client';

import { cn } from '@/lib/utils';
import { TrendingUp, Clock, CalendarDays, Target, Zap } from 'lucide-react';

export interface InsightData {
  label: string;
  value: string;
  subValue?: string;
  winRate: number;
  trades: number;
  pnl: number;
  type: 'symbol' | 'hour' | 'day' | 'model' | 'confidence';
}

const TYPE_CONFIG = {
  symbol: { icon: Target, accent: '#3b82f6', label: 'Best Symbol' },
  hour: { icon: Clock, accent: '#8b5cf6', label: 'Best Hour' },
  day: { icon: CalendarDays, accent: '#f0b90b', label: 'Best Day' },
  model: { icon: Zap, accent: '#0ecb81', label: 'Best Setup' },
  confidence: { icon: TrendingUp, accent: '#f97316', label: 'Best AI Band' },
};

interface InsightCardProps {
  data: InsightData | null;
  type: InsightData['type'];
  className?: string;
}

export function InsightCard({ data, type, className }: InsightCardProps) {
  const config = TYPE_CONFIG[type];
  const Icon = config.icon;
  const accent = config.accent;

  if (!data) {
    return (
      <div className={cn('glow-card flex flex-col gap-3 p-4', className)}>
        <div className='flex items-center gap-2'>
          <div
            className='flex h-7 w-7 items-center justify-center rounded-lg'
            style={{
              background: `${accent}15`,
              border: `1px solid ${accent}25`,
            }}
          >
            <Icon className='h-3.5 w-3.5' style={{ color: accent }} />
          </div>
          <span
            className='text-[10px] font-bold uppercase tracking-[0.15em] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {config.label}
          </span>
        </div>
        <p
          className='text-[11px] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          Not enough data
        </p>
      </div>
    );
  }

  const winRateColor =
    data.winRate >= 60 ? '#0ecb81' : data.winRate >= 50 ? '#f0b90b' : '#f6465d';

  return (
    <div
      className={cn(
        'glow-card relative overflow-hidden flex flex-col gap-3 p-4',
        className
      )}
      style={{ borderColor: `${accent}20` }}
    >
      {/* Subtle background glow */}
      <div
        className='pointer-events-none absolute inset-0 opacity-[0.04]'
        style={{
          background: `radial-gradient(ellipse at 0% 0%, ${accent} 0%, transparent 70%)`,
        }}
      />

      {/* Header */}
      <div className='relative flex items-center justify-between'>
        <div className='flex items-center gap-2'>
          <div
            className='flex h-7 w-7 items-center justify-center rounded-lg'
            style={{
              background: `${accent}15`,
              border: `1px solid ${accent}25`,
            }}
          >
            <Icon className='h-3.5 w-3.5' style={{ color: accent }} />
          </div>
          <span
            className='text-[10px] font-bold uppercase tracking-[0.15em] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {config.label}
          </span>
        </div>
        <span
          className='rounded px-1.5 py-0.5 text-[9px] font-bold'
          style={{
            background: `${winRateColor}15`,
            color: winRateColor,
            border: `1px solid ${winRateColor}25`,
            fontFamily: 'var(--font-mono)',
          }}
        >
          {data.winRate.toFixed(0)}% WR
        </span>
      </div>

      {/* Main value */}
      <div className='relative'>
        <p
          className='text-xl font-black tracking-tight text-[var(--to-text-primary)]'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {data.value}
        </p>
        {data.subValue && (
          <p
            className='mt-0.5 text-[10px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            {data.subValue}
          </p>
        )}
      </div>

      {/* Stats row */}
      <div className='relative flex items-center gap-3 border-t border-[var(--to-border)] pt-2.5'>
        <div className='flex flex-col'>
          <span
            className='text-[9px] uppercase tracking-[0.12em] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            Trades
          </span>
          <span
            className='text-xs font-bold tabular-nums text-[var(--to-text-secondary)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {data.trades}
          </span>
        </div>
        <div className='h-6 w-px bg-[var(--to-border)]' />
        <div className='flex flex-col'>
          <span
            className='text-[9px] uppercase tracking-[0.12em] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            Total PnL
          </span>
          <span
            className='text-xs font-bold tabular-nums'
            style={{
              color: data.pnl >= 0 ? '#0ecb81' : '#f6465d',
              fontFamily: 'var(--font-mono)',
            }}
          >
            {data.pnl >= 0 ? '+' : ''}${data.pnl.toFixed(2)}
          </span>
        </div>

        {/* Win rate bar */}
        <div className='ml-auto flex flex-col items-end gap-1'>
          <div className='h-1.5 w-20 overflow-hidden rounded-full bg-[#1e2329]'>
            <div
              className='h-full rounded-full transition-all duration-700'
              style={{
                width: `${Math.min(data.winRate, 100)}%`,
                backgroundColor: winRateColor,
                boxShadow: `0 0 6px ${winRateColor}60`,
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
