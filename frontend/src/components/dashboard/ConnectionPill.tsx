'use client';

import { useConnectionHealth } from '@/hooks/useConnectionHealth';
import { useTradingMode } from '@/providers/TradingModeProvider';
import { cn } from '@/lib/utils';

interface ConnectionPillProps {
  className?: string;
}

export function ConnectionPill({ className }: ConnectionPillProps) {
  const { isConnected } = useConnectionHealth();
  const { mode } = useTradingMode();

  if (!isConnected) {
    return (
      <div
        className={cn(
          'flex items-center gap-1.5 rounded-full border px-2.5 py-0.5',
          'border-[var(--to-short)]/25 bg-[var(--to-short)]/10',
          'text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--to-short)]',
          className
        )}
      >
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--to-short)]" />
        RECONNECTING
      </div>
    );
  }

  const isLive = mode === 'LIVE';

  return (
    <div
      className={cn(
        'flex items-center gap-1.5 rounded-full border px-2.5 py-0.5',
        isLive
          ? 'border-[var(--to-long)]/25 bg-[var(--to-long)]/10 text-[var(--to-long)]'
          : 'border-[var(--to-warning)]/25 bg-[var(--to-warning)]/10 text-[var(--to-warning)]',
        'text-[10px] font-bold uppercase tracking-[0.1em]',
        className
      )}
    >
      <span
        className={cn(
          'h-1.5 w-1.5 rounded-full',
          isLive ? 'bg-[var(--to-long)]' : 'bg-[var(--to-warning)]'
        )}
      />
      {isLive ? 'LIVE' : 'PAPER'}
    </div>
  );
}
