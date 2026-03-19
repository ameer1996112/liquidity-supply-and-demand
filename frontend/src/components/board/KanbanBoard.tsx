'use client';
import { useState } from 'react';
import { KanbanColumn } from './KanbanColumn';
import { NewTicketModal } from './NewTicketModal';
import { AgentFeed } from './AgentFeed';
import { useTickets, useCreateTicket, useMoveTicket } from '@/hooks/useBoard';
import { type TicketStatus } from '@/lib/boardSupabase';
import { Plus, LayoutGrid } from 'lucide-react';
import { cn } from '@/lib/utils';

const COLUMNS: TicketStatus[] = ['backlog', 'todo', 'in_progress', 'done'];
const TYPE_FILTERS = ['all', 'bug', 'task', 'feature', 'research'] as const;
type TypeFilter = (typeof TYPE_FILTERS)[number];

export function KanbanBoard() {
  const [showModal, setShowModal] = useState(false);
  const [defaultStatus, setDefaultStatus] = useState<TicketStatus>('backlog');
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all');

  const { data: tickets = [], isLoading } = useTickets();
  const createMutation = useCreateTicket();
  const moveMutation = useMoveTicket();

  const filtered =
    typeFilter === 'all' ? tickets : tickets.filter((t) => t.type === typeFilter);

  // Stats
  const bugCount = tickets.filter(
    (t) => t.status !== 'done' && t.type === 'bug'
  ).length;
  const inProg = tickets.filter((t) => t.status === 'in_progress').length;
  const todoCount = tickets.filter((t) => t.status === 'todo').length;
  const doneCount = tickets.filter((t) => t.status === 'done').length;

  function openModal(status: TicketStatus = 'backlog') {
    setDefaultStatus(status);
    setShowModal(true);
  }

  return (
    <div className='flex flex-col gap-5 pb-8'>
      {/* Page header */}
      <div className='flex flex-wrap items-center gap-3'>
        <div className='flex items-center gap-3'>
          <div className='flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-500/12 border border-indigo-500/25'>
            <LayoutGrid className='h-[18px] w-[18px] text-indigo-400' />
          </div>
          <div>
            <h1 className='page-title text-lg font-bold'>Task & Bug Board</h1>
            <p className='page-subtitle mt-0.5 text-xs'>
              Kanban board · AI agent integration · live updates
            </p>
          </div>
        </div>

        <div className='ml-auto flex items-center gap-2'>
          {/* Type filter */}
          <div className='surface-soft flex items-center gap-0.5 rounded-lg p-0.5'>
            {TYPE_FILTERS.map((f) => (
              <button
                key={f}
                onClick={() => setTypeFilter(f)}
                className={cn(
                  'rounded-md px-2.5 py-1 text-[10px] font-medium capitalize transition-colors',
                  typeFilter === f
                    ? 'bg-indigo-500/20 text-indigo-400'
                    : 'text-[var(--to-text-dim)] hover:text-slate-300'
                )}
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {f}
              </button>
            ))}
          </div>

          {/* New Ticket */}
          <button
            onClick={() => openModal('backlog')}
            className='flex items-center gap-1.5 rounded-lg bg-indigo-500 px-3.5 py-2 text-[12px] font-bold text-white shadow-[0_0_18px_rgba(99,102,241,0.35)] hover:bg-indigo-600 transition-colors'
          >
            <Plus className='h-3.5 w-3.5' />
            New Ticket
          </button>
        </div>
      </div>

      {/* Stats row */}
      <div className='grid grid-cols-4 gap-3'>
        {[
          { label: 'Active Bugs', val: bugCount, color: 'text-[var(--to-short)]' },
          { label: 'In Progress', val: inProg, color: 'text-yellow-400' },
          { label: 'Sprint Tasks', val: todoCount, color: 'text-blue-400' },
          { label: 'Completed', val: doneCount, color: 'text-[var(--to-long)]' },
        ].map(({ label, val, color }) => (
          <div
            key={label}
            className='tv-card flex items-center gap-3 px-4 py-3'
          >
            <span
              className={cn('text-2xl font-black tabular-nums', color)}
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {val}
            </span>
            <span className='text-[11px] text-[var(--to-text-dim)]'>{label}</span>
          </div>
        ))}
      </div>

      {/* Kanban columns */}
      {isLoading ? (
        <div className='grid grid-cols-4 gap-3'>
          {COLUMNS.map((s) => (
            <div
              key={s}
              className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface)] animate-pulse h-96'
            />
          ))}
        </div>
      ) : (
        <div className='grid grid-cols-4 gap-3'>
          {COLUMNS.map((status) => (
            <KanbanColumn
              key={status}
              status={status}
              tickets={filtered.filter((t) => t.status === status)}
              onMove={(id, s) => moveMutation.mutate({ id, status: s })}
              onAddNew={() => openModal(status)}
            />
          ))}
        </div>
      )}

      {/* Agent Feed */}
      <AgentFeed />

      {/* New Ticket Modal */}
      {showModal && (
        <NewTicketModal
          defaultStatus={defaultStatus}
          onClose={() => setShowModal(false)}
          isLoading={createMutation.isPending}
          onCreate={(input) => {
            createMutation.mutate(input, {
              onSuccess: () => setShowModal(false),
            });
          }}
        />
      )}
    </div>
  );
}
