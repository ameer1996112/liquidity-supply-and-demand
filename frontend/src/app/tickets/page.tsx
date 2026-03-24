'use client';

import { useState, useCallback } from 'react';
import {
  ClipboardList,
  Plus,
  RefreshCw,
  Bug,
  Sparkles,
  CheckSquare,
  AlertCircle,
  AlertTriangle,
  Minus,
  ChevronUp,
  X,
  ExternalLink,
  Clock,
  Bot,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ── Types ────────────────────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export type TicketType = 'bug' | 'feature' | 'task';
export type TicketStatus = 'todo' | 'in_progress' | 'done';
export type TicketPriority = 'low' | 'medium' | 'high' | 'critical';

export interface AiChangelogEntry {
  timestamp: string;
  agent: string;
  old_status: string;
  new_status: string;
  summary: string;
}

export interface Ticket {
  id: string;
  title: string;
  description: string | null;
  type: TicketType;
  status: TicketStatus;
  priority: TicketPriority;
  assignee: string | null;
  signal_id: number | null;
  ai_changelog: AiChangelogEntry[];
  created_at: string;
  updated_at: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const TYPE_META: Record<TicketType, { icon: React.ComponentType<{ className?: string }>; color: string; bg: string }> = {
  bug:     { icon: Bug,        color: 'text-rose-400',   bg: 'bg-rose-500/10 border-rose-500/25' },
  feature: { icon: Sparkles,   color: 'text-violet-400', bg: 'bg-violet-500/10 border-violet-500/25' },
  task:    { icon: CheckSquare, color: 'text-blue-400',  bg: 'bg-blue-500/10 border-blue-500/25' },
};

const PRIORITY_META: Record<TicketPriority, { icon: React.ComponentType<{ className?: string }>; color: string; label: string }> = {
  critical: { icon: AlertCircle,   color: 'text-rose-400',   label: 'Critical' },
  high:     { icon: AlertTriangle, color: 'text-amber-400',  label: 'High'     },
  medium:   { icon: Minus,         color: 'text-blue-400',   label: 'Medium'   },
  low:      { icon: ChevronUp,     color: 'text-[var(--to-text-dim)]', label: 'Low' },
};

const STATUS_COLUMNS: { key: TicketStatus; label: string; accent: string }[] = [
  { key: 'todo',        label: 'To Do',       accent: 'border-[var(--to-text-dim)]/40' },
  { key: 'in_progress', label: 'In Progress', accent: 'border-amber-500/40' },
  { key: 'done',        label: 'Done',        accent: 'border-emerald-500/40' },
];

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return new Date(iso).toLocaleDateString();
}

// ── Hooks ────────────────────────────────────────────────────────────────────

function useTickets() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetch = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await window.fetch(`${API_BASE}/api/tickets`);
      const data = await res.json();
      setTickets(data.tickets ?? []);
    } catch {
      // keep stale data
    } finally {
      setIsLoading(false);
    }
  }, []);

  return { tickets, setTickets, isLoading, refetch: fetch };
}

// ── TicketCard ────────────────────────────────────────────────────────────────

function TicketCard({
  ticket,
  onDragStart,
  onClick,
}: {
  ticket: Ticket;
  onDragStart: (id: string) => void;
  onClick: (t: Ticket) => void;
}) {
  const type = TYPE_META[ticket.type];
  const priority = PRIORITY_META[ticket.priority];
  const TypeIcon = type.icon;
  const PriorityIcon = priority.icon;

  return (
    <div
      draggable
      onDragStart={() => onDragStart(ticket.id)}
      onClick={() => onClick(ticket)}
      className={cn(
        'group cursor-grab active:cursor-grabbing select-none',
        'rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)]',
        'p-3 space-y-2 transition-all duration-150',
        'hover:border-[var(--to-border)]/80 hover:bg-[var(--to-surface-raised)] hover:shadow-sm hover:-translate-y-[1px]',
      )}
    >
      {/* Type + Priority row */}
      <div className="flex items-center justify-between">
        <div className={cn('flex h-5 w-5 items-center justify-center rounded border', type.bg)}>
          <TypeIcon className={cn('h-3 w-3', type.color)} />
        </div>
        <div className="flex items-center gap-1">
          {ticket.ai_changelog.length > 0 && (
            <Bot className="h-3 w-3 text-violet-400/70" />
          )}
          <PriorityIcon className={cn('h-3 w-3', priority.color)} />
        </div>
      </div>

      {/* Title */}
      <p className="font-sans text-[12px] font-medium leading-snug text-[var(--to-text-primary)] line-clamp-2">
        {ticket.title}
      </p>

      {/* Footer */}
      <div className="flex items-center justify-between">
        <span className="font-mono text-[9px] font-bold text-[var(--to-text-dim)] tracking-tight">
          {ticket.id}
        </span>
        <span className="font-mono text-[9px] text-[var(--to-text-dim)]">
          {relativeTime(ticket.created_at)}
        </span>
      </div>
    </div>
  );
}

