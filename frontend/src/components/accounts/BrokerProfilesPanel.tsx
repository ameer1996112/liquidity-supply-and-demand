'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Server,
  Plus,
  Trash2,
  CheckCircle2,
  XCircle,
  Loader2,
  RadioTower,
  Eye,
  EyeOff,
  Pencil,
  Zap,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/utils';

// ── API helpers ──────────────────────────────────────────────────────────────

const rawApiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_BASE = rawApiUrl.replace(/\/$/, '');

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
}

async function fetchProfiles(): Promise<BrokerProfile[]> {
  const r = await fetch(`${API_BASE}/api/broker-profiles`);
  if (!r.ok) throw new Error('Failed to load broker profiles');
  return r.json();
}

async function createProfile(body: {
  name: string;
  meta_api_account_id: string;
  token: string;
  risk_pct: number;
  max_positions: number;
  run_mode: string;
}): Promise<BrokerProfile> {
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

async function activateProfile(id: number): Promise<BrokerProfile> {
  const r = await fetch(`${API_BASE}/api/broker-profiles/${id}/activate`, { method: 'POST' });
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(e.detail || 'Activate failed');
  }
  return r.json();
}

async function testProfile(id: number): Promise<{ success: boolean; message: string; account_name?: string }> {
  const r = await fetch(`${API_BASE}/api/broker-profiles/${id}/test`, { method: 'POST' });
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(e.detail || 'Test failed');
  }
  return r.json();
}

// ── Sub-components ────────────────────────────────────────────────────────────

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
      <span
        className="inline-flex items-center gap-1 text-[10px] font-medium text-[var(--to-short)] bg-[var(--to-short)]/10 border border-[var(--to-short)]/20 rounded px-1.5 py-0.5 cursor-help"
        title={error || 'Connection error'}
      >
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

