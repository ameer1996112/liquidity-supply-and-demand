import React from 'react';
import { Bot } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Ticket, TYPE_META, PRIORITY_META, relativeTime } from './types';

export interface TicketCardProps {
  ticket: Ticket;
  onDragStart: (id: string) => void;
  onClick: (ticket: Ticket) => void;
}

export function TicketCard({ ticket, onDragStart, onClick }: TicketCardProps) {
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
