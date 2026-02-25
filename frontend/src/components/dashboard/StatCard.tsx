'use client';

import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';

type Trend = 'up' | 'down' | 'neutral';
type Variant = 'default' | 'profit' | 'loss' | 'warning';

interface StatCardProps {
  label: string;
  value: string;
  icon?: LucideIcon;
  trend?: Trend;
  subValue?: string;
  variant?: Variant;
  className?: string;
}

const VARIANT_STYLES: Record<Variant, string> = {
  default: 'text-[var(--to-text-primary)]',
  profit: 'text-[var(--to-long)]',
  loss: 'text-[var(--to-short)]',
  warning: 'text-[var(--to-warning)]',
};

const TREND_CONFIG: Record<Trend, { icon: typeof TrendingUp; color: string }> = {
  up: { icon: TrendingUp, color: 'text-[var(--to-long)]' },
  down: { icon: TrendingDown, color: 'text-[var(--to-short)]' },
  neutral: { icon: Minus, color: 'text-[var(--to-text-dim)]' },
};

function detectVariant(value: string): Variant {
  const cleaned = value.replace(/[,$%\s]/g, '');
  const num = parseFloat(cleaned);
  if (isNaN(num) || num === 0) return 'default';
  if (value.includes('%') && Math.abs(num) > 5) return num > 0 ? 'profit' : 'loss';
  if (value.startsWith('+') || value.startsWith('-')) return num > 0 ? 'profit' : 'loss';
  return 'default';
}

export function StatCard({
  label,
  value,
  icon: Icon,
  trend,
  subValue,
  variant,
  className,
}: StatCardProps) {
  const resolvedVariant = variant ?? detectVariant(value);
  const TrendIcon = trend ? TREND_CONFIG[trend].icon : null;

  return (
    <div
      className={cn(
        'relative overflow-hidden rounded border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2.5',
        'transition-colors duration-150 hover:border-[var(--to-border)]/80',
        className,
      )}
    >
      <div className='flex items-center justify-between'>
        <p
          className='text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          {label}
        </p>
        {Icon && <Icon className='h-3.5 w-3.5 text-[var(--to-text-dim)]' />}
      </div>

      <div className='mt-1.5 flex items-baseline gap-1.5'>
        <p
          className={cn(
            'text-base font-bold tabular-nums leading-none',
            VARIANT_STYLES[resolvedVariant],
          )}
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {value}
        </p>
        {TrendIcon && (
          <TrendIcon className={cn('h-3.5 w-3.5', TREND_CONFIG[trend!].color)} />
        )}
      </div>

      {subValue && (
        <p
          className='mt-1 text-[10px] tabular-nums text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {subValue}
        </p>
      )}
    </div>
  );
}
