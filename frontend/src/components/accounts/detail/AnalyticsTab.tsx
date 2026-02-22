'use client';

import { useQuery } from '@tanstack/react-query';
import { TrendingUp, TrendingDown, AlertTriangle, Target } from 'lucide-react';
import { getPortfolioControlUrl } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

interface AnalyticsTabProps {
  accountName: string;
}

interface PairStats {
  symbol: string;
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  largest_win: number;
  largest_loss: number;
  avg_hold_time_hours: number;
}

interface LosingStreak {
  start_date: string;
  end_date: string;
  streak_length: number;
  total_loss: number;
  symbols: string[];
  status: 'active' | 'ended';
}

async function fetchPairStats(accountName: string): Promise<PairStats[]> {
  const url = getPortfolioControlUrl(
    `/accounts/${encodeURIComponent(accountName)}/analytics/pairs`,
  );
  if (!url) throw new Error('Backend API URL not configured');
  const res = await fetch(url, { signal: AbortSignal.timeout(15000) });
  if (!res.ok) throw new Error(`Failed to fetch pair stats (${res.status})`);
  const data = await res.json();
  return data.pairs || [];
}

async function fetchLosingStreaks(
  accountName: string,
): Promise<LosingStreak[]> {
  const url = getPortfolioControlUrl(
    `/accounts/${encodeURIComponent(accountName)}/analytics/streaks`,
  );
  if (!url) throw new Error('Backend API URL not configured');
  const res = await fetch(url, { signal: AbortSignal.timeout(15000) });
  if (!res.ok)
    throw new Error(`Failed to fetch losing streaks (${res.status})`);
  const data = await res.json();
  return data.streaks || [];
}

