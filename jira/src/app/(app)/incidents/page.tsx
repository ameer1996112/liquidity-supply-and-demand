'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, Bot, Bug, Cpu, FlaskConical, RefreshCw, CheckCheck, Clock } from 'lucide-react';
import { cn, relativeTime } from '@/lib/utils';

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

interface Incident {
  id: string;
  type: 'worker_error' | 'test_failure' | 'ml_drift' | 'watchdog_alert' | 'generic';
  title: string;
  summary: string;
  detail?: string;
  source: string;
  priority: 'P1' | 'P2' | 'P3' | 'P4';
  jira_key?: string;
  acked: boolean;
  created_at: string;
}

const TYPE_CONFIG: Record<Incident['type'], { label: string; icon: typeof Bug; color: string; bg: string }> = {
  worker_error:   { label: 'Worker Error',   icon: AlertTriangle, color: '#ef4444', bg: 'rgba(239,68,68,0.08)' },
  test_failure:   { label: 'Test Failure',   icon: FlaskConical,  color: '#f59e0b', bg: 'rgba(245,158,11,0.08)' },
  ml_drift:       { label: 'ML Drift',       icon: Cpu,           color: '#8b5cf6', bg: 'rgba(139,92,246,0.08)' },
  watchdog_alert: { label: 'Watchdog Alert', icon: Bot,           color: '#38bdf8', bg: 'rgba(56,189,248,0.08)' },
  generic:        { label: 'Incident',       icon: AlertTriangle, color: '#94a3b8', bg: 'rgba(148,163,184,0.08)' },
};

const PRIORITY_COLOR: Record<Incident['priority'], string> = {
  P1: '#ef4444',
  P2: '#f59e0b',
  P3: '#3b82f6',
  P4: '#475569',
};

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/incidents?limit=100`);
      if (res.ok) {
        const data = await res.json();
        setIncidents(data.incidents ?? []);
      }
    } catch {
      // api unavailable
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  // Auto-refresh every 30s
  useEffect(() => {
    const t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, []);

  const ack = async (id: string) => {
    try {
      await fetch(`${API_BASE}/api/incidents/ack/${id}`, { method: 'POST' });
      setIncidents((prev) => prev.map((i) => i.id === id ? { ...i, acked: true } : i));
    } catch {/* ignore */}
  };

  const unacked = incidents.filter((i) => !i.acked);
  const acked   = incidents.filter((i) => i.acked);

  return (
    <div className="flex flex-col h-full">
      <header className="flex items-center justify-between border-b border-[#1f2335] px-6 py-3 shrink-0">
        <div className="flex items-center gap-3">
          <h1 className="text-[15px] font-bold font-mono text-[#e2e8f0]">Incidents</h1>
          {unacked.length > 0 && (
            <span className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-400">
              {unacked.length} active
            </span>
          )}
        </div>
        <button
          onClick={load}
          disabled={isLoading}
          className="p-1.5 rounded border border-[#1f2335] text-[#475569] hover:text-[#94a3b8] hover:border-[#2a2d3e] transition-colors"
        >
          <RefreshCw className={cn('h-3.5 w-3.5', isLoading && 'animate-spin')} />
        </button>
      </header>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Active incidents */}
        <section>
          <p className="text-[10px] font-mono uppercase tracking-widest text-[#475569] mb-3">Active ({unacked.length})</p>
          {unacked.length === 0 && !isLoading && (
            <div className="flex flex-col items-center py-12 gap-2">
              <CheckCheck className="h-6 w-6 text-emerald-400" />
              <p className="text-[12px] font-mono text-[#475569]">No active incidents</p>
            </div>
          )}
          <div className="space-y-2">
            {unacked.map((inc) => (
              <IncidentRow key={inc.id} inc={inc} expanded={expanded === inc.id} onExpand={() => setExpanded(expanded === inc.id ? null : inc.id)} onAck={() => ack(inc.id)} />
            ))}
          </div>
        </section>

        {/* Acknowledged */}
        {acked.length > 0 && (
          <section>
            <p className="text-[10px] font-mono uppercase tracking-widest text-[#475569] mb-3">Acknowledged ({acked.length})</p>
            <div className="space-y-2 opacity-50">
              {acked.slice(0, 10).map((inc) => (
                <IncidentRow key={inc.id} inc={inc} expanded={false} onExpand={() => {}} onAck={() => {}} />
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

function IncidentRow({ inc, expanded, onExpand, onAck }: {
  inc: Incident;
  expanded: boolean;
  onExpand: () => void;
  onAck: () => void;
}) {
  const cfg = TYPE_CONFIG[inc.type];
  const Icon = cfg.icon;

  return (
    <div
      className="rounded-xl border border-[#1f2335] overflow-hidden transition-colors hover:border-[#2a2d3e]"
      style={{ background: cfg.bg }}
    >
      <div className="flex items-center gap-3 p-3 cursor-pointer" onClick={onExpand}>
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg" style={{ background: cfg.color + '20', border: `1px solid ${cfg.color}30` }}>
          <Icon className="h-3.5 w-3.5" style={{ color: cfg.color }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono font-bold" style={{ color: PRIORITY_COLOR[inc.priority] }}>{inc.priority}</span>
            <p className="text-[12px] font-medium text-[#e2e8f0] truncate">{inc.title}</p>
          </div>
          <p className="text-[10px] font-mono text-[#475569] mt-0.5">{inc.source} · {relativeTime(inc.created_at)}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {inc.jira_key && (
            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-[#2a2d3e] text-[#94a3b8]">{inc.jira_key}</span>
          )}
          {!inc.acked && (
            <button
              onClick={(e) => { e.stopPropagation(); onAck(); }}
              className="text-[9px] font-mono px-2 py-0.5 rounded border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 transition-colors"
            >
              Ack
            </button>
          )}
        </div>
      </div>
      {expanded && inc.detail && (
        <div className="px-3 pb-3 border-t border-[#1f2335]/50 mt-1 pt-2">
          <pre className="text-[10px] font-mono text-[#94a3b8] whitespace-pre-wrap break-words max-h-40 overflow-y-auto bg-[#0d0f14] rounded p-2">
            {inc.detail.slice(0, 1000)}
          </pre>
        </div>
      )}
    </div>
  );
}
