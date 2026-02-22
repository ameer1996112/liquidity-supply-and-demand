'use client';

import { useTradingMode } from '@/providers/TradingModeProvider';
import { Radio, FlaskConical, Wifi, WifiOff, Power } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useRiskStatus, useKillSwitchMutation } from '@/hooks/useRiskStatus';
import { useQuery } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';

export function TopBar() {
  const { mode, setMode } = useTradingMode();
  const { data: risk } = useRiskStatus();
  const killMutation = useKillSwitchMutation();

  const { data: health } = useQuery({
    queryKey: ['topbar-health'],
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) return { status: 'offline' as const };
      const res = await fetch(`${base}/health`, {
        signal: AbortSignal.timeout(3000),
      });
      if (!res.ok) return { status: 'offline' as const };
      return res.json() as Promise<{
        status: 'healthy' | 'degraded' | 'offline';
      }>;
    },
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
  const isConnected = health?.status != null && health.status !== 'offline';

  const toggleKillSwitch = () => {
    const enabled = !risk?.kill_switch_active;
    killMutation.mutate({
      enabled,
      reason: enabled ? 'TopBar emergency stop' : 'TopBar manual resume',
    });
  };

  return (
    <header className='flex h-12 shrink-0 items-center justify-between border-b border-[var(--to-border)] bg-[var(--to-bg)] px-3'>
      <div />

      <div className='flex items-center gap-2'>
        <div
          suppressHydrationWarning
          className={cn(
            'hidden items-center gap-1.5 rounded-md border px-2 py-1 text-[10px] font-semibold uppercase tracking-wider sm:flex',
            isConnected
              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
              : 'border-red-500/30 bg-red-500/10 text-red-400',
          )}
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {isConnected ? (
            <Wifi className='h-3 w-3' />
          ) : (
            <WifiOff className='h-3 w-3' />
          )}
          {isConnected ? 'Connected' : 'Reconnecting'}
        </div>

        {/* Mode toggle */}
        <div className='flex items-center rounded-lg border border-slate-800 bg-slate-900 p-0.5'>
          <button
            onClick={() => setMode('LIVE')}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-2.5 py-1 transition-colors',
              mode === 'LIVE'
                ? 'bg-emerald-500/15 text-emerald-400'
                : 'text-slate-500 hover:text-slate-300',
            )}
          >
            <Radio className='h-3 w-3' />
            <span
              className='text-[10px] font-semibold uppercase tracking-wider'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              Live
            </span>
          </button>
          <button
            onClick={() => setMode('PAPER')}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-2.5 py-1 transition-colors',
              mode === 'PAPER'
                ? 'bg-amber-500/15 text-amber-400'
                : 'text-slate-500 hover:text-slate-300',
            )}
          >
            <FlaskConical className='h-3 w-3' />
            <span
              className='text-[10px] font-semibold uppercase tracking-wider'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              Paper
            </span>
          </button>
        </div>

        <button
          onClick={toggleKillSwitch}
          disabled={killMutation.isPending}
          className={cn(
            'flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider transition-all',
            risk?.kill_switch_active
              ? 'animate-pulse border-red-500 bg-red-500/20 text-red-300'
              : 'border-slate-700 bg-slate-800/60 text-slate-300 hover:border-red-500/50 hover:text-red-300',
          )}
          style={{ fontFamily: 'var(--font-mono)' }}
          title='Emergency trading kill switch'
        >
          <Power className='h-3 w-3' />
          {risk?.kill_switch_active ? 'Kill Active' : 'Kill'}
        </button>
      </div>
    </header>
  );
}
