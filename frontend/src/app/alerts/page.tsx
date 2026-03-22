'use client';

import { useState } from 'react';
import {
  Bell,
  RefreshCw,
  AlertTriangle,
  ShieldAlert,
  Info,
  CheckCircle2,
  RotateCcw,
  X,
  Trash2,
  Inbox,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAlerts } from '@/hooks/useAlerts';
import { AlertItem } from '@/components/alerts/AlertItem';
import {
  useSystemHealth,
  useDeadLetters,
  useRetryDeadLetter,
  useDiscardDeadLetter,
  useClearDeadLetters,
  type DeadLetterItem,
} from '@/hooks/useSystemHealth';

// ── Types ────────────────────────────────────────────────────────────────────

type SeverityFilter = 'all' | 'critical' | 'error' | 'warning' | 'info';

const FILTER_TABS: { key: SeverityFilter; label: string }[] = [
  { key: 'all',      label: 'All'      },
  { key: 'critical', label: 'Critical' },
  { key: 'error',    label: 'Error'    },
  { key: 'warning',  label: 'Warning'  },
  { key: 'info',     label: 'Info'     },
];

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatRelativeTime(epoch: number): string {
  const diff = Date.now() - epoch * 1000;
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return new Date(epoch * 1000).toLocaleDateString();
}

// ── Stat card ────────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string;
  value: number | string;
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  color: string;
  bg: string;
  active?: boolean;
  onClick?: () => void;
}

function StatCard({ label, value, icon: Icon, color, bg, active, onClick }: StatCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      className={cn(
        'rounded-xl border p-4 text-left transition-all duration-150',
        'bg-[var(--to-surface)] border-[var(--to-border)]',
        onClick && !active && 'hover:border-[var(--to-border)]/80 hover:bg-[var(--to-surface-raised)] cursor-pointer',
        active && 'border-[var(--to-warning)]/40 bg-[var(--to-warning)]/5',
        !onClick && 'cursor-default',
      )}
    >
      <div className={cn('mb-2 flex h-8 w-8 items-center justify-center rounded-lg border', bg)}>
        <Icon className={cn('h-4 w-4', color)} />
      </div>
      <div className="font-mono text-2xl font-bold tabular-nums text-[var(--to-text-primary)]">
        {value}
      </div>
      <div className="font-mono text-[10px] font-bold uppercase tracking-widest text-[var(--to-text-dim)] mt-0.5">
        {label}
      </div>
    </button>
  );
}

// ── Dead letter row ──────────────────────────────────────────────────────────

interface DlRowProps {
  item: DeadLetterItem;
  onRetry: (id: string) => void;
  onDiscard: (id: string) => void;
  retrying: boolean;
  discarding: boolean;
}

