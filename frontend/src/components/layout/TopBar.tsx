'use client';

import { useSignalStats, useRefreshSignals } from '@/hooks/useTradingSignals';
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
    <div className="flex items-center gap-2 px-4">
      <div className="flex items-center justify-center w-7 h-7 rounded bg-[#1e222d] text-zinc-500">
        {icon}
      </div>
      <div className="flex flex-col">
        <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-medium leading-none">
          {label}
        </span>
        <span
          className={cn(
            'font-mono text-sm font-semibold leading-tight tabular-nums',
            trend === 'up' && 'text-emerald-400',
            trend === 'down' && 'text-red-400',
            !trend && 'text-zinc-200'
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
    <div className="flex items-center gap-2 px-4">
      <Skeleton className="w-7 h-7 rounded bg-[#1e222d]" />
      <div className="flex flex-col gap-1">
        <Skeleton className="w-14 h-2.5 bg-[#1e222d]" />
        <Skeleton className="w-10 h-3.5 bg-[#1e222d]" />
      </div>
    </div>
  );
}

export function TopBar() {
  const { data: stats, isLoading } = useSignalStats();
  const refreshSignals = useRefreshSignals();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refreshSignals();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  const winRate = stats?.live_win_rate ?? stats?.win_rate ?? 0;
  const dailyPnl = stats?.daily_pnl ?? 0;
  const totalPnl = stats?.total_pnl ?? 0;

  return (
    <header className="h-12 bg-[#0f1117] border-b border-[#2a2e39] flex items-center justify-between px-4">
      {/* Left: Metrics */}
      <div className="flex items-center divide-x divide-[#2a2e39]">
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
              label="Win Rate"
              value={`${winRate.toFixed(1)}%`}
              icon={
                winRate >= 50 ? (
                  <TrendingUp className="w-3.5 h-3.5" />
                ) : (
                  <TrendingDown className="w-3.5 h-3.5" />
                )
              }
              trend={winRate >= 50 ? 'up' : 'down'}
            />
            <Metric
              label="Active"
              value={stats?.active_trades || 0}
              icon={<Zap className="w-3.5 h-3.5" />}
            />
            <Metric
              label="Daily PnL"
              value={`${dailyPnl >= 0 ? '+' : ''}$${dailyPnl.toFixed(2)}`}
              icon={<DollarSign className="w-3.5 h-3.5" />}
              trend={dailyPnl >= 0 ? 'up' : 'down'}
            />
            <Metric
              label="Total PnL"
              value={`${totalPnl >= 0 ? '+' : ''}$${totalPnl.toFixed(2)}`}
              icon={<Activity className="w-3.5 h-3.5" />}
              trend={totalPnl >= 0 ? 'up' : 'down'}
            />
          </>
        )}
      </div>

      {/* Center: Risk Cockpit */}
      <RiskBar />

      {/* Right: Actions */}
      <div className="flex items-center gap-3">
        {/* Alerts */}
        <AlertBell />

        {/* Connection indicator */}
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-[#1e222d]">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-mono">
            Live
          </span>
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="h-8 w-8 p-0 text-zinc-500 hover:text-zinc-300 hover:bg-[#1e222d]"
        >
          <RefreshCw
            className={cn('w-3.5 h-3.5', isRefreshing && 'animate-spin')}
          />
        </Button>
      </div>
    </header>
  );
}
