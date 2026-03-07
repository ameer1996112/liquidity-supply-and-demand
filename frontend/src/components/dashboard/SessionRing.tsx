'use client';

import { cn } from '@/lib/utils';
import { TrendingUp } from 'lucide-react';

interface SessionRingProps {
  todayPnl: number | null | undefined;
  dailyTarget?: number; // e.g. 200 USD
  className?: string;
}

/**
 * Circular SVG ring showing today's P&L progress toward a daily target.
 * If no target is set, shows a simple profit/loss indicator.
 */
export function SessionRing({
  todayPnl,
  dailyTarget = 200,
  className,
}: SessionRingProps) {
  const pnl = todayPnl ?? 0;
  const radius = 22;
  const strokeWidth = 4;
  const circumference = 2 * Math.PI * radius;

  // Progress: clamp between -100% and 100%
  const rawPct = dailyTarget > 0 ? pnl / dailyTarget : 0;
  const pct = Math.min(Math.abs(rawPct), 1);
  const fillLength = pct * circumference;

  const isPositive = pnl >= 0;
  const color = isPositive ? '#0ecb81' : '#f6465d';
  const bgColor = isPositive ? 'rgba(14,203,129,0.08)' : 'rgba(246,70,93,0.08)';
  const borderColor = isPositive
    ? 'rgba(14,203,129,0.2)'
    : 'rgba(246,70,93,0.2)';

  return (
    <div
      className={cn(
        'flex items-center gap-2.5 rounded-xl border px-3 py-2',
        className
      )}
      style={{ backgroundColor: bgColor, borderColor }}
    >
      {/* Ring */}
      <div className='relative shrink-0' style={{ width: 52, height: 52 }}>
        <svg width={52} height={52} viewBox='0 0 52 52'>
          {/* Track */}
          <circle
            cx='26'
            cy='26'
            r={radius}
            fill='none'
            stroke='rgba(255,255,255,0.06)'
            strokeWidth={strokeWidth}
          />
          {/* Fill */}
          <circle
            cx='26'
            cy='26'
            r={radius}
            fill='none'
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap='round'
            strokeDasharray={`${fillLength} ${circumference - fillLength}`}
            strokeDashoffset={circumference * 0.25}
            style={{
              transition: 'stroke-dasharray 0.8s ease',
              filter: `drop-shadow(0 0 3px ${color}80)`,
            }}
          />
        </svg>
        {/* Center icon */}
        <div className='absolute inset-0 flex items-center justify-center'>
          <TrendingUp
            className='h-4 w-4'
            style={{ color, transform: isPositive ? 'none' : 'scaleY(-1)' }}
          />
        </div>
      </div>

      {/* Labels */}
      <div className='flex flex-col'>
        <span
          className='text-[9px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          Session
        </span>
        <span
          className='text-[15px] font-bold tabular-nums leading-tight'
          style={{ color, fontFamily: 'var(--font-mono)' }}
        >
          {pnl >= 0 ? '+' : ''}
          {pnl.toFixed(2)}
        </span>
        <span
          className='text-[9px] tabular-nums'
          style={{
            color: 'var(--to-text-dim)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {(rawPct * 100).toFixed(0)}% of ${dailyTarget} target
        </span>
      </div>
    </div>
  );
}