function DlRow({ item, onRetry, onDiscard, retrying, discarding }: DlRowProps) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2.5">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-rose-500/10 text-rose-400">
        <AlertTriangle className="h-3.5 w-3.5" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate font-mono text-[11px] text-rose-300">
          {item.error || 'Unknown error'}
        </p>
        <p className="font-mono text-[10px] text-[var(--to-text-dim)] mt-0.5">
          Failed {formatRelativeTime(item.failed_at)} · attempt {item.attempt}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        <button
          type="button"
          onClick={() => onRetry(item.id)}
          disabled={retrying || discarding}
          className={cn(
            'flex items-center gap-1 rounded px-2 py-1',
            'border border-[var(--to-border)] text-[10px] font-mono font-semibold uppercase tracking-wider',
            'text-[var(--to-text-secondary)] hover:border-emerald-500/40 hover:text-emerald-400',
            'transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
          )}
        >
          <RotateCcw className="h-3 w-3" />
          Retry
        </button>
        <button
          type="button"
          onClick={() => onDiscard(item.id)}
          disabled={retrying || discarding}
          className={cn(
            'flex items-center gap-1 rounded px-2 py-1',
            'border border-[var(--to-border)] text-[10px] font-mono font-semibold uppercase tracking-wider',
            'text-[var(--to-text-dim)] hover:border-rose-500/40 hover:text-rose-400',
            'transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
          )}
        >
          <X className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function AlertsPage() {
  const [filter, setFilter] = useState<SeverityFilter>('all');

  const { alerts, isLoading, markAsRead, clearAll, snoozeAlert, refetch } = useAlerts();
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const { data: health } = useSystemHealth();
  const { data: dlData } = useDeadLetters();
  const retryMutation    = useRetryDeadLetter();
  const discardMutation  = useDiscardDeadLetter();
  const clearDlqMutation = useClearDeadLetters();

  const dlItems = dlData?.items ?? [];
  const dlCount = health?.dead_letter_count ?? dlItems.length;

  const criticalCount = alerts.filter(
    (a) => a.severity === 'critical' || a.severity === 'error',
  ).length;
  const warningCount  = alerts.filter((a) => a.severity === 'warning').length;
  const infoCount     = alerts.filter((a) => a.severity === 'info').length;

  const handleRefetch = () => {
    refetch().then(() => setLastUpdated(new Date()));
  };

  const filteredAlerts =
    filter === 'all'
      ? alerts
      : alerts.filter((a) => String(a.severity).toLowerCase() === filter);

  return (
    <div className="space-y-6">
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-amber-500/20 bg-amber-500/10">
            <Bell className="h-4 w-4 text-amber-400" />
          </div>
          <div>
            <h1 className="font-mono text-lg font-bold text-[var(--to-text-primary)] tracking-tight">
              Alerts
            </h1>
            <p className="font-mono text-[10px] uppercase tracking-widest text-[var(--to-text-dim)]">
              Monitoring · Active alerts &amp; dead letters
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {lastUpdated && (
            <span className="font-mono text-[9px] text-[var(--to-text-dim)]" suppressHydrationWarning>
              Updated {lastUpdated.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          )}
          <button
            type="button"
            onClick={handleRefetch}
            disabled={isLoading}
            className={cn(
              'flex items-center gap-1.5 rounded border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-1.5',
              'font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--to-text-dim)]',
              'hover:text-[var(--to-text-secondary)] transition-colors',
              isLoading && 'opacity-60 cursor-not-allowed',
            )}
          >
            <RefreshCw className={cn('h-3 w-3', isLoading && 'animate-spin')} />
            Refresh
          </button>

          {alerts.length > 0 && (
            <button
              type="button"
              onClick={clearAll}
              className={cn(
                'flex items-center gap-1.5 rounded border border-amber-500/30 bg-amber-500/10 px-3 py-1.5',
                'font-mono text-[10px] font-semibold uppercase tracking-wider text-amber-400',
                'hover:bg-amber-500/15 transition-colors',
              )}
            >
              <CheckCircle2 className="h-3 w-3" />
              Acknowledge All
            </button>
          )}
        </div>
      </header>

      {/* ── Stat cards ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <StatCard
          label="Active Alerts"
          value={alerts.length}
          icon={Bell}
          color="text-amber-400"
          bg="bg-amber-500/10 border-amber-500/20"
          active={filter === 'all'}
          onClick={() => setFilter('all')}
        />
        <StatCard
          label="Critical / Error"
          value={criticalCount}
          icon={ShieldAlert}
          color="text-rose-400"
          bg="bg-rose-500/10 border-rose-500/20"
          active={filter === 'critical' || filter === 'error'}
          onClick={() => setFilter('critical')}
        />
        <StatCard
          label="Warnings"
          value={warningCount}
          icon={AlertTriangle}
          color="text-amber-400"
          bg="bg-amber-500/10 border-amber-500/20"
          active={filter === 'warning'}
          onClick={() => setFilter('warning')}
        />
        <StatCard
          label="Info"
          value={infoCount}
          icon={Info}
          color="text-blue-400"
          bg="bg-blue-500/10 border-blue-500/20"
          active={filter === 'info'}
          onClick={() => setFilter('info')}
        />
        <StatCard
          label="Dead Letters"
          value={dlCount}
          icon={Inbox}
          color="text-[var(--to-text-dim)]"
          bg="bg-[var(--to-surface-raised)] border-[var(--to-border)]"
        />
      </div>

      {/* ── Filter tabs ─────────────────────────────────────────────────── */}
      <div className="flex items-center gap-1.5">
        {FILTER_TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setFilter(tab.key)}
            className={cn(
              'rounded-md border px-3 py-1.5 font-mono text-[10px] font-bold uppercase tracking-widest transition-all',
              filter === tab.key
                ? 'border-amber-500/40 bg-amber-500/10 text-amber-400'
                : 'border-[var(--to-border)] bg-[var(--to-surface)] text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Alert list ──────────────────────────────────────────────────── */}
      <section>
        <div className="rounded-xl border border-[var(--to-border)] overflow-hidden">
          {isLoading ? (
            <div className="py-10 text-center font-mono text-xs text-[var(--to-text-dim)]">
              Loading alerts…
            </div>
          ) : filteredAlerts.length === 0 ? (
            <div className="py-10 text-center space-y-1">
              <Info className="mx-auto h-5 w-5 text-[var(--to-text-dim)]" />
              <p className="font-mono text-xs text-[var(--to-text-dim)]">
                No active alerts. You&apos;re all clear.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-[var(--to-border)]">
              {filteredAlerts.map((alert) => (
                <AlertItem key={alert.id} alert={alert} onMarkRead={markAsRead} onSnooze={snoozeAlert} />
              ))}
            </div>
          )}
        </div>
      </section>

      {/* ── Dead Letters ────────────────────────────────────────────────── */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="font-mono text-sm font-bold text-[var(--to-text-primary)]">
              Dead Letters
            </h2>
            {dlCount > 0 && (
              <span className="rounded-full bg-rose-500/15 px-2 py-0.5 font-mono text-[10px] font-bold text-rose-400">
                {dlCount}
              </span>
            )}
          </div>

          {dlItems.length > 0 && (
            <button
              type="button"
              onClick={() => clearDlqMutation.mutate()}
              disabled={clearDlqMutation.isPending}
              className={cn(
                'flex items-center gap-1.5 rounded border border-rose-500/30 bg-rose-500/10 px-3 py-1.5',
                'font-mono text-[10px] font-semibold uppercase tracking-wider text-rose-400',
                'hover:bg-rose-500/15 transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
              )}
            >
              <Trash2 className="h-3 w-3" />
              Clear All
            </button>
          )}
        </div>

        {dlItems.length === 0 ? (
          <div className="rounded-xl border border-[var(--to-border)] py-8 text-center">
            <CheckCircle2 className="mx-auto h-5 w-5 text-[var(--to-long)] mb-1" />
            <p className="font-mono text-xs text-[var(--to-text-dim)]">
              Dead letter queue is empty.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {dlItems.map((item) => (
              <DlRow
                key={item.id}
                item={item}
                onRetry={(id) => retryMutation.mutate(id)}
                onDiscard={(id) => discardMutation.mutate(id)}
                retrying={retryMutation.isPending}
                discarding={discardMutation.isPending}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
