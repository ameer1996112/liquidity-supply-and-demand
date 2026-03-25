'use client';

import { useEffect, useState, useCallback } from 'react';
import { Bot, AlertCircle, Github, Ticket, TrendingUp, TrendingDown, ShieldX, RefreshCw, Zap, Activity } from 'lucide-react';
import { cn } from '@/lib/utils';

/* ──────────────────────────────────────────────────────────────
   Types
────────────────────────────────────────────────────────────── */
interface AgentEvent {
  type: string;
  message: string;
  timestamp: number;
  timestamp_iso?: string;
  jira_key?: string;
  symbol?: string;
  account?: string;
}

interface AgentStatus {
  status: 'active' | 'degraded';
  event_count: number;
  last_event_at: string | null;
  events: AgentEvent[];
}

/* ──────────────────────────────────────────────────────────────
   Event type definitions
────────────────────────────────────────────────────────────── */
interface EventConfig {
  icon: React.ElementType;
  label: string;
  color: string;
  glow: string;
  bg: string;
  border: string;
}

const EVENT_CONFIG: Record<string, EventConfig> = {
  trade_executed: {
    icon: TrendingUp,
    label: 'Trade Executed',
    color: 'text-[var(--to-long)]',
    glow: 'rgba(14,203,129,0.25)',
    bg: 'bg-[var(--to-long)]/10',
    border: 'border-[var(--to-long)]/30',
  },
  trade_rejected: {
    icon: TrendingDown,
    label: 'Trade Rejected',
    color: 'text-[var(--to-warning)]',
    glow: 'rgba(240,185,11,0.25)',
    bg: 'bg-[var(--to-warning)]/10',
    border: 'border-[var(--to-warning)]/30',
  },
  jira_ticket: {
    icon: Ticket,
    label: 'Jira Ticket',
    color: 'text-[var(--to-accent-blue)]',
    glow: 'rgba(59,130,246,0.25)',
    bg: 'bg-[var(--to-accent-blue)]/10',
    border: 'border-[var(--to-accent-blue)]/30',
  },
  pr_sync: {
    icon: Github,
    label: 'PR Synced',
    color: 'text-[var(--to-accent-purple)]',
    glow: 'rgba(139,92,246,0.25)',
    bg: 'bg-[var(--to-accent-purple)]/10',
    border: 'border-[var(--to-accent-purple)]/30',
  },
  exception: {
    icon: AlertCircle,
    label: 'Exception',
    color: 'text-[var(--to-short)]',
    glow: 'rgba(246,70,93,0.25)',
    bg: 'bg-[var(--to-short)]/10',
    border: 'border-[var(--to-short)]/30',
  },
  guard_activated: {
    icon: ShieldX,
    label: 'Guard Activated',
    color: 'text-[var(--to-warning)]',
    glow: 'rgba(240,185,11,0.25)',
    bg: 'bg-[var(--to-warning)]/10',
    border: 'border-[var(--to-warning)]/30',
  },
  kill_switch: {
    icon: ShieldX,
    label: 'Kill Switch',
    color: 'text-[var(--to-short)]',
    glow: 'rgba(246,70,93,0.35)',
    bg: 'bg-[var(--to-short)]/15',
    border: 'border-[var(--to-short)]/40',
  },
};

const DEFAULT_CONFIG: EventConfig = {
  icon: Zap,
  label: 'Agent Event',
  color: 'text-[var(--to-text-secondary)]',
  glow: 'rgba(139,149,165,0.2)',
  bg: 'bg-[var(--to-surface-raised)]/60',
  border: 'border-[var(--to-border)]',
};

