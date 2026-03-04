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
        // Success semantics for active/live status
        'bg-[var(--to-long)]/15 text-[var(--to-long)] border-[var(--to-long)]/40',
        !compact && 'shadow-[0_0_12px_rgba(59,130,246,0.3)] animate-pulse',
      ),
  },
  closed: {
    icon: () => <CheckCircle2 className='w-3 h-3' />,
    label: 'CLOSED',
    // Neutral semantics for closed trades regardless of PnL
    className: () =>
      'bg-[var(--to-surface-raised)] text-[var(--to-text-secondary)] border-[var(--to-border-subtle)]',
  },
  executed: {
    icon: () => <CheckCircle2 className='w-3 h-3' />,
    label: 'FILLED',
    // Treat filled orders as success/open
    className: () =>
      'bg-[var(--to-long)]/15 text-[var(--to-long)] border-[var(--to-long)]/40',
  },
  ai_rejected: {
    icon: () => <ShieldX className='w-3 h-3' />,
    label: 'VETO',
    className: () =>
      'bg-[var(--to-short)]/15 text-[var(--to-short)] border-[var(--to-short)]/40 shadow-[0_0_8px_rgba(244,63,94,0.2)]',
  },
  filtered: {
    icon: () => <Filter className='w-3 h-3' />,
    label: 'FILTER',
    className: () =>
      'bg-[var(--to-surface-raised)] text-[var(--to-text-dim)] border-[var(--to-border-subtle)]',
  },
  symbol_blacklisted: {
    icon: () => <ShieldX className='w-3 h-3' />,
    label: 'BLACKLIST',
    className: () =>
      'bg-[var(--to-short)]/15 text-[var(--to-short)] border-[var(--to-short)]/40',
  },
  received: {
    icon: () => <Clock className='w-3 h-3' />,
    label: 'RECEIVED',
    className: () =>
      'bg-[var(--to-warning)]/15 text-[var(--to-warning)] border-[var(--to-warning)]/40',
  },
  failed: {
    icon: () => <XCircle className='w-3 h-3' />,
    label: 'FAILED',
    className: () =>
      'bg-[var(--to-short)]/15 text-[var(--to-short)] border-[var(--to-short)]/40',
  },
  pending: {
    icon: () => <Clock className='w-3 h-3' />,
    label: 'PENDING',
    className: () =>
      'bg-[var(--to-warning)]/15 text-[var(--to-warning)] border-[var(--to-warning)]/40',
  },
};

const DEFAULT_CONFIG = {
  icon: () => <Clock className='w-3 h-3' />,
  label: 'UNKNOWN',
  className: () =>
    'bg-[var(--to-surface-raised)] text-[var(--to-text-dim)] border-[var(--to-border-subtle)]',
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
