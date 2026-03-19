'use client';

import { useEffect, useState } from 'react';
import { supabase } from '@/lib/supabase';
import { getHealthUrl } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Database, Radio, Train, Wifi } from 'lucide-react';

type Status = 'checking' | 'online' | 'offline' | 'error';

interface ServiceStatus {
  name: string;
  status: Status;
  detail: string;
  icon: React.ReactNode;
}

export function ConnectionStatus() {
  const [services, setServices] = useState<ServiceStatus[]>([
    { name: 'Supabase Database', status: 'checking', detail: 'Checking connection...', icon: <Database className="w-4 h-4" /> },
    { name: 'Supabase Realtime', status: 'checking', detail: 'Checking subscription...', icon: <Radio className="w-4 h-4" /> },
    { name: 'Railway Backend', status: 'checking', detail: 'Checking API health...', icon: <Train className="w-4 h-4" /> },
  ]);

  useEffect(() => {
    const update = (index: number, status: Status, detail: string) => {
      setServices((prev) => prev.map((s, i) => (i === index ? { ...s, status, detail } : s)));
    };

    let channel: ReturnType<NonNullable<typeof supabase>['channel']> | null = null;

    // 1. Test Supabase DB
    if (!supabase) {
      update(0, 'offline', 'Supabase not configured (missing env vars)');
      update(1, 'offline', 'Requires Supabase connection');
    } else {
      const client = supabase;

      Promise.resolve(
        client
          .from('trading_signals')
          .select('count', { count: 'exact', head: true })
      )
        .then(({ error }) => {
          if (error) {
            update(0, 'error', error.message);
          } else {
            update(0, 'online', 'Connected to trading_signals table');
          }
        })
        .catch((err) => {
          update(0, 'error', err instanceof Error ? err.message : 'Unknown error');
        });

      // 2. Test Realtime
      channel = client
        .channel('settings-health-check')
        .on('postgres_changes', { event: '*', schema: 'public', table: 'trading_signals' }, () => {})
        .subscribe((status, err) => {
          if (status === 'SUBSCRIBED') {
            update(1, 'online', 'Listening for postgres_changes events');
          } else if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT') {
            update(1, 'error', err?.message || `Channel ${status.toLowerCase()}`);
          } else if (status === 'CLOSED') {
            update(1, 'offline', 'Channel closed');
          }
        });
    }

    // 3. Test Railway Backend API (always runs, independent of Supabase)
    const healthUrl = getHealthUrl();
    if (!healthUrl) {
      update(2, 'offline', 'NEXT_PUBLIC_API_URL not configured');
    } else {
      fetch(healthUrl, { signal: AbortSignal.timeout(5000) })
        .then((res) => {
          if (res.ok) {
            return res.json().then((data) => {
              const extra = data?.status || 'healthy';
              update(2, 'online', `Railway API responding (${extra})`);
            }).catch(() => {
              update(2, 'online', 'Railway API responding');
            });
          } else {
            update(2, 'error', `HTTP ${res.status}`);
          }
        })
        .catch(() => {
          update(2, 'offline', `Cannot reach ${healthUrl}`);
        });
    }

    return () => {
      if (channel && supabase) {
        supabase.removeChannel(channel);
      }
    };
  }, []);

  const statusColor = (status: Status) => {
    switch (status) {
      case 'online': return 'text-[var(--to-long)]';
      case 'offline': return 'text-[var(--to-text-dim)]';
      case 'error': return 'text-rose-400';
      default: return 'text-amber-400';
    }
  };

  const statusDot = (status: Status) => {
    switch (status) {
      case 'online': return 'bg-emerald-400';
      case 'offline': return 'bg-[var(--to-surface-raised)]';
      case 'error': return 'bg-rose-400';
      default: return 'bg-amber-400 animate-pulse';
    }
  };

  const rowTone = (service: ServiceStatus) => {
    // Highlight obvious misconfigurations (missing env / URL) with semantic tones
    const detail = service.detail.toLowerCase();
    const isMissingEnv =
      detail.includes('not configured') || detail.includes('missing env');
    const isCritical =
      isMissingEnv && (detail.includes('supabase') || detail.includes('api_url'));

    if (!isMissingEnv) return '';
    if (isCritical) {
      return 'bg-[var(--to-short)]/8 border-l-2 border-[var(--to-short)]/50';
    }
    return 'bg-amber-500/5 border-l-2 border-amber-500/40';
  };

  return (
    <div className="to-panel">
      <div className="to-panel-header">
        <div className="flex items-center gap-2">
          <Wifi className="w-4 h-4 text-text-dim" />
          <span
            className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-muted"
          >
            Connection Status
          </span>
        </div>
      </div>
      <div className="divide-y divide-panel-border-subtle">
        {services.map((service) => (
          <div
            key={service.name}
            className={cn(
              'px-4 py-3 flex items-center justify-between',
              rowTone(service),
            )}
          >
            <div className="flex items-center gap-3">
              <div className="text-text-muted">{service.icon}</div>
              <div>
                <span className="text-[13px] text-text-primary font-medium">
                  {service.name}
                </span>
                <p className="mt-0.5 font-mono text-[11px] text-text-secondary">
                  {service.detail}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className={cn('w-2 h-2 rounded-full', statusDot(service.status))} />
              <span
                className={cn(
                  'font-mono text-[11px] uppercase',
                  statusColor(service.status),
                )}
              >
                {service.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
