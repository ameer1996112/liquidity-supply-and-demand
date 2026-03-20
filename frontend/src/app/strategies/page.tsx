'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  Loader2,
  Plus,
  Save,
  CheckCircle2,
  AlertTriangle,
  ToggleLeft,
  ToggleRight,
} from 'lucide-react';
import {
  API_BASE_URL,
  getStrategiesUrl,
  getStrategyDetailUrl,
  getStrategyActivateUrl,
} from '@/lib/api';
import { cn } from '@/lib/utils';

interface StrategyListItem {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  version: number;
  created_at?: string;
  updated_at?: string;
}

interface StrategyDetail extends StrategyListItem {
  description?: string | null;
  config: Record<string, unknown>;
}

interface ValidationErrorItem {
  field: string;
  message: string;
  type: string;
}

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<StrategyListItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<StrategyDetail | null>(null);
  const [configText, setConfigText] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationErrors, setValidationErrors] = useState<
    ValidationErrorItem[]
  >([]);
  const [message, setMessage] = useState<string | null>(null);

  const loadStrategies = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(getStrategiesUrl());
      const data = await res.json();
      setStrategies((data.strategies as StrategyListItem[]) || []);
    } catch (e) {
      console.error('Failed to load strategies', e);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadDetail = useCallback(async (id: number) => {
    setDetail(null);
    setValidationErrors([]);
    setMessage(null);
    try {
      const res = await fetch(getStrategyDetailUrl(id));
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = (await res.json()) as StrategyDetail;
      setDetail(data);
      setConfigText(JSON.stringify(data.config ?? {}, null, 2));
    } catch (e) {
      console.error('Failed to load strategy', e);
    }
  }, []);

  useEffect(() => {
    loadStrategies();
  }, [loadStrategies]);

  useEffect(() => {
    if (selectedId != null) {
      loadDetail(selectedId);
    }
  }, [selectedId, loadDetail]);

  const handleValidate = async () => {
    setValidating(true);
    setValidationErrors([]);
    setMessage(null);
    try {
      let parsed: unknown;
      try {
        parsed = JSON.parse(configText);
      } catch {
        throw new Error('Config must be valid JSON');
      }
      const res = await fetch(`${getStrategiesUrl()}/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: parsed }),
      });
      const data = await res.json();
      if (!data.valid) {
        setValidationErrors((data.errors as ValidationErrorItem[]) || []);
        setMessage('Config has validation errors.');
      } else {
        setMessage('Config is valid.');
      }
    } catch (e: unknown) {
      setMessage(e instanceof Error ? e.message : 'Validation failed');
    } finally {
      setValidating(false);
    }
  };

  const handleSave = async () => {
    if (!detail) return;
    setSaving(true);
    setValidationErrors([]);
    setMessage(null);
    try {
      let parsed: unknown;
      try {
        parsed = JSON.parse(configText);
      } catch {
        throw new Error('Config must be valid JSON before saving');
      }
      const res = await fetch(getStrategyDetailUrl(detail.id), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: detail.name,
          description: detail.description,
          config: parsed,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        const errors = (data.detail && data.detail.errors) || [];
        setValidationErrors(errors as ValidationErrorItem[]);
        setMessage('Save failed: invalid config');
      } else {
        setDetail(data as StrategyDetail);
        setMessage('Strategy saved with new version.');
        await loadStrategies();
      }
    } catch (e: unknown) {
      setMessage(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleActivate = async (id: number, active: boolean) => {
    setMessage(null);
    try {
      const res = await fetch(getStrategyActivateUrl(id, active), {
        method: 'PATCH',
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      await loadStrategies();
      if (selectedId === id) {
        await loadDetail(id);
      }
    } catch (e: unknown) {
      setMessage(e instanceof Error ? e.message : 'Activation failed');
    }
  };

  const handleCreateEmpty = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const res = await fetch(getStrategiesUrl(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'New Strategy',
          description: 'Edit config JSON in Strategy Studio',
          config: {
            name: 'New Strategy',
            signal_filters: { symbols: [], exclude_symbols: [], sessions: [] },
            risk: { name: 'balanced', risk_percent: 0.5, min_rr_ratio: 0.0 },
            ai: {
              mode: 'shadow',
              debate: { enabled: true, rounds: 1, min_confidence: 60 },
            },
            execution_routing: [],
          },
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `HTTP ${res.status}`);
      }
      await loadStrategies();
      setSelectedId(data.id);
      setMessage('New strategy created.');
    } catch (e: unknown) {
      setMessage(e instanceof Error ? e.message : 'Create failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className='flex gap-4 h-full animate-fade-in-up'>
      {/* Left: strategy list */}
      <div className='w-64 flex flex-col glow-card p-3 space-y-3'>
        <div className='flex items-center justify-between'>
          <span className='text-xs font-mono text-[var(--to-text-dim)] uppercase tracking-wider'>
            Strategies
          </span>
          <button
            onClick={handleCreateEmpty}
            disabled={saving}
            className={cn(
              'flex items-center gap-1.5 px-2 py-1 rounded text-[11px] font-mono',
              'bg-[var(--to-long)]/10 text-[var(--to-long)] hover:bg-[var(--to-long)]/20 disabled:opacity-50',
            )}
          >
            <Plus className='w-3 h-3' />
            New
          </button>
        </div>
        {loading ? (
          <div className='flex-1 flex items-center justify-center'>
            <Loader2 className='w-4 h-4 animate-spin text-[var(--to-text-dim)]' />
          </div>
        ) : strategies.length === 0 ? (
          <div className='text-xs text-[var(--to-text-dim)] font-mono'>
            No strategies defined. Create one to begin.
          </div>
        ) : (
          <div className='flex-1 overflow-y-auto space-y-1'>
            {strategies.map((s) => (
              <button
                key={s.id}
                onClick={() => setSelectedId(s.id)}
                className={cn(
                  'w-full text-left px-2 py-1.5 rounded text-xs font-mono flex items-center justify-between gap-2',
                  selectedId === s.id
                    ? 'bg-[var(--to-long)]/10 text-[var(--to-long)] border border-[var(--to-long)]/30'
                    : 'bg-[var(--to-surface)] text-[var(--to-text-dim)] border border-[var(--to-border)] hover:bg-[var(--to-surface-raised)]',
                )}
              >
                <span className='truncate'>{s.name}</span>
                <span
                  className={cn(
                    'flex items-center gap-1 text-[10px]',
                    s.is_active ? 'text-[var(--to-long)]' : 'text-[var(--to-text-dim)]',
                  )}
                >
                  v{s.version}
                  {s.is_active && <CheckCircle2 className='w-3 h-3' />}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Right: editor */}
      <div className='flex-1 flex flex-col glow-card p-4 space-y-3'>
        <div className='flex items-center justify-between'>
          <div>
            <h1 className='page-title text-sm font-semibold'>
              Strategy Studio
            </h1>
            <p className='page-subtitle mt-0.5 text-[11px]'>
              Edit strategy-as-data config (JSON) with validation.
            </p>
          </div>
          {detail && (
            <button
              onClick={() => handleActivate(detail.id, !detail.is_active)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-mono',
                detail.is_active
                  ? 'bg-[var(--to-long)]/10 text-[var(--to-long)] hover:bg-[var(--to-long)]/20'
                  : 'bg-[var(--to-surface-raised)] text-[var(--to-text-secondary)] hover:bg-[var(--to-surface-raised)]/80',
              )}
            >
              {detail.is_active ? (
                <>
                  <ToggleRight className='w-3.5 h-3.5' />
                  Active
                </>
              ) : (
                <>
                  <ToggleLeft className='w-3.5 h-3.5' />
                  Inactive
                </>
              )}
            </button>
          )}
        </div>

        {message && (
          <div className='flex items-center gap-2 text-[11px] font-mono px-3 py-2 rounded border border-[var(--to-border)] bg-[var(--to-surface)] text-[var(--to-text-secondary)]'>
            <AlertTriangle className='w-3.5 h-3.5 text-amber-400' />
            <span>{message}</span>
          </div>
        )}

        {validationErrors.length > 0 && (
          <div className='bg-red-500/5 border border-red-500/30 rounded p-3 space-y-1'>
            {validationErrors.map((e) => (
              <div
                key={`${e.field}-${e.message}`}
                className='text-[11px] font-mono text-[var(--to-short)]'
              >
                <span className='font-semibold'>{e.field || '(root)'}:</span>{' '}
                {e.message}
              </div>
            ))}
          </div>
        )}

        {!detail ? (
          <div className='flex-1 flex items-center justify-center text-xs text-[var(--to-text-dim)] font-mono'>
            Select a strategy on the left or create a new one.
          </div>
        ) : (
          <>
            <div className='flex items-center justify-between'>
              <div className='text-[11px] text-[var(--to-text-secondary)] font-mono'>
                ID #{detail.id} · v{detail.version}{' '}
                {detail.is_active ? '· ACTIVE' : '· INACTIVE'}
              </div>
              <div className='flex items-center gap-2'>
                <button
                  onClick={handleValidate}
                  disabled={validating}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-mono',
                    'bg-[var(--to-surface-raised)] text-[var(--to-text-primary)] hover:bg-[var(--to-surface-raised)]/80 disabled:opacity-50',
                  )}
                >
                  {validating && (
                    <Loader2 className='w-3.5 h-3.5 animate-spin' />
                  )}
                  Validate
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-mono',
                    'bg-[var(--to-long)] text-white hover:bg-[var(--to-long)]/80 disabled:opacity-50',
                  )}
                >
                  {saving ? (
                    <Loader2 className='w-3.5 h-3.5 animate-spin' />
                  ) : (
                    <Save className='w-3.5 h-3.5' />
                  )}
                  Save
                </button>
              </div>
            </div>

            <textarea
              id='strategy-config-editor'
              value={configText}
              onChange={(e) => setConfigText(e.target.value)}
              className={cn(
                'flex-1 w-full bg-[var(--to-surface)] border border-[var(--to-border)] rounded-lg px-3 py-2',
                'font-mono text-[11px] text-[var(--to-text-primary)] resize-none',
                'focus:outline-none focus:border-[var(--to-long)]/60',
              )}
              rows={24}
              spellCheck={false}
            />
          </>
        )}
      </div>
    </div>
  );
}