export function AnalyticsTab({ accountName }: AnalyticsTabProps) {
  const {
    data: pairStats,
    isLoading: loadingPairs,
    error: pairError,
  } = useQuery({
    queryKey: ['account-analytics-pairs', accountName],
    queryFn: () => fetchPairStats(accountName),
    staleTime: 60_000,
  });

  const {
    data: streaks,
    isLoading: loadingStreaks,
    error: streaksError,
  } = useQuery({
    queryKey: ['account-analytics-streaks', accountName],
    queryFn: () => fetchLosingStreaks(accountName),
    staleTime: 60_000,
  });

  return (
    <div className='space-y-6'>
      {/* Per-Pair Performance */}
      <section className='space-y-3'>
        <div className='flex items-center justify-between'>
          <h3 className='text-sm font-medium text-zinc-300 flex items-center gap-2'>
            <Target className='h-4 w-4 text-emerald-500' />
            Per-Pair Performance
          </h3>
          {!loadingPairs && pairStats && (
            <span className='text-xs text-zinc-500'>
              {pairStats.length} pairs traded
            </span>
          )}
        </div>

        {loadingPairs ? (
          <div className='space-y-2'>
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className='h-16 bg-[#1e222d]' />
            ))}
          </div>
        ) : pairError ? (
          <div className='rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-600'>
            Analytics endpoints not yet implemented. This will show per-pair win
            rate, profit factor, and avg hold time.
          </div>
        ) : !pairStats || pairStats.length === 0 ? (
          <div className='flex flex-col items-center justify-center rounded-lg border border-[#2a2e39] bg-[#1e222d]/50 py-12 text-zinc-500'>
            <div className='text-3xl mb-3'>📊</div>
            <p className='text-sm font-mono'>No trade data yet</p>
            <p className='text-xs text-zinc-600 mt-1'>
              Per-pair analytics will appear after closing some trades.
            </p>
          </div>
        ) : (
          <div className='tv-card overflow-hidden'>
            <div className='overflow-x-auto'>
              <table className='w-full text-sm'>
                <thead>
                  <tr className='border-b border-[#2a2e39] bg-[#1e222d]/50'>
                    <th className='text-left px-4 py-2 text-xs font-mono text-zinc-500'>
                      Pair
                    </th>
                    <th className='text-center px-4 py-2 text-xs font-mono text-zinc-500'>
                      Trades
                    </th>
                    <th className='text-right px-4 py-2 text-xs font-mono text-zinc-500'>
                      Win Rate
                    </th>
                    <th className='text-right px-4 py-2 text-xs font-mono text-zinc-500'>
                      Total P&L
                    </th>
                    <th className='text-right px-4 py-2 text-xs font-mono text-zinc-500'>
                      Avg Win
                    </th>
                    <th className='text-right px-4 py-2 text-xs font-mono text-zinc-500'>
                      Avg Loss
                    </th>
                    <th className='text-right px-4 py-2 text-xs font-mono text-zinc-500'>
                      PF
                    </th>
                    <th className='text-right px-4 py-2 text-xs font-mono text-zinc-500'>
                      Avg Hold
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {pairStats.map((pair) => {
                    const isProfitable = pair.total_pnl >= 0;
                    const winRateGood = pair.win_rate >= 0.5;
                    const pfGood = pair.profit_factor >= 1.5;

                    return (
                      <tr
                        key={pair.symbol}
                        className='border-b border-[#2a2e39] hover:bg-[#1e222d]/30'
                      >
                        <td className='px-4 py-3 font-mono text-xs font-semibold text-zinc-200'>
                          {pair.symbol}
                        </td>
                        <td className='px-4 py-3 text-center font-mono text-xs text-zinc-400'>
                          {pair.total_trades}
                          <span className='text-[10px] ml-1 text-zinc-600'>
                            ({pair.wins}W/{pair.losses}L)
                          </span>
                        </td>
                        <td className='px-4 py-3 text-right'>
                          <span
                            className={cn(
                              'font-mono text-xs font-medium',
                              winRateGood ? 'text-[#26a69a]' : 'text-zinc-400',
                            )}
                          >
                            {(pair.win_rate * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td className='px-4 py-3 text-right'>
                          <span
                            className={cn(
                              'font-mono text-xs font-semibold',
                              isProfitable
                                ? 'text-[#26a69a]'
                                : 'text-[#ef5350]',
                            )}
                          >
                            {isProfitable ? '+' : ''}$
                            {pair.total_pnl.toFixed(2)}
                          </span>
                        </td>
                        <td className='px-4 py-3 text-right font-mono text-xs text-[#26a69a]'>
                          +${pair.avg_win.toFixed(2)}
                        </td>
                        <td className='px-4 py-3 text-right font-mono text-xs text-[#ef5350]'>
                          -${Math.abs(pair.avg_loss).toFixed(2)}
                        </td>
                        <td className='px-4 py-3 text-right'>
                          <span
                            className={cn(
                              'font-mono text-xs font-medium',
                              pfGood ? 'text-[#26a69a]' : 'text-zinc-400',
                            )}
                          >
                            {pair.profit_factor.toFixed(2)}
                          </span>
                        </td>
                        <td className='px-4 py-3 text-right font-mono text-xs text-zinc-400'>
                          {pair.avg_hold_time_hours.toFixed(1)}h
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* Losing Streaks Detection */}
      <section className='space-y-3'>
        <div className='flex items-center justify-between'>
          <h3 className='text-sm font-medium text-zinc-300 flex items-center gap-2'>
            <AlertTriangle className='h-4 w-4 text-amber-500' />
            Losing Streaks
          </h3>
          {!loadingStreaks && streaks && streaks.length > 0 && (
            <span className='text-xs text-zinc-500'>
              {streaks.filter((s) => s.status === 'active').length > 0 && (
                <span className='text-amber-500'>
                  ⚠️ Active streak detected
                </span>
              )}
            </span>
          )}
        </div>

        {loadingStreaks ? (
          <div className='space-y-2'>
            {[1, 2].map((i) => (
              <Skeleton key={i} className='h-20 bg-[#1e222d]' />
            ))}
          </div>
        ) : streaksError ? (
          <div className='rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-600'>
            Streak detection endpoint not yet implemented. This will show
            consecutive losing trades with total loss and affected pairs.
          </div>
        ) : !streaks || streaks.length === 0 ? (
          <div className='rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-4 py-3 text-sm text-emerald-600'>
            <div className='flex items-center gap-2'>
              <TrendingUp className='h-4 w-4' />
              <span className='font-medium'>
                No significant losing streaks detected
              </span>
            </div>
            <p className='text-xs mt-1 text-emerald-600/80'>
              You're managing risk well. Streaks of 3+ consecutive losses will
              appear here.
            </p>
          </div>
        ) : (
          <div className='space-y-3'>
            {streaks.map((streak, idx) => (
              <div
                key={idx}
                className={cn(
                  'rounded-lg border px-4 py-3',
                  streak.status === 'active'
                    ? 'border-amber-500/30 bg-amber-500/5'
                    : 'border-[#2a2e39] bg-[#1e222d]/50',
                )}
              >
                <div className='flex items-start justify-between'>
                  <div className='space-y-1'>
                    <div className='flex items-center gap-2'>
                      <span
                        className={cn(
                          'font-mono text-sm font-semibold',
                          streak.status === 'active'
                            ? 'text-amber-500'
                            : 'text-zinc-400',
                        )}
                      >
                        {streak.streak_length} consecutive losses
                      </span>
                      {streak.status === 'active' && (
                        <span className='px-1.5 py-0.5 text-[9px] font-mono rounded bg-amber-500/20 text-amber-400 border border-amber-500/30'>
                          ACTIVE
                        </span>
                      )}
                    </div>
                    <div
                      suppressHydrationWarning
                      className='text-xs text-zinc-500'
                    >
                      {new Date(streak.start_date).toLocaleDateString()} -{' '}
                      {streak.status === 'active'
                        ? 'Now'
                        : new Date(streak.end_date).toLocaleDateString()}
                    </div>
                    <div className='flex items-center gap-3 mt-2'>
                      <div>
                        <span className='text-[10px] text-zinc-600 uppercase'>
                          Total Loss
                        </span>
                        <div className='font-mono text-sm font-semibold text-[#ef5350]'>
                          -${Math.abs(streak.total_loss).toFixed(2)}
                        </div>
                      </div>
                      <div className='h-8 w-px bg-[#2a2e39]'></div>
                      <div>
                        <span className='text-[10px] text-zinc-600 uppercase'>
                          Pairs Affected
                        </span>
                        <div className='font-mono text-xs text-zinc-400'>
                          {streak.symbols.join(', ')}
                        </div>
                      </div>
                    </div>
                  </div>
                  {streak.status === 'active' && (
                    <AlertTriangle className='h-5 w-5 text-amber-500 flex-shrink-0' />
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Session Performance (Placeholder for Chart) */}
      <section className='space-y-3'>
        <h3 className='text-sm font-medium text-zinc-300'>
          Session Performance
        </h3>
        <div className='rounded-lg border border-[#2a2e39] bg-[#1e222d]/50 px-4 py-12 text-center text-xs text-zinc-600'>
          <div className='text-3xl mb-3'>📈</div>
          <p className='font-mono'>Chart Coming Soon</p>
          <p className='mt-1 max-w-md mx-auto'>
            Daily P&L breakdown showing trading sessions (London, NY, Asian)
            with performance heatmap.
          </p>
        </div>
      </section>

      {/* Equity Curve (Placeholder for Chart) */}
      <section className='space-y-3'>
        <h3 className='text-sm font-medium text-zinc-300'>Equity Curve</h3>
        <div className='rounded-lg border border-[#2a2e39] bg-[#1e222d]/50 px-4 py-12 text-center text-xs text-zinc-600'>
          <div className='text-3xl mb-3'>📊</div>
          <p className='font-mono'>Chart Coming Soon</p>
          <p className='mt-1 max-w-md mx-auto'>
            Account equity over time with drawdown periods highlighted.
          </p>
        </div>
      </section>
    </div>
  );
}
