'use client';

import { useEffect, useState } from 'react';
import { useTradingMode } from '@/providers/TradingModeProvider';
import { Radio, FlaskConical, Wifi, WifiOff, Power, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useRiskStatus, useKillSwitchMutation } from '@/hooks/useRiskStatus';
import { useQuery } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';
import { KillSwitchConfirmDialog, type KillSwitchMode } from '@/components/risk/KillSwitchConfirmDialog';

function DualClock() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  if (!now) return null;

  const utc = now.toLocaleTimeString('en-GB', {
    timeZone: 'UTC',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
  const israel = now.toLocaleTimeString('en-GB', {
    timeZone: 'Asia/Jerusalem',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });

  return (
    <div
      className='hidden items-center gap-3 text-[10px] tabular-nums sm:flex'
      style={{ fontFamily: 'var(--font-mono)' }}
    >
      <div className='flex items-center gap-1.5 text-[var(--to-text-dim)]'>
        <Clock className='h-3 w-3' />
        <span className='text-[var(--to-text-secondary)]'>{utc}</span>
        <span className='text-[var(--to-text-dim)]'>UTC</span>
      </div>
      <span className='text-[var(--to-border)]'>|</span>
      <div className='flex items-center gap-1.5 text-[var(--to-text-dim)]'>
        <span className='text-[var(--to-text-secondary)]'>{israel}</span>
        <span className='text-[var(--to-text-dim)]'>IL</span>
      </div>
    </div>
  );
}

export function TopBar() {
  const { mode, setMode } = useTradingMode();
  const { data: risk } = useRiskStatus();
  const killMutation = useKillSwitchMutation();
  const [killDialogOpen, setKillDialogOpen] = useState(false);
  const [killDialogMode, setKillDialogMode] = useState<KillSwitchMode>('engage');

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

  const openKillDialog = () => {
    if (!risk) return;
    const mode: KillSwitchMode = risk.kill_switch_active ? 'reset' : 'engage';
    setKillDialogMode(mode);
    setKillDialogOpen(true);
  };

  return (
    <header className='flex h-10 shrink-0 items-center justify-between border-b border-[var(--to-border)] bg-[var(--to-bg)] px-3'>
      {/* Left: Clock */}
      <DualClock />

      <div className='flex items-center gap-1.5'>
        {/* Connection indicator */}
        <div
          suppressHydrationWarning
          className={cn(
            'hidden items-center gap-1.5 rounded border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider sm:flex',
            isConnected
              ? 'border-[var(--to-long)]/25 bg-[var(--to-long)]/8 text-[var(--to-long)]'
              : 'border-[var(--to-short)]/25 bg-[var(--to-short)]/8 text-[var(--to-short)]',
          )}
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {isConnected ? (
            <Wifi className='h-3 w-3' />
          ) : (
            <WifiOff className='h-3 w-3' />
          )}
          {isConnected ? 'Connected' : 'Offline'}
        </div>

        {/* Mode toggle */}
        <div className='flex items-center rounded border border-[var(--to-border)] bg-[var(--to-surface)] p-0.5'>
          <button
            onClick={() => setMode('LIVE')}
            className={cn(
              'flex items-center gap-1 rounded px-2 py-0.5 transition-colors',
              mode === 'LIVE'
                ? 'bg-[var(--to-long)]/12 text-[var(--to-long)]'
                : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]',
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
              'flex items-center gap-1 rounded px-2 py-0.5 transition-colors',
              mode === 'PAPER'
                ? 'bg-[var(--to-warning)]/12 text-[var(--to-warning)]'
                : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]',
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

        {/* Kill switch */}
        <button
          onClick={openKillDialog}
          disabled={killMutation.isPending}
          className={cn(
            'flex items-center gap-1 rounded border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider transition-all',
            risk?.kill_switch_active
              ? 'animate-pulse border-[var(--to-short)] bg-[var(--to-short)]/20 text-[var(--to-short)]'
              : 'border-[var(--to-border)] bg-[var(--to-surface)] text-[var(--to-text-dim)] hover:border-[var(--to-short)]/50 hover:text-[var(--to-short)]',
          )}
          style={{ fontFamily: 'var(--font-mono)' }}
          title='Emergency trading kill switch'
        >
          <Power className='h-3 w-3' />
          {risk?.kill_switch_active ? 'KILL ON' : 'Kill'}
        </button>
      </div>

      <KillSwitchConfirmDialog
        open={killDialogOpen}
        mode={killDialogMode}
        onOpenChange={setKillDialogOpen}
        isPending={killMutation.isPending}
        onConfirm={(reason) => {
          const enabled = killDialogMode === 'engage';
          killMutation.mutate({ enabled, reason });
          setKillDialogOpen(false);
        }}
      />
    </header>
  );
}
