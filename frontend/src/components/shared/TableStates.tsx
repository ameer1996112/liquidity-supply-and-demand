'use client';

import { type ReactNode } from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { Activity } from 'lucide-react';

interface TableSkeletonProps {
  rowCount?: number;
  columnCount?: number;
  className?: string;
}

export function TableSkeleton({
  rowCount = 6,
  columnCount = 4,
  className,
}: TableSkeletonProps) {
  const rows = Array.from({ length: rowCount });
  const cols = Array.from({ length: columnCount });

  return (
    <div className={cn('space-y-1.5', className)}>
      {rows.map((_, rowIndex) => (
        <div
          key={rowIndex}
          className='flex items-center gap-2 rounded border border-panel-border-subtle bg-surface-raised/40 px-3 py-2'
        >
          {cols.map((__, colIndex) => (
            <Skeleton
               
              key={colIndex}
              className={cn(
                'h-3 rounded bg-surface-raised/80',
                colIndex === 0 && 'w-16',
                colIndex === columnCount - 1 && 'w-14',
                colIndex > 0 && colIndex < columnCount - 1 && 'flex-1',
              )}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

interface TableEmptyStateProps {
  title?: string;
  description?: string;
  icon?: ReactNode;
}

export function TableEmptyState({
  title = 'No records',
  description,
  icon,
}: TableEmptyStateProps) {
  return (
    <div className='empty-state py-12'>
      <div className='mb-3 text-slate-500'>
        {icon ?? <Activity className='h-5 w-5' />}
      </div>
      <span className='text-sm font-medium text-slate-200'>
        {title}
      </span>
      {description ? (
        <span
          className='mt-1 text-[11px] text-slate-500'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {description}
        </span>
      ) : null}
    </div>
  );
}

