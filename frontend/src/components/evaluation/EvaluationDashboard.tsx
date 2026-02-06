'use client';

import { useEvaluationStats } from '@/hooks/useEvaluationStats';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { AlertCircle, CheckCircle2, TrendingUp, Calendar, Target } from 'lucide-react';
import { cn } from '@/lib/utils';

export function EvaluationDashboard() {
  const { data: eval, isLoading, error } = useEvaluationStats();

  if (isLoading) {
    return (
      <div className="tv-card p-6">
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#2962ff]" />
        </div>
      </div>
    );
  }

  if (error || !eval?.evaluation_mode) {
    return null; // Don't show if evaluation mode is off
  }

  const phaseLabel = {
    phase1: 'Phase 1',
    phase2: 'Phase 2',
    funded: 'Funded Account',
  }[eval.phase];

  const phaseBadgeColor = {
    phase1: 'bg-[#2962ff]/15 text-[#2962ff] border-[#2962ff]/30',
    phase2: 'bg-[#ff9800]/15 text-[#ff9800] border-[#ff9800]/30',
    funded: 'bg-[#26a69a]/15 text-[#26a69a] border-[#26a69a]/30',
  }[eval.phase];

  return (
    <div className="tv-card">
      {/* Header */}
      <div className="px-6 py-4 border-b border-[#2a2e39] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Target className="w-5 h-5 text-[#787b86]" />
          <h2 className="text-sm font-semibold text-zinc-100">
            Evaluation Progress
          </h2>
        </div>
        <Badge className={cn('font-mono text-xs', phaseBadgeColor)}>
          {phaseLabel}
        </Badge>
      </div>

      <div className="p-6 space-y-6">
        {/* Day Counter */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-zinc-400">
            <Calendar className="w-4 h-4" />
            <span>Day {eval.current_day} of {eval.total_days}</span>
          </div>
          <div className="text-xs text-zinc-500">
            {eval.actual_trading_days} / {eval.min_trading_days} trading days
          </div>
        </div>

        {/* Profit Target Progress */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-zinc-400">Profit Target</span>
            <span className={cn(
              'font-mono font-semibold',
              eval.current_profit >= eval.profit_target ? 'text-emerald-400' :
              eval.current_profit >= 0 ? 'text-zinc-100' : 'text-rose-400'
            )}>
              ${eval.current_profit.toFixed(2)} / ${eval.profit_target.toFixed(0)}
            </span>
          </div>
          <Progress
            value={eval.profit_progress_pct}
            className="h-2 bg-[#1e222d]"
            indicatorClassName={cn(
              eval.profit_progress_pct >= 100 ? 'bg-emerald-500' :
              eval.profit_progress_pct >= 75 ? 'bg-[#26a69a]' :
              eval.profit_progress_pct >= 50 ? 'bg-[#2962ff]' : 'bg-[#787b86]'
            )}
          />
          <div className="text-right text-xs text-zinc-500">
            {eval.profit_progress_pct.toFixed(1)}%
          </div>
        </div>

        {/* Daily Loss Buffer */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-zinc-400">Max Daily Loss</span>
            <span className={cn(
              'font-mono font-semibold',
              eval.daily_loss_buffer <= 0 ? 'text-rose-400' :
              eval.daily_loss_buffer < eval.max_daily_loss * 0.2 ? 'text-orange-400' :
              'text-emerald-400'
            )}>
              ${Math.abs(eval.today_pnl).toFixed(2)} / ${eval.max_daily_loss.toFixed(0)}
            </span>
          </div>
          <Progress
            value={Math.abs(eval.today_pnl / eval.max_daily_loss * 100)}
            className="h-2 bg-[#1e222d]"
            indicatorClassName={cn(
              eval.daily_loss_buffer <= 0 ? 'bg-rose-500' :
              eval.daily_loss_buffer < eval.max_daily_loss * 0.2 ? 'bg-orange-500' :
              'bg-emerald-500'
            )}
          />
          <div className="flex justify-between text-xs">
            <span className="text-zinc-500">
              Buffer: ${eval.daily_loss_buffer.toFixed(2)}
            </span>
            <span className={cn(
              'font-semibold',
              eval.daily_loss_buffer <= 0 ? 'text-rose-400' : 'text-emerald-400'
            )}>
              {eval.rules_passed.max_daily_loss ? '✓ Safe' : '⚠ At Risk'}
            </span>
          </div>
        </div>

        {/* Drawdown */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-zinc-400">Max Drawdown</span>
            <span className={cn(
              'font-mono font-semibold',
              eval.current_drawdown_pct >= eval.max_drawdown_pct ? 'text-rose-400' :
              eval.current_drawdown_pct >= eval.max_drawdown_pct * 0.8 ? 'text-orange-400' :
              'text-emerald-400'
            )}>
              {eval.current_drawdown_pct.toFixed(2)}% / {eval.max_drawdown_pct.toFixed(1)}%
            </span>
          </div>
          <Progress
            value={(eval.current_drawdown_pct / eval.max_drawdown_pct) * 100}
            className="h-2 bg-[#1e222d]"
            indicatorClassName={cn(
              eval.current_drawdown_pct >= eval.max_drawdown_pct ? 'bg-rose-500' :
              eval.current_drawdown_pct >= eval.max_drawdown_pct * 0.8 ? 'bg-orange-500' :
              'bg-emerald-500'
            )}
          />
          <div className="text-right text-xs text-zinc-500">
            Peak: ${eval.peak_balance.toFixed(2)}
          </div>
        </div>

        {/* Consistency */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-zinc-400">Consistency</span>
            <span className={cn(
              'font-mono font-semibold',
              eval.consistency_pct >= eval.consistency_target_pct ? 'text-emerald-400' :
              eval.consistency_pct >= eval.consistency_target_pct * 0.8 ? 'text-[#2962ff]' :
              'text-zinc-400'
            )}>
              {eval.consistency_pct.toFixed(0)}% / {eval.consistency_target_pct.toFixed(0)}%
            </span>
          </div>
          <Progress
            value={(eval.consistency_pct / eval.consistency_target_pct) * 100}
            className="h-2 bg-[#1e222d]"
            indicatorClassName={cn(
              eval.consistency_pct >= eval.consistency_target_pct ? 'bg-emerald-500' : 'bg-[#2962ff]'
            )}
          />
        </div>

        {/* Rules Checklist */}
        <div className="space-y-2 pt-4 border-t border-[#2a2e39]">
          <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-3">
            Requirements
          </div>
          <div className="grid grid-cols-1 gap-2">
            {Object.entries(eval.rules_passed).map(([rule, passed]) => (
              <div
                key={rule}
                className="flex items-center justify-between text-sm"
              >
                <span className="text-zinc-400 capitalize">
                  {rule.replace(/_/g, ' ')}
                </span>
                {passed ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                ) : (
                  <div className="w-4 h-4 rounded-full border-2 border-[#2a2e39]" />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Violations */}
        {eval.violations.length > 0 && (
          <div className="space-y-2 pt-4 border-t border-[#2a2e39]">
            <div className="flex items-center gap-2 text-xs font-semibold text-rose-400 uppercase tracking-wide mb-3">
              <AlertCircle className="w-4 h-4" />
              Rule Violations
            </div>
            {eval.violations.map((violation, idx) => (
              <div
                key={idx}
                className={cn(
                  'p-3 rounded border text-sm',
                  violation.severity === 'critical'
                    ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                    : 'bg-orange-500/10 border-orange-500/30 text-orange-300'
                )}
              >
                <div className="font-semibold mb-1 capitalize">
                  {violation.rule.replace(/_/g, ' ')}
                </div>
                <div className="text-xs opacity-90">{violation.message}</div>
              </div>
            ))}
          </div>
        )}

        {/* Upgrade Button */}
        {eval.can_upgrade && (
          <button
            className={cn(
              'w-full mt-4 px-4 py-3 rounded font-semibold text-sm',
              'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30',
              'hover:bg-emerald-500/30 transition-colors',
              'flex items-center justify-center gap-2'
            )}
          >
            <TrendingUp className="w-4 h-4" />
            Ready to Upgrade to {eval.phase === 'phase1' ? 'Phase 2' : 'Funded Account'}
          </button>
        )}
      </div>
    </div>
  );
}
