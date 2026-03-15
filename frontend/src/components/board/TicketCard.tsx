'use client';
import { type Ticket, type TicketStatus } from '@/lib/boardSupabase';
import { cn } from '@/lib/utils';
import { Bug, Bookmark, Sparkles, FlaskConical } from 'lucide-react';

const TYPE_ICONS = {
  bug: Bug,
  task: Bookmark,
  feature: Sparkles,
  research: FlaskConical,
};

const PRIORITY_BORDER: Record<string, string> = {
  critical: 'border-l-red-500',
  high: 'border-l-orange-500',
  medium: 'border-l-yellow-500',
  low: 'border-l-blue-500',
};

const PRIORITY_BADGE: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-300 border border-red-500/30',
  high: 'bg-orange-500/15 text-orange-300 border border-orange-500/30',
  medium: 'bg-yellow-500/15 text-yellow-300 border border-yellow-500/30',
  low: 'bg-blue-500/15 text-blue-300 border border-blue-500/30',
};

const COMPONENT_BADGE: Record<string, string> = {
  'Pine Script': 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20',
  'Python Backend': 'bg-blue-500/10 text-blue-300 border border-blue-500/20',
  'Supabase / DB': 'bg-purple-500/10 text-purple-300 border border-purple-500/20',
  'Frontend (React)': 'bg-orange-500/10 text-orange-300 border border-orange-500/20',
  'MetaTrader / MT5': 'bg-yellow-500/10 text-yellow-300 border border-yellow-500/20',
  'AI / ML Pipeline': 'bg-pink-500/10 text-pink-300 border border-pink-500/20',
  Infrastructure: 'bg-slate-500/10 text-slate-300 border border-slate-500/20',
};

const STATUS_ORDER: TicketStatus[] = ['backlog', 'todo', 'in_progress', 'done'];

interface Props {
  ticket: Ticket;
  onMove?: (id: string, status: TicketStatus) => void;
}

export function TicketCard({ ticket, onMove }: Props) {
  const IconComp = TYPE_ICONS[ticket.type] ?? Bookmark;
  const compClass =
    COMPONENT_BADGE[ticket.component] ??
    'bg-slate-500/10 text-slate-300 border border-slate-500/20';
  const currentIdx = STATUS_ORDER.indexOf(ticket.status);
  const canAdvance = onMove && currentIdx < STATUS_ORDER.length - 1;
  const canRevert = onMove && currentIdx > 0;

  return (
    <div
      className={cn(
        'group relative rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)]',
        'border-l-[3px] p-3 transition-all duration-200',
        'hover:border-[var(--to-warning)]/40 hover:shadow-md cursor-pointer',
        PRIORITY_BORDER[ticket.priority]
      )}
    >
      {/* Header */}
      <div className='flex items-start gap-2 mb-2'>
        <span
          className='text-[10px] text-[var(--to-text-dim)] shrink-0 mt-0.5'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {ticket.ticket_id}
        </span>
        <IconComp className='h-3.5 w-3.5 text-[var(--to-text-dim)] shrink-0 mt-0.5' />
        <p className='text-[12px] font-medium text-[var(--to-text-secondary)] leading-snug flex-1'>
          {ticket.title}
        </p>
      </div>

      {/* Tags */}
      <div className='flex flex-wrap gap-1.5 mt-2'>
        <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium', compClass)}>
          {ticket.component}
        </span>
        <span
          className={cn(
            'rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide',
            PRIORITY_BADGE[ticket.priority]
          )}
        >
          {ticket.priority}
        </span>
      </div>

      {/* Quick-move buttons (visible on hover) */}
      {onMove && (
        <div className='absolute top-2 right-2 hidden group-hover:flex gap-1'>
          {canRevert && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onMove(ticket.id, STATUS_ORDER[currentIdx - 1]);
              }}
              className='text-[10px] px-1.5 py-0.5 rounded bg-[var(--to-surface)] border border-[var(--to-border)] text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)] transition-colors'
              title='Move back'
            >
              ←
            </button>
          )}
          {canAdvance && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onMove(ticket.id, STATUS_ORDER[currentIdx + 1]);
              }}
              className='text-[10px] px-1.5 py-0.5 rounded bg-[var(--to-surface)] border border-[var(--to-border)] text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)] transition-colors'
              title='Move forward'
            >
              →
            </button>
          )}
        </div>
      )}
    </div>
  );
}
