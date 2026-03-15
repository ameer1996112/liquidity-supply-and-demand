'use client';
import { type Ticket, type TicketStatus } from '@/lib/boardSupabase';
import { TicketCard } from './TicketCard';
import { cn } from '@/lib/utils';
import { Plus } from 'lucide-react';

const COL_CONFIG: Record<
  TicketStatus,
  { label: string; icon: string; accent: string }
> = {
  backlog: {
    label: 'Backlog / Known Issues',
    icon: '📋',
    accent: 'bg-slate-500',
  },
  todo: {
    label: 'To Do (Current Sprint)',
    icon: '🛠️',
    accent: 'bg-blue-500',
  },
  in_progress: {
    label: 'In Progress',
    icon: '⏳',
    accent: 'bg-yellow-500',
  },
  done: {
    label: 'Completed / Deployed',
    icon: '✅',
    accent: 'bg-emerald-500',
  },
};

interface Props {
  status: TicketStatus;
  tickets: Ticket[];
  onMove: (id: string, status: TicketStatus) => void;
  onAddNew: () => void;
}

export function KanbanColumn({ status, tickets, onMove, onAddNew }: Props) {
  const cfg = COL_CONFIG[status];

  return (
    <div className='flex flex-col rounded-xl border border-[var(--to-border)] bg-[var(--to-surface)] overflow-hidden min-w-0'>
      {/* Column header */}
      <div className='relative px-4 py-3 border-b border-[var(--to-border)]'>
        <div className={cn('absolute top-0 left-0 right-0 h-0.5', cfg.accent)} />
        <div className='flex items-center gap-2'>
          <span className='text-sm'>{cfg.icon}</span>
          <span className='text-[12px] font-semibold text-[var(--to-text-secondary)]'>
            {cfg.label}
          </span>
          <span
            className='ml-auto text-[10px] px-2 py-0.5 rounded-full bg-[var(--to-surface-raised)] border border-[var(--to-border)] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {tickets.length}
          </span>
        </div>
      </div>

      {/* Cards */}
      <div className='flex-1 flex flex-col gap-2.5 p-3 overflow-y-auto max-h-[calc(100vh-300px)]'>
        {tickets.length === 0 ? (
          <div className='flex items-center justify-center h-16 rounded-lg border border-dashed border-[var(--to-border)]/50'>
            <span className='text-[11px] text-[var(--to-text-dim)]'>No tickets</span>
          </div>
        ) : (
          tickets.map((t) => <TicketCard key={t.id} ticket={t} onMove={onMove} />)
        )}
      </div>

      {/* Add button */}
      <button
        onClick={onAddNew}
        className='group flex items-center gap-1.5 px-4 py-2.5 border-t border-dashed border-[var(--to-border)] text-[11px] text-[var(--to-text-dim)] hover:text-[var(--to-warning)] hover:bg-[var(--to-warning)]/5 transition-colors'
      >
        <Plus className='h-3 w-3' />
        Add ticket
      </button>
    </div>
  );
}
