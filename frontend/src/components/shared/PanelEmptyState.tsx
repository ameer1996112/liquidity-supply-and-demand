'use client';

import { ReactNode } from 'react';

interface PanelEmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
}

export function PanelEmptyState({
  icon,
  title,
  description,
}: PanelEmptyStateProps) {
  return (
    <div className='empty-state py-10'>
      {icon ? <div className='mb-2 text-[var(--to-text-dim)] animate-bounce'>{icon}</div> : null}
      <span className='text-sm font-medium text-slate-300'>{title}</span>
      {description ? (
        <span
          className='mt-1 text-[11px] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {description}
        </span>
      ) : null}
    </div>
  );
}
