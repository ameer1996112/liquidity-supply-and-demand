'use client';

import { useTCASummary } from '@/hooks/useExecutionQuality';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertTriangle, TrendingDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import Link from 'next/link';

export function ExecutionQualityWidget() {
  const { data, isLoading, error } = useTCASummary(1); // Last 24 hours

  const hasHighSlippage = data && data.avg_slippage_pips < -3.0;
  const hasHighLatency = data && data.avg_execution_time_ms > 5000;
  const hasAlert = hasHighSlippage || hasHighLatency;

  if (error || !data) return null;

  return (
    <Link
      href='/execution-quality'
      className='tv-card block transition-colors hover:border-slate-600'
    >
      <div className='flex flex-col h-full p-3'>
        {/* Header */}
        <div className='flex items-center justify-between mb-2.5'>
          <div className='flex items-center gap-1.5'>
            <TrendingDown className='h-3.5 w-3.5 text-indigo-400' />
            <span
              className='panel-label'
              style={{ fontFamily: 'var(--font-sans)' }}
            >
              Execution Quality
            </span>
          </div>
          {hasAlert && (
            <AlertTriangle className='h-3.5 w-3.5 text-amber-400 animate-pulse' />
          )}
        </div>

        {/* Metrics */}
        <div className='space-y-2'>
          {isLoading ? (
            <>
              <Skeleton className='h-8 w-full bg-slate-800/60' />
              <Skeleton className='h-8 w-full bg-slate-800/60' />
              <Skeleton className='h-8 w-full bg-slate-800/60' />
            </>
          ) : (
            <>
              {/* Slippage */}
              <div className='flex items-center justify-between'>
                <span
                  className='text-[10px] text-[var(--to-text-dim)]'
                  style={{ fontFamily: 'var(--font-sans)' }}
                >
                  Avg Slippage (24h)
                </span>
                <div className='text-right'>
                  <div
                    className={cn(
                      'text-xs font-semibold tabular-nums',
                      hasHighSlippage ? 'text-[var(--to-short)]' : 'text-slate-200'
                    )}
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    {data.avg_slippage_pips.toFixed(2)} pips
                  </div>
                  <div
                    className='text-[9px] text-[var(--to-text-dim)]'
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    ${data.total_slippage_cost_usd.toFixed(2)} cost
                  </div>
                </div>
              </div>

              {/* Execution Time */}
              <div className='flex items-center justify-between'>
                <span
                  className='text-[10px] text-[var(--to-text-dim)]'
                  style={{ fontFamily: 'var(--font-sans)' }}
                >
                  Avg Execution
                </span>
                <div className='text-right'>
                  <div
                    className={cn(
                      'text-xs font-semibold tabular-nums',
                      hasHighLatency ? 'text-amber-400' : 'text-slate-200'
                    )}
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    {data.avg_execution_time_ms.toFixed(0)}ms
                  </div>
                  <div
                    className='text-[9px] text-[var(--to-text-dim)]'
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    signal to fill
                  </div>
                </div>
              </div>

              {/* Total Cost */}
              <div className='flex items-center justify-between border-t border-slate-800 pt-2'>
                <span
                  className='text-[10px] text-[var(--to-text-dim)]'
                  style={{ fontFamily: 'var(--font-sans)' }}
                >
                  Total TX Cost
                </span>
                <div className='text-right'>
                  <div
                    className='text-xs font-semibold tabular-nums text-[var(--to-short)]'
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    -$
                    {(
                      data.total_slippage_cost_usd + data.total_spread_cost_usd
                    ).toFixed(2)}
                  </div>
                  <div
                    className='text-[9px] text-[var(--to-text-dim)]'
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    {data.total_trades} trades
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        {!isLoading && (
          <div className='mt-2.5 border-t border-slate-800 pt-2'>
            <div
              className='text-center text-[9px] text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              view detailed TCA →
            </div>
          </div>
        )}
      </div>
    </Link>
  );
}
