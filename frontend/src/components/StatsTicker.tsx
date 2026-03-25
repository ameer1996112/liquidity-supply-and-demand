'use client';

import { useSignalStats } from '@/hooks/useTradingSignals';
import { useActivePositions } from '@/hooks/usePositions';
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
import { PnLText } from '@/components/ui/typography';

interface StatItemProps {
  label: string;
  value: React.ReactNode;
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
            ? 'bg-[var(--to-long)]/20 text-[var(--to-long)]'
            : 'bg-surface-raised text-text-secondary',
        )}
      >
        {icon}
      </div>
      <div className="flex flex-col">
        <span className="text-[10px] uppercase tracking-wider text-text-dim font-medium">
          {label}
        </span>
        <span
          className={cn(
            'font-mono text-sm font-semibold',
            trend === 'up' && 'text-long',
            trend === 'down' && 'text-short',
            !trend && 'text-text-secondary',
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
      <Skeleton className="w-8 h-8 rounded-md bg-[var(--to-surface-raised)]" />
      <div className="flex flex-col gap-1">
        <Skeleton className="w-16 h-2.5 bg-[var(--to-surface-raised)]" />
        <Skeleton className="w-12 h-4 bg-[var(--to-surface-raised)]" />
      </div>
    </div>
  );
}

export function StatsTicker() {
  const { data: stats, isLoading, error } = useSignalStats();
  const { data: positionsData } = useActivePositions();

  const floatingPnl =
    positionsData?.positions?.reduce((sum, p) => sum + (p.live_pnl ?? 0), 0) ?? 0;

  if (error) {
    return (
      <div className="flex items-center justify-center h-14 bg-zinc-950/80 border-b border-zinc-800 text-[var(--to-short)] text-sm">
        <span className="font-mono">Error loading stats</span>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between h-14 bg-[var(--to-bg)]/95 backdrop-blur-sm border-b border-panel-border-subtle px-2">
      {/* Left Section - Logo/Title */}
      <div className="flex items-center gap-3 pl-2">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-long animate-pulse" />
          <span className="font-mono text-sm font-bold text-text-primary tracking-tight">
            MISSION CONTROL
          </span>
        </div>
        <div className="h-6 w-px bg-panel-border" />
      </div>

      {/* Center Section - Stats */}
      <div className="flex items-center divide-x divide-panel-border-subtle/60">
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
              value={<span>{stats?.total_signals_24h || 0}</span>}
              icon={<Activity className="w-4 h-4" />}
            />
            <StatItem
              label="Live Win Rate"
              value={`${(stats?.live_win_rate ?? stats?.win_rate ?? 0).toFixed(1)}%`}
              icon={
                (stats?.live_win_rate ?? stats?.win_rate ?? 0) >= 50 ? (
                  <TrendingUp className="w-4 h-4" />
                ) : (
                  <TrendingDown className="w-4 h-4" />
                )
              }
              trend={(stats?.live_win_rate ?? stats?.win_rate ?? 0) >= 50 ? 'up' : 'down'}
            />
            <StatItem
              label="Active"
              value={<span>{stats?.active_trades || 0}</span>}
              icon={<Zap className="w-4 h-4" />}
              highlight={(stats?.active_trades || 0) > 0}
            />
            <StatItem
              label="AI Reject"
              value={`${(stats?.ai_reject_rate || 0).toFixed(1)}%`}
              icon={<Filter className="w-4 h-4" />}
            />
            <StatItem
              label="Live PnL (w/ Float)"
              value={
                <PnLText
                  value={(stats?.live_pnl_24h ?? stats?.total_pnl_24h ?? 0) + floatingPnl}
                  variant="currency"
                  size="lg"
                />
              }
              icon={<DollarSign className="w-4 h-4" />}
              trend={(stats?.live_pnl_24h ?? stats?.total_pnl_24h ?? 0) + floatingPnl >= 0 ? 'up' : 'down'}
            />
            <StatItem
              label="Paper PnL"
              value={
                <PnLText
                  value={stats?.paper_pnl_24h ?? 0}
                  variant="currency"
                  size="lg"
                />
              }
              icon={<DollarSign className="w-4 h-4" />}
            />
          </>
        )}
      </div>

      {/* Right Section - Connection Status */}
      <div className="flex items-center gap-2 pr-2">
        <div className="h-6 w-px bg-panel-border" />
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-surface border border-panel-border-subtle/70">
          <div className="w-1.5 h-1.5 rounded-full bg-long animate-pulse" />
          <span className="text-[10px] uppercase tracking-wider text-text-secondary font-medium font-mono">
            Live
          </span>
        </div>
      </div>
    </div>
  );
}