/* ──────────────────────────────────────────────────────────────
   Helpers
────────────────────────────────────────────────────────────── */
function formatRelativeTime(isoOrEpoch: string | number | undefined): string {
  if (!isoOrEpoch) return '';
  try {
    const ts = typeof isoOrEpoch === 'number'
      ? isoOrEpoch * 1000
      : new Date(isoOrEpoch).getTime();
    const diff = Date.now() - ts;
    if (diff < 60_000) return `${Math.round(diff / 1000)}s ago`;
    if (diff < 3_600_000) return `${Math.round(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.round(diff / 3_600_000)}h ago`;
    return new Date(ts).toLocaleDateString();
  } catch {
    return '';
  }
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/* ──────────────────────────────────────────────────────────────
   Event Card
────────────────────────────────────────────────────────────── */
function EventCard({ event, index }: { event: AgentEvent; index: number }) {
  const cfg = EVENT_CONFIG[event.type] ?? DEFAULT_CONFIG;
  const Icon = cfg.icon;
  const relTime = formatRelativeTime(event.timestamp_iso ?? event.timestamp);

  return (
    <div
      className={cn(
        'group relative flex items-start gap-3 rounded-xl border p-3.5 transition-all duration-200',
        cfg.bg,
        cfg.border,
        'hover:scale-[1.01] hover:shadow-lg',
      )}
      style={{
        animationDelay: `${index * 40}ms`,
        boxShadow: `0 0 0 transparent`,
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = `0 4px 20px ${cfg.glow}`;
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.boxShadow = '0 0 0 transparent';
      }}
    >
      {/* Timeline connector */}
      <div
        className={cn(
          'mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg',
          cfg.bg,
          'border',
          cfg.border,
        )}
        style={{ boxShadow: `0 0 10px ${cfg.glow}` }}
      >
        <Icon className={cn('h-3.5 w-3.5', cfg.color)} />
      </div>

      <div className='min-w-0 flex-1'>
        <div className='mb-0.5 flex items-center gap-2'>
          <span
            className={cn('text-xs font-semibold uppercase tracking-wider', cfg.color)}
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {cfg.label}
          </span>
          {event.jira_key && (
            <span
              className='rounded bg-[var(--to-accent-blue)]/15 px-1.5 py-0.5 text-[10px] font-mono font-bold text-[var(--to-accent-blue)]'
            >
              {event.jira_key}
            </span>
          )}
          {event.symbol && (
            <span className='rounded bg-[var(--to-surface-raised)] px-1.5 py-0.5 text-[10px] font-mono text-[var(--to-text-secondary)]'>
              {event.symbol}
            </span>
          )}
          <span
            className='ml-auto flex-shrink-0 text-[10px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {relTime}
          </span>
        </div>
        <p className='text-sm leading-snug text-[var(--to-text-secondary)]'>
          {event.message}
        </p>
        {event.account && event.account !== 'default' && (
          <span className='mt-1 inline-block text-[10px] text-[var(--to-text-dim)]'>
            account: {event.account}
          </span>
        )}
      </div>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────
   Stat Pill
────────────────────────────────────────────────────────────── */
function StatPill({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className='flex flex-col items-center rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/60 px-5 py-3 backdrop-blur'>
      <span
        className={cn('text-2xl font-bold tabular-nums', color ?? 'text-[var(--to-text-primary)]')}
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        {value}
      </span>
      <span className='mt-0.5 text-[10px] uppercase tracking-widest text-[var(--to-text-dim)]'>
        {label}
      </span>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────
   Main Page
────────────────────────────────────────────────────────────── */
export default function AgenticViewPage() {
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/agent/status?limit=50`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: AgentStatus = await res.json();
      setStatus(data);
      setError(null);
      setLastRefresh(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchStatus();
    const interval = setInterval(() => void fetchStatus(), 10_000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  // Compute type counts from events
  const typeCounts = (status?.events ?? []).reduce<Record<string, number>>((acc, evt) => {
    acc[evt.type] = (acc[evt.type] ?? 0) + 1;
    return acc;
  }, {});

  const tradeCount = (typeCounts['trade_executed'] ?? 0);
  const jiraCount = (typeCounts['jira_ticket'] ?? 0) + (typeCounts['exception'] ?? 0);
  const guardCount = (typeCounts['guard_activated'] ?? 0) + (typeCounts['kill_switch'] ?? 0) + (typeCounts['trade_rejected'] ?? 0);

  return (
    <div className='min-h-screen bg-[var(--to-bg)]'>
      {/* Header */}
      <div className='border-b border-[var(--to-border)] bg-[var(--to-surface)]/80 backdrop-blur-xl'>
        <div className='mx-auto max-w-5xl px-6 py-5'>
          <div className='flex items-center justify-between'>
            <div className='flex items-center gap-3'>
              <div
                className='flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--to-accent-purple)]/15 border border-[var(--to-accent-purple)]/30'
                style={{ boxShadow: '0 0 18px rgba(139,92,246,0.3)' }}
              >
                <Bot className='h-5 w-5 text-[var(--to-accent-purple)]' />
              </div>
              <div>
                <h1 className='text-lg font-semibold text-[var(--to-text-primary)]'>Agentic View</h1>
                <p className='text-xs text-[var(--to-text-dim)]'>Real-time AI autonomous pipeline events</p>
              </div>
            </div>

            <div className='flex items-center gap-3'>
              {/* Status badge */}
              <div
                className={cn(
                  'flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium',
                  error
                    ? 'border-[var(--to-short)]/40 bg-[var(--to-short)]/10 text-[var(--to-short)]'
                    : 'border-[var(--to-long)]/40 bg-[var(--to-long)]/10 text-[var(--to-long)]',
                )}
              >
                <span
                  className={cn(
                    'h-1.5 w-1.5 rounded-full',
                    error ? 'bg-[var(--to-short)]' : 'bg-[var(--to-long)] pulse-active',
                  )}
                  style={!error ? { boxShadow: '0 0 6px rgba(14,203,129,0.7)' } : undefined}
                />
                {error ? 'Offline' : 'Active'}
              </div>

              {/* Refresh */}
              <button
                onClick={() => void fetchStatus()}
                className='flex items-center gap-1.5 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-1.5 text-xs text-[var(--to-text-secondary)] transition-all hover:border-[var(--to-accent-purple)]/40 hover:text-[var(--to-accent-purple)]'
              >
                <RefreshCw className='h-3 w-3' />
                Refresh
              </button>

              <span
                className='text-[10px] text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {lastRefresh.toLocaleTimeString()}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className='mx-auto max-w-5xl px-6 py-6 space-y-6'>

        {/* Stat pills */}
        <div className='grid grid-cols-3 gap-4'>
          <StatPill label='Trades Executed' value={tradeCount} color='text-[var(--to-long)]' />
          <StatPill label='Bugs / Tickets' value={jiraCount} color='text-[var(--to-accent-blue)]' />
          <StatPill label='Guards Fired' value={guardCount} color='text-[var(--to-warning)]' />
        </div>

        {/* Event feed */}
        <div className='rounded-2xl border border-[var(--to-border)] bg-[var(--to-surface)]/60 backdrop-blur-xl overflow-hidden'>
          {/* Feed header */}
          <div className='flex items-center justify-between border-b border-[var(--to-border)] px-5 py-3'>
            <div className='flex items-center gap-2'>
              <Activity className='h-4 w-4 text-[var(--to-accent-purple)]' />
              <span className='text-sm font-semibold text-[var(--to-text-primary)]'>Event Feed</span>
              {status && (
                <span className='rounded-full bg-[var(--to-accent-purple)]/15 px-2 py-0.5 text-[10px] font-mono text-[var(--to-accent-purple)]'>
                  {status.event_count} events
                </span>
              )}
            </div>
            <span className='text-[10px] text-[var(--to-text-dim)]' style={{ fontFamily: 'var(--font-mono)' }}>
              auto-refresh every 10s
            </span>
          </div>

          {/* Events list */}
          <div className='divide-y divide-[var(--to-border)]/40 px-4 py-3 space-y-2'>
            {loading && (
              <div className='flex items-center justify-center py-16'>
                <div className='h-8 w-8 animate-spin rounded-full border-2 border-[var(--to-accent-purple)]/30 border-t-[var(--to-accent-purple)]' />
              </div>
            )}

            {!loading && error && (
              <div className='flex flex-col items-center gap-3 py-16 text-center'>
                <AlertCircle className='h-10 w-10 text-[var(--to-short)]/60' />
                <p className='text-sm text-[var(--to-text-secondary)]'>Could not connect to backend</p>
                <p className='text-xs text-[var(--to-text-dim)]' style={{ fontFamily: 'var(--font-mono)' }}>{error}</p>
              </div>
            )}

            {!loading && !error && (!status?.events.length) && (
              <div className='flex flex-col items-center gap-3 py-16 text-center'>
                <Bot className='h-10 w-10 text-[var(--to-accent-purple)]/40' />
                <p className='text-sm text-[var(--to-text-secondary)]'>No events yet</p>
                <p className='text-xs text-[var(--to-text-dim)]'>Events will appear here as the autonomous pipeline runs</p>
              </div>
            )}

            {!loading && !error && status?.events.map((event, idx) => (
              <EventCard key={`${event.timestamp}-${idx}`} event={event} index={idx} />
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}
