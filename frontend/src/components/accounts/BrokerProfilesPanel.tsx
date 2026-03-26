'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Server, Plus, Trash2, CheckCircle2, XCircle, Loader2,
  RadioTower, Eye, EyeOff, Zap, ChevronRight, ChevronLeft,
  User, ClipboardList, Trophy, Copy, Check, Pencil, X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/utils';

// ── API helpers ──────────────────────────────────────────────────────────────

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');

export interface BrokerProfile {
  id: number;
  name: string;
  meta_api_account_id: string;
  token_masked: string;
  risk_pct: number;
  max_positions: number;
  run_mode: string;
  is_active: boolean;
  selected_for_trading: boolean;
  connection_status: 'unknown' | 'connected' | 'error';
  connection_error: string | null;
  last_tested_at: string | null;
  created_at: string | null;
  account_type: 'personal' | 'evaluation' | 'funded';
  prop_firm_name?: string | null;
  evaluation_phase?: string | null;
  max_daily_loss_pct?: number | null;
  max_drawdown_pct?: number | null;
  profit_target_usd?: number | null;
}

async function fetchProfiles(): Promise<BrokerProfile[]> {
  const r = await fetch(`${API_BASE}/api/broker-profiles`);
  if (!r.ok) throw new Error('Failed to load broker profiles');
  return r.json();
}

async function createProfile(body: Record<string, unknown>): Promise<BrokerProfile> {
  const r = await fetch(`${API_BASE}/api/broker-profiles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(e.detail || 'Create failed');
  }
  return r.json();
}

async function deleteProfile(id: number): Promise<void> {
  const r = await fetch(`${API_BASE}/api/broker-profiles/${id}`, { method: 'DELETE' });
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(e.detail || 'Delete failed');
  }
}

async function updateProfile(id: number, body: Record<string, unknown>): Promise<BrokerProfile> {
  const r = await fetch(`${API_BASE}/api/broker-profiles/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(e.detail || 'Update failed');
  }
  return r.json();
}

async function activateProfile(id: number): Promise<BrokerProfile> {
  const r = await fetch(`${API_BASE}/api/broker-profiles/${id}/activate`, { method: 'POST' });
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(e.detail || 'Activate failed');
  }
  return r.json();
}

async function testProfile(id: number): Promise<{ success: boolean; message: string }> {
  const r = await fetch(`${API_BASE}/api/broker-profiles/${id}/test`, { method: 'POST' });
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(e.detail || 'Test failed');
  }
  return r.json();
}

// ── Prop firm presets ────────────────────────────────────────────────────────

const PROP_FIRMS = [
  'FTMO', 'MyFundedFX', 'The Funded Trader', 'Apex Trader Funding',
  'E8 Markets', 'FundedNext', 'True Forex Funds', 'Maven Trading',
  'Lux Trading Firm', 'City Traders Imperium', 'Fidelcrest',
  'TopstepTrader', 'Earn2Trade', 'Funded Trading Plus', 'Alpha Capital Group',
];

function PropFirmSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [query, setQuery] = useState(value);
  const [open, setOpen] = useState(false);

  const filtered = PROP_FIRMS.filter(f => f.toLowerCase().includes(query.toLowerCase()));

  const select = (firm: string) => {
    setQuery(firm);
    onChange(firm);
    setOpen(false);
  };

  return (
    <div className="relative">
      <input
        className={inputCls}
        placeholder="Search prop firms…"
        value={query}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onChange={e => { setQuery(e.target.value); onChange(e.target.value); setOpen(true); }}
      />
      {open && filtered.length > 0 && (
        <div className="absolute z-20 mt-1 w-full rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)] shadow-lg overflow-hidden">
          {filtered.map(firm => (
            <button
              key={firm}
              type="button"
              onMouseDown={() => select(firm)}
              className={cn(
                'w-full px-3 py-2 text-left text-xs transition-colors hover:bg-[var(--to-warning)]/10',
                value === firm ? 'text-[var(--to-warning)] font-medium' : 'text-[var(--to-text-secondary)]'
              )}
            >
              {firm}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Types ─────────────────────────────────────────────────────────────────────

type AccountType = 'personal' | 'evaluation' | 'funded';
type WizardStep = 1 | 2 | 3;

interface WizardForm {
  accountType: AccountType;
  name: string;
  meta_api_account_id: string;
  token: string;
  risk_pct: number;
  max_positions: number;
  prop_firm_name: string;
  evaluation_phase: 'phase1' | 'phase2';
  max_daily_loss_pct: string;
  max_drawdown_pct: string;
  profit_target_usd: string;
}

function defaultForm(type: AccountType): WizardForm {
  return {
    accountType: type,
    name: '', meta_api_account_id: '', token: '',
    risk_pct: 1.0, max_positions: 3,
    prop_firm_name: '', evaluation_phase: 'phase1',
    max_daily_loss_pct: '', max_drawdown_pct: '', profit_target_usd: '',
  };
}

// ── Wizard sub-components ─────────────────────────────────────────────────────

const ACCOUNT_TYPE_OPTIONS: { type: AccountType; icon: typeof User; emoji: string; label: string; description: string }[] = [
  { type: 'personal', icon: User, emoji: '🧑', label: 'Personal', description: 'Your own live or demo account — no prop firm rules' },
  { type: 'evaluation', icon: ClipboardList, emoji: '📋', label: 'Evaluation', description: 'Phase 1 or 2 prop firm challenge with daily loss & profit target tracking' },
  { type: 'funded', icon: Trophy, emoji: '🏆', label: 'Funded', description: 'Passed your challenge — trading the real funded account' },
];

function StepIndicator({ step }: { step: WizardStep }) {
  const labels = ['Type', 'Details', 'Review'];
  return (
    <div className="flex items-center gap-1">
      {labels.map((label, i) => {
        const s = (i + 1) as WizardStep;
        const done = s < step;
        const active = s === step;
        return (
          <div key={s} className="flex items-center gap-1">
            <div className={cn(
              'flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold transition-colors',
              done ? 'bg-[var(--to-long)] text-black' : active ? 'bg-[var(--to-warning)] text-black' : 'bg-[var(--to-surface-raised)] text-[var(--to-text-dim)]'
            )}>
              {done ? '✓' : s}
            </div>
            {!active && done ? null : (
              <span className={cn('text-[10px] hidden sm:inline', active ? 'text-[var(--to-warning)]' : 'text-[var(--to-text-dim)]')}>{label}</span>
            )}
            {s < 3 && <ChevronRight className="h-3 w-3 text-[var(--to-border)] mx-0.5" />}
          </div>
        );
      })}
    </div>
  );
}

function TypePickerStep({ onSelect }: { onSelect: (t: AccountType) => void }) {
  return (
    <div className="space-y-3">
      <p className="text-[11px] text-[var(--to-text-dim)]">What kind of account is this?</p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {ACCOUNT_TYPE_OPTIONS.map((opt) => (
          <button
            key={opt.type}
            onClick={() => onSelect(opt.type)}
            className="group flex flex-col items-center gap-2.5 rounded-xl border border-[var(--to-border)] bg-[var(--to-surface)] p-5 text-center transition-all hover:border-[var(--to-warning)]/60 hover:bg-[var(--to-warning)]/5 hover:shadow-[0_0_16px_rgba(240,185,11,0.08)]"
          >
            <span className="text-3xl">{opt.emoji}</span>
            <span className="text-sm font-semibold text-[var(--to-text-primary)] group-hover:text-[var(--to-warning)] transition-colors">{opt.label}</span>
            <span className="text-[10px] text-[var(--to-text-dim)] leading-snug">{opt.description}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function InputField({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">
        {label}{required && <span className="text-[var(--to-warning)] ml-0.5">*</span>}
      </label>
      {children}
    </div>
  );
}

const inputCls = "w-full bg-[var(--to-surface)] border border-[var(--to-border)] rounded-lg px-3 py-2 text-xs text-[var(--to-text-primary)] focus:outline-none focus:border-[var(--to-warning)]/50 placeholder:text-[var(--to-text-dim)]";

function DetailsStep({ form, onChange, onBack, onNext }: {
  form: WizardForm;
  onChange: (f: WizardForm) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const [showToken, setShowToken] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const set = (patch: Partial<WizardForm>) => onChange({ ...form, ...patch });
  const isPropFirm = form.accountType !== 'personal';
  const isEval = form.accountType === 'evaluation';
  const invalid = !form.name || !form.meta_api_account_id || !form.token;

  return (
    <div className="space-y-4">
      {/* Account type badge */}
      <div className="inline-flex items-center gap-1.5 rounded-full bg-[var(--to-surface-raised)] border border-[var(--to-border)] px-3 py-1">
        <span>{ACCOUNT_TYPE_OPTIONS.find(o => o.type === form.accountType)?.emoji}</span>
        <span className="text-[11px] font-medium text-[var(--to-text-secondary)]">
          {ACCOUNT_TYPE_OPTIONS.find(o => o.type === form.accountType)?.label} Account
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {/* Shared fields */}
        <InputField label="Account Name" required>
          <input className={inputCls} placeholder={isPropFirm ? 'FTMO $50K Phase 1' : 'IC Markets Live'} value={form.name} onChange={e => set({ name: e.target.value })} />
        </InputField>

        {isPropFirm && (
          <InputField label="Prop Firm">
            <PropFirmSelect value={form.prop_firm_name} onChange={v => set({ prop_firm_name: v })} />
          </InputField>
        )}

        {isEval && (
          <InputField label="Phase">
            <div className="flex gap-2">
              {(['phase1', 'phase2'] as const).map(ph => (
                <button
                  key={ph}
                  type="button"
                  onClick={() => set({ evaluation_phase: ph })}
                  className={cn(
                    'flex-1 rounded-lg border py-2 text-xs font-medium transition-colors',
                    form.evaluation_phase === ph
                      ? 'border-[var(--to-warning)]/50 bg-[var(--to-warning)]/10 text-[var(--to-warning)]'
                      : 'border-[var(--to-border)] bg-[var(--to-surface)] text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]'
                  )}
                >
                  {ph === 'phase1' ? 'Phase 1' : 'Phase 2'}
                </button>
              ))}
            </div>
          </InputField>
        )}

        <InputField label="MetaAPI Account ID" required>
          <input className={cn(inputCls, 'font-mono')} placeholder="a09b89c3-cf09-45e7-…" value={form.meta_api_account_id} onChange={e => set({ meta_api_account_id: e.target.value })} />
        </InputField>

        <InputField label="MetaAPI Token" required>
          <div className="relative">
            <input
              className={cn(inputCls, 'font-mono pr-9')}
              placeholder="eyJ0eXAiOiJKV1Q…"
              type={showToken ? 'text' : 'password'}
              value={form.token}
              onChange={e => set({ token: e.target.value })}
            />
            <button type="button" onClick={() => setShowToken(v => !v)} className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)]">
              {showToken ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            </button>
          </div>
        </InputField>

        <InputField label="Risk % per trade">
          <input className={inputCls} type="number" min="0.1" max="10" step="0.1" value={form.risk_pct} onChange={e => set({ risk_pct: parseFloat(e.target.value) || 1 })} />
        </InputField>

        <InputField label="Max Positions">
          <input className={inputCls} type="number" min="1" max="20" value={form.max_positions} onChange={e => set({ max_positions: parseInt(e.target.value) || 3 })} />
        </InputField>
      </div>

      {/* Advanced risk rules for prop firm accounts */}
      {isPropFirm && (
        <div className="rounded-xl border border-[var(--to-border)]/60 bg-[var(--to-surface-raised)]/40">
          <button
            type="button"
            className="flex w-full items-center justify-between px-4 py-2.5 text-[11px] text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]"
            onClick={() => setShowAdvanced(v => !v)}
          >
            <span className="font-medium">Risk Rules <span className="opacity-60">(optional)</span></span>
            <ChevronRight className={cn('h-3 w-3 transition-transform', showAdvanced && 'rotate-90')} />
          </button>
          {showAdvanced && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 px-4 pb-4">
              <InputField label="Max Daily Loss %">
                <input className={inputCls} type="number" min="0" max="100" step="0.5" placeholder="5" value={form.max_daily_loss_pct} onChange={e => set({ max_daily_loss_pct: e.target.value })} />
              </InputField>
              <InputField label="Max Drawdown %">
                <input className={inputCls} type="number" min="0" max="100" step="0.5" placeholder="10" value={form.max_drawdown_pct} onChange={e => set({ max_drawdown_pct: e.target.value })} />
              </InputField>
              {isEval && (
                <InputField label="Profit Target $">
                  <input className={inputCls} type="number" min="0" step="100" placeholder="5000" value={form.profit_target_usd} onChange={e => set({ profit_target_usd: e.target.value })} />
                </InputField>
              )}
            </div>
          )}
        </div>
      )}

      <div className="flex gap-2 pt-1">
        <Button variant="ghost" size="sm" className="h-7 text-xs gap-1" onClick={onBack}>
          <ChevronLeft className="h-3.5 w-3.5" /> Back
        </Button>
        <Button size="sm" className="h-7 text-xs gap-1 bg-[var(--to-warning)] text-black hover:bg-[var(--to-warning)]/90" disabled={invalid} onClick={onNext}>
          Review <ChevronRight className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}

function ReviewStep({ form, onBack, onSave, isSaving }: {
  form: WizardForm;
  onBack: () => void;
  onSave: () => void;
  isSaving: boolean;
}) {
  const typeInfo = ACCOUNT_TYPE_OPTIONS.find(o => o.type === form.accountType)!;
  const rows = [
    { label: 'Type', value: `${typeInfo.emoji} ${typeInfo.label}` },
    { label: 'Name', value: form.name },
    ...(form.prop_firm_name ? [{ label: 'Prop Firm', value: form.prop_firm_name }] : []),
    ...(form.accountType === 'evaluation' ? [{ label: 'Phase', value: form.evaluation_phase === 'phase1' ? 'Phase 1' : 'Phase 2' }] : []),
    { label: 'Account ID', value: `${form.meta_api_account_id.slice(0, 8)}…` },
    { label: 'Token', value: `••••••••${form.token.slice(-4)}` },
    { label: 'Risk %', value: `${form.risk_pct}%` },
    { label: 'Max Positions', value: String(form.max_positions) },
    ...(form.max_daily_loss_pct ? [{ label: 'Max Daily Loss', value: `${form.max_daily_loss_pct}%` }] : []),
    ...(form.max_drawdown_pct ? [{ label: 'Max Drawdown', value: `${form.max_drawdown_pct}%` }] : []),
    ...(form.profit_target_usd ? [{ label: 'Profit Target', value: `$${form.profit_target_usd}` }] : []),
  ];

  return (
    <div className="space-y-4">
      <p className="text-[11px] text-[var(--to-text-dim)]">Confirm your account details before saving.</p>
      <div className="rounded-xl border border-[var(--to-border)] divide-y divide-[var(--to-border)] overflow-hidden">
        {rows.map(r => (
          <div key={r.label} className="flex items-center justify-between px-4 py-2.5">
            <span className="text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">{r.label}</span>
            <span className="text-xs font-mono text-[var(--to-text-primary)]">{r.value}</span>
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <Button variant="ghost" size="sm" className="h-7 text-xs gap-1" onClick={onBack} disabled={isSaving}>
          <ChevronLeft className="h-3.5 w-3.5" /> Back
        </Button>
        <Button size="sm" className="h-7 text-xs gap-1.5 bg-[var(--to-warning)] text-black hover:bg-[var(--to-warning)]/90" disabled={isSaving} onClick={onSave}>
          {isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
          {isSaving ? 'Saving…' : 'Save Account'}
        </Button>
      </div>
    </div>
  );
}

function AddAccountWizard({ onSuccess, onCancel }: { onSuccess: () => void; onCancel: () => void }) {
  const [step, setStep] = useState<WizardStep>(1);
  const [form, setForm] = useState<WizardForm | null>(null);
  const qc = useQueryClient();
  const { addToast } = useToast();

  const save = useMutation({
    mutationFn: (f: WizardForm) => createProfile({
      name: f.name,
      meta_api_account_id: f.meta_api_account_id,
      token: f.token,
      risk_pct: f.risk_pct,
      max_positions: f.max_positions,
      account_type: f.accountType,
      prop_firm_name: f.prop_firm_name || undefined,
      evaluation_phase: f.accountType === 'funded' ? 'funded' : f.evaluation_phase,
      max_daily_loss_pct: f.max_daily_loss_pct ? parseFloat(f.max_daily_loss_pct) : undefined,
      max_drawdown_pct: f.max_drawdown_pct ? parseFloat(f.max_drawdown_pct) : undefined,
      profit_target_usd: f.profit_target_usd ? parseFloat(f.profit_target_usd) : undefined,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-profiles'] });
      addToast({ title: 'Account added', message: 'Your new account is ready.', severity: 'success' });
      onSuccess();
    },
    onError: (e: Error) => addToast({ title: 'Failed to save', message: e.message, severity: 'critical' }),
  });

  return (
    <div className="border border-[var(--to-warning)]/30 rounded-xl bg-[var(--to-warning)]/5 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-[var(--to-text-primary)] flex items-center gap-2">
          <Plus className="h-3.5 w-3.5 text-[var(--to-warning)]" /> Add MetaAPI Account
        </h3>
        <StepIndicator step={step} />
      </div>

      {step === 1 && (
        <>
          <TypePickerStep onSelect={(t) => { setForm(defaultForm(t)); setStep(2); }} />
          <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={onCancel}>Cancel</Button>
        </>
      )}
      {step === 2 && form && (
        <DetailsStep form={form} onChange={setForm} onBack={() => setStep(1)} onNext={() => setStep(3)} />
      )}
      {step === 3 && form && (
        <ReviewStep form={form} onBack={() => setStep(2)} onSave={() => save.mutate(form)} isSaving={save.isPending} />
      )}
    </div>
  );
}

// ── Profile Row ────────────────────────────────────────────────────────────────

function ConnectionBadge({ status, error }: { status: BrokerProfile['connection_status']; error: string | null }) {
  if (status === 'connected') {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] font-medium text-[var(--to-long)] bg-[var(--to-long)]/10 border border-[var(--to-long)]/20 rounded px-1.5 py-0.5">
        <CheckCircle2 className="h-3 w-3" /> Connected
      </span>
    );
  }
  if (status === 'error') {
    return (
      <span title={error || 'Connection error'} className="inline-flex items-center gap-1 text-[10px] font-medium text-[var(--to-short)] bg-[var(--to-short)]/10 border border-[var(--to-short)]/20 rounded px-1.5 py-0.5 cursor-help">
        <XCircle className="h-3 w-3" /> Error
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-medium text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] border border-[var(--to-border)] rounded px-1.5 py-0.5">
      <RadioTower className="h-3 w-3" /> Unknown
    </span>
  );
}

function AccountTypeBadge({ type }: { type: BrokerProfile['account_type'] }) {
  const opts = { personal: { emoji: '🧑', label: 'Personal' }, evaluation: { emoji: '📋', label: 'Eval' }, funded: { emoji: '🏆', label: 'Funded' } };
  const opt = opts[type] ?? opts.personal;
  return (
    <span className="inline-flex items-center gap-1 text-[9px] font-medium text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] border border-[var(--to-border)] rounded px-1.5 py-0.5">
      {opt.emoji} {opt.label}
    </span>
  );
}

function ProfileRow({ profile }: { profile: BrokerProfile }) {
  const [copied, setCopied] = useState(false);
  const [editing, setEditing] = useState(false);
  const copyAccountId = () => {
    navigator.clipboard.writeText(profile.meta_api_account_id).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };
  const qc = useQueryClient();
  const { addToast } = useToast();
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [isTesting, setIsTesting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  // Edit form state
  const [editForm, setEditForm] = useState({
    name: profile.name,
    meta_api_account_id: profile.meta_api_account_id,
    token: '',
    risk_pct: profile.risk_pct,
    max_positions: profile.max_positions,
  });
  const [showEditToken, setShowEditToken] = useState(false);

  const update = useMutation({
    mutationFn: () => updateProfile(profile.id, {
      name: editForm.name || undefined,
      meta_api_account_id: editForm.meta_api_account_id || undefined,
      ...(editForm.token ? { token: editForm.token } : {}),
      risk_pct: editForm.risk_pct,
      max_positions: editForm.max_positions,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-profiles'] });
      addToast({ title: 'Account updated', message: `${profile.name} saved.`, severity: 'success' });
      setEditing(false);
    },
    onError: (e: Error) => addToast({ title: 'Update failed', message: e.message, severity: 'critical' }),
  });

  const activate = useMutation({
    mutationFn: () => activateProfile(profile.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-profiles'] });
      addToast({ title: 'Account activated', message: `${profile.name} is now the active trading account.`, severity: 'success' });
    },
    onError: (e: Error) => addToast({ title: 'Activate failed', message: e.message, severity: 'critical' }),
  });

  const remove = useMutation({
    mutationFn: () => deleteProfile(profile.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-profiles'] });
      addToast({ title: 'Account deleted', message: `${profile.name} removed.`, severity: 'success' });
    },
    onError: (e: Error) => { addToast({ title: 'Delete failed', message: e.message, severity: 'critical' }); setConfirmDelete(false); },
  });

  const handleTest = async () => {
    setIsTesting(true); setTestResult(null);
    try {
      const res = await testProfile(profile.id);
      setTestResult(res);
      qc.invalidateQueries({ queryKey: ['broker-profiles'] });
    } catch (e: unknown) {
      setTestResult({ success: false, message: e instanceof Error ? e.message : 'Test failed' });
    } finally { setIsTesting(false); }
  };

  return (
    <div className={cn('rounded-xl border p-4 space-y-3 transition-colors', profile.selected_for_trading ? 'border-[var(--to-warning)]/40 bg-[var(--to-warning)]/5' : 'border-[var(--to-border)] bg-[var(--to-surface)]')}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Server className={cn('h-4 w-4 shrink-0', profile.selected_for_trading ? 'text-[var(--to-warning)]' : 'text-[var(--to-text-dim)]')} />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-sm font-semibold text-[var(--to-text-primary)] truncate">{profile.name}</span>
              {profile.selected_for_trading && (
                <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--to-warning)] bg-[var(--to-warning)]/15 border border-[var(--to-warning)]/25 rounded px-1.5 py-0.5">Active</span>
              )}
              <AccountTypeBadge type={profile.account_type} />
              {profile.prop_firm_name && (
                <span className="text-[9px] text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] border border-[var(--to-border)] rounded px-1.5 py-0.5">{profile.prop_firm_name}</span>
              )}
            </div>
            <div className="flex items-center gap-1 group/id">
              <span className="text-[10px] font-mono text-[var(--to-text-dim)] truncate">{profile.meta_api_account_id}</span>
              <button
                type="button"
                title="Copy full account ID"
                onClick={copyAccountId}
                className="shrink-0 opacity-0 group-hover/id:opacity-100 transition-opacity text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)]"
              >
                {copied ? <Check className="h-3 w-3 text-[var(--to-long)]" /> : <Copy className="h-3 w-3" />}
              </button>
            </div>
          </div>
        </div>
        <ConnectionBadge status={profile.connection_status} error={profile.connection_error} />
      </div>

      <div className="flex flex-wrap gap-3 text-[10px] text-[var(--to-text-dim)]" style={{ fontFamily: 'var(--font-mono)' }}>
        <span>Risk: {profile.risk_pct}%</span>
        <span>Max pos: {profile.max_positions}</span>
        <span>Mode: {profile.run_mode}</span>
        <span>Token: {profile.token_masked}</span>
        {profile.evaluation_phase && profile.account_type !== 'personal' && (
          <span>Phase: {profile.evaluation_phase === 'funded' ? 'Funded' : profile.evaluation_phase === 'phase1' ? 'Phase 1' : 'Phase 2'}</span>
        )}
        {profile.last_tested_at && <span>Tested: {new Date(profile.last_tested_at).toLocaleDateString()}</span>}
      </div>

      {/* Inline edit form */}
      {editing && (
        <div className="rounded-xl border border-[var(--to-warning)]/25 bg-[var(--to-warning)]/5 p-3 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <InputField label="Name">
              <input className={inputCls} value={editForm.name} onChange={e => setEditForm(f => ({ ...f, name: e.target.value }))} />
            </InputField>
            <InputField label="Account ID">
              <input className={cn(inputCls, 'font-mono')} value={editForm.meta_api_account_id} onChange={e => setEditForm(f => ({ ...f, meta_api_account_id: e.target.value }))} />
            </InputField>
            <InputField label="New Token (leave blank to keep current)">
              <div className="relative">
                <input
                  className={cn(inputCls, 'font-mono pr-9')}
                  type={showEditToken ? 'text' : 'password'}
                  placeholder="Paste new token only if rotating…"
                  value={editForm.token}
                  onChange={e => setEditForm(f => ({ ...f, token: e.target.value }))}
                />
                <button type="button" onClick={() => setShowEditToken(v => !v)} className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)]">
                  {showEditToken ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
              </div>
            </InputField>
            <InputField label="Risk %">
              <input className={inputCls} type="number" min="0.1" max="10" step="0.1" value={editForm.risk_pct} onChange={e => setEditForm(f => ({ ...f, risk_pct: parseFloat(e.target.value) || 1 }))} />
            </InputField>
          </div>
          <div className="flex gap-2">
            <Button size="sm" className="h-7 text-xs bg-[var(--to-warning)] text-black" disabled={update.isPending} onClick={() => update.mutate()}>
              {update.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : null} Save Changes
            </Button>
            <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setEditing(false)}>Cancel</Button>
          </div>
        </div>
      )}
        <div className={cn('text-[11px] rounded-lg px-3 py-2 border', testResult?.success ? 'bg-[var(--to-long)]/10 border-[var(--to-long)]/20 text-[var(--to-long)]' : 'bg-[var(--to-short)]/10 border-[var(--to-short)]/20 text-[var(--to-short)]')}>
          {testResult?.success ? '✅ ' : '❌ '}{testResult?.message}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="outline" className="h-7 text-[11px] gap-1.5 border-[var(--to-border)] text-[var(--to-text-secondary)]" disabled={isTesting} onClick={handleTest}>
          {isTesting ? <Loader2 className="h-3 w-3 animate-spin" /> : <RadioTower className="h-3 w-3" />} Test
        </Button>
        <Button size="sm" variant="ghost" className="h-7 text-[11px] gap-1.5 text-[var(--to-text-dim)] hover:text-[var(--to-warning)]" onClick={() => { setEditing(v => !v); setTestResult(null); }}>
          {editing ? <X className="h-3 w-3" /> : <Pencil className="h-3 w-3" />}
          {editing ? 'Cancel' : 'Edit'}
        </Button>
        {!profile.selected_for_trading && (
          <Button size="sm" variant="outline" className="h-7 text-[11px] gap-1.5 border-[var(--to-warning)]/30 text-[var(--to-warning)] hover:bg-[var(--to-warning)]/10" disabled={activate.isPending} onClick={() => activate.mutate()}>
            {activate.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Zap className="h-3 w-3" />} Activate
          </Button>
        )}
        {confirmDelete ? (
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] text-[var(--to-short)]">Delete?</span>
            <Button size="sm" className="h-6 text-[10px] bg-[var(--to-short)] text-white" disabled={remove.isPending} onClick={() => remove.mutate()}>Yes</Button>
            <Button size="sm" variant="ghost" className="h-6 text-[10px]" onClick={() => setConfirmDelete(false)}>No</Button>
          </div>
        ) : !profile.selected_for_trading && (
          <Button size="sm" variant="ghost" className="h-7 text-[11px] gap-1.5 text-[var(--to-text-dim)] hover:text-[var(--to-short)]" onClick={() => setConfirmDelete(true)}>
            <Trash2 className="h-3 w-3" />
          </Button>
        )}
      </div>
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

export function BrokerProfilesPanel() {
  const [showAdd, setShowAdd] = useState(false);
  const { data: profiles, isLoading, error } = useQuery<BrokerProfile[]>({
    queryKey: ['broker-profiles'],
    queryFn: fetchProfiles,
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Server className="h-4 w-4 text-[var(--to-warning)]" />
          <h2 className="text-sm font-semibold text-[var(--to-text-primary)]">MetaAPI Broker Accounts</h2>
          {profiles && profiles.length > 0 && (
            <span className="text-[10px] text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] border border-[var(--to-border)] rounded px-1.5 py-0.5">
              {profiles.length} {profiles.length === 1 ? 'account' : 'accounts'}
            </span>
          )}
        </div>
        {!showAdd && (
          <Button size="sm" variant="outline" className="h-7 text-xs gap-1.5 border-[var(--to-warning)]/30 text-[var(--to-warning)] hover:bg-[var(--to-warning)]/10" onClick={() => setShowAdd(true)}>
            <Plus className="h-3.5 w-3.5" /> Add Account
          </Button>
        )}
      </div>

      <p className="text-[11px] text-[var(--to-text-dim)] leading-relaxed">
        Store MetaAPI credentials securely in the database. <strong>Test</strong> to validate connectivity, then <strong>Activate</strong> to route all new trades through that account.
      </p>

      {showAdd && <AddAccountWizard onSuccess={() => setShowAdd(false)} onCancel={() => setShowAdd(false)} />}

      {isLoading && <div className="text-xs text-[var(--to-text-dim)] py-8 text-center">Loading accounts…</div>}
      {error && <div className="text-xs text-[var(--to-short)] py-4 text-center">Failed to load broker profiles — check API connectivity</div>}
      {profiles && profiles.length === 0 && !showAdd && (
        <div className="rounded-xl border border-dashed border-[var(--to-border)] py-10 text-center">
          <Server className="h-8 w-8 text-[var(--to-text-dim)] mx-auto mb-3" />
          <p className="text-sm text-[var(--to-text-dim)]">No accounts configured</p>
          <p className="text-[11px] text-[var(--to-text-dim)] mt-1">Click "Add Account" to get started</p>
        </div>
      )}
      {profiles && profiles.length > 0 && (
        <div className="space-y-3">
          {profiles.map(p => <ProfileRow key={p.id} profile={p} />)}
        </div>
      )}
    </div>
  );
}