function AddProfileForm({ onSuccess, onCancel }: { onSuccess: () => void; onCancel: () => void }) {
  const [form, setForm] = useState({
    name: '',
    meta_api_account_id: '',
    token: '',
    risk_pct: 1.0,
    max_positions: 3,
    run_mode: 'LIVE',
  });
  const [showToken, setShowToken] = useState(false);
  const qc = useQueryClient();
  const { addToast } = useToast();

  const create = useMutation({
    mutationFn: createProfile,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-profiles'] });
      addToast({ title: 'Account added', message: `${form.name} is ready to configure.`, severity: 'success' });
      onSuccess();
    },
    onError: (e: Error) => {
      addToast({ title: 'Failed to add account', message: e.message, severity: 'critical' });
    },
  });

  const invalid = !form.name || !form.meta_api_account_id || !form.token;

  return (
    <div className="border border-[var(--to-warning)]/30 rounded-xl bg-[var(--to-warning)]/5 p-4 space-y-3">
      <h3 className="text-xs font-semibold text-[var(--to-text-primary)] flex items-center gap-2">
        <Plus className="h-3.5 w-3.5 text-[var(--to-warning)]" /> Add MetaAPI Account
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">Name</label>
          <input
            className="w-full bg-[var(--to-surface)] border border-[var(--to-border)] rounded-lg px-3 py-2 text-xs text-[var(--to-text-primary)] focus:outline-none focus:border-[var(--to-warning)]/50"
            placeholder="IC Markets Live"
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          />
        </div>
        <div className="space-y-1">
          <label className="text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">MetaAPI Account ID</label>
          <input
            className="w-full bg-[var(--to-surface)] border border-[var(--to-border)] rounded-lg px-3 py-2 text-xs font-mono text-[var(--to-text-primary)] focus:outline-none focus:border-[var(--to-warning)]/50"
            placeholder="a09b89c3-cf09-45e7-..."
            value={form.meta_api_account_id}
            onChange={(e) => setForm((f) => ({ ...f, meta_api_account_id: e.target.value }))}
          />
        </div>
        <div className="space-y-1 sm:col-span-2">
          <label className="text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">MetaAPI Token</label>
          <div className="relative">
            <input
              className="w-full bg-[var(--to-surface)] border border-[var(--to-border)] rounded-lg px-3 py-2 pr-9 text-xs font-mono text-[var(--to-text-primary)] focus:outline-none focus:border-[var(--to-warning)]/50"
              placeholder="eyJ0eXAiOiJKV1Q..."
              type={showToken ? 'text' : 'password'}
              value={form.token}
              onChange={(e) => setForm((f) => ({ ...f, token: e.target.value }))}
            />
            <button
              type="button"
              onClick={() => setShowToken((v) => !v)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)]"
            >
              {showToken ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            </button>
          </div>
        </div>
        <div className="space-y-1">
          <label className="text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">Risk % per trade</label>
          <input
            className="w-full bg-[var(--to-surface)] border border-[var(--to-border)] rounded-lg px-3 py-2 text-xs text-[var(--to-text-primary)] focus:outline-none focus:border-[var(--to-warning)]/50"
            type="number"
            min="0.1"
            max="10"
            step="0.1"
            value={form.risk_pct}
            onChange={(e) => setForm((f) => ({ ...f, risk_pct: parseFloat(e.target.value) || 1.0 }))}
          />
        </div>
        <div className="space-y-1">
          <label className="text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">Max Positions</label>
          <input
            className="w-full bg-[var(--to-surface)] border border-[var(--to-border)] rounded-lg px-3 py-2 text-xs text-[var(--to-text-primary)] focus:outline-none focus:border-[var(--to-warning)]/50"
            type="number"
            min="1"
            max="20"
            value={form.max_positions}
            onChange={(e) => setForm((f) => ({ ...f, max_positions: parseInt(e.target.value) || 3 }))}
          />
        </div>
      </div>
      <div className="flex gap-2 pt-1">
        <Button
          size="sm"
          className="bg-[var(--to-warning)] text-black hover:bg-[var(--to-warning)]/90 text-xs h-7"
          disabled={invalid || create.isPending}
          onClick={() => create.mutate(form)}
        >
          {create.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
          {create.isPending ? 'Saving…' : 'Save Account'}
        </Button>
        <Button size="sm" variant="ghost" className="text-xs h-7" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function ProfileRow({ profile }: { profile: BrokerProfile }) {
  const qc = useQueryClient();
  const { addToast } = useToast();
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [isTesting, setIsTesting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const activate = useMutation({
    mutationFn: () => activateProfile(profile.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-profiles'] });
      addToast({ title: 'Account activated', message: `${profile.name} is now the active trading account.`, severity: 'success' });
    },
    onError: (e: Error) => {
      addToast({ title: 'Activate failed', message: e.message, severity: 'critical' });
    },
  });

  const remove = useMutation({
    mutationFn: () => deleteProfile(profile.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['broker-profiles'] });
      addToast({ title: 'Account deleted', message: `${profile.name} has been removed.`, severity: 'success' });
    },
    onError: (e: Error) => {
      addToast({ title: 'Delete failed', message: e.message, severity: 'critical' });
      setConfirmDelete(false);
    },
  });

  const handleTest = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const res = await testProfile(profile.id);
      setTestResult(res);
      qc.invalidateQueries({ queryKey: ['broker-profiles'] });
    } catch (e: unknown) {
      setTestResult({ success: false, message: e instanceof Error ? e.message : 'Test failed' });
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div
      className={cn(
        'rounded-xl border p-4 space-y-3 transition-colors',
        profile.selected_for_trading
          ? 'border-[var(--to-warning)]/40 bg-[var(--to-warning)]/5'
          : 'border-[var(--to-border)] bg-[var(--to-surface)]'
      )}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Server className={cn('h-4 w-4 shrink-0', profile.selected_for_trading ? 'text-[var(--to-warning)]' : 'text-[var(--to-text-dim)]')} />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-[var(--to-text-primary)] truncate">{profile.name}</span>
              {profile.selected_for_trading && (
                <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--to-warning)] bg-[var(--to-warning)]/15 border border-[var(--to-warning)]/25 rounded px-1.5 py-0.5">
                  Active
                </span>
              )}
            </div>
            <span className="text-[10px] font-mono text-[var(--to-text-dim)] truncate block">
              {profile.meta_api_account_id}
            </span>
          </div>
        </div>
        <ConnectionBadge status={profile.connection_status} error={profile.connection_error} />
      </div>

      {/* Metadata row */}
      <div className="flex flex-wrap items-center gap-3 text-[10px] text-[var(--to-text-dim)]" style={{ fontFamily: 'var(--font-mono)' }}>
        <span>Risk: {profile.risk_pct}%</span>
        <span>Max pos: {profile.max_positions}</span>
        <span>Mode: {profile.run_mode}</span>
        <span>Token: {profile.token_masked}</span>
        {profile.last_tested_at && (
          <span>Tested: {new Date(profile.last_tested_at).toLocaleDateString()}</span>
        )}
      </div>

      {/* Test result inline feedback */}
      {testResult && (
        <div
          className={cn(
            'text-[11px] rounded-lg px-3 py-2 border',
            testResult.success
              ? 'bg-[var(--to-long)]/10 border-[var(--to-long)]/20 text-[var(--to-long)]'
              : 'bg-[var(--to-short)]/10 border-[var(--to-short)]/20 text-[var(--to-short)]'
          )}
        >
          {testResult.success ? '✅ ' : '❌ '}{testResult.message}
        </div>
      )}

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          className="h-7 text-[11px] gap-1.5 border-[var(--to-border)] text-[var(--to-text-secondary)] hover:text-[var(--to-text-primary)]"
          disabled={isTesting}
          onClick={handleTest}
        >
          {isTesting ? <Loader2 className="h-3 w-3 animate-spin" /> : <RadioTower className="h-3 w-3" />}
          Test
        </Button>

        {!profile.selected_for_trading && (
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-[11px] gap-1.5 border-[var(--to-warning)]/30 text-[var(--to-warning)] hover:bg-[var(--to-warning)]/10"
            disabled={activate.isPending}
            onClick={() => activate.mutate()}
          >
            {activate.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Zap className="h-3 w-3" />}
            Activate
          </Button>
        )}

        {confirmDelete ? (
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] text-[var(--to-short)]">Confirm delete?</span>
            <Button
              size="sm"
              className="h-6 text-[10px] bg-[var(--to-short)] text-white hover:bg-[var(--to-short)]/90"
              disabled={remove.isPending}
              onClick={() => remove.mutate()}
            >
              Yes, delete
            </Button>
            <Button size="sm" variant="ghost" className="h-6 text-[10px]" onClick={() => setConfirmDelete(false)}>
              Cancel
            </Button>
          </div>
        ) : (
          !profile.selected_for_trading && (
            <Button
              size="sm"
              variant="ghost"
              className="h-7 text-[11px] gap-1.5 text-[var(--to-text-dim)] hover:text-[var(--to-short)]"
              onClick={() => setConfirmDelete(true)}
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          )
        )}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function BrokerProfilesPanel() {
  const [showAdd, setShowAdd] = useState(false);
  const { data: profiles, isLoading, error } = useQuery<BrokerProfile[]>({
    queryKey: ['broker-profiles'],
    queryFn: fetchProfiles,
    refetchInterval: 30_000,
  });

  return (
    <div className="space-y-4">
      {/* Panel header */}
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
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs gap-1.5 border-[var(--to-warning)]/30 text-[var(--to-warning)] hover:bg-[var(--to-warning)]/10"
            onClick={() => setShowAdd(true)}
          >
            <Plus className="h-3.5 w-3.5" /> Add Account
          </Button>
        )}
      </div>

      {/* Description */}
      <p className="text-[11px] text-[var(--to-text-dim)] leading-relaxed">
        Store MetaAPI credentials securely in the database. Use <strong>Test</strong> to validate connectivity before
        trading, then <strong>Activate</strong> to route all new trades through that account. Credentials are encrypted
        at rest by Supabase and only the last 8 characters of the token are displayed.
      </p>

      {/* Add form */}
      {showAdd && (
        <AddProfileForm onSuccess={() => setShowAdd(false)} onCancel={() => setShowAdd(false)} />
      )}

      {/* Profile list */}
      {isLoading && (
        <div className="text-xs text-[var(--to-text-dim)] py-8 text-center">Loading accounts…</div>
      )}
      {error && (
        <div className="text-xs text-[var(--to-short)] py-4 text-center">
          Failed to load broker profiles — check API connectivity
        </div>
      )}
      {profiles && profiles.length === 0 && !showAdd && (
        <div className="rounded-xl border border-dashed border-[var(--to-border)] py-10 text-center">
          <Server className="h-8 w-8 text-[var(--to-text-dim)] mx-auto mb-3" />
          <p className="text-sm text-[var(--to-text-dim)]">No accounts configured</p>
          <p className="text-[11px] text-[var(--to-text-dim)] mt-1">
            Add your MetaAPI account to start trading without env vars
          </p>
        </div>
      )}
      {profiles && profiles.length > 0 && (
        <div className="space-y-3">
          {profiles.map((p) => (
            <ProfileRow key={p.id} profile={p} />
          ))}
        </div>
      )}

      {/* Run migration reminder */}
      <div className="rounded-lg border border-[var(--to-border)]/60 bg-[var(--to-surface-raised)]/50 px-3 py-2">
        <p className="text-[10px] text-[var(--to-text-dim)]">
          💡 <strong>First time?</strong> Run migration{' '}
          <code className="font-mono">migrations/060_broker_profiles_connection_status.sql</code> in your Supabase SQL
          editor to enable connection status tracking.
        </p>
      </div>
    </div>
  );
}
