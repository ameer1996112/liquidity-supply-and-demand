'use client';

import { useSignalStats } from '@/hooks/useTradingSignals';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Activity,
  TrendingUp,
  TrendingDown,
  Filter,
  Zap,
  DollarSign,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface StatItemProps {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  trend?: 'up' | 'down' | 'neutral';
  highlight?: boolean;
}

function StatItem({ label, value, icon, trend, highlight }: StatItemProps) {
  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <div
        className={cn(
          'flex items-center justify-center w-8 h-8 rounded-md',
          highlight
            ? 'bg-emerald-500/20 text-emerald-400'
            : 'bg-zinc-800 text-zinc-400'
        )}
      >
        {icon}
      </div>
      <div className="flex flex-col">
        <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-medium">
          {label}
        </span>
        <span
          className={cn(
            'font-mono text-sm font-semibold',
            trend === 'up' && 'text-emerald-400',
            trend === 'down' && 'text-red-400',
            !trend && 'text-zinc-100'
          )}
        >
          {value}
        </span>
      </div>
    </div>
  );
}

function StatItemSkeleton() {
  return (
    <div className="flex items-center gap-2 px-4 py-2">
      <Skeleton className="w-8 h-8 rounded-md bg-zinc-800" />
      <div className="flex flex-col gap-1">
        <Skeleton className="w-16 h-2.5 bg-zinc-800" />
        <Skeleton className="w-12 h-4 bg-zinc-800" />
      </div>
    </div>
  );
}

export function StatsTicker() {
  const { data: stats, isLoading, error } = useSignalStats();

  if (error) {
    return (
      <div className="flex items-center justify-center h-14 bg-zinc-950/80 border-b border-zinc-800 text-red-400 text-sm">
        <span className="font-mono">Error loading stats</span>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between h-14 bg-zinc-950/80 backdrop-blur-sm border-b border-zinc-800/50 px-2">
      {/* Left Section - Logo/Title */}
      <div className="flex items-center gap-3 pl-2">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="font-mono text-sm font-bold text-zinc-100 tracking-tight">
            MISSION CONTROL
          </span>
        </div>
        <div className="h-6 w-px bg-zinc-800" />
      </div>

      {/* Center Section - Stats */}
      <div className="flex items-center divide-x divide-zinc-800/50">
        {isLoading ? (
          <>
            <StatItemSkeleton />
            <StatItemSkeleton />
            <StatItemSkeleton />
            <StatItemSkeleton />
            <StatItemSkeleton />
          </>
        ) : (
          <>
            <StatItem
              label="24h Volume"
              value={stats?.total_signals_24h || 0}
              icon={<Activity className="w-4 h-4" />}
            />
            <StatItem
              label="Win Rate"
              value={`${(stats?.win_rate || 0).toFixed(1)}%`}
              icon={
                (stats?.win_rate || 0) >= 50 ? (
                  <TrendingUp className="w-4 h-4" />
                ) : (
                  <TrendingDown className="w-4 h-4" />
                )
              }
              trend={(stats?.win_rate || 0) >= 50 ? 'up' : 'down'}
            />
            <StatItem
              label="Active"
              value={stats?.active_trades || 0}
              icon={<Zap className="w-4 h-4" />}
              highlight={(stats?.active_trades || 0) > 0}
            />
            <StatItem
              label="AI Reject"
              value={`${(stats?.ai_reject_rate || 0).toFixed(1)}%`}
              icon={<Filter className="w-4 h-4" />}
            />
            <StatItem
              label="24h PnL"
              value={`${(stats?.total_pnl_24h || 0) >= 0 ? '+' : ''}$${(stats?.total_pnl_24h || 0).toFixed(2)}`}
              icon={<DollarSign className="w-4 h-4" />}
              trend={(stats?.total_pnl_24h || 0) >= 0 ? 'up' : 'down'}
            />
          </>
        )}
      </div>

      {/* Right Section - Connection Status */}
      <div className="flex items-center gap-2 pr-2">
        <div className="h-6 w-px bg-zinc-800" />
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-zinc-900 border border-zinc-800/50">
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-[10px] uppercase tracking-wider text-zinc-400 font-medium font-mono">
            Live
          </span>
        </div>
      </div>
    </div>
  );
}