// ── KanbanColumn ──────────────────────────────────────────────────────────────

function KanbanColumn({
  column,
  tickets,
  onDragStart,
  onDrop,
  onClick,
}: {
  column: (typeof STATUS_COLUMNS)[number];
  tickets: Ticket[];
  onDragStart: (id: string) => void;
  onDrop: (status: TicketStatus) => void;
  onClick: (t: Ticket) => void;
}) {
  const [isDragOver, setIsDragOver] = useState(false);

  return (
    <div
      className="glass-panel flex flex-col min-h-[400px] p-3 rounded-xl"
      onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={() => { setIsDragOver(false); onDrop(column.key); }}
    >
      {/* Column header */}
      <div className={cn('flex items-center gap-2 mb-3 pb-2 border-b-2', column.accent)}>
        <span className="font-mono text-[11px] font-bold uppercase tracking-widest text-[var(--to-text-secondary)]">
          {column.label}
        </span>
        <span className="rounded-full bg-[var(--to-surface-raised)] px-2 py-0.5 font-mono text-[9px] font-bold text-[var(--to-text-dim)]">
          {tickets.length}
        </span>
      </div>

      {/* Cards */}
      <div
        className={cn(
          'flex-1 space-y-2 rounded-lg transition-colors duration-150 p-1',
          isDragOver && 'bg-[var(--to-warning)]/5 border border-dashed border-[var(--to-warning)]/30',
        )}
      >
        {tickets.length === 0 && !isDragOver && (
          <div className="py-4">
            <div className="flex flex-col items-center gap-1 py-6 text-center">
              <div className="mb-1 animate-bounce text-[var(--to-text-dim)]">
                <Minus className="h-4 w-4" />
              </div>
              <span className="font-mono text-[10px] text-[var(--to-text-dim)]">No tickets</span>
            </div>
          </div>
        )}
        {tickets.map((t) => (
          <TicketCard
            key={t.id}
            ticket={t}
            onDragStart={onDragStart}
            onClick={onClick}
          />
        ))}
      </div>
    </div>
  );
}

// ── TicketDrawer ──────────────────────────────────────────────────────────────

