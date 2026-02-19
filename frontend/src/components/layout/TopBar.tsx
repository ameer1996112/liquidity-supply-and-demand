'use client';

import { useMemo, useState } from 'react';
import {
  useSignalStats,
  useRefreshSignals,
  useTradingSignals,
} from '@/hooks/useTradingSignals';
import { useTradingMode } from '@/providers/TradingModeProvider';
import { getPnl } from '@/types/trading';
import { Button } from '@/components/ui/button';
import { RiskBar } from '@/components/risk/RiskBar';
import {
  TrendingUp,
  TrendingDown,
  Zap,
  DollarSign,
  RefreshCw,
  Radio,
  FlaskConical,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { AlertBell } from '@/components/alerts/AlertBell';

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
  const { data: stats, isLoading } = useSignalStats();
  const { data: signals = [] } = useTradingSignals(mode);
  const refreshSignals = useRefreshSignals();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refreshSignals();
    setTimeout(() => setIsRefreshing(false), 500);
  };

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

  const totalPnl = useMemo(() => {
    const closed = signals.filter((s) => {
      const st = s.status?.toLowerCase();
      const pnl = getPnl(s);
      return (st === 'closed' || st === 'executed') && pnl != null;
    });
    return closed.reduce((sum, s) => sum + (getPnl(s) ?? 0), 0);
  }, [signals]);

  return (
    <header className='flex h-12 shrink-0 items-center justify-between border-b border-slate-800 bg-[#0F172A] px-3'>
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
              value={`${winRate.toFixed(1)}%`}
              trend={winRate >= 50 ? 'up' : 'down'}
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
      </div>
    </header>
  );
}
