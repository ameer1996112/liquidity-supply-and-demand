'use client';

import Link from 'next/link';
import { useRiskDashboard } from '@/hooks/usePortfolioRisk';
import { Skeleton } from '@/components/ui/skeleton';
import { TrendingDown, AlertTriangle, ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { getVarUtilizationColor } from '@/types/portfolio';

export function PortfolioRiskWidget() {
  const { data, isLoading } = useRiskDashboard(30);

  const hasData = data && data.position_count > 0;
  const varUtilization = data?.var_utilization_pct || 0;
  const isHighRisk = varUtilization >= 80;
  const isHighCorrelation = (data?.correlation_avg || 0) > 0.7;

  return (
    <div className="tv-card flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#2a2e39]">
        <div className="flex items-center gap-2">
          <TrendingDown className="w-4 h-4 text-[#2962ff]" />
          <span className="font-mono text-xs font-semibold text-zinc-300 uppercase tracking-wider">
            Portfolio Risk
          </span>
        </div>
        {(isHighRisk || isHighCorrelation) && (
          <AlertTriangle className="w-3.5 h-3.5 text-yellow-500" />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 p-4">
        {isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-12 w-full bg-[#1e222d]" />
            <Skeleton className="h-8 w-full bg-[#1e222d]" />
            <Skeleton className="h-8 w-full bg-[#1e222d]" />
          </div>
        ) : hasData ? (
          <div className="space-y-3">
            {/* VaR Metric */}
            <div>
              <div className="text-[10px] text-zinc-500 font-mono mb-1">
                Portfolio VaR (95%)
              </div>
              <div className="flex items-baseline gap-2">
                <span
                  className={cn(
                    'text-2xl font-bold',
                    getVarUtilizationColor(varUtilization)
                  )}
                >
                  ${Math.abs(data.var_95_1d).toFixed(0)}
                </span>
                <span className="text-xs text-zinc-500">
                  {varUtilization.toFixed(0)}% used
                </span>
              </div>
              {/* VaR Utilization Bar */}
              <div className="mt-2 h-1.5 bg-[#1e222d] rounded-full overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full transition-all',
                    varUtilization >= 100
                      ? 'bg-red-500'
                      : varUtilization >= 80
                      ? 'bg-yellow-500'
                      : 'bg-[#26a69a]'
                  )}
                  style={{ width: `${Math.min(varUtilization, 100)}%` }}
                />
              </div>
            </div>

            {/* Correlation Warning */}
            {isHighCorrelation && (
              <div className="flex items-center gap-2 px-2 py-1.5 bg-yellow-500/10 border border-yellow-500/20 rounded">
                <AlertTriangle className="w-3 h-3 text-yellow-500 flex-shrink-0" />
                <span className="text-[10px] text-yellow-500 font-mono">
                  High correlation: {data.correlation_avg.toFixed(2)}
                </span>
              </div>
            )}

            {/* Quick Stats */}
            <div className="grid grid-cols-2 gap-2 pt-2">
              <div>
                <div className="text-[9px] text-zinc-600 font-mono mb-0.5">
                  Volatility
                </div>
                <div className="text-sm font-mono text-zinc-300">
                  {data.portfolio_volatility.toFixed(1)}%
                </div>
              </div>
              <div>
                <div className="text-[9px] text-zinc-600 font-mono mb-0.5">
                  Exposure
                </div>
                <div className="text-sm font-mono text-zinc-300">
                  ${(data.total_exposure / 1000).toFixed(1)}k
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <TrendingDown className="w-8 h-8 text-zinc-700 mb-2" />
            <span className="text-xs text-zinc-600 font-mono">
              No active positions
            </span>
            <span className="text-[10px] text-zinc-700 font-mono mt-1">
              VaR analysis unavailable
            </span>
          </div>
        )}
      </div>

      {/* Footer - Link to Full Page */}
      <Link
        href="/portfolio-risk"
        className="flex items-center justify-between px-4 py-2 border-t border-[#2a2e39] hover:bg-[#1e222d]/50 transition-colors group"
      >
        <span className="text-[10px] text-zinc-500 font-mono group-hover:text-zinc-400">
          View full analysis
        </span>
        <ArrowRight className="w-3 h-3 text-zinc-600 group-hover:text-zinc-400" />
      </Link>
    </div>
  );
}
