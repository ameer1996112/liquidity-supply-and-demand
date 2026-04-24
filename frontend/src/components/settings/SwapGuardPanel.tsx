'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, Check, Clock3, Loader2, RefreshCw, Save, ShieldCheck } from 'lucide-react';
import {
  fetchSwapGuardConfig,
  patchSwapGuardConfig,
  SwapGuardConfigResponse,
} from '@/lib/api';
import { cn } from '@/lib/utils';

type LoadState = 'loading' | 'loaded' | 'error';

const TIMEZONES = ['Asia/Jerusalem', 'UTC', 'Europe/London', 'Europe/Athens', 'America/New_York'];

function NumberField({
  label,
  value,
  min,
  max,
  step = 1,
  onChange,
}: {
  label: string;
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className='space-y-1'>
      <span className='block font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>
        {label}
      </span>
      <input
        type='number'
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(event) => onChange(Number(event.target.value))}
        className='w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-2 font-mono text-xs text-[var(--to-text-primary)] outline-none transition focus:border-emerald-500/50'
      />
    </label>
  );
}

function TextField({
  label,
  value,
  onChange,
  type = 'text',
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
}) {
  return (
    <label className='space-y-1'>
      <span className='block font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>
        {label}
      </span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className='w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-2 font-mono text-xs text-[var(--to-text-primary)] outline-none transition focus:border-emerald-500/50'
      />
    </label>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className='space-y-1'>
      <span className='block font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className='w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-2 font-mono text-xs text-[var(--to-text-primary)] outline-none transition focus:border-emerald-500/50'
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function normalizeDraft(config: SwapGuardConfigResponse): SwapGuardConfigResponse {
  return {
    ...config,
    swap_symbol_spread_overrides_json:
      config.swap_symbol_spread_overrides_json || '',
  };
}

export function SwapGuardPanel() {
  const [state, setState] = useState<LoadState>('loading');
  const [config, setConfig] = useState<SwapGuardConfigResponse | null>(null);
  const [draft, setDraft] = useState<SwapGuardConfigResponse | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const load = async () => {
    setState('loading');
    setError('');
    setMessage('');
    try {
      const next = normalizeDraft(await fetchSwapGuardConfig());
      setConfig(next);
      setDraft(next);
      setState('loaded');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load swap guard settings');
      setState('error');
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const setField = <K extends keyof SwapGuardConfigResponse>(
    key: K,
    value: SwapGuardConfigResponse[K]
  ) => {
    setDraft((current) => (current ? { ...current, [key]: value } : current));
  };

  const handleSave = async () => {
    if (!draft) return;
    setIsSaving(true);
    setError('');
    setMessage('');
    try {
      const next = normalizeDraft(await patchSwapGuardConfig(draft));
      setConfig(next);
      setDraft(next);
      setMessage('Saved');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save swap guard settings');
    } finally {
      setIsSaving(false);
    }
  };

  if (state === 'loading') {
    return (
      <div className='to-panel flex items-center justify-center p-6'>
        <Loader2 className='h-4 w-4 animate-spin text-[var(--to-text-dim)]' />
      </div>
    );
  }

  if (state === 'error' || !draft) {
    return (
      <div className='to-panel p-4'>
        <div className='flex items-center gap-2 text-amber-300'>
          <AlertTriangle className='h-4 w-4' />
          <span className='font-mono text-xs'>{error || 'Unavailable'}</span>
        </div>
        <button
          type='button'
          onClick={() => void load()}
          className='mt-3 inline-flex items-center gap-1 rounded-md border border-[var(--to-border)] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-secondary)] hover:border-white/15 hover:text-white'
        >
          <RefreshCw className='h-3 w-3' />
          Retry
        </button>
      </div>
    );
  }

  const dirty = JSON.stringify(config) !== JSON.stringify(draft);

  return (
    <div className='to-panel'>
      <div className='to-panel-header'>
        <div className='flex items-center gap-2'>
          <ShieldCheck className='h-3.5 w-3.5 text-text-dim' />
          <span className='panel-label'>Rollover Guard</span>
        </div>
        <div className='flex items-center gap-2'>
          {message && (
            <span className='inline-flex items-center gap-1 rounded bg-[var(--to-long)]/10 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--to-long)]'>
              <Check className='h-3 w-3' />
              {message}
            </span>
          )}
          <button
            type='button'
            onClick={() => void load()}
            className='inline-flex items-center gap-1 rounded-md border border-[var(--to-border)] px-2 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-secondary)] transition hover:border-white/15 hover:text-white'
          >
            <RefreshCw className='h-3 w-3' />
            Refresh
          </button>
          <button
            type='button'
            onClick={() => void handleSave()}
            disabled={isSaving || !dirty}
            className={cn(
              'inline-flex items-center gap-1 rounded-md border px-2 py-1 font-mono text-[10px] uppercase tracking-[0.18em] transition',
              dirty
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/15'
                : 'border-[var(--to-border)] text-[var(--to-text-dim)]',
              isSaving && 'opacity-60'
            )}
          >
            {isSaving ? <Loader2 className='h-3 w-3 animate-spin' /> : <Save className='h-3 w-3' />}
            Save
          </button>
        </div>
      </div>

      <div className='space-y-4 p-3'>
        {error && (
          <div className='rounded-md border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-200'>
            {error}
          </div>
        )}

        <div className='flex flex-wrap items-center justify-between gap-3 rounded-md border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-2'>
          <div className='flex items-center gap-2'>
            <Clock3 className='h-3.5 w-3.5 text-[var(--to-text-dim)]' />
            <span className='font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-secondary)]'>
              Runtime Managed
            </span>
          </div>
          <button
            type='button'
            onClick={() => setField('enable_swap_guard', !draft.enable_swap_guard)}
            className={cn(
              'rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-[0.18em] transition',
              draft.enable_swap_guard
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                : 'border-rose-500/30 bg-rose-500/10 text-rose-300'
            )}
          >
            {draft.enable_swap_guard ? 'Enabled' : 'Disabled'}
          </button>
        </div>

        <div className='grid gap-3 md:grid-cols-3'>
          <TextField label='Swap Time' type='time' value={draft.swap_time} onChange={(value) => setField('swap_time', value)} />
          <SelectField label='Timezone' value={draft.swap_timezone} options={TIMEZONES} onChange={(value) => setField('swap_timezone', value)} />
          <NumberField label='Close Before Min' value={draft.swap_close_before_min} min={1} max={60} onChange={(value) => setField('swap_close_before_min', value)} />
          <NumberField label='Min Block After Min' value={draft.swap_min_block_after_min} min={1} max={360} onChange={(value) => setField('swap_min_block_after_min', value)} />
          <NumberField label='Max Block After Min' value={draft.swap_max_block_after_min} min={30} max={480} onChange={(value) => setField('swap_max_block_after_min', value)} />
          <NumberField label='Healthy Checks' value={draft.swap_recovery_consecutive_checks} min={1} max={10} onChange={(value) => setField('swap_recovery_consecutive_checks', value)} />
          <NumberField label='Recovery Window Sec' value={draft.swap_recovery_window_seconds} min={30} max={1800} onChange={(value) => setField('swap_recovery_window_seconds', value)} />
          <NumberField label='FX Max Spread' value={draft.swap_fx_max_spread} min={0.00001} step={0.00001} onChange={(value) => setField('swap_fx_max_spread', value)} />
          <NumberField label='JPY Max Spread' value={draft.swap_jpy_max_spread} min={0.001} step={0.001} onChange={(value) => setField('swap_jpy_max_spread', value)} />
          <NumberField label='Gold Max Spread' value={draft.swap_gold_max_spread} min={0.01} step={0.01} onChange={(value) => setField('swap_gold_max_spread', value)} />
          <NumberField label='Default Max Spread' value={draft.swap_default_max_spread} min={0.00001} step={0.00001} onChange={(value) => setField('swap_default_max_spread', value)} />
        </div>

        <label className='block space-y-1'>
          <span className='block font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>
            Symbol Overrides JSON
          </span>
          <textarea
            value={draft.swap_symbol_spread_overrides_json}
            onChange={(event) => setField('swap_symbol_spread_overrides_json', event.target.value)}
            rows={3}
            spellCheck={false}
            className='w-full resize-y rounded-md border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-2 font-mono text-xs text-[var(--to-text-primary)] outline-none transition focus:border-emerald-500/50'
          />
        </label>
      </div>
    </div>
  );
}
