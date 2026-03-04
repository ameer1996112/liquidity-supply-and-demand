'use client';

import { useEvaluationStats } from '@/hooks/useEvaluationStats';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { AlertCircle, CheckCircle2, TrendingUp, Calendar, Target } from 'lucide-react';
import { cn } from '@/lib/utils';
import { PnLText } from '@/components/ui/typography';
import { Skeleton } from '@/components/ui/skeleton';
import { PanelEmptyState } from '@/components/shared/PanelEmptyState';

export function EvaluationDashboard() {
  const { data: evaluation, isLoading, error } = useEvaluationStats();

  if (isLoading) {
    return (
      <div className='tv-card p-6 space-y-4'>
        <div className='flex items-center justify-between'>
          <div className='flex items-center gap-3'>
            <Skeleton className='h-5 w-5 rounded-full bg-slate-800/60' />
            <Skeleton className='h-4 w-40 bg-slate-800/60' />
          </div>
          <Skeleton className='h-6 w-24 bg-slate-800/60' />
        </div>
        <Skeleton className='h-4 w-32 bg-slate-800/60' />
        <Skeleton className='h-3 w-full bg-slate-800/60' />
        <Skeleton className='h-3 w-3/4 bg-slate-800/60' />
      </div>
    );
  }

  if (error || !evaluation?.evaluation_mode) {
    return (
      <div className='tv-card p-6'>
        <PanelEmptyState
          title='Evaluation disabled or offline'
          description='Connect an evaluation account or try again when the backend is reachable.'
        />
      </div>
    );
  }

  const phaseLabel = {
    phase1: 'Phase 1',
    phase2: 'Phase 2',
    funded: 'Funded Account',
  }[evaluation.phase];

  const phaseBadgeColor = {
    phase1:
      'bg-[var(--to-accent-blue)]/15 text-[var(--to-accent-blue)] border-[var(--to-accent-blue)]/30',
    phase2:
      'bg-[var(--to-accent-amber)]/15 text-[var(--to-accent-amber)] border-[var(--to-accent-amber)]/30',
    funded:
      'bg-[var(--to-long)]/15 text-[var(--to-long)] border-[var(--to-long)]/30',
  }[evaluation.phase];

  return (
    <div className='tv-card'>
      {/* Header */}
      <div className='px-6 py-4 border-b border-panel-border flex items-center justify-between'>
        <div className='flex items-center gap-3'>
          <Target className='w-5 h-5 text-[var(--to-text-secondary)]' />
          <h2 className='text-sm font-semibold text-zinc-100'>
            Evaluation Progress
          </h2>
        </div>
        <Badge className={cn('font-mono text-xs', phaseBadgeColor)}>
          {phaseLabel}
        </Badge>
      </div>

      <div className='p-6 space-y-6'>
        {/* Day Counter */}
        <div className='flex items-center justify-between'>
          <div className='flex items-center gap-2 text-sm text-zinc-400'>
            <Calendar className='w-4 h-4' />
            <span>Day {evaluation.current_day} of {evaluation.total_days}</span>
          </div>
          <div className='text-xs text-zinc-500'>
            {evaluation.actual_trading_days} / {evaluation.min_trading_days} trading days
          </div>
        </div>

        {/* Profit Target Progress */}
        <div className='space-y-2'>
          <div className='flex items-center justify-between text-sm'>
            <span className='text-zinc-400'>Profit Target</span>
            <span className='font-mono font-semibold text-text-secondary'>
              <PnLText
                value={evaluation.current_profit}
                variant='currency'
                size='lg'
              />{' '}
              /{' '}
              <PnLText
                value={evaluation.profit_target}
                variant='currency'
                size='lg'
              />
            </span>
          </div>
          <Progress
            value={evaluation.profit_progress_pct}
            className='h-2 bg-surface'
            indicatorClassName={cn(
              evaluation.profit_progress_pct >= 100
                ? 'bg-[var(--to-long)]'
                : evaluation.profit_progress_pct >= 75
                  ? 'bg-[var(--to-accent-green)]'
                  : evaluation.profit_progress_pct >= 50
                    ? 'bg-[var(--to-accent-blue)]'
                    : 'bg-[var(--to-text-secondary)]',
            )}
          />
          <div className='text-right text-xs text-zinc-500'>
            {evaluation.profit_progress_pct.toFixed(1)}%
          </div>
        </div>

        {/* Daily Loss Buffer */}
        <div className='space-y-2'>
          <div className='flex items-center justify-between text-sm'>
            <span className='text-zinc-400'>Max Daily Loss</span>
            <span className='font-mono font-semibold'>
              <PnLText
                value={evaluation.today_pnl}
                variant='currency'
                size='lg'
              />{' '}
              /{' '}
              <PnLText
                value={evaluation.max_daily_loss}
                variant='currency'
                size='lg'
              />
            </span>
          </div>
          <Progress
            value={Math.abs(
              (evaluation.today_pnl / evaluation.max_daily_loss) * 100,
            )}
            className='h-2 bg-surface'
            indicatorClassName={cn(
              evaluation.daily_loss_buffer <= 0
                ? 'bg-[var(--to-short)]'
                : evaluation.daily_loss_buffer <
                    evaluation.max_daily_loss * 0.2
                  ? 'bg-[var(--to-warning)]'
                  : 'bg-[var(--to-long)]',
            )}
          />
          <div className='flex justify-between text-xs'>
            <span className='text-zinc-500'>
              Buffer:{' '}
              <PnLText
                value={evaluation.daily_loss_buffer}
                variant='currency'
                size='sm'
              />
            </span>
            <span
              className={cn(
                'font-semibold',
                evaluation.daily_loss_buffer <= 0
                  ? 'text-[var(--to-short)]'
                  : 'text-[var(--to-long)]',
              )}
            >
              {evaluation.rules_passed.max_daily_loss ? '✓ Safe' : '⚠ At Risk'}
            </span>
          </div>
        </div>

        {/* Drawdown */}
        <div className='space-y-2'>
          <div className='flex items-center justify-between text-sm'>
            <span className='text-zinc-400'>Max Drawdown</span>
            <span className='font-mono font-semibold text-text-secondary'>
              {evaluation.current_drawdown_pct.toFixed(2)}% /{' '}
              {evaluation.max_drawdown_pct.toFixed(1)}%
            </span>
          </div>
          <Progress
            value={
              (evaluation.current_drawdown_pct /
                evaluation.max_drawdown_pct) *
              100
            }
            className='h-2 bg-surface'
            indicatorClassName={cn(
              evaluation.current_drawdown_pct >=
                evaluation.max_drawdown_pct
                ? 'bg-[var(--to-short)]'
                : evaluation.current_drawdown_pct >=
                    evaluation.max_drawdown_pct * 0.8
                  ? 'bg-[var(--to-warning)]'
                  : 'bg-[var(--to-long)]',
            )}
          />
          <div className='text-right text-xs text-zinc-500'>
            Peak:{' '}
            <PnLText
              value={evaluation.peak_balance}
              variant='currency'
              size='sm'
            />
          </div>
        </div>

        {/* Consistency */}
        <div className='space-y-2'>
          <div className='flex items-center justify-between text-sm'>
            <span className='text-zinc-400'>Consistency</span>
            <span className='font-mono font-semibold text-text-secondary'>
              {evaluation.consistency_pct.toFixed(0)}% /{' '}
              {evaluation.consistency_target_pct.toFixed(0)}%
            </span>
          </div>
          <Progress
            value={
              (evaluation.consistency_pct /
                evaluation.consistency_target_pct) *
              100
            }
            className='h-2 bg-surface'
            indicatorClassName={cn(
              evaluation.consistency_pct >=
                evaluation.consistency_target_pct
                ? 'bg-[var(--to-long)]'
                : 'bg-[var(--to-accent-blue)]',
            )}
          />
        </div>

        {/* Rules Checklist */}
        <div className='space-y-2 pt-4 border-t border-panel-border'>
          <div className='text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-3'>
            Requirements
          </div>
          <div className='grid grid-cols-1 gap-2'>
            {Object.entries(evaluation.rules_passed).map(([rule, passed]) => (
              <div
                key={rule}
                className='flex items-center justify-between text-sm'
              >
                <span className='text-zinc-400 capitalize'>
                  {rule.replace(/_/g, ' ')}
                </span>
                {passed ? (
                  <CheckCircle2 className='w-4 h-4 text-[var(--to-long)]' />
                ) : (
                  <div className='w-4 h-4 rounded-full border-2 border-panel-border-subtle' />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Violations */}
        {evaluation.violations.length > 0 && (
          <div className='space-y-2 pt-4 border-t border-panel-border'>
            <div className='flex items-center gap-2 text-xs font-semibold text-[var(--to-short)] uppercase tracking-wide mb-3'>
              <AlertCircle className='w-4 h-4' />
              Rule Violations
            </div>
            {evaluation.violations.map((violation, idx) => (
              <div
                key={idx}
                className={cn(
                  'p-3 rounded border text-sm',
                  violation.severity === 'critical'
                    ? 'bg-[var(--to-short)]/10 border-[var(--to-short)]/30 text-[var(--to-short)]'
                    : 'bg-[var(--to-warning)]/10 border-[var(--to-warning)]/30 text-[var(--to-warning)]',
                )}
              >
                <div className='font-semibold mb-1 capitalize'>
                  {violation.rule.replace(/_/g, ' ')}
                </div>
                <div className='text-xs opacity-90'>{violation.message}</div>
              </div>
            ))}
          </div>
        )}

        {/* Upgrade Button */}
        {evaluation.can_upgrade && (
          <button
            className={cn(
              'w-full mt-4 px-4 py-3 rounded font-semibold text-sm',
              'bg-[var(--to-long)]/20 text-[var(--to-long)] border border-[var(--to-long)]/30',
              'hover:bg-[var(--to-long)]/30 transition-colors',
              'flex items-center justify-center gap-2',
            )}
          >
            <TrendingUp className='w-4 h-4' />
            Ready to Upgrade to {evaluation.phase === 'phase1' ? 'Phase 2' : 'Funded Account'}
          </button>
        )}
      </div>
    </div>
  );
}
