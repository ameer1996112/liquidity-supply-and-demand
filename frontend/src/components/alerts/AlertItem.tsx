'use client';

import { AlertCircle, Bell, ShieldAlert } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Alert } from '@/hooks/useAlerts';

interface AlertItemProps {
  alert: Alert;
  onMarkRead?: (id: number) => void;
}

export function AlertItem({ alert, onMarkRead }: AlertItemProps) {
  const isCritical =
    String(alert.severity).toLowerCase() === 'critical' ||
    String(alert.severity).toLowerCase() === 'error';

  const Icon = isCritical ? ShieldAlert : AlertCircle;

  return (
    <div
      className={cn(
        'flex items-start gap-3 px-3 py-2 rounded-md',
        'bg-[#141821] hover:bg-[#1a1f2a] transition-colors',
      )}
    >
      <div
        className={cn(
          'mt-0.5 flex h-6 w-6 items-center justify-center rounded-full',
          isCritical
            ? 'bg-[var(--to-short)]/10 text-[var(--to-short)]'
            : 'bg-amber-500/10 text-amber-300',
        )}
      >
        <Icon className='h-3.5 w-3.5' />
      </div>
      <div className='flex-1 space-y-0.5'>
        <div className='flex items-center justify-between gap-2'>
          <div className='flex items-center gap-2'>
            <span className='text-xs font-semibold text-[var(--to-text-primary)]'>
              {alert.title || alert.alert_type}
            </span>
            {alert.signal_id && (
              <span className='rounded bg-[#1e222d] px-1.5 py-0.5 text-[10px] font-mono text-[var(--to-text-dim)]'>
                #{alert.signal_id}
              </span>
            )}
          </div>
          <span
            suppressHydrationWarning
            className='text-[10px] font-mono text-[var(--to-text-dim)]'
          >
            {new Date(alert.created_at).toLocaleTimeString(undefined, {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        </div>
        <p className='text-[11px] text-[var(--to-text-dim)] leading-snug'>
          {alert.message}
        </p>
        <div className='flex items-center justify-between pt-1'>
          <span className='text-[10px] uppercase tracking-wide text-[var(--to-text-dim)]'>
            {String(alert.severity).toUpperCase()}
          </span>
          {onMarkRead && (
            <button
              type='button'
              onClick={() => onMarkRead(alert.id)}
              className='inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)] hover:bg-[#242938]'
            >
              <Bell className='h-3 w-3' />
              Mark read
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
