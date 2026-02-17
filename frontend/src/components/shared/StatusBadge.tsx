'use client';

import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import {
  Radio,
  CheckCircle2,
  ShieldX,
  Filter,
  XCircle,
  Clock,
} from 'lucide-react';

interface StatusBadgeProps {
  status: string | undefined;
  pnl?: number | null;
  compact?: boolean;
}

const CONFIGS: Record<
  string,
  {
    icon: (compact: boolean) => React.ReactNode;
    label: string;
    className: (isWin: boolean, isLoss: boolean, compact: boolean) => string;
  }
> = {
  active: {
    icon: (compact) => (
      <Radio className={cn('w-3 h-3', !compact && 'animate-pulse')} />
    ),
    label: 'LIVE',
    className: (_w, _l, compact) =>
      cn(
        'bg-blue-500/20 text-blue-400 border-blue-500/40',
        !compact && 'shadow-[0_0_12px_rgba(59,130,246,0.3)] animate-pulse',
      ),
  },
  closed: {
    icon: () => <CheckCircle2 className='w-3 h-3' />,
    label: 'CLOSED',
    className: (isWin, isLoss) =>
      isWin
        ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
        : isLoss
          ? 'bg-rose-500/20 text-rose-400 border-rose-500/40'
          : 'bg-zinc-500/20 text-zinc-400 border-zinc-500/40',
  },
  executed: {
    icon: () => <CheckCircle2 className='w-3 h-3' />,
    label: 'FILLED',
    className: (isWin, isLoss) =>
      isWin
        ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
        : isLoss
          ? 'bg-rose-500/20 text-rose-400 border-rose-500/40'
          : 'bg-zinc-500/20 text-zinc-400 border-zinc-500/40',
  },
  ai_rejected: {
    icon: () => <ShieldX className='w-3 h-3' />,
    label: 'VETO',
    className: () =>
      'bg-rose-500/20 text-rose-400 border-rose-500/40 shadow-[0_0_8px_rgba(244,63,94,0.2)]',
  },
  filtered: {
    icon: () => <Filter className='w-3 h-3' />,
    label: 'FILTER',
    className: () => 'bg-zinc-500/20 text-zinc-400 border-zinc-500/40',
  },
  failed: {
    icon: () => <XCircle className='w-3 h-3' />,
    label: 'FAILED',
    className: () => 'bg-rose-500/20 text-rose-400 border-rose-500/40',
  },
  pending: {
    icon: () => <Clock className='w-3 h-3' />,
    label: 'PENDING',
    className: () => 'bg-amber-500/20 text-amber-400 border-amber-500/40',
  },
};

const DEFAULT_CONFIG = {
  icon: () => <Clock className='w-3 h-3' />,
  label: 'UNKNOWN',
  className: () => 'bg-zinc-500/20 text-zinc-500 border-zinc-500/40',
};

/**
 * Unified StatusBadge - replaces 4 duplicate implementations.
 *
 * - `active` → LIVE (Blue Pulse)
 * - `ai_rejected` → VETO (Red Shield)
 * - `filtered` → FILTER (Gray)
 * - `closed` → CLOSED (Green/Red based on PnL)
 */
export function StatusBadge({
  status,
  pnl,
  compact = false,
}: StatusBadgeProps) {
  const normalized = status?.toLowerCase() || '';
  const isWin = pnl != null && pnl > 0;
  const isLoss = pnl != null && pnl < 0;

  const config = CONFIGS[normalized] || DEFAULT_CONFIG;
  const label =
    CONFIGS[normalized]?.label || status?.toUpperCase() || 'UNKNOWN';

  return (
    <Badge
      className={cn(
        'font-mono text-[9px] font-semibold uppercase tracking-wider gap-1 border px-1.5 py-0.5',
        config.className(isWin, isLoss, compact),
      )}
    >
      {config.icon(compact)}
      {!compact && label}
    </Badge>
  );
}
