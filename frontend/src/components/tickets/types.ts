import { Bug, Sparkles, CheckSquare, AlertCircle, AlertTriangle, Minus, ChevronUp } from 'lucide-react';
import React from 'react';

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
  sprint_id: number | null;
  sprint_name: string | null;
  ai_changelog: AiChangelogEntry[];
  created_at: string;
  updated_at: string;
}

export const TYPE_META: Record<TicketType, { icon: React.ComponentType<{ className?: string }>; color: string; bg: string }> = {
  bug:     { icon: Bug,        color: 'text-rose-400',   bg: 'bg-rose-500/10 border-rose-500/25' },
  feature: { icon: Sparkles,   color: 'text-violet-400', bg: 'bg-violet-500/10 border-violet-500/25' },
  task:    { icon: CheckSquare, color: 'text-blue-400',  bg: 'bg-blue-500/10 border-blue-500/25' },
};

export const PRIORITY_META: Record<TicketPriority, { icon: React.ComponentType<{ className?: string }>; color: string; label: string }> = {
  critical: { icon: AlertCircle,   color: 'text-rose-400',   label: 'Critical' },
  high:     { icon: AlertTriangle, color: 'text-amber-400',  label: 'High'     },
  medium:   { icon: Minus,         color: 'text-blue-400',   label: 'Medium'   },
  low:      { icon: ChevronUp,     color: 'text-[var(--to-text-dim)]', label: 'Low' },
};

export const STATUS_COLUMNS: { key: TicketStatus; label: string; accent: string }[] = [
  { key: 'todo',        label: 'To Do',       accent: 'border-[var(--to-text-dim)]/40' },
  { key: 'in_progress', label: 'In Progress', accent: 'border-amber-500/40' },
  { key: 'done',        label: 'Done',        accent: 'border-emerald-500/40' },
];

export const STATUS_META: Record<TicketStatus, { label: string; color: string; bg: string }> = {
  todo:        { label: 'Todo',        color: 'text-[var(--to-text-dim)]',    bg: 'bg-[var(--to-surface-raised)]' },
  in_progress: { label: 'In Progress', color: 'text-[var(--to-warning)]',     bg: 'bg-[var(--to-warning)]/10' },
  done:        { label: 'Done',        color: 'text-[var(--to-long)]',        bg: 'bg-[var(--to-long)]/10' },
};

export function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return new Date(iso).toLocaleDateString();
}
