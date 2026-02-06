'use client';

import type { BacktestRun } from '@/hooks/useBacktest';
import { cn } from '@/lib/utils';
import { Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { format } from 'date-fns';

const STATUS_CONFIG = {
  pending: { icon: Clock, color: 'text-zinc-500', bg: 'bg-zinc-800' },
  running: { icon: Loader2, color: 'text-blue-400', bg: 'bg-blue-950' },
  completed: { icon: CheckCircle, color: 'text-[#26a69a]', bg: 'bg-emerald-950' },
  failed: { icon: XCircle, color: 'text-[#ef5350]', bg: 'bg-red-950' },
} as const;

interface BacktestRunsListProps {
  runs: BacktestRun[];
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
}

export function BacktestRunsList({
  runs,
  selectedRunId,
  onSelect,
}: BacktestRunsListProps) {
  if (runs.length === 0) {
    return (
      <div className="tv-card p-4">
        <p className="text-[11px] text-zinc-500 font-mono text-center">
          No backtest runs yet
        </p>
      </div>
    );
  }

  return (
    <div className="tv-card">
      <div className="px-4 py-3 border-b border-[#2a2e39]">
        <span className="font-mono text-xs text-zinc-400 uppercase tracking-wider">
          Past Runs ({runs.length})
        </span>
      </div>
      <div className="divide-y divide-[#2a2e39] max-h-80 overflow-y-auto">
        {runs.map((run) => {
          const cfg = STATUS_CONFIG[run.status] || STATUS_CONFIG.pending;
          const Icon = cfg.icon;
          const isSelected = selectedRunId === run.run_id;

          return (
            <button
              key={run.run_id}
              onClick={() => onSelect(run.run_id)}
              className={cn(
                'w-full px-4 py-2.5 flex items-center gap-3 text-left transition-colors',
                isSelected ? 'bg-[#1e222d]' : 'hover:bg-[#1e222d]/50',
              )}
            >
              <div className={cn('p-1 rounded', cfg.bg)}>
                <Icon
                  className={cn(
                    'w-3.5 h-3.5',
                    cfg.color,
                    run.status === 'running' && 'animate-spin',
                  )}
                />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-mono text-[11px] text-zinc-300 truncate">
                  {run.name || run.run_id}
                </div>
                <div className="text-[9px] text-zinc-600 font-mono">
                  {run.created_at
                    ? format(new Date(run.created_at), 'MMM d, HH:mm')
                    : '—'}{' '}
                  &middot; {run.signal_count || 0} signals
                </div>
              </div>
              {isSelected && (
                <div className="w-1 h-5 rounded-full bg-[#26a69a]" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
