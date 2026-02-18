'use client';

import { useMemo } from 'react';
import {
  useSignalStats,
  useRefreshSignals,
  useTradingSignals,
} from '@/hooks/useTradingSignals';
import { useTradingMode } from '@/providers/TradingModeProvider';
import { getPnl } from '@/types/trading';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { RiskBar } from '@/components/risk/RiskBar';
import {
  Activity,
  TrendingUp,
  TrendingDown,
  Zap,
  DollarSign,
  RefreshCw,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useState } from 'react';
import { AlertBell } from '@/components/alerts/AlertBell';

interface MetricProps {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  trend?: 'up' | 'down';
}

function Metric({ label, value, icon, trend }: MetricProps) {
  return (
    <div className='flex min-w-[120px] items-center gap-2 rounded-xl border border-[rgba(95,119,163,0.3)] bg-[rgba(17,26,44,0.86)] px-2.5 py-1.5'>
      <div className='flex h-7 w-7 items-center justify-center rounded-lg border border-[rgba(102,126,173,0.4)] bg-[rgba(30,45,72,0.8)] text-[#9eb3dc]'>
        {icon}
      </div>
      <div className='flex flex-col'>
        <span className='text-[10px] font-medium leading-none tracking-wider text-[#8e9dbf] uppercase'>
          {label}
        </span>
        <span
          className={cn(
            'font-mono text-sm font-semibold leading-tight tabular-nums',
            trend === 'up' && 'text-[#2ec9aa]',
            trend === 'down' && 'text-[#ff7288]',
            !trend && 'text-[#edf3ff]'
          )}
        >
          {value}
        </span>
      </div>
    </div>
  );
}

function MetricSkeleton() {
  return (
    <div className='flex min-w-[120px] items-center gap-2 rounded-xl border border-[rgba(95,119,163,0.3)] bg-[rgba(17,26,44,0.86)] px-2.5 py-1.5'>
      <Skeleton className='h-7 w-7 rounded-lg bg-[rgba(30,45,72,0.8)]' />
      <div className='flex flex-col gap-1'>
        <Skeleton className='h-2.5 w-14 bg-[rgba(30,45,72,0.8)]' />
        <Skeleton className='h-3.5 w-10 bg-[rgba(30,45,72,0.8)]' />
      </div>
    </div>
  );
}

export function TopBar() {
  const { mode } = useTradingMode();
  const { data: stats, isLoading } = useSignalStats();
  const { data: signals = [] } = useTradingSignals(mode);
  const refreshSignals = useRefreshSignals();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refreshSignals();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  // Win rate: compute from closed signals for current mode (same source as Total PnL)
  const winRate = useMemo(() => {
    const closed = signals.filter((s) => {
      const st = s.status?.toLowerCase();
      const pnl = getPnl(s);
      return (st === 'closed' || st === 'executed') && pnl != null;
    });
    if (closed.length === 0) return 0;
    const wins = closed.filter((s) => (getPnl(s) ?? 0) > 0).length;
    return (wins / closed.length) * 100;
  }, [signals]);

  const dailyPnl =
    mode === 'PAPER'
      ? stats?.paper_daily_pnl ?? stats?.paper_pnl_24h ?? 0
      : stats?.live_daily_pnl ?? stats?.live_pnl_24h ?? 0;

  // Total PnL: use same source as Equity Curve (closed signals for current mode) for consistency
  const totalPnl = useMemo(() => {
    const closed = signals.filter((s) => {
      const st = s.status?.toLowerCase();
      const pnl = getPnl(s);
      return (st === 'closed' || st === 'executed') && pnl != null;
    });
    return closed.reduce((sum, s) => sum + (getPnl(s) ?? 0), 0);
  }, [signals]);

  return (
    <header className='flex h-14 items-center justify-between gap-3 border-b border-[rgba(94,117,161,0.28)] bg-[rgba(8,14,25,0.86)] px-3 backdrop-blur-md sm:px-4'>
      {/* Left: Metrics */}
      <div className='scrollbar-thin flex items-center gap-2 overflow-x-auto pr-1'>
        {isLoading ? (
          <>
            <MetricSkeleton />
            <MetricSkeleton />
            <MetricSkeleton />
            <MetricSkeleton />
          </>
        ) : (
          <>
            <Metric
              label='Win Rate'
              value={`${winRate.toFixed(1)}%`}
              icon={
                winRate >= 50 ? (
                  <TrendingUp className='w-3.5 h-3.5' />
                ) : (
                  <TrendingDown className='w-3.5 h-3.5' />
                )
              }
              trend={winRate >= 50 ? 'up' : 'down'}
            />
            <Metric
              label='Active'
              value={stats?.active_trades || 0}
              icon={<Zap className='w-3.5 h-3.5' />}
            />
            <Metric
              label='Daily PnL'
              value={`${dailyPnl >= 0 ? '+' : ''}$${dailyPnl.toFixed(2)}`}
              icon={<DollarSign className='w-3.5 h-3.5' />}
              trend={dailyPnl >= 0 ? 'up' : 'down'}
            />
            <Metric
              label='Total PnL'
              value={`${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}`}
              icon={<Activity className='w-3.5 h-3.5' />}
              trend={totalPnl >= 0 ? 'up' : 'down'}
            />
          </>
        )}
      </div>

      {/* Center: Risk Cockpit */}
      <div className='hidden xl:flex xl:flex-1 xl:justify-center'>
        <RiskBar />
      </div>

      {/* Right: Actions */}
      <div className='flex items-center gap-2 sm:gap-3'>
        {/* Alerts */}
        <AlertBell />

        {/* Connection indicator / mode badge */}
        <div className='flex items-center gap-1.5 rounded-lg border border-[rgba(95,119,163,0.3)] bg-[rgba(17,26,44,0.86)] px-2.5 py-1'>
          <div
            className={cn(
              'h-1.5 w-1.5 rounded-full animate-pulse',
              mode === 'PAPER' ? 'bg-[#ffb14f]' : 'bg-[#2ec9aa]'
            )}
          />
          <span className='font-mono text-[10px] uppercase tracking-wider text-[#9aabce]'>
            {mode}
          </span>
        </div>

        <Button
          variant='ghost'
          size='sm'
          onClick={handleRefresh}
          disabled={isRefreshing}
          className='h-8 w-8 rounded-lg border border-transparent p-0 text-[#9aabce] hover:border-[rgba(95,119,163,0.3)] hover:bg-[rgba(17,26,44,0.86)] hover:text-[#edf3ff]'
        >
          <RefreshCw
            className={cn('w-3.5 h-3.5', isRefreshing && 'animate-spin')}
          />
        </Button>
      </div>
    </header>
  );
}
