'use client';

import { ConnectionStatus } from '@/components/settings/ConnectionStatus';
import { ConfigDisplay } from '@/components/settings/ConfigDisplay';
import { AiConfigPanel } from '@/components/settings/AiConfigPanel';
import { SystemHealthPanel } from '@/components/settings/SystemHealthPanel';
import { AlertRulesPanel } from '@/components/settings/AlertRulesPanel';
import { Info, Layers, Settings } from 'lucide-react';

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className='flex items-center justify-between border-b border-slate-800 px-3 py-2 last:border-0'>
      <span
        className='text-[10px] uppercase tracking-wider text-slate-500'
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        {label}
      </span>
      <span
        className='text-xs text-slate-300'
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        {value}
      </span>
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
          <Settings className='h-4 w-4 text-slate-400' />
          <h1 className='page-title text-lg font-semibold'>Settings</h1>
        </div>
        <p className='page-subtitle mt-0.5 text-xs'>
          System configuration, connections, and infrastructure.
        </p>
      </div>

      {/* Connection Status */}
      <ConnectionStatus />

      {/* AI / ML / RAG Configuration */}
      <AiConfigPanel />

      {/* System Health */}
      <SystemHealthPanel />

      {/* Alert Rules */}
      <AlertRulesPanel />

      {/* Environment Config */}
      <ConfigDisplay
        title='Environment'
        items={[
          { key: 'SUPABASE_URL', value: supabaseUrl, sensitive: true, critical: true },
          { key: 'SUPABASE_KEY', value: supabaseKey, sensitive: true, critical: true },
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
