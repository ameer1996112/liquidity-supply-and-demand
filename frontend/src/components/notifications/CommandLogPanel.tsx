'use client';

import { useQuery } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';
import { Terminal, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface CommandLog {
  id: number;
  platform: 'telegram' | 'discord';
  user_id: string;
  command: string;
  args: string | null;
  result: string | null;
  success: boolean;
  executed_at: string;
}

const PLATFORM_BADGE: Record<string, string> = {
  telegram: 'bg-sky-500/20 text-sky-400',
  discord:  'bg-indigo-500/20 text-indigo-400',
};

function useCommandLog() {
  return useQuery<CommandLog[]>({
    queryKey: ['notification-commands'],
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) return [];
      const res = await fetch(`${base}/api/notifications/commands?limit=50`, { signal: AbortSignal.timeout(5_000) });
      if (!res.ok) return [];
      return res.json();
    },
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return iso;
  }
}

export function CommandLogPanel() {
  const { data: logs = [], isLoading } = useCommandLog();

  return (
    <div className="to-panel">
      <div className="to-panel-header">
        <div className="flex items-center gap-2">
          <Terminal className="h-3.5 w-3.5 text-[var(--to-text-dim)]" />
          <span className="to-panel-title">Command History</span>
        </div>
        <span className="text-[10px] text-[var(--to-text-dim)]">last 50</span>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-6">
          <Loader2 className="h-4 w-4 animate-spin text-[var(--to-text-dim)]" />
        </div>
      ) : logs.length === 0 ? (
        <div className="px-3 py-6 text-center text-xs text-[var(--to-text-dim)]">
          No commands issued yet.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[var(--to-border)]">
                <th className="py-2 px-3 text-left text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">Time</th>
                <th className="py-2 px-3 text-left text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">Platform</th>
                <th className="py-2 px-3 text-left text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">Command</th>
                <th className="py-2 px-3 text-left text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">Result</th>
                <th className="py-2 px-3 text-center text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">Status</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id} className="border-b border-[var(--to-border)] last:border-0 hover:bg-[var(--to-surface-hover)]">
                  <td className="py-2 px-3 font-mono text-[var(--to-text-dim)] whitespace-nowrap">
                    {formatTime(log.executed_at)}
                  </td>
                  <td className="py-2 px-3">
                    <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium', PLATFORM_BADGE[log.platform] ?? 'bg-gray-500/20 text-gray-400')}>
                      {log.platform}
                    </span>
                  </td>
                  <td className="py-2 px-3 font-mono text-[var(--to-text-secondary)]">
                    /{log.command}{log.args ? ` ${log.args}` : ''}
                  </td>
                  <td className="py-2 px-3 text-[var(--to-text-dim)] max-w-[280px] truncate" title={log.result ?? ''}>
                    {log.result ?? '—'}
                  </td>
                  <td className="py-2 px-3 text-center">
                    {log.success ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 inline" />
                    ) : (
                      <XCircle className="h-3.5 w-3.5 text-red-400 inline" />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
