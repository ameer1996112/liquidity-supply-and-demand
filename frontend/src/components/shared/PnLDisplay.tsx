'use client';

import { cn } from '@/lib/utils';
import { safeFloat } from '@/lib/format';

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
  if (pnl === null || pnl === undefined) {
    return (
      <span
        className={cn('font-mono font-bold text-zinc-600', SIZE_CLASSES[size])}
      >
        --
      </span>
    );
  }

  const isPositive = pnl >= 0;
  return (
    <span
      className={cn(
        'font-mono font-bold tabular-nums',
        SIZE_CLASSES[size],
        isPositive ? 'text-emerald-400' : 'text-rose-400',
      )}
    >
      {isPositive ? '+' : ''}
      {safeFloat(pnl, 2)}
    </span>
  );
}
