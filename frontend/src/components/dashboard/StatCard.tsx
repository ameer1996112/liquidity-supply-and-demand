'use client';

import { cn } from '@/lib/utils';
import type { LucideIcon } from 'lucide-react';
import { AnimatedNumber, FlashValue } from '@/components/ui/AnimatedNumber';
import { MiniSparkline } from '@/components/ui/MiniSparkline';

type Variant = 'default' | 'profit' | 'loss' | 'warning';

interface StatCardProps {
  label: string;
  value: string;
  icon?: LucideIcon;
  subValue?: string;
  variant?: Variant;
  className?: string;
  /** If provided, animates the number smoothly on change */
  numericValue?: number;
  /** Format function for numericValue */
  numericFormat?: (v: number) => string;
  /** Show a trend indicator arrow */
  trend?: 'up' | 'down' | 'neutral';
  /** Optional sparkline data (array of numbers) shown at the bottom */
  sparklineData?: number[];
  /** Hero variant — larger value text + amber glow border for primary KPI card */
  hero?: boolean;
}

// Detect sign from value string
function detectVariant(value: string): Variant {
  const cleaned = value.replace(/[,$%\s]/g, '');
  const num = parseFloat(cleaned);
  if (isNaN(num) || num === 0) return 'default';
  if (value.includes('%') && Math.abs(num) > 5)
    return num > 0 ? 'profit' : 'loss';
  if (value.startsWith('+') || value.startsWith('-'))
    return num > 0 ? 'profit' : 'loss';
  return 'default';
}

const VARIANT_CONFIG: Record<
  Variant,
  {
    valueClass: string;
    iconBg: string;
    iconColor: string;
    barColor: string;
    glowClass: string;
  }
> = {
  default: {
    valueClass: 'text-[var(--to-text-primary)]',
    iconBg: 'bg-[var(--to-surface-raised)] border border-[var(--to-border)]',
    iconColor: 'text-[var(--to-text-secondary)]',
    barColor: 'bg-[var(--to-border)]',
    glowClass: '',
  },
  profit: {
    valueClass: 'gradient-text-green text-glow-green',
    iconBg: 'bg-[#0ecb81]/10 border border-[#0ecb81]/25',
    iconColor: 'text-[#0ecb81]',
    barColor: 'bg-[#0ecb81]',
    glowClass: 'hover:glow-green',
  },
  loss: {
    valueClass: 'gradient-text-red text-glow-red',
    iconBg: 'bg-[#f6465d]/10 border border-[#f6465d]/25',
    iconColor: 'text-[#f6465d]',
    barColor: 'bg-[#f6465d]',
    glowClass: 'hover:glow-red',
  },
  warning: {
    valueClass: 'gradient-text-amber text-glow-amber',
    iconBg: 'bg-[#f0b90b]/10 border border-[#f0b90b]/25',
    iconColor: 'text-[#f0b90b]',
    barColor: 'bg-[#f0b90b]',
    glowClass: 'hover:glow-amber',
  },
};

export function StatCard({
  label,
  value,
  icon: Icon,
  subValue,
  variant,
  className,
  numericValue,
  numericFormat,
  trend,
  sparklineData,
  hero,
}: StatCardProps) {
  const resolvedVariant = variant ?? detectVariant(value);
  const cfg = VARIANT_CONFIG[resolvedVariant];

  return (
    <div
      className={cn(
        'group relative overflow-hidden rounded-xl',
        hero
          ? [
              'border border-[var(--to-accent-amber)]/40',
              'hover:border-[var(--to-accent-amber)]/70',
              'shadow-[0_0_20px_rgba(240,185,11,0.12)]',
              'px-5 py-4',
            ]
          : [
              'border border-[var(--to-border)]',
              'hover:border-[var(--to-border-glow)]',
              'px-4 py-3.5',
            ],
        'bg-gradient-to-br from-[var(--to-surface)] to-[var(--to-surface-raised)]',
        'transition-all duration-200 ease-out',
        'hover:-translate-y-[1px]',
        'hover:shadow-[0_4px_24px_rgba(0,0,0,0.4)]',
        className
      )}
    >
      {/* Shimmer scan line on hover */}
      <div className='absolute inset-x-0 top-0 h-px overflow-hidden opacity-0 group-hover:opacity-100 transition-opacity duration-300'>
        <div className='h-px w-1/3 bg-gradient-to-r from-transparent via-[rgba(240,185,11,0.6)] to-transparent animate-[shimmer-scan_2s_ease-in-out_infinite]' />
      </div>

      {/* Top row: label + icon chip */}
      <div className='flex items-center justify-between mb-2.5'>
        <p
          className='text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          {label}
        </p>
        <div className='flex items-center gap-1.5'>
          {trend && trend !== 'neutral' && (
            <span
              className={cn(
                'text-[9px] font-bold',
                trend === 'up'
                  ? 'text-[var(--to-long)]'
                  : 'text-[var(--to-short)]'
              )}
            >
              {trend === 'up' ? '▲' : '▼'}
            </span>
          )}
          {Icon && (
            <div
              className={cn(
                'flex h-6 w-6 items-center justify-center rounded-md',
                cfg.iconBg
              )}
            >
              <Icon className={cn('h-3.5 w-3.5', cfg.iconColor)} />
            </div>
          )}
        </div>
      </div>

      {/* Value — animated if numericValue provided */}
      <p
        className={cn(
          hero ? 'text-[2rem]' : 'text-[1.15rem]',
          'font-bold tabular-nums leading-none',
          cfg.valueClass
        )}
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        {numericValue !== undefined ? (
          <FlashValue value={numericValue}>
            <AnimatedNumber
              value={numericValue}
              format={numericFormat}
              duration={500}
            />
          </FlashValue>
        ) : (
          value
        )}
      </p>

      {/* Sub-value */}
      {subValue && (
        <p
          className='mt-1.5 text-[10px] tabular-nums text-[var(--to-text-dim)] truncate'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {subValue}
        </p>
      )}

      {/* Sparkline */}
      {sparklineData && sparklineData.length >= 2 && (
        <div className='mt-2 opacity-70 group-hover:opacity-100 transition-opacity'>
          <MiniSparkline
            data={sparklineData}
            width={120}
            height={22}
            strokeWidth={1.5}
            fill
          />
        </div>
      )}

      {/* Bottom accent bar */}
      <div
        className={cn(
          'absolute bottom-0 inset-x-0 h-[2px] opacity-0 group-hover:opacity-100 transition-opacity duration-300',
          cfg.barColor
        )}
      />

      {/* Subtle gradient overlay on bg */}
      <div className='pointer-events-none absolute inset-0 rounded-xl bg-gradient-to-br from-white/[0.015] via-transparent to-transparent' />
    </div>
  );
}
