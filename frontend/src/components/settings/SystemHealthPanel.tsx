'use client';

import {
  useSystemHealth,
  useDeadLetters,
  useRetryDeadLetter,
} from '@/hooks/useSystemHealth';
import { Activity, Inbox, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';

export function SystemHealthPanel() {
  const { data: health } = useSystemHealth();
  const { data: dlData } = useDeadLetters();
  const retryMutation = useRetryDeadLetter();

  return (
    <div className="space-y-4">
      {/* System Health Card */}
      <div className="tv-card">
        <div className="px-4 py-3 border-b border-[#2a2e39]">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-zinc-500" />
            <span className="font-mono text-xs text-zinc-400 uppercase tracking-wider">
              System Health
            </span>
          </div>
        </div>
        <div className="divide-y divide-[#2a2e39]">
          <div className="px-4 py-2.5 flex items-center justify-between">
            <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-mono">
              Dead Letters
            </span>
            <span
              className={cn(
                'font-mono text-xs font-semibold',
                (health?.dead_letter_count ?? 0) > 0
                  ? 'text-[#ef5350]'
                  : 'text-[#26a69a]',
              )}
            >
              {health?.dead_letter_count ?? '...'}
            </span>
          </div>
          <div className="px-4 py-2.5 flex items-center justify-between">
            <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-mono">
              Queue Depth
            </span>
            <span className="font-mono text-xs text-zinc-300">
              {health?.queue_depth ?? '...'}
            </span>
          </div>
          <div className="px-4 py-2.5 flex items-center justify-between">
            <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-mono">
              Redis
            </span>
            <span
              className={cn(
                'font-mono text-xs font-semibold',
                health?.redis_connected ? 'text-[#26a69a]' : 'text-[#ef5350]',
              )}
            >
              {health?.redis_connected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
      </div>

      {/* Dead Letter Inspector */}
      {(dlData?.count ?? 0) > 0 && (
        <div className="tv-card">
          <div className="px-4 py-3 border-b border-[#2a2e39]">
            <div className="flex items-center gap-2">
              <Inbox className="w-4 h-4 text-[#ef5350]" />
              <span className="font-mono text-xs text-zinc-400 uppercase tracking-wider">
                Dead Letter Queue ({dlData?.count})
              </span>
            </div>
          </div>
          <div className="divide-y divide-[#2a2e39] max-h-64 overflow-y-auto">
            {dlData?.items.map((item) => (
              <div
                key={item.id}
                className="px-4 py-2.5 flex items-center justify-between gap-2"
              >
                <div className="flex-1 min-w-0">
                  <div className="font-mono text-[11px] text-zinc-300 truncate">
                    {(item.payload as Record<string, unknown>)?.symbol as string ??
                      'Unknown'}{' '}
                    &mdash; {item.error.slice(0, 60)}
                  </div>
                  <div className="text-[9px] text-zinc-600 font-mono">
                    Attempt #{item.attempt} &middot;{' '}
                    {new Date(item.failed_at * 1000).toLocaleTimeString()}
                  </div>
                </div>
                <button
                  onClick={() => retryMutation.mutate(item.id)}
                  disabled={retryMutation.isPending}
                  className="flex items-center gap-1 px-2 py-1 bg-[#2a2e39] rounded text-[10px] text-zinc-300 hover:bg-[#363a45] font-mono shrink-0"
                >
                  <RefreshCw className="w-3 h-3" />
                  Retry
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
