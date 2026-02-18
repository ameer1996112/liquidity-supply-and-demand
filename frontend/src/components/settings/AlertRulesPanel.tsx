'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';
import { Bell, Plus, Trash2, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface AlertRule {
  id: number;
  rule_type: string;
  condition: Record<string, unknown>;
  severity: string;
  enabled: boolean;
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

function useCreateAlertRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: {
      rule_type: string;
      condition: Record<string, unknown>;
      severity: string;
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
  warning: 'bg-amber-500/15 text-amber-400',
  info: 'bg-blue-500/15 text-blue-400',
};

function formatCondition(condition: Record<string, unknown>): string {
  return Object.entries(condition)
    .map(([k, v]) => `${k}: ${v}`)
    .join(', ');
}

export function AlertRulesPanel() {
  const { data: rules = [], isLoading } = useAlertRules();
  const deleteRule = useDeleteAlertRule();
  const createRule = useCreateAlertRule();
  const [showAdd, setShowAdd] = useState(false);
  const [newType, setNewType] = useState('');
  const [newThreshold, setNewThreshold] = useState('');
  const [newSeverity, setNewSeverity] = useState('warning');

  const handleAdd = () => {
    if (!newType.trim()) return;
    createRule.mutate(
      {
        rule_type: newType.trim(),
        condition: { threshold: Number(newThreshold) || 1 },
        severity: newSeverity,
      },
      {
        onSuccess: () => {
          setShowAdd(false);
          setNewType('');
          setNewThreshold('');
          setNewSeverity('warning');
        },
      },
    );
  };

  return (
    <div className='tv-card'>
      <div className='px-4 py-3 border-b border-[#2a2e39] flex items-center justify-between'>
        <div className='flex items-center gap-2'>
          <Bell className='w-4 h-4 text-zinc-500' />
          <span className='font-mono text-xs text-zinc-400 uppercase tracking-wider'>
            Alert Rules
          </span>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className='flex items-center gap-1 text-[10px] font-mono text-zinc-500 hover:text-zinc-300 transition-colors'
        >
          <Plus className='w-3 h-3' />
          Add Rule
        </button>
      </div>

      {showAdd && (
        <div className='px-4 py-3 border-b border-[#2a2e39] space-y-2'>
          <div className='grid grid-cols-3 gap-2'>
            <input
              type='text'
              placeholder='Rule type'
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
              className='bg-[#1e222d] border border-[#2a2e39] rounded px-2 py-1 text-xs font-mono text-zinc-300 focus:outline-none focus:border-[#26a69a]'
            />
            <input
              type='number'
              placeholder='Threshold'
              value={newThreshold}
              onChange={(e) => setNewThreshold(e.target.value)}
              className='bg-[#1e222d] border border-[#2a2e39] rounded px-2 py-1 text-xs font-mono text-zinc-300 focus:outline-none focus:border-[#26a69a]'
            />
            <select
              value={newSeverity}
              onChange={(e) => setNewSeverity(e.target.value)}
              className='bg-[#1e222d] border border-[#2a2e39] rounded px-2 py-1 text-xs font-mono text-zinc-300 focus:outline-none focus:border-[#26a69a]'
            >
              <option value='info'>Info</option>
              <option value='warning'>Warning</option>
              <option value='critical'>Critical</option>
            </select>
          </div>
          <button
            onClick={handleAdd}
            disabled={createRule.isPending}
            className='flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider bg-[#26a69a]/15 text-[#26a69a] hover:bg-[#26a69a]/25 transition-colors'
          >
            {createRule.isPending && (
              <Loader2 className='w-3 h-3 animate-spin' />
            )}
            Create
          </button>
        </div>
      )}

      <div className='divide-y divide-[#2a2e39]'>
        {isLoading && (
          <div className='px-4 py-6 text-center text-xs text-zinc-500 font-mono'>
            Loading rules...
          </div>
        )}
        {!isLoading && rules.length === 0 && (
          <div className='px-4 py-6 text-center text-xs text-zinc-500 font-mono'>
            No alert rules configured
          </div>
        )}
        {rules.map((rule) => (
          <div
            key={rule.id}
            className='px-4 py-2.5 flex items-center justify-between'
          >
            <div className='flex items-center gap-3'>
              <span className='font-mono text-xs text-zinc-300'>
                {rule.rule_type}
              </span>
              <span className='font-mono text-[10px] text-zinc-500'>
                {formatCondition(rule.condition)}
              </span>
              <span
                className={cn(
                  'font-mono text-[10px] px-1.5 py-0.5 rounded uppercase',
                  SEVERITY_COLORS[rule.severity] ||
                    'bg-zinc-500/15 text-zinc-400',
                )}
              >
                {rule.severity}
              </span>
            </div>
            <button
              onClick={() => deleteRule.mutate(rule.id)}
              disabled={deleteRule.isPending}
              className='text-zinc-600 hover:text-[#ef5350] transition-colors'
            >
              <Trash2 className='w-3.5 h-3.5' />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
