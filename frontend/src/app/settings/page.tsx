'use client';

import { ConnectionStatus } from '@/components/settings/ConnectionStatus';
import { ConfigDisplay } from '@/components/settings/ConfigDisplay';
import { AiConfigPanel } from '@/components/settings/AiConfigPanel';
import { SystemHealthPanel } from '@/components/settings/SystemHealthPanel';
import { AlertRulesPanel } from '@/components/settings/AlertRulesPanel';
import { Info, Layers } from 'lucide-react';

export default function SettingsPage() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';

  return (
    <div className="space-y-6">
      {/* Header */}
      <h1 className="text-lg font-semibold text-zinc-100">Settings</h1>

      {/* Connection Status */}
      <ConnectionStatus />

      {/* AI / ML / RAG Configuration */}
      <AiConfigPanel />

      {/* System Health (DLQ, Queue, Redis) */}
      <SystemHealthPanel />

      {/* Alert Rules */}
      <AlertRulesPanel />

      {/* Environment Config */}
      <ConfigDisplay
        title="Environment"
        items={[
          { key: 'SUPABASE_URL', value: supabaseUrl, sensitive: true },
          { key: 'SUPABASE_KEY', value: supabaseKey, sensitive: true },
          { key: 'API_URL', value: apiUrl },
          { key: 'NODE_ENV', value: process.env.NODE_ENV || 'development' },
        ]}
      />

      {/* Infrastructure */}
      <div className="tv-card">
        <div className="px-4 py-3 border-b border-[#2a2e39]">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-zinc-500" />
            <span className="font-mono text-xs text-zinc-400 uppercase tracking-wider">
              Infrastructure
            </span>
          </div>
        </div>
        <div className="divide-y divide-[#2a2e39]">
          <div className="px-4 py-2.5 flex items-center justify-between">
            <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-mono">Hosting</span>
            <span className="font-mono text-xs text-zinc-300">Railway</span>
          </div>
          <div className="px-4 py-2.5 flex items-center justify-between">
            <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-mono">Broker</span>
            <span className="font-mono text-xs text-zinc-300">MetaAPI (MT5)</span>
          </div>
          <div className="px-4 py-2.5 flex items-center justify-between">
            <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-mono">Database</span>
            <span className="font-mono text-xs text-zinc-300">Supabase (PostgreSQL)</span>
          </div>
          <div className="px-4 py-2.5 flex items-center justify-between">
            <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-mono">Realtime</span>
            <span className="font-mono text-xs text-zinc-300">Supabase Realtime (WebSocket)</span>
          </div>
        </div>
      </div>

      {/* Tech Stack */}
      <div className="tv-card">
        <div className="px-4 py-3 border-b border-[#2a2e39]">
          <div className="flex items-center gap-2">
            <Info className="w-4 h-4 text-zinc-500" />
            <span className="font-mono text-xs text-zinc-400 uppercase tracking-wider">
              Tech Stack
            </span>
          </div>
        </div>
        <div className="divide-y divide-[#2a2e39]">
          <div className="px-4 py-2.5 flex items-center justify-between">
            <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-mono">Frontend</span>
            <span className="font-mono text-xs text-zinc-300">Next.js 16 + React 19</span>
          </div>
          <div className="px-4 py-2.5 flex items-center justify-between">
            <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-mono">Backend</span>
            <span className="font-mono text-xs text-zinc-300">Python FastAPI + Redis</span>
          </div>
          <div className="px-4 py-2.5 flex items-center justify-between">
            <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-mono">UI</span>
            <span className="font-mono text-xs text-zinc-300">Tailwind CSS v4 + Shadcn/ui</span>
          </div>
          <div className="px-4 py-2.5 flex items-center justify-between">
            <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-mono">Charts</span>
            <span className="font-mono text-xs text-zinc-300">Recharts v3</span>
          </div>
          <div className="px-4 py-2.5 flex items-center justify-between">
            <span className="text-[11px] text-zinc-500 uppercase tracking-wider font-mono">Execution</span>
            <span className="font-mono text-xs text-zinc-300">MetaAPI REST (MT5 Bridge)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
