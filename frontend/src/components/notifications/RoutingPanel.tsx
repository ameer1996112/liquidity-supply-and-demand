'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';
import { Route, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface RoutingRule {
  id: number;
  alert_type: string;
  discord_enabled: boolean;
  telegram_enabled: boolean;
  discord_channel: 'signals' | 'alerts';
  updated_at: string;
}

const TYPE_LABELS: Record<string, string> = {
  signal:  'Trade Signals',
  close:   'Trade Closes',
  alert:   'Risk Alerts',
  guard:   'Guard Alerts',
  bug:     'Bug / System Errors',
};

const qKeys = { routing: ['notification-routing'] as const };

function useRouting() {
  return useQuery<RoutingRule[]>({
    queryKey: qKeys.routing,
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) return [];
      const res = await fetch(`${base}/api/notifications/routing`, { signal: AbortSignal.timeout(5_000) });
      if (!res.ok) return [];
      return res.json();
    },
    staleTime: 30_000,
  });
}

function useUpdateRouting() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ alertType, field, value }: { alertType: string; field: string; value: boolean | string }) => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/api/notifications/routing/${alertType}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: value }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: qKeys.routing }),
  });
}

function Toggle({ checked, onChange, disabled }: { checked: boolean; onChange: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onChange}
      disabled={disabled}
      className={cn(
        'relative inline-flex h-4 w-7 items-center rounded-full transition-colors',
        checked ? 'bg-emerald-500' : 'bg-[var(--to-border)]',
        disabled && 'opacity-40 cursor-not-allowed'
      )}
    >
      <span
        className={cn(
          'inline-block h-3 w-3 transform rounded-full bg-white transition-transform',
          checked ? 'translate-x-3.5' : 'translate-x-0.5'
        )}
      />
    </button>
  );
}

export function RoutingPanel() {
  const { data: rules = [], isLoading } = useRouting();
  const update = useUpdateRouting();

  return (
    <div className="to-panel">
      <div className="to-panel-header">
        <div className="flex items-center gap-2">
          <Route className="h-3.5 w-3.5 text-[var(--to-text-dim)]" />
          <span className="to-panel-title">Notification Routing</span>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-6">
          <Loader2 className="h-4 w-4 animate-spin text-[var(--to-text-dim)]" />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[var(--to-border)]">
                <th className="py-2 px-3 text-left text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">Alert Type</th>
                <th className="py-2 px-3 text-center text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">Discord</th>
                <th className="py-2 px-3 text-center text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">Telegram</th>
                <th className="py-2 px-3 text-center text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">Discord Channel</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.id} className="border-b border-[var(--to-border)] last:border-0 hover:bg-[var(--to-surface-hover)]">
                  <td className="py-2.5 px-3 text-[var(--to-text-secondary)] font-medium">
                    {TYPE_LABELS[rule.alert_type] ?? rule.alert_type}
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <div className="flex justify-center">
                      <Toggle
                        checked={rule.discord_enabled}
                        onChange={() => update.mutate({ alertType: rule.alert_type, field: 'discord_enabled', value: !rule.discord_enabled })}
                        disabled={update.isPending}
                      />
                    </div>
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <div className="flex justify-center">
                      <Toggle
                        checked={rule.telegram_enabled}
                        onChange={() => update.mutate({ alertType: rule.alert_type, field: 'telegram_enabled', value: !rule.telegram_enabled })}
                        disabled={update.isPending}
                      />
                    </div>
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <select
                      value={rule.discord_channel}
                      onChange={(e) => update.mutate({ alertType: rule.alert_type, field: 'discord_channel', value: e.target.value })}
                      disabled={update.isPending}
                      className="bg-[var(--to-surface)] border border-[var(--to-border)] rounded px-1.5 py-0.5 text-xs text-[var(--to-text-secondary)] cursor-pointer disabled:opacity-40"
                    >
                      <option value="signals">signals</option>
                      <option value="alerts">alerts</option>
                    </select>
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
