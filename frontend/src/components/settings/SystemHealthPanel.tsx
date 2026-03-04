'use client';

import {
  useSystemHealth,
  useDeadLetters,
  useRetryDeadLetter,
  useDiscardDeadLetter,
  useClearDeadLetters,
} from '@/hooks/useSystemHealth';
import { Activity, Inbox, RefreshCw, Trash2, X } from 'lucide-react';
import { cn } from '@/lib/utils';

export function SystemHealthPanel() {
  const { data: health } = useSystemHealth();
  const { data: dlData } = useDeadLetters();
  const retryMutation = useRetryDeadLetter();
  const discardMutation = useDiscardDeadLetter();
  const clearMutation = useClearDeadLetters();

  return (
    <div className='space-y-4'>
      {/* System Health Card */}
      <div className='to-panel'>
        <div className='to-panel-header'>
          <div className='flex items-center gap-2'>
            <Activity className='w-4 h-4 text-text-dim' />
            <span className='font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted'>
              System Health
            </span>
          </div>
        </div>
        <div className='divide-y divide-panel-border-subtle'>
          <div className='px-4 py-2.5 flex items-center justify-between'>
            <span className='text-[11px] text-text-muted uppercase tracking-wider font-mono'>
              Dead Letters
            </span>
            <span
              className={cn(
                'font-mono text-xs font-semibold',
                (health?.dead_letter_count ?? 0) > 0
                  ? 'text-[var(--to-short)]'
                  : 'text-[var(--to-long)]',
              )}
            >
              {health?.dead_letter_count ?? '...'}
            </span>
          </div>
          <div className='px-4 py-2.5 flex items-center justify-between'>
            <span className='text-[11px] text-text-muted uppercase tracking-wider font-mono'>
              Queue Depth
            </span>
            <span className='font-mono text-xs text-text-secondary'>
              {health?.queue_depth ?? '...'}
            </span>
          </div>
          <div className='px-4 py-2.5 flex items-center justify-between'>
            <span className='text-[11px] text-text-muted uppercase tracking-wider font-mono'>
              Redis
            </span>
            <span
              className={cn(
                'font-mono text-xs font-semibold',
                health?.redis_connected
                  ? 'text-[var(--to-long)]'
                  : 'text-[var(--to-short)]',
              )}
            >
              {health?.redis_connected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
      </div>

      {/* Dead Letter Inspector */}
      {(dlData?.count ?? 0) > 0 && (
        <div className='to-panel'>
          <div className='to-panel-header flex items-center justify-between'>
            <div className='flex items-center gap-2'>
              <Inbox className='w-4 h-4 text-[var(--to-short)]' />
              <span className='font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted'>
                Dead Letter Queue ({dlData?.count})
              </span>
            </div>
            <button
              onClick={() => clearMutation.mutate()}
              disabled={clearMutation.isPending}
              className='flex items-center gap-1 px-2 py-1 rounded text-[10px] font-mono text-text-muted hover:text-text-secondary bg-surface-raised hover:bg-surface-raised/90'
              title='Clear all dead letters'
            >
              <Trash2 className='w-3 h-3' />
              Clear All
            </button>
          </div>
          <div className='divide-y divide-panel-border-subtle max-h-64 overflow-y-auto'>
            {dlData?.items.map((item) => (
              <div
                key={item.id}
                className='px-4 py-2.5 flex items-center justify-between gap-2'
              >
                <div className='flex-1 min-w-0'>
                  <div className='font-mono text-[11px] text-text-secondary truncate'>
                    {((item.payload as Record<string, unknown>)
                      ?.symbol as string) ?? 'Unknown'}{' '}
                    &mdash; {item.error.slice(0, 60)}
                  </div>
                  <div
                    suppressHydrationWarning
                    className='text-[9px] text-text-muted font-mono'
                  >
                    Attempt #{item.attempt} &middot;{' '}
                    {new Date(item.failed_at * 1000).toLocaleTimeString()}
                  </div>
                </div>
                <div className='flex items-center gap-1 shrink-0'>
                  <button
                    onClick={() => retryMutation.mutate(item.id)}
                    disabled={retryMutation.isPending}
                    className='flex items-center gap-1 px-2 py-1 rounded text-[10px] font-mono text-text-secondary bg-surface-raised hover:bg-surface-raised/90'
                    title='Re-queue for processing'
                  >
                    <RefreshCw className='w-3 h-3' />
                    Retry
                  </button>
                  <button
                    onClick={() => discardMutation.mutate(item.id)}
                    disabled={discardMutation.isPending}
                    className='flex items-center gap-1 px-2 py-1 rounded text-[10px] font-mono text-text-muted hover:text-text-secondary bg-surface-raised hover:bg-surface-raised/90'
                    title='Discard permanently'
                  >
                    <X className='w-3 h-3' />
                    Discard
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
