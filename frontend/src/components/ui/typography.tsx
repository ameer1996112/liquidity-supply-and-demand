/**
 * Typography primitives — enforces JetBrains Mono for all numeric/data output
 * and provides a consistent panel-label pattern across the design system.
 *
 * Usage:
 *   <Mono size="lg" className="text-[var(--to-long)]">+$1,240.00</Mono>
 *   <PanelLabel>Signal Book</PanelLabel>
 *   <DataField label="Entry" value="1.08543" />
 */

import { cn } from '@/lib/utils';
import { HTMLAttributes } from 'react';

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
      <span className={cn('font-mono text-[11px] tabular-nums text-[var(--to-text-secondary)]', valueClassName)}>
        {value}
      </span>
    </div>
  );
}
