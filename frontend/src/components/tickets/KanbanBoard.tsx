import React, { useState } from 'react';
import { Minus, Inbox } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Ticket, TicketStatus, STATUS_COLUMNS } from './types';
import { TicketCard } from './TicketCard';

interface KanbanColumnProps {
  column: { key: TicketStatus; label: string; accent: string };
  tickets: Ticket[];
  onDragStart: (id: string) => void;
  onDrop: (status: TicketStatus) => void;
  onClick: (t: Ticket) => void;
}

function KanbanColumn({
  column,
  tickets,
  onDragStart,
  onDrop,
  onClick,
}: KanbanColumnProps) {
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
          <div className="py-4 h-full flex items-center justify-center">
            <div className="flex flex-col items-center gap-2 py-8 text-center rounded-lg border border-dashed border-[var(--to-border)] w-full bg-[var(--to-surface)]/30">
              <div className="mb-1 animate-bounce text-[var(--to-text-dim)]">
                <Inbox className="h-5 w-5" />
              </div>
              <span className="font-mono text-[10px] uppercase tracking-wider font-semibold text-[var(--to-text-dim)]">No tickets</span>
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

export interface KanbanBoardProps {
  tickets: Ticket[];
  isLoading: boolean;
  onDragStart: (id: string) => void;
  onDrop: (status: TicketStatus) => void;
  onClickTicket: (ticket: Ticket) => void;
}

export function KanbanBoard({ tickets, isLoading, onDragStart, onDrop, onClickTicket }: KanbanBoardProps) {
  if (isLoading && tickets.length === 0) {
    return (
      <div className="py-16 text-center">
        <p className="font-mono text-xs text-[var(--to-text-dim)] animate-pulse">Loading tickets…</p>
      </div>
    );
  }

  const getTicketsByStatus = (status: TicketStatus) => 
    tickets.filter((t) => t.status === status);

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {STATUS_COLUMNS.map((col) => (
        <KanbanColumn
          key={col.key}
          column={col}
          tickets={getTicketsByStatus(col.key)}
          onDragStart={onDragStart}
          onDrop={onDrop}
          onClick={onClickTicket}
        />
      ))}
    </div>
  );
}
