'use client';

import { Skeleton } from '@/components/ui/skeleton';
import { AlertTriangle, Inbox, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';

interface AsyncSectionProps {
  /** Is data currently loading? */
  isLoading: boolean;
  /** Error object or message string */
  error?: Error | string | null;
  /** Is the data empty (after loading)? */
  isEmpty?: boolean;
  /** Content to render when data is ready */
  children: React.ReactNode;
  /** Number of skeleton rows to show while loading */
  skeletonRows?: number;
  /** Custom skeleton component */
  skeleton?: React.ReactNode;
  /** Label for empty state */
  emptyLabel?: string;
  /** Sub-label for empty state */
  emptySubLabel?: string;
  /** Custom empty state component */
  emptyState?: React.ReactNode;
  /** Retry callback shown on error */
  onRetry?: () => void;
  /** Label for the section (shown in error state) */
  label?: string;
  className?: string;
  /** Minimum height to prevent layout shift */
  minHeight?: number;
}

/**
 * Unified async state wrapper.
 * Handles loading → error → empty → content transitions consistently
 * across all dashboard panels.
 *
 * Usage:
 * ```tsx
 * <AsyncSection isLoading={isLoading} error={error} isEmpty={data.length === 0}>
 *   <MyTable data={data} />
 * </AsyncSection>
 * ```
 */
export function AsyncSection({
  isLoading,
  error,
  isEmpty = false,
  children,
  skeletonRows = 4,
  skeleton,
  emptyLabel = 'No data yet',
  emptySubLabel,
  emptyState,
  onRetry,
  label,
  className,
  minHeight,
}: AsyncSectionProps) {
  const style = minHeight ? { minHeight } : undefined;

  // ── Loading state ──────────────────────────────────────────────────────────
  if (isLoading) {
    if (skeleton) {
      return (
        <div className={className} style={style}>
          {skeleton}
        </div>
      );
    }
    return (
      <div className={cn('space-y-2 p-2', className)} style={style}>
        {Array.from({ length: skeletonRows }).map((_, i) => (
          <Skeleton
            key={i}
            className='h-8 w-full rounded-lg bg-[var(--to-surface-raised)]'
            style={{ opacity: 1 - i * 0.15 }}
          />
        ))}
      </div>
    );
  }

  // ── Error state ────────────────────────────────────────────────────────────
  if (error) {
    const message =
      typeof error === 'string'
        ? error
        : (error as Error).message || 'An unexpected error occurred';

    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center gap-3 rounded-xl p-6 text-center',
          className
        )}
        style={style}
      >
        <div className='flex h-10 w-10 items-center justify-center rounded-full bg-[var(--to-short)]/10 ring-1 ring-[var(--to-short)]/20'>
          <AlertTriangle className='h-5 w-5 text-[var(--to-short)]' />
        </div>
        <div className='space-y-0.5'>
          <p className='text-xs font-semibold text-[var(--to-text-primary)]'>
            {label ? `Failed to load ${label}` : 'Failed to load data'}
          </p>
          {process.env.NODE_ENV === 'development' && (
            <p className='max-w-xs font-mono text-[10px] text-[var(--to-text-dim)]'>
              {message}
            </p>
          )}
        </div>
        {onRetry && (
          <button
            onClick={onRetry}
            className='flex items-center gap-1.5 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-1.5 text-[11px] font-medium text-[var(--to-text-secondary)] transition-colors hover:text-[var(--to-text-primary)]'
          >
            <RefreshCw className='h-3 w-3' />
            Retry
          </button>
        )}
      </div>
    );
  }

  // ── Empty state ────────────────────────────────────────────────────────────
  if (isEmpty) {
    if (emptyState) {
      return (
        <div className={className} style={style}>
          {emptyState}
        </div>
      );
    }
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center gap-2 rounded-xl p-6 text-center',
          className
        )}
        style={style}
      >
        <div className='flex h-10 w-10 items-center justify-center rounded-full bg-[var(--to-surface-raised)] ring-1 ring-[var(--to-border)]'>
          <Inbox className='h-5 w-5 text-[var(--to-text-dim)]' />
        </div>
        <div className='space-y-0.5'>
          <p className='text-xs font-medium text-[var(--to-text-secondary)]'>
            {emptyLabel}
          </p>
          {emptySubLabel && (
            <p className='text-[10px] text-[var(--to-text-dim)]'>
              {emptySubLabel}
            </p>
          )}
        </div>
      </div>
    );
  }

  // ── Content ────────────────────────────────────────────────────────────────
  return (
    <div className={className} style={style}>
      {children}
    </div>
  );
}
