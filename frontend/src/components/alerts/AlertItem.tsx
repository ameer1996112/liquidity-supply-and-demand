'use client';

import { useState } from 'react';
import {
  ShieldAlert,
  TrendingDown,
  Clock,
  Zap,
  Inbox,
  AlertTriangle,
  Info,
  ChevronDown,
  ChevronUp,
  BellOff,
  Check,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Alert } from '@/hooks/useAlerts';

// ── Icon by alert type ────────────────────────────────────────

function alertIcon(type: string) {
  const t = type.toLowerCase();
  if (t.includes('drawdown') || t.includes('loss')) return TrendingDown;
  if (t.includes('position_age') || t.includes('age')) return Clock;
  if (t.includes('latency') || t.includes('slippage')) return Zap;
  if (t.includes('dlq')) return Inbox;
  if (t.includes('critical') || t.includes('shield')) return ShieldAlert;
  return AlertTriangle;
}

// ── Severity styling ─────────────────────────────────────────

const SEVERITY_STYLE: Record<string, { icon: string; badge: string; border: string }> = {
  critical: {
    icon: 'bg-rose-500/15 text-rose-400',
    badge: 'bg-rose-500/15 text-rose-400',
    border: 'border-l-2 border-l-rose-500/60',
  },
  error: {
    icon: 'bg-orange-500/15 text-orange-400',
    badge: 'bg-orange-500/15 text-orange-400',
    border: 'border-l-2 border-l-orange-500/60',
  },
  warning: {
    icon: 'bg-amber-500/15 text-amber-400',
    badge: 'bg-amber-500/15 text-amber-400',
    border: 'border-l-2 border-l-amber-500/40',
  },
  info: {
    icon: 'bg-blue-500/15 text-blue-400',
    badge: 'bg-blue-500/15 text-blue-400',
    border: 'border-l-2 border-l-blue-500/30',
  },
};

function severityStyle(sev: string) {
  return SEVERITY_STYLE[sev.toLowerCase()] ?? SEVERITY_STYLE.info;
}

// ── Relative time ────────────────────────────────────────────

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return new Date(iso).toLocaleDateString();
}

// ── Snooze dropdown ─────────────────────────────────────────

interface SnoozeMenuProps {
  onSnooze: (hours: 1 | 24) => void;
  onClose: () => void;
}

function SnoozeMenu({ onSnooze, onClose }: SnoozeMenuProps) {
  return (
    <div className="absolute right-0 top-full z-20 mt-1 w-32 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] shadow-xl">
      {([1, 24] as const).map((h) => (
        <button
          key={h}
          type="button"
          onClick={() => { onSnooze(h); onClose(); }}
          className="w-full px-3 py-2 text-left font-mono text-[10px] text-[var(--to-text-secondary)] hover:bg-[var(--to-surface)] hover:text-[var(--to-text-primary)] transition-colors first:rounded-t-lg last:rounded-b-lg"
        >
          {h === 1 ? '1 hour' : '24 hours'}
        </button>
      ))}
    </div>
  );
}

// ── Component ────────────────────────────────────────────────

interface AlertItemProps {
  alert: Alert;
  onMarkRead?: (id: number) => void;
  onSnooze?: (id: number, hours: 1 | 24) => void;
}

export function AlertItem({ alert, onMarkRead, onSnooze }: AlertItemProps) {
  const [expanded, setExpanded] = useState(false);
  const [showSnooze, setShowSnooze] = useState(false);

  const sev = String(alert.severity).toLowerCase();
  const style = severityStyle(sev);
  const Icon = alertIcon(alert.alert_type);

  const metaEntries = Object.entries(alert.metadata ?? {}).filter(
    ([k]) => k !== 'source',
  );
  const hasMetadata = metaEntries.length > 0;

  return (
    <div
      className={cn(
        'flex items-start gap-3 px-3 py-2.5 transition-colors bg-[var(--to-surface)] hover:bg-[var(--to-surface-raised)]',
        style.border,
      )}
    >
      {/* Icon */}
      <div
        className={cn(
          'mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full',
          style.icon,
        )}
      >
        <Icon className="h-3.5 w-3.5" />
      </div>

      {/* Body */}
      <div className="min-w-0 flex-1 space-y-0.5">
        {/* Top row */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <span className="truncate text-xs font-semibold text-[var(--to-text-primary)]">
              {alert.title || alert.alert_type}
            </span>
            {alert.signal_id && (
              <span className="shrink-0 rounded bg-[var(--to-surface-raised)] px-1.5 py-0.5 font-mono text-[10px] text-[var(--to-text-dim)]">
                #{alert.signal_id}
              </span>
            )}
          </div>
          <span
            suppressHydrationWarning
            className="shrink-0 font-mono text-[10px] text-[var(--to-text-dim)]"
          >
            {relativeTime(alert.created_at)}
          </span>
        </div>

        {/* Message */}
        <p className="text-[11px] leading-snug text-[var(--to-text-dim)]">
          {alert.message}
        </p>

        {/* Metadata (expandable) */}
        {hasMetadata && (
          <div>
            <button
              type="button"
              onClick={() => setExpanded((p) => !p)}
              className="flex items-center gap-0.5 font-mono text-[9px] text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] transition-colors"
            >
              {expanded ? <ChevronUp className="h-2.5 w-2.5" /> : <ChevronDown className="h-2.5 w-2.5" />}
              {expanded ? 'Hide details' : 'Show details'}
            </button>
            {expanded && (
              <div className="mt-1 rounded border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-2 py-1.5 space-y-0.5">
                {metaEntries.map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between gap-4">
                    <span className="font-mono text-[9px] text-[var(--to-text-dim)] uppercase tracking-wider">{k}</span>
                    <span className="font-mono text-[9px] text-[var(--to-text-secondary)]">{String(v)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Footer: severity badge + actions */}
        <div className="flex items-center justify-between pt-0.5">
          <span
            className={cn(
              'rounded px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider',
              style.badge,
            )}
          >
            {sev}
          </span>

          <div className="relative flex items-center gap-1">
            {onSnooze && (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowSnooze((p) => !p)}
                  className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[10px] text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)] hover:bg-[var(--to-surface-raised)] transition-colors"
                >
                  <BellOff className="h-3 w-3" />
                  Snooze
                </button>
                {showSnooze && (
                  <SnoozeMenu
                    onSnooze={(h) => onSnooze(alert.id, h)}
                    onClose={() => setShowSnooze(false)}
                  />
                )}
              </div>
            )}
            {onMarkRead && (
              <button
                type="button"
                onClick={() => onMarkRead(alert.id)}
                className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[10px] text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)] hover:bg-[var(--to-surface-raised)] transition-colors"
              >
                <Check className="h-3 w-3" />
                Done
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
