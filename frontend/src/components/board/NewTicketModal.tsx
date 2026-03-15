'use client';
import { useState } from 'react';
import { X } from 'lucide-react';
import { type CreateTicketInput, type TicketStatus } from '@/lib/boardSupabase';

const COMPONENTS = [
  'Pine Script',
  'Python Backend',
  'Supabase / DB',
  'Frontend (React)',
  'MetaTrader / MT5',
  'AI / ML Pipeline',
  'Infrastructure',
];

interface Props {
  defaultStatus?: TicketStatus;
  onClose: () => void;
  onCreate: (input: CreateTicketInput) => void;
  isLoading?: boolean;
}

export function NewTicketModal({
  defaultStatus = 'backlog',
  onClose,
  onCreate,
  isLoading,
}: Props) {
  const [form, setForm] = useState<CreateTicketInput>({
    type: 'bug',
    title: '',
    description: '',
    component: 'Python Backend',
    priority: 'medium',
    status: defaultStatus,
  });

  const set = (k: keyof CreateTicketInput, v: string) =>
    setForm((f) => ({ ...f, [k]: v }));

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim()) return;
    onCreate(form);
  }

  return (
    <div
      className='fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm'
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className='w-[520px] max-h-[90vh] overflow-y-auto rounded-2xl border border-[var(--to-border)] bg-[var(--to-surface)] shadow-2xl'>
        {/* Header */}
        <div className='flex items-center justify-between border-b border-[var(--to-border)] px-6 py-4'>
          <h2 className='text-[15px] font-bold text-[var(--to-text-primary)]'>
            ✏️ Create New Ticket
          </h2>
          <button
            onClick={onClose}
            className='rounded-lg p-1.5 text-[var(--to-text-dim)] hover:bg-[var(--to-surface-raised)] hover:text-[var(--to-text-primary)] transition-colors'
          >
            <X className='h-4 w-4' />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className='flex flex-col gap-4 px-6 py-5'>
          {/* Title */}
          <label className='flex flex-col gap-1.5'>
            <span
              className='text-[11px] font-bold uppercase tracking-wider text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              Title *
            </span>
            <input
              required
              value={form.title}
              onChange={(e) => set('title', e.target.value)}
              placeholder='e.g. Council column showing empty on dashboard'
              className='rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-2 text-[13px] text-[var(--to-text-primary)] outline-none placeholder:text-[var(--to-text-dim)] focus:border-[var(--to-warning)]/60'
            />
          </label>

          {/* Type + Priority */}
          <div className='grid grid-cols-2 gap-3'>
            <label className='flex flex-col gap-1.5'>
              <span
                className='text-[11px] font-bold uppercase tracking-wider text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                Type *
              </span>
              <select
                value={form.type}
                onChange={(e) => set('type', e.target.value)}
                className='rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-2 text-[13px] text-[var(--to-text-primary)] outline-none focus:border-[var(--to-warning)]/60'
              >
                <option value='bug'>🐛 Bug</option>
                <option value='task'>📌 Task</option>
                <option value='feature'>✨ Feature</option>
                <option value='research'>🔬 Research</option>
              </select>
            </label>
            <label className='flex flex-col gap-1.5'>
              <span
                className='text-[11px] font-bold uppercase tracking-wider text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                Priority *
              </span>
              <select
                value={form.priority}
                onChange={(e) => set('priority', e.target.value)}
                className='rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-2 text-[13px] text-[var(--to-text-primary)] outline-none focus:border-[var(--to-warning)]/60'
              >
                <option value='critical'>🔴 Critical</option>
                <option value='high'>🟠 High</option>
                <option value='medium'>🟡 Medium</option>
                <option value='low'>🔵 Low</option>
              </select>
            </label>
          </div>

          {/* Component + Initial Column */}
          <div className='grid grid-cols-2 gap-3'>
            <label className='flex flex-col gap-1.5'>
              <span
                className='text-[11px] font-bold uppercase tracking-wider text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                Component *
              </span>
              <select
                value={form.component}
                onChange={(e) => set('component', e.target.value)}
                className='rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-2 text-[13px] text-[var(--to-text-primary)] outline-none focus:border-[var(--to-warning)]/60'
              >
                {COMPONENTS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <label className='flex flex-col gap-1.5'>
              <span
                className='text-[11px] font-bold uppercase tracking-wider text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                Initial Column
              </span>
              <select
                value={form.status}
                onChange={(e) => set('status', e.target.value)}
                className='rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-2 text-[13px] text-[var(--to-text-primary)] outline-none focus:border-[var(--to-warning)]/60'
              >
                <option value='backlog'>📋 Backlog</option>
                <option value='todo'>🛠️ To Do</option>
                <option value='in_progress'>⏳ In Progress</option>
              </select>
            </label>
          </div>

          {/* Description */}
          <label className='flex flex-col gap-1.5'>
            <span
              className='text-[11px] font-bold uppercase tracking-wider text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              Description
            </span>
            <textarea
              value={form.description}
              onChange={(e) => set('description', e.target.value)}
              rows={3}
              placeholder='Steps to reproduce, expected vs actual behavior, relevant logs…'
              className='rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 py-2 text-[13px] text-[var(--to-text-primary)] outline-none placeholder:text-[var(--to-text-dim)] focus:border-[var(--to-warning)]/60 resize-none'
            />
          </label>

          {/* AI integration note */}
          <div className='rounded-lg border border-indigo-500/20 bg-indigo-500/8 px-4 py-3 flex gap-3'>
            <span className='text-base shrink-0'>🤖</span>
            <p className='text-[11px] text-indigo-300 leading-relaxed'>
              <strong className='text-indigo-400'>AI Agent Integration:</strong> When
              an agent picks up this ticket, it will automatically move the card through
              columns and post updates to the Activity Feed.
            </p>
          </div>

          {/* Footer */}
          <div className='flex justify-end gap-2 pt-1'>
            <button
              type='button'
              onClick={onClose}
              className='rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-4 py-2 text-[12px] font-medium text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)] transition-colors'
            >
              Cancel
            </button>
            <button
              type='submit'
              disabled={isLoading}
              className='rounded-lg bg-[var(--to-warning)] px-4 py-2 text-[12px] font-bold text-black hover:opacity-90 transition-opacity disabled:opacity-50'
            >
              {isLoading ? 'Creating…' : 'Create Ticket'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
