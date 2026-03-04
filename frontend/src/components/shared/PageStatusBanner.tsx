'use client';

import { AlertTriangle } from 'lucide-react';

type HealthStatus = 'healthy' | 'degraded' | 'offline';

interface PageStatusBannerProps {
  status: HealthStatus;
  /**
   * Optional label for the surface, e.g. "Dashboard" or "Signals".
   * Used only in the copy; safe to omit.
   */
  surfaceLabel?: string;
}

export function PageStatusBanner({ status, surfaceLabel }: PageStatusBannerProps) {
  if (status === 'healthy') return null;

  const isOffline = status === 'offline';
  const title = isOffline ? 'Trading backend unreachable' : 'Trading backend degraded';
  const scope = surfaceLabel ? `${surfaceLabel} · ` : '';
  const message = isOffline
    ? `${scope}Realtime data and actions may be unavailable until the API comes back online.`
    : `${scope}Realtime data may be delayed or partially unavailable while the API is degraded.`;

  return (
    <div className='rounded-lg border border-amber-500/30 bg-amber-950/60 px-3 py-2.5 text-[11px] text-amber-100 flex items-start gap-2'>
      <AlertTriangle className='mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-300' />
      <div>
        <div className='font-mono text-[10px] font-semibold uppercase tracking-[0.14em]'>
          {title}
        </div>
        <p className='mt-0.5 font-mono text-[10px] text-amber-100/80'>{message}</p>
      </div>
    </div>
  );
}

