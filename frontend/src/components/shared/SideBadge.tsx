'use client';

import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface SideBadgeProps {
  side: 'buy' | 'sell';
  compact?: boolean;
}

/**
 * Unified SideBadge - replaces duplicate implementations.
 */
export function SideBadge({ side, compact = false }: SideBadgeProps) {
  const isBuy = side === 'buy';
  return (
    <Badge
      className={cn(
        'font-mono font-bold border-0 gap-0.5',
        compact ? 'text-[10px] px-1.5 py-0.5' : 'text-xs px-2.5 py-1 gap-1',
        isBuy
          ? 'bg-[var(--to-long)]/15 text-[var(--to-long)]'
          : 'bg-[var(--to-short)]/15 text-[var(--to-short)]',
      )}
    >
      {isBuy ? (
        <TrendingUp className='w-3 h-3' />
      ) : (
        <TrendingDown className='w-3 h-3' />
      )}
      {!compact && side.toUpperCase()}
    </Badge>
  );
}
