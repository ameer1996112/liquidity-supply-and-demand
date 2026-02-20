'use client';

import { cn } from '@/lib/utils';
import {
  EMPTY_VALUE,
  formatNumber,
  normalizeNegativeZero,
} from '@/lib/formatters';

interface PnLDisplayProps {
  pnl: number | null;
  size?: 'sm' | 'md' | 'lg';
}

const SIZE_CLASSES = {
  sm: 'text-xs',
  md: 'text-sm',
  lg: 'text-base',
} as const;

/**
 * Unified PnL Display - handles null safely with "--".
 * Used across SignalFeed, SignalCard, and RecentSignalsPanel.
 */
export function PnLDisplay({ pnl, size = 'md' }: PnLDisplayProps) {
  const normalizedPnl = normalizeNegativeZero(pnl);

  if (normalizedPnl === null) {
    return (
      <span
        className={cn('font-mono font-bold text-zinc-600', SIZE_CLASSES[size])}
      >
        {EMPTY_VALUE}
      </span>
    );
  }

  const isPositive = normalizedPnl > 0;
  const isNegative = normalizedPnl < 0;

  return (
    <span
      className={cn(
        'font-mono font-bold tabular-nums',
        SIZE_CLASSES[size],
        isPositive
          ? 'text-emerald-400'
          : isNegative
          ? 'text-rose-400'
          : 'text-slate-300'
      )}
    >
      {isPositive ? '+' : ''}
      {formatNumber(normalizedPnl, { decimals: 2 })}
    </span>
  );
}
