'use client';

import { useBacktestRun } from '@/hooks/useBacktest';
import { MetricCard } from '@/components/analytics/MetricCard';
import {
  Target,
  TrendingUp,
  BarChart3,
  Hash,
  FlaskConical,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface BacktestResultsProps {
  runId: string | null;
}

export function BacktestResults({ runId }: BacktestResultsProps) {
  const { data: run, isLoading } = useBacktestRun(runId);

  if (!runId) {
    return (
      <div className="tv-card p-8 flex flex-col items-center justify-center gap-3 min-h-[300px]">
        <FlaskConical className="w-8 h-8 text-zinc-600" />
        <p className="text-[11px] text-zinc-500 font-mono text-center">
          Select a backtest run to view results
        </p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="tv-card p-8 flex items-center justify-center min-h-[300px]">
        <Loader2 className="w-6 h-6 text-zinc-500 animate-spin" />
      </div>
    );
  }

  if (!run) {
    return (
      <div className="tv-card p-8 flex items-center justify-center min-h-[300px]">
        <p className="text-[11px] text-zinc-500 font-mono">Run not found</p>
      </div>
    );
  }

  // Parse summary
  const summary =
    typeof run.result_summary === 'string'
      ? (() => {
          try {
            return JSON.parse(run.result_summary);
          } catch {
            return {};
          }
        })()
      : run.result_summary || {};

  const isRunning = run.status === 'running';
  const isFailed = run.status === 'failed';

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="tv-card p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-mono text-sm font-semibold text-zinc-200">
              {run.name || run.run_id}
            </h2>
            <span className="text-[10px] text-zinc-500 font-mono">{run.run_id}</span>
          </div>
          <div
            className={cn(
              'px-2 py-0.5 rounded font-mono text-[10px] font-semibold uppercase',
              run.status === 'completed' && 'bg-emerald-950 text-[#26a69a]',
              run.status === 'running' && 'bg-blue-950 text-blue-400',
              run.status === 'failed' && 'bg-red-950 text-[#ef5350]',
              run.status === 'pending' && 'bg-zinc-800 text-zinc-400',
            )}
          >
            {isRunning && <Loader2 className="w-3 h-3 inline animate-spin mr-1" />}
            {run.status}
          </div>
        </div>
      </div>

      {/* Error message for failed runs */}
      {isFailed && summary.error && (
        <div className="tv-card p-4 border-[#ef5350]/30">
          <p className="font-mono text-[11px] text-[#ef5350]">{summary.error}</p>
        </div>
      )}

      {/* KPI Cards */}
      {run.status === 'completed' && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              label="Win Rate"
              value={`${(summary.win_rate || 0).toFixed(1)}%`}
              icon={<Target className="w-4 h-4" />}
              trend={(summary.win_rate || 0) >= 50 ? 'up' : 'down'}
              subtitle={`${summary.wins || 0}W / ${summary.losses || 0}L`}
            />
            <MetricCard
              label="Total PnL (R)"
              value={`${(summary.total_pnl_r || 0) >= 0 ? '+' : ''}${(summary.total_pnl_r || 0).toFixed(1)}R`}
              icon={<TrendingUp className="w-4 h-4" />}
              trend={(summary.total_pnl_r || 0) >= 0 ? 'up' : 'down'}
            />
            <MetricCard
              label="Accepted"
              value={summary.accepted || 0}
              icon={<BarChart3 className="w-4 h-4" />}
              subtitle={`of ${summary.total_signals || 0} signals`}
            />
            <MetricCard
              label="Rejected"
              value={summary.rejected || 0}
              icon={<Hash className="w-4 h-4" />}
            />
          </div>

          {/* Config overrides summary */}
          {summary.config_overrides &&
            Object.keys(summary.config_overrides).length > 0 && (
              <div className="tv-card">
                <div className="px-4 py-3 border-b border-[#2a2e39]">
                  <span className="font-mono text-xs text-zinc-400 uppercase tracking-wider">
                    Config Overrides
                  </span>
                </div>
                <div className="divide-y divide-[#2a2e39]">
                  {Object.entries(summary.config_overrides).map(
                    ([key, val]) => (
                      <div
                        key={key}
                        className="px-4 py-2 flex items-center justify-between"
                      >
                        <span className="text-[11px] text-zinc-500 font-mono uppercase">
                          {key}
                        </span>
                        <span className="font-mono text-xs text-zinc-300">
                          {String(val)}
                        </span>
                      </div>
                    ),
                  )}
                </div>
              </div>
            )}
        </>
      )}
    </div>
  );
}
