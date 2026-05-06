'use client';

import { useState, useEffect } from 'react';
import { Shield, Target, TrendingDown, Calendar, CheckCircle, AlertTriangle, ChevronRight, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { useChallengeSettings, useUpdateChallengeSettings } from '@/hooks/useChallenge';
import type { ChallengeSettings } from '@/lib/api';
import { cn } from '@/lib/utils';

interface ChallengeTabProps {
  accountName: string;
}

// Provider-specific defaults (bot kill thresholds, not firm limits)
// Bot kills at 80% of firm limits to maintain a safety buffer.
const PROVIDER_PRESETS: Record<string, Record<string, Partial<ChallengeSettings>>> = {
  FTMO: {
    phase1: { profit_target: 5000, max_daily_loss_pct: 4.0, max_drawdown_pct: 8.0, min_trading_days: 4, consistency_limit_pct: 40 },
    phase2: { profit_target: 2500, max_daily_loss_pct: 4.0, max_drawdown_pct: 8.0, min_trading_days: 4, consistency_limit_pct: 40 },
    funded:  { profit_target: 0,    max_daily_loss_pct: 4.0, max_drawdown_pct: 8.0, min_trading_days: 0, consistency_limit_pct: 40 },
  },
  ACG: {
    phase1: { profit_target: 5000, max_daily_loss_pct: 4.0, max_drawdown_pct: 8.0, min_trading_days: 5, consistency_limit_pct: 40, consistency_enabled: false },
    phase2: { profit_target: 2500, max_daily_loss_pct: 4.0, max_drawdown_pct: 8.0, min_trading_days: 5, consistency_limit_pct: 40, consistency_enabled: false },
    funded:  { profit_target: 0,    max_daily_loss_pct: 4.0, max_drawdown_pct: 8.0, min_trading_days: 0, consistency_limit_pct: 40, consistency_enabled: false },
  },
  MyFundedFX: {
    phase1: { profit_target: 8000, max_daily_loss_pct: 4.0, max_drawdown_pct: 8.0, min_trading_days: 5, consistency_limit_pct: 50 },
    phase2: { profit_target: 4000, max_daily_loss_pct: 4.0, max_drawdown_pct: 8.0, min_trading_days: 5, consistency_limit_pct: 50 },
    funded:  { profit_target: 0,    max_daily_loss_pct: 4.0, max_drawdown_pct: 8.0, min_trading_days: 0, consistency_limit_pct: 50 },
  },
};

const PHASE_LABELS: Record<string, string> = {
  phase1: 'Phase 1',
  phase2: 'Phase 2',
  funded: 'Funded',
};

const PHASE_ORDER = ['phase1', 'phase2', 'funded'] as const;

function ProgressBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className='h-1.5 w-full rounded-full bg-[#2a2e39]'>
      <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function ChallengeTab({ accountName }: ChallengeTabProps) {
  const { addToast } = useToast();
  const { data: settings, isLoading } = useChallengeSettings(accountName);
  const updateMutation = useUpdateChallengeSettings(accountName);

  // Local edit state
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Omit<ChallengeSettings, 'account_name' | 'broker_profile_id' | 'evaluation_start_date'>>(
    {
    evaluation_mode: true,
    evaluation_phase: 'phase1',
    starting_balance: 50000,
    profit_target: 5000,
    max_daily_loss_pct: 4.0,
    max_drawdown_pct: 8.0,
    min_trading_days: 4,
    consistency_limit_pct: 40,
    consistency_enabled: null,  // null = use global setting
  });

  // Sync form when data loads
  useEffect(() => {
    if (settings) {
      setForm({
        evaluation_mode: settings.evaluation_mode,
        evaluation_phase: settings.evaluation_phase,
        starting_balance: settings.starting_balance,
        profit_target: settings.profit_target,
        max_daily_loss_pct: settings.max_daily_loss_pct,
        max_drawdown_pct: settings.max_drawdown_pct,
        min_trading_days: settings.min_trading_days,
        consistency_limit_pct: settings.consistency_limit_pct,
        consistency_enabled: settings.consistency_enabled ?? null,
      });
    }
  }, [settings]);

  const handlePhaseSwitch = async (phase: 'phase1' | 'phase2' | 'funded') => {
    const updated = { ...form, evaluation_phase: phase, evaluation_mode: true };
    setForm(updated);
    try {
      await updateMutation.mutateAsync(updated);
      addToast({ title: 'Phase updated', message: `Switched to ${PHASE_LABELS[phase]}`, severity: 'success', duration: 3000 });
    } catch (e) {
      addToast({ title: 'Update failed', message: (e as Error).message, severity: 'critical', duration: 5000 });
    }
  };

  const handleSave = async () => {
    try {
      await updateMutation.mutateAsync(form);
      setEditing(false);
      addToast({ title: 'Challenge settings saved', message: 'Bot will enforce new limits on next trade', severity: 'success', duration: 4000 });
    } catch (e) {
      addToast({ title: 'Save failed', message: (e as Error).message, severity: 'critical', duration: 5000 });
    }
  };

  const applyPreset = (provider: string, phase: string) => {
    const preset = PROVIDER_PRESETS[provider]?.[phase];
    if (preset) setForm(f => ({ ...f, ...preset, evaluation_phase: phase as 'phase1' | 'phase2' | 'funded' }));
  };

  if (isLoading) {
    return (
      <div className='flex items-center justify-center h-32'>
        <Loader2 className='h-5 w-5 animate-spin text-[var(--to-text-dim)]' />
      </div>
    );
  }

  const current = settings ?? form;
  const dailyLimitUsd = (current.starting_balance * current.max_daily_loss_pct) / 100;
  const ddLimitUsd = (current.starting_balance * current.max_drawdown_pct) / 100;
  const currentPhaseIdx = PHASE_ORDER.indexOf(current.evaluation_phase as typeof PHASE_ORDER[number]);

  return (
    <div className='space-y-5'>

      {/* Evaluation toggle banner */}
      <div className={cn(
        'rounded-lg border px-4 py-3 flex items-center justify-between',
        current.evaluation_mode
          ? 'border-indigo-500/30 bg-indigo-500/5'
          : 'border-[var(--to-border)] bg-[var(--to-surface-raised)]/40'
      )}>
        <div className='flex items-center gap-2'>
          <Shield className={cn('h-4 w-4', current.evaluation_mode ? 'text-indigo-400' : 'text-[var(--to-text-dim)]')} />
          <span className={cn('text-sm font-medium', current.evaluation_mode ? 'text-indigo-300' : 'text-[var(--to-text-dim)]')}>
            {current.evaluation_mode ? 'Evaluation mode active — prop firm guardrails enforced' : 'Evaluation mode off — no prop firm limits'}
          </span>
        </div>
        <button
          onClick={() => {
            const updated = { ...form, evaluation_mode: !form.evaluation_mode };
            setForm(updated);
            updateMutation.mutateAsync(updated).catch(() => {});
          }}
          className={cn(
            'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
            form.evaluation_mode ? 'bg-indigo-600' : 'bg-[var(--to-surface-raised)]'
          )}
        >
          <span className={cn(
            'inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform',
            form.evaluation_mode ? 'translate-x-4' : 'translate-x-0.5'
          )} />
        </button>
      </div>

      {/* Consistency rule toggle — only meaningful when evaluation_mode is on */}
      {current.evaluation_mode && (
        <div className={cn(
          'rounded-lg border px-4 py-3 flex items-center justify-between',
          'border-[var(--to-border)] bg-[var(--to-surface-raised)]/40'
        )}>
          <div className='flex flex-col gap-0.5'>
            <div className='flex items-center gap-2'>
              <Shield className='h-4 w-4 text-[var(--to-text-dim)]' />
              <span className='text-sm font-medium text-[var(--to-text)]'>Consistency rule (best day ≤ 40%)</span>
            </div>
            <span className='text-[11px] text-[var(--to-text-dim)] pl-6'>
              {(form.consistency_enabled ?? true)
                ? 'Enforced — FTMO / MyFundedFX accounts'
                : 'Disabled — ACG and firms without this rule'}
            </span>
          </div>
          <button
            id={`consistency-toggle-${accountName}`}
            type='button'
            onClick={() => {
              const next = !(form.consistency_enabled ?? true);
              const updated = { ...form, consistency_enabled: next };
              setForm(updated);
              updateMutation.mutateAsync(updated).catch(() => {});
            }}
            className={cn(
              'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
              (form.consistency_enabled ?? true) ? 'bg-indigo-600' : 'bg-[var(--to-surface-raised)]'
            )}
          >
            <span className={cn(
              'inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform',
              (form.consistency_enabled ?? true) ? 'translate-x-4' : 'translate-x-0.5'
            )} />
          </button>
        </div>
      )}

      {/* Phase switcher */}
      <section>
        <h3 className='text-xs font-mono text-[var(--to-text-dim)] uppercase tracking-wider mb-3'>Current Phase</h3>
        <div className='flex gap-2'>
          {PHASE_ORDER.map((phase, idx) => {
            const isActive = current.evaluation_phase === phase;
            const isPast = idx < currentPhaseIdx;
            return (
              <button
                key={phase}
                onClick={() => !isActive && handlePhaseSwitch(phase)}
                disabled={updateMutation.isPending}
                className={cn(
                  'flex-1 flex flex-col items-center gap-1.5 rounded-lg border py-3 px-2 text-xs font-mono transition-all',
                  isActive
                    ? 'border-indigo-500/60 bg-indigo-500/10 text-indigo-300'
                    : isPast
                    ? 'border-[var(--to-long)]/30 bg-emerald-500/5 text-[var(--to-long)] cursor-pointer hover:bg-[var(--to-long)]/10'
                    : 'border-[var(--to-border)] bg-[var(--to-surface-raised)]/40 text-[var(--to-text-dim)] cursor-pointer hover:bg-[var(--to-surface-raised)]/40 hover:text-[var(--to-text-secondary)]'
                )}
              >
                {isPast ? (
                  <CheckCircle className='h-4 w-4 text-[var(--to-long)]' />
                ) : isActive ? (
                  <div className='h-2 w-2 rounded-full bg-indigo-400 animate-pulse' />
                ) : (
                  <div className='h-2 w-2 rounded-full bg-[var(--to-surface-raised)]' />
                )}
                <span>{PHASE_LABELS[phase]}</span>
                {isActive && <ChevronRight className='h-3 w-3 rotate-90' />}
              </button>
            );
          })}
        </div>
      </section>

      {/* Limit summary cards */}
      <section className='grid grid-cols-2 md:grid-cols-4 gap-3'>
        <div className='rounded-lg border border-[#2a2e39] bg-[#1e222d]/80 p-3'>
          <div className='flex items-center gap-1.5 mb-2'>
            <Target className='h-3.5 w-3.5 text-[var(--to-long)]' />
            <span className='text-[10px] text-[var(--to-text-dim)] font-mono uppercase'>Profit Target</span>
          </div>
          <div className='text-lg font-mono font-semibold text-[var(--to-text-primary)]'>
            ${current.profit_target.toLocaleString()}
          </div>
          <ProgressBar value={0} max={current.profit_target} color='bg-emerald-500' />
        </div>
        <div className='rounded-lg border border-[#2a2e39] bg-[#1e222d]/80 p-3'>
          <div className='flex items-center gap-1.5 mb-2'>
            <AlertTriangle className='h-3.5 w-3.5 text-amber-400' />
            <span className='text-[10px] text-[var(--to-text-dim)] font-mono uppercase'>Daily Kill</span>
          </div>
          <div className='text-lg font-mono font-semibold text-[var(--to-text-primary)]'>
            ${dailyLimitUsd.toLocaleString()}
          </div>
          <div className='text-[9px] text-[var(--to-text-dim)] font-mono mt-1'>{current.max_daily_loss_pct}% of balance</div>
        </div>
        <div className='rounded-lg border border-[#2a2e39] bg-[#1e222d]/80 p-3'>
          <div className='flex items-center gap-1.5 mb-2'>
            <TrendingDown className='h-3.5 w-3.5 text-[var(--to-short)]' />
            <span className='text-[10px] text-[var(--to-text-dim)] font-mono uppercase'>DD Kill</span>
          </div>
          <div className='text-lg font-mono font-semibold text-[var(--to-text-primary)]'>
            ${ddLimitUsd.toLocaleString()}
          </div>
          <div className='text-[9px] text-[var(--to-text-dim)] font-mono mt-1'>{current.max_drawdown_pct}% of balance</div>
        </div>
        <div className='rounded-lg border border-[#2a2e39] bg-[#1e222d]/80 p-3'>
          <div className='flex items-center gap-1.5 mb-2'>
            <Calendar className='h-3.5 w-3.5 text-blue-400' />
            <span className='text-[10px] text-[var(--to-text-dim)] font-mono uppercase'>Min Days</span>
          </div>
          <div className='text-lg font-mono font-semibold text-[var(--to-text-primary)]'>
            {current.min_trading_days}
          </div>
          <div className='text-[9px] text-[var(--to-text-dim)] font-mono mt-1'>trading days required</div>
        </div>
      </section>

      {/* Edit settings */}
      {!editing ? (
        <div className='flex items-center gap-3'>
          <Button size='sm' variant='outline' onClick={() => setEditing(true)}
            className='border-[var(--to-border)] text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)] hover:bg-[var(--to-surface-raised)]'>
            Edit Limits
          </Button>
          <span className='text-[10px] text-[var(--to-text-dim)] font-mono'>
            {settings?.evaluation_start_date ? `Started ${settings.evaluation_start_date}` : 'No start date set'}
          </span>
        </div>
      ) : (
        <div className='rounded-lg border border-[#2a2e39] bg-[#1e222d]/80 p-4 space-y-4'>
          <div className='flex items-center justify-between mb-1'>
            <h4 className='text-sm font-semibold text-[var(--to-text-primary)]'>Edit Challenge Limits</h4>
            <div className='flex gap-2 text-[10px] text-[var(--to-text-dim)] font-mono'>
              Apply preset:
              {Object.keys(PROVIDER_PRESETS).map(p => (
                <button key={p} onClick={() => applyPreset(p, form.evaluation_phase)}
                  className='text-indigo-400 hover:text-indigo-300 underline underline-offset-2'>
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div className='grid grid-cols-2 gap-3'>
            <div>
              <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>Starting Balance ($)</label>
              <input type='number' min={1000} step={1000} value={form.starting_balance}
                onChange={e => setForm(f => ({ ...f, starting_balance: parseFloat(e.target.value) || 0 }))}
                className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-[var(--to-text-primary)] focus:outline-none focus:border-zinc-500' />
            </div>
            <div>
              <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>Profit Target ($)</label>
              <input type='number' min={0} step={500} value={form.profit_target}
                onChange={e => setForm(f => ({ ...f, profit_target: parseFloat(e.target.value) || 0 }))}
                className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-[var(--to-text-primary)] focus:outline-none focus:border-zinc-500' />
            </div>
            <div>
              <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>
                Daily Kill % <span className='text-[var(--to-text-dim)]'>(bot stops at this loss)</span>
              </label>
              <input type='number' min={0.5} max={10} step={0.5} value={form.max_daily_loss_pct}
                onChange={e => setForm(f => ({ ...f, max_daily_loss_pct: parseFloat(e.target.value) || 0 }))}
                className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-[var(--to-text-primary)] focus:outline-none focus:border-zinc-500' />
              <p className='text-[9px] text-[var(--to-text-dim)] mt-1 font-mono'>
                = ${((form.starting_balance * form.max_daily_loss_pct) / 100).toLocaleString(undefined, { maximumFractionDigits: 0 })} — set below firm&apos;s limit
              </p>
            </div>
            <div>
              <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>
                Drawdown Kill % <span className='text-[var(--to-text-dim)]'>(bot stops at this DD)</span>
              </label>
              <input type='number' min={1} max={20} step={0.5} value={form.max_drawdown_pct}
                onChange={e => setForm(f => ({ ...f, max_drawdown_pct: parseFloat(e.target.value) || 0 }))}
                className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-[var(--to-text-primary)] focus:outline-none focus:border-zinc-500' />
              <p className='text-[9px] text-[var(--to-text-dim)] mt-1 font-mono'>
                = ${((form.starting_balance * form.max_drawdown_pct) / 100).toLocaleString(undefined, { maximumFractionDigits: 0 })} — set below firm&apos;s limit
              </p>
            </div>
            <div>
              <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>Min Trading Days</label>
              <input type='number' min={0} max={60} step={1} value={form.min_trading_days}
                onChange={e => setForm(f => ({ ...f, min_trading_days: parseInt(e.target.value, 10) || 0 }))}
                className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-[var(--to-text-primary)] focus:outline-none focus:border-zinc-500' />
            </div>
            <div>
              <label className='text-[10px] text-[var(--to-text-dim)] font-mono block mb-1'>
                Consistency Limit % <span className='text-[var(--to-text-dim)]'>(FTMO: 40%)</span>
              </label>
              <input type='number' min={10} max={100} step={5} value={form.consistency_limit_pct}
                onChange={e => setForm(f => ({ ...f, consistency_limit_pct: parseFloat(e.target.value) || 40 }))}
                className='w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-[var(--to-text-primary)] focus:outline-none focus:border-zinc-500' />
              <p className='text-[9px] text-[var(--to-text-dim)] mt-1 font-mono'>Best single day ≤ this% of total profit</p>
            </div>
          </div>

          <div className='flex gap-2 pt-1'>
            <Button size='sm' onClick={handleSave} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? <Loader2 className='h-3.5 w-3.5 animate-spin mr-2' /> : null}
              Save
            </Button>
            <Button size='sm' variant='ghost' onClick={() => setEditing(false)}>Cancel</Button>
          </div>
        </div>
      )}
    </div>
  );
}