function TicketDrawer({ ticket, onClose }: { ticket: Ticket; onClose: () => void }) {
  const type = TYPE_META[ticket.type];
  const priority = PRIORITY_META[ticket.priority];
  const TypeIcon = type.icon;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div
        className={cn(
          'h-full w-full max-w-md overflow-y-auto',
          'border-l border-[var(--to-border)] bg-[var(--to-bg)] shadow-2xl',
          'flex flex-col',
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3 border-b border-[var(--to-border)] p-4">
          <div className="flex items-center gap-3 min-w-0">
            <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border', type.bg)}>
              <TypeIcon className={cn('h-4 w-4', type.color)} />
            </div>
            <div className="min-w-0">
              <h2 className="font-sans text-[13px] font-semibold text-[var(--to-text-primary)] leading-snug">
                {ticket.title}
              </h2>
              <div className="flex items-center gap-2 mt-0.5">
                <span className={cn('font-mono text-[9px] uppercase font-bold', priority.color)}>
                  {priority.label}
                </span>
                <span className="font-mono text-[9px] text-[var(--to-text-dim)]">·</span>
                <span className="font-mono text-[9px] text-[var(--to-text-dim)] capitalize">
                  {ticket.type}
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 space-y-5 p-4">
          {/* Meta */}
          <div className="grid grid-cols-2 gap-3 text-[11px] font-mono">
            <div className="rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2">
              <p className="text-[9px] uppercase tracking-widest text-[var(--to-text-dim)] mb-0.5">Status</p>
              <p className="capitalize text-[var(--to-text-primary)] font-semibold">
                {ticket.status.replace('_', ' ')}
              </p>
            </div>
            <div className="rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2">
              <p className="text-[9px] uppercase tracking-widest text-[var(--to-text-dim)] mb-0.5">Created</p>
              <p className="text-[var(--to-text-primary)] font-semibold">{relativeTime(ticket.created_at)}</p>
            </div>
          </div>

          {/* Signal link */}
          {ticket.signal_id && (
            <div className="flex items-center gap-2 rounded-lg border border-blue-500/20 bg-blue-500/5 px-3 py-2">
              <ExternalLink className="h-3.5 w-3.5 text-blue-400 shrink-0" />
              <span className="font-mono text-[11px] text-blue-400">
                Linked to Signal #{ticket.signal_id}
              </span>
            </div>
          )}

          {/* Description */}
          {ticket.description && (
            <section>
              <h3 className="font-mono text-[10px] uppercase tracking-widest text-[var(--to-text-dim)] mb-2">
                Description
              </h3>
              <p className="font-sans text-[12px] text-[var(--to-text-secondary)] leading-relaxed whitespace-pre-wrap">
                {ticket.description}
              </p>
            </section>
          )}

          {/* AI Changelog */}
          <section>
            <div className="flex items-center gap-2 mb-3">
              <Bot className="h-3.5 w-3.5 text-violet-400" />
              <h3 className="font-mono text-[10px] uppercase tracking-widest text-[var(--to-text-dim)]">
                AI Changelog
              </h3>
              {ticket.ai_changelog.length > 0 && (
                <span className="rounded-full bg-violet-500/15 px-2 py-0.5 font-mono text-[9px] font-bold text-violet-400">
                  {ticket.ai_changelog.length}
                </span>
              )}
            </div>

            {ticket.ai_changelog.length === 0 ? (
              <div className="rounded-lg border border-dashed border-[var(--to-border)] py-6 text-center">
                <p className="font-mono text-[10px] text-[var(--to-text-dim)]">
                  No AI actions yet
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {[...ticket.ai_changelog].reverse().map((entry, i) => (
                  <div
                    key={i}
                    className="rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2.5 space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <Bot className="h-3 w-3 text-violet-400" />
                        <span className="font-mono text-[10px] font-semibold text-violet-400">
                          {entry.agent}
                        </span>
                        <span className="font-mono text-[9px] text-[var(--to-text-dim)]">
                          {entry.old_status} → {entry.new_status}
                        </span>
                      </div>
                      <div className="flex items-center gap-1 text-[var(--to-text-dim)]">
                        <Clock className="h-2.5 w-2.5" />
                        <span className="font-mono text-[9px]">
                          {relativeTime(entry.timestamp)}
                        </span>
                      </div>
                    </div>
                    <p className="font-sans text-[11px] text-[var(--to-text-secondary)] leading-relaxed">
                      {entry.summary}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

// ── NewTicketModal ────────────────────────────────────────────────────────────

function NewTicketModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({
    title: '',
    description: '',
    type: 'task' as TicketType,
    priority: 'medium' as TicketPriority,
    signal_id: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) return;
    setIsSubmitting(true);
    setError('');
    try {
      const body: Record<string, unknown> = {
        title: form.title.trim(),
        description: form.description.trim() || null,
        type: form.type,
        priority: form.priority,
      };
      if (form.signal_id.trim()) {
        body.signal_id = parseInt(form.signal_id, 10);
      }
      const res = await window.fetch(`${API_BASE}/api/tickets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      onCreated();
      onClose();
    } catch (err) {
      setError(String(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-xl border border-[var(--to-border)] bg-[var(--to-bg)] shadow-2xl p-5 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="font-mono text-[13px] font-bold text-[var(--to-text-primary)]">New Ticket</h2>
          <button onClick={onClose} className="text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]">
            <X className="h-4 w-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block font-mono text-[9px] uppercase tracking-widest text-[var(--to-text-dim)] mb-1">
              Title *
            </label>
            <input
              autoFocus
              type="text"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              placeholder="Short descriptive title..."
              className={cn(
                'w-full rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2',
                'font-sans text-[12px] text-[var(--to-text-primary)] placeholder:text-[var(--to-text-dim)]',
                'focus:outline-none focus:border-[var(--to-warning)]/50',
              )}
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-mono text-[9px] uppercase tracking-widest text-[var(--to-text-dim)] mb-1">
                Type
              </label>
              <select
                value={form.type}
                onChange={(e) => setForm((f) => ({ ...f, type: e.target.value as TicketType }))}
                className={cn(
                  'w-full rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2',
                  'font-mono text-[11px] text-[var(--to-text-primary)]',
                  'focus:outline-none focus:border-[var(--to-warning)]/50',
                )}
              >
                <option value="task">Task</option>
                <option value="bug">Bug</option>
                <option value="feature">Feature</option>
              </select>
            </div>
            <div>
              <label className="block font-mono text-[9px] uppercase tracking-widest text-[var(--to-text-dim)] mb-1">
                Priority
              </label>
              <select
                value={form.priority}
                onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value as TicketPriority }))}
                className={cn(
                  'w-full rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2',
                  'font-mono text-[11px] text-[var(--to-text-primary)]',
                  'focus:outline-none focus:border-[var(--to-warning)]/50',
                )}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block font-mono text-[9px] uppercase tracking-widest text-[var(--to-text-dim)] mb-1">
              Description
            </label>
            <textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="Optional details, steps to reproduce, context..."
              rows={3}
              className={cn(
                'w-full rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2',
                'font-sans text-[12px] text-[var(--to-text-primary)] placeholder:text-[var(--to-text-dim)]',
                'focus:outline-none focus:border-[var(--to-warning)]/50 resize-none',
              )}
            />
          </div>

          <div>
            <label className="block font-mono text-[9px] uppercase tracking-widest text-[var(--to-text-dim)] mb-1">
              Link to Signal ID (optional)
            </label>
            <input
              type="number"
              value={form.signal_id}
              onChange={(e) => setForm((f) => ({ ...f, signal_id: e.target.value }))}
              placeholder="e.g. 206"
              className={cn(
                'w-full rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2',
                'font-mono text-[12px] text-[var(--to-text-primary)] placeholder:text-[var(--to-text-dim)]',
                'focus:outline-none focus:border-[var(--to-warning)]/50',
              )}
            />
          </div>

          {error && (
            <p className="font-mono text-[10px] text-rose-400">{error}</p>
          )}

          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className={cn(
                'flex-1 rounded-lg border border-[var(--to-border)] px-4 py-2',
                'font-mono text-[11px] font-semibold uppercase tracking-wider text-[var(--to-text-dim)]',
                'hover:text-[var(--to-text-secondary)] transition-colors',
              )}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !form.title.trim()}
              className={cn(
                'flex-1 rounded-lg border border-[var(--to-warning)]/40 bg-[var(--to-warning)]/10 px-4 py-2',
                'font-mono text-[11px] font-semibold uppercase tracking-wider text-[var(--to-warning)]',
                'hover:bg-[var(--to-warning)]/15 transition-colors',
                'disabled:opacity-50 disabled:cursor-not-allowed',
              )}
            >
              {isSubmitting ? 'Creating…' : 'Create Ticket'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function TicketsPage() {
  const { tickets, setTickets, isLoading, refetch } = useTickets();
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [activeTicket, setActiveTicket] = useState<Ticket | null>(null);
  const [showNewModal, setShowNewModal] = useState(false);

  // Fetch on mount
  useState(() => { refetch(); });

  const handleDrop = useCallback(async (newStatus: TicketStatus) => {
    if (!draggingId) return;
    const ticket = tickets.find((t) => t.id === draggingId);
    if (!ticket || ticket.status === newStatus) { setDraggingId(null); return; }

    // Optimistic update
    setTickets((prev) =>
      prev.map((t) => t.id === draggingId ? { ...t, status: newStatus } : t)
    );
    setDraggingId(null);

    try {
      await window.fetch(`${API_BASE}/api/tickets/${draggingId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
    } catch {
      // Revert on failure
      setTickets((prev) =>
        prev.map((t) => t.id === draggingId ? { ...t, status: ticket.status } : t)
      );
    }
  }, [draggingId, tickets, setTickets]);

  const byStatus = (status: TicketStatus) =>
    tickets.filter((t) => t.status === status);

  const totalOpen = tickets.filter((t) => t.status !== 'done').length;

  return (
    <div className="space-y-4 animate-fade-in-up">
      {/* ── Header ── */}
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-violet-500/20 bg-violet-500/10">
            <ClipboardList className="h-4 w-4 text-violet-400" />
          </div>
          <div>
            <h1 className="page-title text-lg font-semibold">
              Tickets
            </h1>
            <p className="page-subtitle mt-0.5 text-xs">
              Project tracker · {totalOpen} open
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={refetch}
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
          <button
            type="button"
            onClick={() => setShowNewModal(true)}
            className={cn(
              'flex items-center gap-1.5 rounded border border-[var(--to-warning)]/40 bg-[var(--to-warning)]/10 px-3 py-1.5',
              'font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--to-warning)]',
              'hover:bg-[var(--to-warning)]/15 transition-colors',
            )}
          >
            <Plus className="h-3 w-3" />
            New Ticket
          </button>
        </div>
      </header>

      {/* ── Kanban board ── */}
      {isLoading && tickets.length === 0 ? (
        <div className="py-16 text-center">
          <p className="font-mono text-xs text-[var(--to-text-dim)]">Loading tickets…</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {STATUS_COLUMNS.map((col) => (
            <KanbanColumn
              key={col.key}
              column={col}
              tickets={byStatus(col.key)}
              onDragStart={setDraggingId}
              onDrop={handleDrop}
              onClick={setActiveTicket}
            />
          ))}
        </div>
      )}

      {/* ── Drawer ── */}
      {activeTicket && (
        <TicketDrawer ticket={activeTicket} onClose={() => setActiveTicket(null)} />
      )}

      {/* ── New ticket modal ── */}
      {showNewModal && (
        <NewTicketModal
          onClose={() => setShowNewModal(false)}
          onCreated={() => { refetch(); }}
        />
      )}
    </div>
  );
}
