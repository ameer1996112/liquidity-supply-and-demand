'use client';

import { useState } from 'react';
import { Bell } from 'lucide-react';
import { useAlerts } from '@/hooks/useAlerts';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { AlertItem } from '@/components/alerts/AlertItem';

export function AlertBell() {
  const [open, setOpen] = useState(false);
  const { alerts, unreadCount, markAsRead, clearAll, isLoading } = useAlerts();

  const hasAlerts = alerts.length > 0;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="relative inline-flex h-8 w-8 items-center justify-center rounded-md border border-[#2a2e39] bg-[#141821] text-zinc-400 hover:text-zinc-100 hover:bg-[#1a1f2a] transition-colors"
          aria-label="Open alerts"
        >
          <Bell className="h-4 w-4" />
          {unreadCount > 0 && (
            <span className="absolute -right-0.5 -top-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0">
        <div className="flex items-center justify-between border-b border-[#2a2e39] px-3 py-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
              Alerts
            </span>
            {isLoading && (
              <span className="text-[10px] text-zinc-600 font-mono">syncing…</span>
            )}
          </div>
          {hasAlerts && (
            <button
              type="button"
              onClick={clearAll}
              className="text-[10px] text-zinc-500 hover:text-zinc-200"
            >
              Clear all
            </button>
          )}
        </div>
        <div className="max-h-80 overflow-y-auto py-2 space-y-1">
          {!hasAlerts && (
            <p className="px-3 py-6 text-center text-xs text-zinc-500">
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

