'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';
import { Shield, Plus, Trash2, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface WhitelistEntry {
  id: number;
  platform: 'telegram' | 'discord';
  user_id: string;
  label: string | null;
  created_at: string;
}

const qKeys = { whitelist: ['notification-whitelist'] as const };

function useWhitelist() {
  return useQuery<WhitelistEntry[]>({
    queryKey: qKeys.whitelist,
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) return [];
      const res = await fetch(`${base}/api/notifications/whitelist`, { signal: AbortSignal.timeout(5_000) });
      if (!res.ok) return [];
      return res.json();
    },
    staleTime: 30_000,
  });
}

function useAddToWhitelist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (entry: { platform: string; user_id: string; label?: string }) => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/api/notifications/whitelist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entry),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? `HTTP ${res.status}`);
      }
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: qKeys.whitelist }),
  });
}

function useRemoveFromWhitelist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/api/notifications/whitelist/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: qKeys.whitelist }),
  });
}

const PLATFORM_BADGE: Record<string, string> = {
  telegram: 'bg-sky-500/20 text-sky-400',
  discord:  'bg-indigo-500/20 text-indigo-400',
};

export function WhitelistPanel() {
  const { data: entries = [], isLoading } = useWhitelist();
  const add = useAddToWhitelist();
  const remove = useRemoveFromWhitelist();

  const [showForm, setShowForm] = useState(false);
  const [platform, setPlatform] = useState<'telegram' | 'discord'>('telegram');
  const [userId, setUserId] = useState('');
  const [label, setLabel] = useState('');
  const [formError, setFormError] = useState('');

  const handleAdd = async () => {
    setFormError('');
    if (!userId.trim()) { setFormError('User ID is required'); return; }
    try {
      await add.mutateAsync({ platform, user_id: userId.trim(), label: label.trim() || undefined });
      setUserId(''); setLabel(''); setShowForm(false);
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : 'Failed to add user');
    }
  };

  return (
    <div className="to-panel">
      <div className="to-panel-header">
        <div className="flex items-center gap-2">
          <Shield className="h-3.5 w-3.5 text-[var(--to-text-dim)]" />
          <span className="to-panel-title">Allowed Command Users</span>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1 text-xs text-[var(--to-accent)] hover:opacity-80 transition-opacity"
        >
          <Plus className="h-3 w-3" />
          Add User
        </button>
      </div>

      {showForm && (
        <div className="border-b border-[var(--to-border)] px-3 py-3 space-y-2">
          <div className="flex gap-2">
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value as 'telegram' | 'discord')}
              className="bg-[var(--to-surface)] border border-[var(--to-border)] rounded px-2 py-1 text-xs text-[var(--to-text-secondary)]"
            >
              <option value="telegram">Telegram</option>
              <option value="discord">Discord</option>
            </select>
            <input
              placeholder="User ID (numeric)"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              className="flex-1 bg-[var(--to-surface)] border border-[var(--to-border)] rounded px-2 py-1 text-xs text-[var(--to-text-secondary)] placeholder:text-[var(--to-text-dim)]"
            />
            <input
              placeholder="Label (optional)"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="flex-1 bg-[var(--to-surface)] border border-[var(--to-border)] rounded px-2 py-1 text-xs text-[var(--to-text-secondary)] placeholder:text-[var(--to-text-dim)]"
            />
          </div>
          {formError && <p className="text-xs text-red-400">{formError}</p>}
          <div className="flex gap-2">
            <button
              onClick={handleAdd}
              disabled={add.isPending}
              className="flex items-center gap-1 px-2.5 py-1 rounded bg-emerald-500/20 text-emerald-400 text-xs hover:bg-emerald-500/30 disabled:opacity-50"
            >
              {add.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
              Save
            </button>
            <button
              onClick={() => { setShowForm(false); setFormError(''); }}
              className="px-2.5 py-1 rounded border border-[var(--to-border)] text-xs text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center justify-center py-6">
          <Loader2 className="h-4 w-4 animate-spin text-[var(--to-text-dim)]" />
        </div>
      ) : entries.length === 0 ? (
        <div className="px-3 py-6 text-center text-xs text-[var(--to-text-dim)]">
          No users whitelisted. Add a user to enable two-way commands.
        </div>
      ) : (
        <div className="divide-y divide-[var(--to-border)]">
          {entries.map((entry) => (
            <div key={entry.id} className="flex items-center justify-between px-3 py-2.5 hover:bg-[var(--to-surface-hover)]">
              <div className="flex items-center gap-2">
                <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium', PLATFORM_BADGE[entry.platform] ?? 'bg-gray-500/20 text-gray-400')}>
                  {entry.platform}
                </span>
                <span className="text-xs text-[var(--to-text-secondary)] font-mono">{entry.user_id}</span>
                {entry.label && (
                  <span className="text-xs text-[var(--to-text-dim)]">— {entry.label}</span>
                )}
              </div>
              <button
                onClick={() => remove.mutate(entry.id)}
                disabled={remove.isPending}
                className="text-[var(--to-text-dim)] hover:text-red-400 transition-colors disabled:opacity-40"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
