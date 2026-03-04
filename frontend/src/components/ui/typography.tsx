/**
 * Typography primitives — enforces JetBrains Mono for all numeric/data output
 * and provides a consistent panel-label pattern across the design system.
 *
 * Usage:
 *   <Mono size="lg" className="text-long">+$1,240.00</Mono>
 *   <PnLText value={123.45} />
 *   <Number value={12345.678} />
 *   <PanelLabel>Signal Book</PanelLabel>
 *   <KpiMeta>Session KPIs</KpiMeta>
 *   <DataField label="Entry" value="1.08543" />
 */

import { cn } from '@/lib/utils';
import { HTMLAttributes } from 'react';
import {
  EMPTY_VALUE,
  formatCurrency,
  formatNumber,
  formatPercent,
  normalizeNegativeZero,
} from '@/lib/formatters';

// ── Size scale ────────────────────────────────────────────────────────────────

type MonoSize = '2xs' | 'xs' | 'sm' | 'base' | 'lg' | 'xl' | '2xl';

const MONO_SIZE: Record<MonoSize, string> = {
  '2xs': 'text-[9px]',
  xs: 'text-[10px]',
  sm: 'text-[11px]',
  base: 'text-xs',
  lg: 'text-sm',
  xl: 'text-base',
  '2xl': 'text-lg',
};

// ── Mono — tabular-nums span using JetBrains Mono ─────────────────────────────

interface MonoProps extends HTMLAttributes<HTMLSpanElement> {
  size?: MonoSize;
  bold?: boolean;
}

/**
 * Renders any numeric or code value in JetBrains Mono with tabular-nums.
 * Replaces every `style={{ fontFamily: 'var(--font-mono)' }}` inline style.
 */
export function Mono({ size = 'base', bold = false, className, children, ...props }: MonoProps) {
  return (
    <span
      className={cn(
        'font-mono tabular-nums',
        MONO_SIZE[size],
        bold && 'font-bold',
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}

// ── PanelLabel — uppercase section header ─────────────────────────────────────

interface PanelLabelProps extends HTMLAttributes<HTMLSpanElement> {}

/**
 * Renders a panel section label — uppercase, tracked, muted.
 * Replaces every `<span className="panel-label">` with inline font hacks.
 */
export function PanelLabel({ className, children, ...props }: PanelLabelProps) {
  return (
    <span className={cn('panel-label', className)} {...props}>
      {children}
    </span>
  );
}

// ── DataField — compact label + value pair ────────────────────────────────────

interface DataFieldProps {
  label: string;
  value: React.ReactNode;
  className?: string;
  valueClassName?: string;
}

/**
 * A tight vertical label/value pair — standard pattern for trade detail rows.
 */
export function DataField({ label, value, className, valueClassName }: DataFieldProps) {
  return (
    <div className={cn('flex flex-col', className)}>
      <span className='kpi-meta'>{label}</span>
      <span className={cn('font-mono text-[11px] tabular-nums text-text-secondary', valueClassName)}>
        {value}
      </span>
    </div>
  );
}

// ── KpiMeta — uppercase micro-label ──────────────────────────────────────────

interface KpiMetaProps extends HTMLAttributes<HTMLSpanElement> {}

/**
 * Renders a KPI sub-label — uppercase, tracked, dim. Replaces every
 * `<p className="kpi-meta">` / `<span className="kpi-meta">` in page code.
 */
export function KpiMeta({ className, children, ...props }: KpiMetaProps) {
  return (
    <span className={cn('kpi-meta', className)} {...props}>
      {children}
    </span>
  );
}

// ── PnLText — semantic profit/loss number with sign & color ────────────────────

type PnLVariant = 'raw' | 'currency' | 'percent';

interface PnLTextProps extends Omit<HTMLAttributes<HTMLSpanElement>, 'children'> {
  value: number | null | undefined;
  variant?: PnLVariant;
  decimals?: number;
  size?: MonoSize;
  /**
   * When true, adds a "+" prefix for positive values.
   * For currency/percent variants this is handled by the formatter.
   */
  signed?: boolean;
  empty?: string;
}

/**
 * Design-system PnL atom:
 * - JetBrains Mono with tabular-nums
 * - Color-coded via semantic tokens (text-profit / text-loss)
 * - Stable sign handling with tiny values normalized to zero
 */
export function PnLText({
  value,
  variant = 'raw',
  decimals = 2,
  size = 'base',
  signed = true,
  empty = EMPTY_VALUE,
  className,
  ...props
}: PnLTextProps) {
  const normalized = normalizeNegativeZero(value);

  if (normalized == null) {
    return (
      <Mono
        size={size}
        bold
        className={cn('text-text-secondary/70', className)}
        {...props}
      >
        {empty}
      </Mono>
    );
  }

  const isPositive = normalized > 0;
  const isNegative = normalized < 0;

  const baseClasses = cn(
    'tabular-nums',
    isPositive ? 'text-profit' : isNegative ? 'text-loss' : 'text-text-secondary',
    className,
  );

  let formatted: string;
  switch (variant) {
    case 'currency':
      formatted = formatCurrency(normalized, {
        decimals,
        signed,
        empty,
      });
      break;
    case 'percent':
      formatted = formatPercent(normalized, {
        decimals,
        signed,
        empty,
      });
      break;
    case 'raw':
    default: {
      const prefix =
        signed && (isPositive || isNegative)
          ? isPositive
            ? '+'
            : '-'
          : '';
      formatted = `${prefix}${Math.abs(normalized).toFixed(decimals)}`;
      break;
    }
  }

  return (
    <Mono size={size} bold className={baseClasses} {...props}>
      {formatted}
    </Mono>
  );
}

// ── Number — locale-aware numeric output using JetBrains Mono ──────────────────

interface NumberProps extends Omit<HTMLAttributes<HTMLSpanElement>, 'children'> {
  value: number | null | undefined;
  decimals?: number;
  locale?: string;
  empty?: string;
  size?: MonoSize;
  bold?: boolean;
}

/**
 * Locale-aware numeric formatter that:
 * - Normalizes tiny values to zero (no "-0.00")
 * - Uses JetBrains Mono + tabular-nums
 * - Respects the user’s locale by default
 */
function NumberComponent({
  value,
  decimals = 2,
  locale,
  empty = EMPTY_VALUE,
  size = 'base',
  bold = false,
  className,
  ...props
}: NumberProps) {
  const normalized = normalizeNegativeZero(value);

  if (normalized == null) {
    return (
      <Mono
        size={size}
        bold={bold}
        className={cn('text-text-secondary/70', className)}
        {...props}
      >
        {empty}
      </Mono>
    );
  }

  const formatter = new Intl.NumberFormat(locale ?? undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  const formatted = formatter.format(normalized);

  return (
    <Mono
      size={size}
      bold={bold}
      className={cn('tabular-nums text-text-secondary', className)}
      {...props}
    >
      {formatted}
    </Mono>
  );
}

// Avoid shadowing the global Number constructor while still exporting <Number />
export { NumberComponent as Number };
