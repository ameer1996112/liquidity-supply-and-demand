'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl, getAlertRulePatchUrl } from '@/lib/api';
import { Bell, Plus, Trash2, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface AlertRule {
  id: number;
  rule_type: string;
  condition: Record<string, unknown>;
  severity: string;
  enabled: boolean;
  cooldown_minutes: number;
  created_at: string;
}

const ruleKeys = { all: ['alert-rules'] as const };

function useAlertRules() {
  return useQuery<AlertRule[]>({
    queryKey: ruleKeys.all,
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) return [];
      const res = await fetch(`${base}/api/alerts/rules`, {
        signal: AbortSignal.timeout(5_000),
      });
      if (!res.ok) return [];
      const json = await res.json();
      return json.rules ?? [];
    },
    staleTime: 60_000,
  });
}

function useDeleteAlertRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (ruleId: number) => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/api/alerts/rules/${ruleId}`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ruleKeys.all }),
  });
}

function useToggleAlertRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ ruleId, enabled }: { ruleId: number; enabled: boolean }) => {
      const url = getAlertRulePatchUrl(ruleId);
      if (!url) throw new Error('API URL not configured');
      const res = await fetch(url, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    onMutate: async ({ ruleId, enabled }) => {
      // Optimistic update
      await qc.cancelQueries({ queryKey: ruleKeys.all });
      const prev = qc.getQueryData<AlertRule[]>(ruleKeys.all);
      qc.setQueryData<AlertRule[]>(ruleKeys.all, (old) =>
        (old ?? []).map((r) => (r.id === ruleId ? { ...r, enabled } : r)),
      );
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(ruleKeys.all, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ruleKeys.all }),
  });
}

function useCreateAlertRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      rule_type: string;
      condition: Record<string, unknown>;
      severity: string;
      cooldown_minutes: number;
    }) => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/api/alerts/rules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ruleKeys.all }),
  });
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-[#ef5350]/15 text-[#ef5350]',
  error:    'bg-orange-500/15 text-orange-400',
  warning:  'bg-amber-500/15 text-amber-400',
  info:     'bg-blue-500/15 text-blue-400',
};

function formatCondition(condition: Record<string, unknown>): string {
  return Object.entries(condition)
    .map(([k, v]) => `${k}: ${v}`)
    .join(', ');
}

// ── Toggle switch component ───────────────────────────────────

interface ToggleProps {
  checked: boolean;
  onChange: (val: boolean) => void;
  disabled?: boolean;
}

function Toggle({ checked, onChange, disabled }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-4 w-7 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-150',
        'focus:outline-none disabled:cursor-not-allowed disabled:opacity-50',
        checked ? 'bg-[var(--to-accent-green)]' : 'bg-[var(--to-border)]',
      )}
    >
      <span
        className={cn(
          'pointer-events-none inline-block h-3 w-3 rounded-full bg-white shadow transition-transform duration-150',
          checked ? 'translate-x-3' : 'translate-x-0',
        )}
      />
    </button>
  );
}

// ── Panel ────────────────────────────────────────────────────

export function AlertRulesPanel() {
  const { data: rules = [], isLoading } = useAlertRules();
  const deleteRule  = useDeleteAlertRule();
  const toggleRule  = useToggleAlertRule();
  const createRule  = useCreateAlertRule();
  const [showAdd, setShowAdd] = useState(false);
  const [newType, setNewType] = useState('');
  const [newThreshold, setNewThreshold] = useState('');
  const [newSeverity, setNewSeverity] = useState('warning');
  const [newCooldown, setNewCooldown] = useState('60');

  const handleAdd = () => {
    if (!newType.trim()) return;
    createRule.mutate(
      {
        rule_type: newType.trim(),
        condition: { threshold: Number(newThreshold) || 1 },
        severity: newSeverity,
        cooldown_minutes: Number(newCooldown) || 60,
      },
      {
        onSuccess: () => {
          setShowAdd(false);
          setNewType('');
          setNewThreshold('');
          setNewSeverity('warning');
          setNewCooldown('60');
        },
      },
    );
  };

  return (
    <div className='to-panel'>
      <div className='to-panel-header flex items-center justify-between'>
        <div className='flex items-center gap-2'>
          <Bell className='w-4 h-4 text-text-dim' />
          <span className='font-mono text-[11px] text-text-muted uppercase tracking-[0.18em]'>
            Alert Rules
          </span>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className='flex items-center gap-1 text-[10px] font-mono text-text-muted hover:text-text-secondary transition-colors'
        >
          <Plus className='w-3 h-3' />
          Add Rule
        </button>
      </div>

      {showAdd && (
        <div className='px-4 py-3 border-b border-panel-border-subtle space-y-2'>
          <div className='grid grid-cols-2 gap-2'>
            <input
              id='alert-rule-type'
              type='text'
              placeholder='Rule type'
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
              className='bg-surface border border-panel-border-subtle rounded px-2 py-1 text-xs font-mono text-text-secondary focus:outline-none focus:border-[var(--to-accent-green)]'
            />
            <input
              id='alert-rule-threshold'
              type='number'
              placeholder='Threshold'
              value={newThreshold}
              onChange={(e) => setNewThreshold(e.target.value)}
              className='bg-surface border border-panel-border-subtle rounded px-2 py-1 text-xs font-mono text-text-secondary focus:outline-none focus:border-[var(--to-accent-green)]'
            />
            <select
              id='alert-rule-severity'
              value={newSeverity}
              onChange={(e) => setNewSeverity(e.target.value)}
              className='bg-surface border border-panel-border-subtle rounded px-2 py-1 text-xs font-mono text-text-secondary focus:outline-none focus:border-[var(--to-accent-green)]'
            >
              <option value='info'>Info</option>
              <option value='warning'>Warning</option>
              <option value='error'>Error</option>
              <option value='critical'>Critical</option>
            </select>
            <input
              id='alert-rule-cooldown'
              type='number'
              placeholder='Cooldown (min)'
              value={newCooldown}
              onChange={(e) => setNewCooldown(e.target.value)}
              className='bg-surface border border-panel-border-subtle rounded px-2 py-1 text-xs font-mono text-text-secondary focus:outline-none focus:border-[var(--to-accent-green)]'
            />
          </div>
          <button
            onClick={handleAdd}
            disabled={createRule.isPending}
            className='flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider bg-[var(--to-accent-green)]/15 text-[var(--to-accent-green)] hover:bg-[var(--to-accent-green)]/25 transition-colors'
          >
            {createRule.isPending && (
              <Loader2 className='w-3 h-3 animate-spin' />
            )}
            Create
          </button>
        </div>
      )}

      <div className='divide-y divide-panel-border-subtle'>
        {isLoading && (
          <div className='px-4 py-6 text-center text-xs font-mono text-text-muted'>
            Loading rules...
          </div>
        )}
        {!isLoading && rules.length === 0 && (
          <div className='px-4 py-6 text-center text-xs font-mono text-text-muted'>
            No alert rules configured
          </div>
        )}
        {rules.map((rule) => (
          <div
            key={rule.id}
            className={cn(
              'px-4 py-2.5 flex items-center justify-between gap-3',
              !rule.enabled && 'opacity-50',
            )}
          >
            {/* Toggle */}
            <Toggle
              checked={rule.enabled}
              onChange={(val) => toggleRule.mutate({ ruleId: rule.id, enabled: val })}
              disabled={toggleRule.isPending}
            />

            {/* Rule info */}
            <div className='flex-1 flex items-center gap-3 min-w-0'>
              <span className='font-mono text-xs text-text-secondary truncate'>
                {rule.rule_type}
              </span>
              <span className='font-mono text-[10px] text-text-muted truncate'>
                {formatCondition(rule.condition)}
              </span>
              <span
                className={cn(
                  'font-mono text-[10px] px-1.5 py-0.5 rounded uppercase shrink-0',
                  SEVERITY_COLORS[rule.severity] ||
                    'bg-zinc-500/15 text-[var(--to-text-dim)]',
                )}
              >
                {rule.severity}
              </span>
              {rule.cooldown_minutes && (
                <span className='font-mono text-[9px] text-text-muted shrink-0'>
                  {rule.cooldown_minutes}m cooldown
                </span>
              )}
            </div>

            {/* Delete */}
            <button
              onClick={() => deleteRule.mutate(rule.id)}
              disabled={deleteRule.isPending}
              className='text-text-muted hover:text-[var(--to-short)] transition-colors shrink-0'
            >
              <Trash2 className='w-3.5 h-3.5' />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
