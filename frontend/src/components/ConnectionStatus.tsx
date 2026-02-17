/**
 * API Connectivity Indicator
 *
 * Shows real-time connection status to the backend API.
 * Displays "🟢 Online" or "🔴 Offline" badge.
 */

'use client';

import { useLiveTrading } from '@/hooks/useLiveTrading';
import { cn } from '@/lib/utils';
import { Cloud, CloudOff } from 'lucide-react';

export function ConnectionStatus() {
  const { isOnline, health } = useLiveTrading();

  const status = isOnline ? 'online' : 'offline';
  const color = isOnline ? 'text-emerald-400' : 'text-red-400';
  const bgColor = isOnline ? 'bg-emerald-400/10' : 'bg-red-400/10';
  const borderColor = isOnline ? 'border-emerald-400/20' : 'border-red-400/20';

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-3 py-1.5 rounded-md border',
        'transition-colors duration-300',
        bgColor,
        borderColor,
      )}
    >
      {isOnline ? (
        <Cloud className={cn('w-3.5 h-3.5', color)} />
      ) : (
        <CloudOff className={cn('w-3.5 h-3.5', color)} />
      )}
      <span className={cn('text-xs font-medium', color)}>
        {status === 'online' ? 'Online' : 'Offline'}
      </span>

      {/* Health Details (Optional) */}
      {health && isOnline && (
        <div className='flex items-center gap-1 ml-1 pl-2 border-l border-zinc-700'>
          <div
            className={cn(
              'w-1.5 h-1.5 rounded-full',
              health.redis ? 'bg-emerald-400' : 'bg-red-400',
            )}
            title={health.redis ? 'Redis Connected' : 'Redis Disconnected'}
          />
          <div
            className={cn(
              'w-1.5 h-1.5 rounded-full',
              health.supabase ? 'bg-emerald-400' : 'bg-red-400',
            )}
            title={
              health.supabase ? 'Supabase Connected' : 'Supabase Disconnected'
            }
          />
        </div>
      )}
    </div>
  );
}

/**
 * Minimal Connection Badge
 *
 * Compact version for sidebars/headers
 */
export function ConnectionBadge() {
  const { isOnline } = useLiveTrading();

  return (
    <div className='flex items-center gap-1.5'>
      <div
        className={cn(
          'w-2 h-2 rounded-full',
          isOnline ? 'bg-emerald-400 animate-pulse' : 'bg-red-400',
        )}
      />
      <span
        className={cn(
          'text-[10px] font-medium uppercase tracking-wider',
          isOnline ? 'text-emerald-400' : 'text-red-400',
        )}
      >
        {isOnline ? 'Live' : 'Offline'}
      </span>
    </div>
  );
}
