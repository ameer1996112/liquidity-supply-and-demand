'use client';

import { useState } from 'react';
import { Bell } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAlerts } from '@/hooks/useAlerts';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { AlertItem } from '@/components/alerts/AlertItem';

export function AlertBell() {
  const [open, setOpen] = useState(false);
  const { alerts, unreadCount, markAsRead, clearAll, isLoading } = useAlerts();

  const hasAlerts = alerts.length > 0;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type='button'
          className={cn(
            'relative inline-flex h-8 w-8 items-center justify-center rounded-md border transition-all',
            open
              ? 'border-amber-500/40 bg-amber-500/15 text-amber-400 ring-1 ring-amber-500/30 shadow-[0_0_10px_rgba(245,158,11,0.15)]'
              : 'border-[#2a2e39] bg-[#141821] text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)] hover:bg-[#1a1f2a]'
          )}
          aria-label='Open alerts'
        >
          <Bell className='h-4 w-4' />
          {unreadCount > 0 && (
            <span className='absolute -right-0.5 -top-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white'>
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent className='w-80 p-0'>
        <div className='flex items-center justify-between border-b border-[#2a2e39] px-3 py-2'>
          <div className='flex items-center gap-2'>
            <span className='text-xs font-semibold uppercase tracking-wide text-[var(--to-text-dim)]'>
              Alerts
            </span>
            {isLoading && (
              <span className='text-[10px] text-[var(--to-text-dim)] font-mono'>
                syncing…
              </span>
            )}
          </div>
          {hasAlerts && (
            <button
              type='button'
              onClick={clearAll}
              className='text-[10px] text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)]'
            >
              Clear all
            </button>
          )}
        </div>
        <div className='max-h-80 overflow-y-auto py-2 space-y-1'>
          {!hasAlerts && (
            <p className='px-3 py-6 text-center text-xs text-[var(--to-text-dim)]'>
              No active alerts. You&apos;re all clear.
            </p>
          )}
          {alerts.map((alert) => (
            <AlertItem key={alert.id} alert={alert} onMarkRead={markAsRead} />
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}
