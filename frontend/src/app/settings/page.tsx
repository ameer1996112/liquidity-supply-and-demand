'use client';

import { useState } from 'react';
import { ConnectionStatus } from '@/components/settings/ConnectionStatus';
import { ConfigDisplay } from '@/components/settings/ConfigDisplay';
import { AiConfigPanel } from '@/components/settings/AiConfigPanel';
import { SystemHealthPanel } from '@/components/settings/SystemHealthPanel';
import { AlertRulesPanel } from '@/components/settings/AlertRulesPanel';
import { Info, Layers, Settings, Globe, Check } from 'lucide-react';
import { useTimezone, TZ_OPTIONS } from '@/providers/TimezoneProvider';
import { cn } from '@/lib/utils';
import { syncAllAccounts } from '@/lib/api';

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className='flex items-center justify-between border-b border-[var(--to-border)] px-3 py-2 last:border-0'>
      <span
        className='text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]'
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        {label}
      </span>
      <span
        className='text-xs text-[var(--to-text-secondary)]'
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        {value}
      </span>
    </div>
  );
}

function TimezonePanel() {
  const { timezone, setTimezone, tzAbbr } = useTimezone();

  return (
    <div className='to-panel'>
      <div className='to-panel-header'>
        <div className='flex items-center gap-2'>
          <Globe className='h-3.5 w-3.5 text-text-dim' />
          <span
            className='panel-label'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            Display Timezone
          </span>
        </div>
        <span
          className='text-[10px] font-bold text-indigo-400 font-mono'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {tzAbbr}
        </span>
      </div>
      <div className='p-3'>
        <p
          className='mb-3 text-[11px] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          All timestamps, session times, and clocks across the dashboard will
          display in the selected timezone. Saved to your browser automatically.
        </p>
        <div className='grid grid-cols-1 gap-1.5 sm:grid-cols-2 lg:grid-cols-4'>
          {TZ_OPTIONS.map((opt) => {
            const isActive = timezone === opt.value;
            return (
              <button
                key={opt.value}
                type='button'
                onClick={() => setTimezone(opt.value)}
                className={cn(
                  'flex items-center justify-between rounded-lg border px-3 py-2.5 text-left transition-all',
                  isActive
                    ? 'border-indigo-500/40 bg-indigo-500/10 text-indigo-300'
                    : 'border-[var(--to-border)] bg-[var(--to-surface-raised)] text-[var(--to-text-secondary)] hover:border-white/10 hover:text-white'
                )}
              >
                <div>
                  <p
                    className='text-[11px] font-semibold'
                    style={{ fontFamily: 'var(--font-sans)' }}
                  >
                    {opt.label}
                  </p>
                  <p
                    className='text-[9px] font-mono text-[var(--to-text-dim)] mt-0.5'
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    {opt.value}
                  </p>
                </div>
                {isActive && (
                  <Check className='h-3.5 w-3.5 text-indigo-400 shrink-0' />
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function ManualSyncPanel() {
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const handleSync = async () => {
    if (isSyncing) return;
    setIsSyncing(true);
    setLastResult(null);
    try {
      const resp = await syncAllAccounts();
      const success = resp?.success_count ?? 0;
      const total = resp?.total_accounts ?? 0;
      setLastResult(`Synced ${success}/${total} accounts`);
    } catch (e) {
      setLastResult('Sync failed — check backend logs');
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <div className='to-panel'>
      <div className='to-panel-header'>
        <div className='flex items-center gap-2'>
          <Layers className='h-3.5 w-3.5 text-text-dim' />
          <span
            className='panel-label'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            Broker Sync Controls
          </span>
        </div>
      </div>
      <div className='flex items-center justify-between px-3 py-3 gap-3'>
        <div className='text-[11px] text-[var(--to-text-dim)]'>
          <p>
            Manually trigger a full MetaAPI account sync and reconciliation for
            all active accounts. Useful after fixing configuration or broker
            drift.
          </p>
          {lastResult && (
            <p className='mt-1 font-mono text-[10px] text-text-secondary'>
              {lastResult}
            </p>
          )}
        </div>
        <button
          type='button'
          onClick={handleSync}
          disabled={isSyncing}
          className='shrink-0 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-4 py-2 text-[11px] font-mono font-bold uppercase tracking-widest text-white hover:border-white/20 hover:bg-white/5 disabled:opacity-60'
        >
          {isSyncing ? 'Syncing…' : 'Sync All Accounts'}
        </button>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';

  return (
    <div className='space-y-4'>
      {/* Header */}
      <div>
        <div className='flex items-center gap-2'>
          <Settings className='h-4 w-4 text-[var(--to-text-dim)]' />
          <h1 className='page-title text-lg font-semibold'>Settings</h1>
        </div>
        <p className='page-subtitle mt-0.5 text-xs'>
          System configuration, connections, and infrastructure.
        </p>
      </div>

      {/* Timezone */}
      <TimezonePanel />

      {/* Connection Status */}
      <ConnectionStatus />

      {/* AI / ML / RAG Configuration */}
      <AiConfigPanel />

      {/* System Health */}
      <SystemHealthPanel />

      {/* Manual broker sync */}
      <ManualSyncPanel />

      {/* Alert Rules */}
      <AlertRulesPanel />

      {/* Environment Config */}
      <ConfigDisplay
        title='Environment'
        items={[
          {
            key: 'SUPABASE_URL',
            value: supabaseUrl,
            sensitive: true,
            critical: true,
          },
          {
            key: 'SUPABASE_KEY',
            value: supabaseKey,
            sensitive: true,
            critical: true,
          },
          { key: 'API_URL', value: apiUrl, critical: true },
          { key: 'NODE_ENV', value: process.env.NODE_ENV || 'development' },
        ]}
      />

      {/* Infrastructure */}
      <div className='to-panel'>
        <div className='to-panel-header'>
          <div className='flex items-center gap-2'>
            <Layers className='h-3.5 w-3.5 text-text-dim' />
            <span
              className='panel-label'
              style={{ fontFamily: 'var(--font-sans)' }}
            >
              Infrastructure
            </span>
          </div>
        </div>
        <div className='divide-y divide-panel-border-subtle'>
          <InfoRow label='Hosting' value='Railway' />
          <InfoRow label='Broker' value='MetaAPI (MT5)' />
          <InfoRow label='Database' value='Supabase (PostgreSQL)' />
          <InfoRow label='Realtime' value='Supabase Realtime (WebSocket)' />
        </div>
      </div>

      {/* Tech Stack */}
      <div className='to-panel'>
        <div className='to-panel-header'>
          <div className='flex items-center gap-2'>
            <Info className='h-3.5 w-3.5 text-text-dim' />
            <span
              className='panel-label'
              style={{ fontFamily: 'var(--font-sans)' }}
            >
              Tech Stack
            </span>
          </div>
        </div>
        <div className='divide-y divide-panel-border-subtle'>
          <InfoRow label='Frontend' value='Next.js 16 + React 19' />
          <InfoRow label='Backend' value='Python FastAPI + Redis' />
          <InfoRow label='UI' value='Tailwind CSS v4 + Shadcn/ui' />
          <InfoRow label='Charts' value='Recharts v3' />
          <InfoRow label='Execution' value='MetaAPI REST (MT5 Bridge)' />
        </div>
      </div>
    </div>
  );
}
