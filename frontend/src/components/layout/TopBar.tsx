'use client';

import { useMemo, useState } from 'react';
import {
  useSignalStats,
  useRefreshSignals,
  useTradingSignals,
} from '@/hooks/useTradingSignals';
import { useTradingMode } from '@/providers/TradingModeProvider';
import {
  computeTradeKpis,
  formatWinRate,
} from '@/domain/metrics/tradingMetrics';
import { Button } from '@/components/ui/button';
import { RiskBar } from '@/components/risk/RiskBar';
import {
  RefreshCw,
  Radio,
  FlaskConical,
  Moon,
  Sun,
  Wifi,
  WifiOff,
  Power,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { AlertBell } from '@/components/alerts/AlertBell';
import { useTheme } from '@/providers/ThemeProvider';
import { useRiskStatus, useKillSwitchMutation } from '@/hooks/useRiskStatus';
import { useQuery } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';

interface MetricProps {
  label: string;
  value: string | number;
  trend?: 'up' | 'down';
}

function Metric({ label, value, trend }: MetricProps) {
  return (
    <div className='flex min-w-[100px] flex-col gap-0.5 border-r border-slate-800 px-3 last:border-r-0'>
      <span
        className='text-[9px] font-medium uppercase tracking-[0.12em] text-slate-500'
        style={{ fontFamily: 'var(--font-sans)' }}
      >
        {label}
      </span>
      <span
        className={cn(
          'text-[13px] font-semibold tabular-nums',
          trend === 'up' && 'text-emerald-400',
          trend === 'down' && 'text-red-400',
          !trend && 'text-slate-200'
        )}
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        {value}
      </span>
    </div>
  );
}

export function TopBar() {
  const { mode, setMode } = useTradingMode();
  const { theme, toggleTheme } = useTheme();
  const { data: stats, isLoading } = useSignalStats();
  const { data: signals = [] } = useTradingSignals(mode);
  const { data: risk } = useRiskStatus();
  const killMutation = useKillSwitchMutation();
  const refreshSignals = useRefreshSignals();
  const [isRefreshing, setIsRefreshing] = useState(false);

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
    refetchInterval: 10_000,
    staleTime: 5_000,
  });

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refreshSignals();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  const tradeKpis = useMemo(() => computeTradeKpis(signals), [signals]);
  const winRateNumeric = tradeKpis.winRatePct ?? 0;
  const winRateLabel = formatWinRate(
    tradeKpis.winRatePct,
    tradeKpis.totalTrades,
    'dash'
  );

  const dailyPnl =
    mode === 'PAPER'
      ? stats?.paper_daily_pnl ?? stats?.paper_pnl_24h ?? 0
      : stats?.live_daily_pnl ?? stats?.live_pnl_24h ?? 0;

  const totalPnl = tradeKpis.totalPnl;
  const isConnected = health?.status && health.status !== 'offline';

  const toggleKillSwitch = () => {
    const enabled = !risk?.kill_switch_active;
    killMutation.mutate({
      enabled,
      reason: enabled ? 'TopBar emergency stop' : 'TopBar manual resume',
    });
  };

  return (
    <header className='flex h-12 shrink-0 items-center justify-between border-b border-[var(--to-border)] bg-[var(--to-bg)] px-3'>
      {/* ── Left: metrics strip ─────────────────────────────────── */}
      <div className='flex items-center overflow-x-auto scrollbar-thin'>
        {isLoading ? (
          <div className='flex items-center gap-0'>
            {[...Array(4)].map((_, i) => (
              <div
                key={i}
                className='flex min-w-[100px] flex-col gap-1 border-r border-slate-800 px-3 last:border-r-0'
              >
                <div className='h-2 w-12 rounded bg-slate-800 animate-pulse' />
                <div className='h-3 w-16 rounded bg-slate-800 animate-pulse' />
              </div>
            ))}
          </div>
        ) : (
          <div className='flex items-center'>
            <Metric
              label='Win Rate'
              value={winRateLabel}
              trend={winRateNumeric >= 50 ? 'up' : 'down'}
            />
            <Metric label='Active' value={stats?.active_trades ?? 0} />
            <Metric
              label='Daily PnL'
              value={`${dailyPnl >= 0 ? '+' : ''}$${dailyPnl.toFixed(2)}`}
              trend={dailyPnl >= 0 ? 'up' : 'down'}
            />
            <Metric
              label='Total PnL'
              value={`${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}`}
              trend={totalPnl >= 0 ? 'up' : 'down'}
            />
          </div>
        )}
      </div>

      {/* ── Center: Risk Cockpit ─────────────────────────────────── */}
      <div className='hidden xl:flex xl:flex-1 xl:justify-center'>
        <RiskBar />
      </div>

      {/* ── Right: mode toggle + actions ────────────────────────── */}
      <div className='flex items-center gap-2'>
        <div
          className={cn(
            'hidden items-center gap-1.5 rounded-md border px-2 py-1 text-[10px] font-semibold uppercase tracking-wider sm:flex',
            isConnected
              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
              : 'border-red-500/30 bg-red-500/10 text-red-400'
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

        <AlertBell />

        {/* Mode toggle */}
        <div className='flex items-center rounded-lg border border-slate-800 bg-slate-900 p-0.5'>
          <button
            onClick={() => setMode('LIVE')}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-2.5 py-1 transition-colors',
              mode === 'LIVE'
                ? 'bg-emerald-500/15 text-emerald-400'
                : 'text-slate-500 hover:text-slate-300'
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
                : 'text-slate-500 hover:text-slate-300'
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

        {/* Refresh */}
        <Button
          variant='ghost'
          size='sm'
          onClick={handleRefresh}
          disabled={isRefreshing}
          className='h-7 w-7 rounded-lg border border-transparent p-0 text-slate-500 hover:border-slate-700 hover:bg-slate-800 hover:text-slate-300'
        >
          <RefreshCw
            className={cn('h-3.5 w-3.5', isRefreshing && 'animate-spin')}
          />
        </Button>

        <Button
          variant='ghost'
          size='sm'
          onClick={toggleTheme}
          className='h-7 w-7 rounded-lg border border-transparent p-0 text-slate-500 hover:border-slate-700 hover:bg-slate-800 hover:text-slate-300'
          title='Toggle theme'
        >
          {theme === 'dark' ? (
            <Sun className='h-3.5 w-3.5' />
          ) : (
            <Moon className='h-3.5 w-3.5' />
          )}
        </Button>

        <button
          onClick={toggleKillSwitch}
          disabled={killMutation.isPending}
          className={cn(
            'flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider transition-all',
            risk?.kill_switch_active
              ? 'animate-pulse border-red-500 bg-red-500/20 text-red-300'
              : 'border-slate-700 bg-slate-800/60 text-slate-300 hover:border-red-500/50 hover:text-red-300'
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
