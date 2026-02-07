'use client';

import { useTCASummary } from '@/hooks/useExecutionQuality';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertTriangle, TrendingDown, Clock, DollarSign } from 'lucide-react';
import { cn } from '@/lib/utils';
import Link from 'next/link';

export function ExecutionQualityWidget() {
  const { data, isLoading, error } = useTCASummary(1); // Last 24 hours

  const hasHighSlippage = data && data.avg_slippage_pips < -3.0;
  const hasHighLatency = data && data.avg_execution_time_ms > 5000;
  const hasAlert = hasHighSlippage || hasHighLatency;

  if (error || !data) {
    return null; // Silently hide if TCA not available
  }

  return (
    <Link href="/execution-quality" className="tv-card block hover:border-[#26a69a]/30 transition-colors">
      <div className="flex flex-col h-full p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <TrendingDown className="w-4 h-4 text-[#26a69a]" />
            <span className="font-mono text-xs font-semibold text-zinc-300 uppercase tracking-wider">
              Execution Quality
            </span>
          </div>
          {hasAlert && (
            <AlertTriangle className="w-4 h-4 text-yellow-500 animate-pulse" />
          )}
        </div>

        {/* Metrics */}
        <div className="space-y-3">
          {isLoading ? (
            <>
              <Skeleton className="h-12 w-full bg-[#1e222d]" />
              <Skeleton className="h-12 w-full bg-[#1e222d]" />
              <Skeleton className="h-12 w-full bg-[#1e222d]" />
            </>
          ) : (
            <>
              {/* Slippage */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-500">Avg Slippage (24h)</span>
                <div className="text-right">
                  <div
                    className={cn(
                      'text-sm font-mono font-bold',
                      hasHighSlippage ? 'text-red-500' : 'text-zinc-200',
                    )}
                  >
                    {data.avg_slippage_pips.toFixed(2)} pips
                  </div>
                  <div className="text-[10px] text-zinc-600">
                    ${data.total_slippage_cost_usd.toFixed(2)} cost
                  </div>
                </div>
              </div>

              {/* Execution Time */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-500">Avg Execution</span>
                <div className="text-right">
                  <div
                    className={cn(
                      'text-sm font-mono font-bold',
                      hasHighLatency ? 'text-yellow-500' : 'text-zinc-200',
                    )}
                  >
                    {data.avg_execution_time_ms.toFixed(0)}ms
                  </div>
                  <div className="text-[10px] text-zinc-600">
                    Signal to fill
                  </div>
                </div>
              </div>

              {/* Total Cost */}
              <div className="flex items-center justify-between pt-2 border-t border-[#2a2e39]">
                <span className="text-xs text-zinc-500">Total TX Cost</span>
                <div className="text-right">
                  <div className="text-sm font-mono font-bold text-red-400">
                    -$
                    {(
                      data.total_slippage_cost_usd + data.total_spread_cost_usd
                    ).toFixed(2)}
                  </div>
                  <div className="text-[10px] text-zinc-600">
                    {data.total_trades} trades
                  </div>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer hint */}
        {!isLoading && (
          <div className="mt-3 pt-3 border-t border-[#2a2e39]">
            <div className="text-[10px] text-zinc-600 text-center">
              Click to view detailed TCA metrics →
            </div>
          </div>
        )}
      </div>
    </Link>
  );
}
