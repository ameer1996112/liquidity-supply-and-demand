'use client';

import { useEffect, useState } from 'react';
import {
  ArrowDownRight,
  BarChart3,
  Loader2,
  Play,
  ShieldCheck,
  Square,
  TrendingUp,
  Trophy,
  Waves,
} from 'lucide-react';
import {
  useAgentStatus,
  useCancelOptimizerRun,
  useCreateOptimizerRun,
  useOptimizerRun,
  useOptimizerRunEvents,
  useOptimizerRunResults,
  useOptimizerRunStressResults,
  useOptimizerRunTrials,
  useOptimizerRuns,
} from '@/hooks/useOptimizerRuns';
import type {
  OptimizerPortfolioResultApi,
  OptimizerRunApi,
  OptimizerRunCreateApi,
  OptimizerRunEventApi,
  OptimizerRunResultApi,
  OptimizerRunStressResultApi,
  OptimizerRunTrialApi,
} from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

function getStrategyBadge(run?: { strategy_id?: string | null; strategy_version?: string | null } | null) {
  if (!run?.strategy_id) return null;
  return `${run.strategy_id}@${run.strategy_version ?? '?'}`;
}

function statusTone(status: string) {
  if (status === 'completed') return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
  if (status === 'running' || status === 'queued') return 'bg-amber-500/15 text-amber-300 border-amber-500/30';
  if (status === 'cancelled' || status === 'interrupted') return 'bg-slate-500/15 text-slate-300 border-slate-500/30';
  return 'bg-red-500/15 text-red-300 border-red-500/30';
}

function formatNumber(value: number | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '--';
  return value.toFixed(2);
}

function formatSignedPercent(value: number | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '--';
  const prefix = value > 0 ? '+' : '';
  return `${prefix}${value.toFixed(2)}%`;
}

function formatWeight(value: number | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '--';
  return `${(value * 100).toFixed(0)}%`;
}

function formatTimelineTimestamp(value?: string) {
  if (!value) return '--';
  return new Date(value).toLocaleString([], {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function cleanTimelineMessage(message: string) {
  return message
    .replace(/^\d{4}-\d{2}-\d{2}[^[]*\[[A-Z]+\]\s+[^:]+:\s*/, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function timelineEventLabel(eventType: string) {
  switch (eventType) {
    case 'run_started':
      return 'Run started';
    case 'pair_started':
      return 'Pair started';
    case 'pair_completed':
      return 'Pair completed';
    case 'pair_failed':
      return 'Pair failed';
    case 'run_finished':
      return 'Run finished';
    case 'run_cancelled':
      return 'Run cancelled';
    case 'log':
      return 'Log';
    default:
      return eventType.replace(/_/g, ' ');
  }
}

function timelineTone(eventType: string) {
  if (eventType === 'pair_failed' || eventType === 'run_finished') {
    return 'border-red-500/30 bg-red-500/10 text-red-200';
  }
  if (eventType === 'pair_completed') {
    return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200';
  }
  if (eventType === 'pair_started' || eventType === 'run_started') {
    return 'border-amber-500/30 bg-amber-500/10 text-amber-200';
  }
  if (eventType === 'run_cancelled') {
    return 'border-slate-500/30 bg-slate-500/10 text-slate-200';
  }
  return 'border-[var(--to-border)] bg-transparent text-[var(--to-text-secondary)]';
}

function getMetricValue(source: Record<string, unknown> | undefined | null, key: string): number | undefined {
  const value = source?.[key];
  return typeof value === 'number' && !Number.isNaN(value) ? value : undefined;
}

function getResultDecision(result: OptimizerRunResultApi, weight?: number): string {
  const explicitDecision = (result as OptimizerRunResultApi & { decision?: string | null }).decision;
  if (explicitDecision) {
    return explicitDecision.replace(/_/g, ' ');
  }
  if (result.status === 'running' || result.status === 'pending' || result.status === 'cancelled') {
    return result.status;
  }
  if (result.status === 'failed') {
    return 'reject';
  }
  if (typeof weight === 'number') {
    if (weight >= 0.75) return 'pass';
    if (weight > 0) return 'reduce risk';
    return 'reject';
  }
  return 'pending review';
}

function decisionTone(decision: string) {
  const normalized = decision.toLowerCase();
  if (normalized === 'pass') {
    return 'border-emerald-500/30 bg-emerald-500/12 text-emerald-200';
  }
  if (normalized === 'reduce risk' || normalized === 'running' || normalized === 'queued') {
    return 'border-amber-500/30 bg-amber-500/12 text-amber-200';
  }
  if (normalized === 'reject' || normalized === 'failed') {
    return 'border-red-500/30 bg-red-500/12 text-red-200';
  }
  return 'border-slate-500/30 bg-slate-500/12 text-slate-200';
}

function derivePortfolioCounts(
  results: OptimizerRunResultApi[],
  portfolioResult?: OptimizerPortfolioResultApi | null
) {
  const weights = portfolioResult?.weights ?? {};
  let approved = 0;
  let reduced = 0;
  let rejected = 0;
  let unresolved = 0;

  for (const result of results) {
    const weight = typeof weights[result.symbol] === 'number' ? weights[result.symbol] : undefined;
    const decision = getResultDecision(result, weight).toLowerCase();
    if (decision === 'pass') {
      approved += 1;
      continue;
    }
    if (decision === 'reduce risk' || (typeof weight === 'number' && weight > 0)) {
      reduced += 1;
      continue;
    }
    if (decision === 'running' || decision === 'pending' || decision === 'pending review' || decision === 'cancelled') {
      unresolved += 1;
      continue;
    }
    rejected += 1;
  }

  return { approved, reduced, rejected, unresolved };
}

function summarizeTrialWindows(trials: OptimizerRunTrialApi[]) {
  const windows = new Set<string>();
  for (const trial of trials) {
    if (trial.window) windows.add(trial.window);
  }
  return windows.size > 0 ? Array.from(windows).join(', ') : 'No validation windows recorded';
}

function summarizeStressScenarios(stressResults: OptimizerRunStressResultApi[]) {
  const labels = new Set<string>();
  for (const result of stressResults) {
    if (result.scenario) {
      labels.add(result.scenario);
      continue;
    }
    if (result.stress_type) labels.add(result.stress_type);
  }
  return labels.size > 0 ? Array.from(labels).join(', ') : 'Stress artifacts not available yet';
}

function getEmbeddedResults(run?: OptimizerRunApi | null) {
  return run?.results ?? [];
}

function getEmbeddedEvents(run?: OptimizerRunApi | null) {
  return run?.artifacts?.events ?? [];
}

function getEmbeddedTrials(run: OptimizerRunApi | null | undefined, symbol: string | null) {
  if (!run?.artifacts?.trials || !symbol) return [];
  return run.artifacts.trials.filter((trial) => trial.symbol === symbol);
}

function getEmbeddedStressResults(run: OptimizerRunApi | null | undefined, symbol: string | null) {
  if (!run?.artifacts?.stress_results || !symbol) return [];
  return run.artifacts.stress_results.filter((result) => result.symbol === symbol);
}

function preferPolledArtifacts<T>(polled: T[], embedded: T[], hasFreshPoll: boolean) {
  if (hasFreshPoll) {
    return polled;
  }
  return polled.length > 0 ? polled : embedded;
}

function deriveDecisionReason(args: {
  result: OptimizerRunResultApi;
  weight?: number;
  trials: OptimizerRunTrialApi[];
  stressResults: OptimizerRunStressResultApi[];
}): string {
  const { result, weight, trials, stressResults } = args;
  const decision = getResultDecision(result, weight).toLowerCase();
  const score = result.metrics?.score;
  const profitFactor = result.metrics?.profit_factor;
  const drawdown = result.metrics?.max_drawdown_pct;
  const topTrial = trials.at(-1);
  const latestStress = stressResults.at(-1);

  if (result.reason) {
    return result.reason;
  }

  if (decision === 'pass') {
    if (typeof weight === 'number') {
      return `Approved because ${result.symbol} kept a ${formatWeight(weight)} portfolio weight with score ${formatNumber(score)} and PF ${formatNumber(profitFactor)}.`;
    }
    return `Approved because ${result.symbol} cleared the current survival gate with score ${formatNumber(score)} and PF ${formatNumber(profitFactor)}.`;
  }
  if (decision === 'reduce risk') {
    if (typeof weight === 'number' && weight > 0) {
      return `Reduced risk because ${result.symbol} still holds a ${formatWeight(weight)} allocation while drawdown reached ${formatSignedPercent(drawdown)}.`;
    }
    return `Reduced risk because ${result.symbol} remains tradable but the current run does not justify a full allocation yet.`;
  }
  if (decision === 'running' || decision === 'pending') {
    return `Decision is still forming because ${result.symbol} is mid-run and the survival allocator has not finalized its approval state yet.`;
  }
  if (decision === 'cancelled') {
    return `Decision is unavailable because ${result.symbol} was cancelled before the survival allocator could finish its review.`;
  }
  if (decision === 'reject') {
    return `Rejected because ${result.symbol} has no surviving portfolio weight and needs a new candidate before it rejoins the approved set.`;
  }
  if (decision === 'pending review') {
    return `Pending review because ${result.symbol} finished its pair run, but the portfolio allocator has not emitted an approval weight or explicit decision yet.`;
  }
  if (latestStress?.scenario || latestStress?.stress_type) {
    return `Current decision is anchored by ${latestStress.scenario ?? latestStress.stress_type} stress coverage while richer pair-level reasons are still sparse.`;
  }
  if (topTrial?.window) {
    return `Current decision is inferred from the ${topTrial.window} trial window until the backend emits an explicit pair reason.`;
  }
  return `Current decision is inferred from status, portfolio weight, and available run metrics until a richer backend reason is stored.`;
}

function describeTimelineEvent(event: OptimizerRunEventApi) {
  switch (event.event_type) {
    case 'run_started':
      return event.payload?.mode
        ? `Mode ${event.payload.mode} · ${event.payload.workers ?? '--'} workers`
        : 'Run started';
    case 'pair_started':
      return event.symbol ? `Working on ${event.symbol}` : 'Pair started';
    case 'pair_completed':
      return event.symbol
        ? `${event.symbol} completed${typeof event.payload?.elapsed_seconds === 'number' ? ` in ${event.payload.elapsed_seconds.toFixed(1)}s` : ''}`
        : 'Pair completed';
    case 'pair_failed':
      return event.symbol
        ? `${event.symbol} failed${event.payload?.error_message ? ` · ${event.payload.error_message}` : ''}`
        : 'Pair failed';
    case 'run_finished':
      return event.payload?.status
        ? `Run ${event.payload.status}`
        : 'Run finished';
    case 'run_cancelled':
      return 'Run cancelled';
    case 'log':
      return cleanTimelineMessage(String(event.payload?.message ?? 'log'));
    default:
      return cleanTimelineMessage(String(event.payload?.message ?? event.event_type));
  }
}

function PortfolioOverview({
  portfolioResult,
  results,
}: {
  portfolioResult?: OptimizerPortfolioResultApi | null;
  results: OptimizerRunResultApi[];
}) {
  const counts = derivePortfolioCounts(results, portfolioResult);
  const weightEntries = Object.entries(portfolioResult?.weights ?? {});

  return (
    <Card>
      <CardHeader>
        <CardTitle className='flex items-center gap-2'>
          <ShieldCheck className='h-4 w-4 text-[var(--to-long)]' />
          Portfolio overview
        </CardTitle>
        <CardDescription>Combined drawdown guardrails, allocation posture, and survivability at the run level.</CardDescription>
      </CardHeader>
      <CardContent className='space-y-4'>
        <div className='grid gap-3 md:grid-cols-2 xl:grid-cols-5'>
          <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/45 p-3'>
            <p className='text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Combined max DD</p>
            <p className='mt-2 text-2xl font-semibold text-[var(--to-text-primary)]'>
              {formatSignedPercent(portfolioResult?.combined_max_drawdown_pct)}
            </p>
          </div>
          <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/45 p-3'>
            <p className='text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Combined daily DD</p>
            <p className='mt-2 text-2xl font-semibold text-[var(--to-text-primary)]'>
              {formatSignedPercent(portfolioResult?.combined_daily_drawdown_pct)}
            </p>
          </div>
          <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/45 p-3'>
            <p className='text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Worst day</p>
            <p className='mt-2 text-2xl font-semibold text-[var(--to-text-primary)]'>
              {formatSignedPercent(portfolioResult?.worst_day_pct)}
            </p>
          </div>
          <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/45 p-3'>
            <p className='text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Pair decisions</p>
            <p className='mt-2 text-sm font-medium text-[var(--to-text-primary)]'>
              {counts.approved} approved · {counts.reduced} reduced · {counts.rejected} rejected
            </p>
            {counts.unresolved > 0 ? (
              <p className='mt-1 text-xs text-[var(--to-text-dim)]'>{counts.unresolved} unresolved</p>
            ) : null}
          </div>
          <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/45 p-3'>
            <p className='text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Weights tracked</p>
            <p className='mt-2 text-2xl font-semibold text-[var(--to-text-primary)]'>{weightEntries.length}</p>
          </div>
        </div>

        <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/20 p-3'>
          <div className='flex items-center justify-between gap-3'>
            <div>
              <p className='text-xs uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Allocation weights</p>
              <p className='mt-1 text-sm text-[var(--to-text-secondary)]'>
                {weightEntries.length > 0
                  ? 'Current portfolio sizing pulled from the optimizer output.'
                  : 'Weights will appear once the portfolio allocator saves a combined result.'}
              </p>
            </div>
            <Waves className='hidden h-4 w-4 text-[var(--to-accent-amber)] sm:block' />
          </div>
          {weightEntries.length > 0 ? (
            <div className='mt-3 flex flex-wrap gap-2'>
              {weightEntries.map(([symbol, weight]) => (
                <Badge
                  key={symbol}
                  className='border border-[var(--to-border)] bg-[var(--to-surface)] px-2 py-1 font-mono text-[11px] text-[var(--to-text-primary)]'
                >
                  {symbol} {formatWeight(weight)}
                </Badge>
              ))}
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

function PairAnalysisTable({
  results,
  weights,
  selectedSymbol,
  onSelectSymbol,
}: {
  results: OptimizerRunResultApi[];
  weights: Record<string, number>;
  selectedSymbol: string | null;
  onSelectSymbol: (symbol: string) => void;
}) {
  if (results.length === 0) {
    return <p className='text-xs text-[var(--to-text-dim)]'>No pair analysis yet. Launch or select a run to inspect symbols.</p>;
  }

  return (
    <div className='overflow-x-auto'>
      <table className='min-w-full text-left text-xs'>
        <thead className='text-[var(--to-text-dim)]'>
          <tr className='border-b border-[var(--to-border)]'>
            <th className='py-2 pr-3'>Symbol</th>
            <th className='py-2 pr-3'>Decision</th>
            <th className='py-2 pr-3'>Score</th>
            <th className='py-2 pr-3'>Max DD %</th>
            <th className='py-2 pr-3'>PF</th>
            <th className='py-2 pr-3'>Risk weight</th>
            <th className='py-2'>Trades</th>
          </tr>
        </thead>
        <tbody>
          {results.map((result) => (
            <tr
              key={result.symbol}
              className={cn(
                'border-b border-[var(--to-border)]/60 transition-colors',
                selectedSymbol === result.symbol ? 'bg-[var(--to-accent-amber)]/8' : 'hover:bg-[var(--to-surface-raised)]/35'
              )}
            >
              <td className='py-2 pr-3 font-mono text-[var(--to-text-primary)]'>
                <button
                  type='button'
                  onClick={() => onSelectSymbol(result.symbol)}
                  className='rounded-sm text-left font-mono text-[var(--to-text-primary)] underline-offset-4 hover:text-[var(--to-accent-amber)] hover:underline'
                >
                  {result.symbol}
                </button>
              </td>
              <td className='py-2 pr-3'>
                <Badge className={cn('border capitalize', decisionTone(getResultDecision(result, weights[result.symbol])))}>
                  {getResultDecision(result, weights[result.symbol])}
                </Badge>
              </td>
              <td className='py-2 pr-3'>{formatNumber(result.metrics?.score)}</td>
              <td className='py-2 pr-3'>{formatNumber(result.metrics?.max_drawdown_pct)}</td>
              <td className='py-2 pr-3'>{formatNumber(result.metrics?.profit_factor)}</td>
              <td className='py-2 pr-3'>{formatWeight(weights[result.symbol])}</td>
              <td className='py-2'>{formatNumber(result.metrics?.total_trades)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PairDrilldown({
  symbol,
  result,
  weight,
  trials,
  stressResults,
}: {
  symbol: string | null;
  result?: OptimizerRunResultApi;
  weight?: number;
  trials: OptimizerRunTrialApi[];
  stressResults: OptimizerRunStressResultApi[];
}) {
  if (!symbol || !result) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Pair drill-down</CardTitle>
          <CardDescription>Select a symbol from the analysis table to inspect it.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const forwardMetrics = (result as OptimizerRunResultApi & { forward_metrics?: Record<string, unknown> | null })
    .forward_metrics;
  const validationMetrics = (result as OptimizerRunResultApi & { validation_metrics?: Record<string, unknown> | null })
    .validation_metrics;
  const topTrial = trials.at(-1);
  const latestStress = stressResults.at(-1);
  const decision = getResultDecision(result, weight);
  const decisionReason = deriveDecisionReason({ result, weight, trials, stressResults });

  return (
    <Card>
      <CardHeader>
        <div className='flex flex-wrap items-center justify-between gap-3'>
          <div>
            <CardTitle className='flex items-center gap-2'>
              <BarChart3 className='h-4 w-4 text-[var(--to-accent-amber)]' />
              {symbol} drill-down
            </CardTitle>
            <CardDescription>Validation, forward, and stress context for the selected pair.</CardDescription>
          </div>
          <div className='flex flex-wrap gap-2'>
            <Badge className={cn('border capitalize', decisionTone(decision))}>
              {decision}
            </Badge>
            <Badge className='border border-[var(--to-border)] bg-[var(--to-surface-raised)] text-[var(--to-text-secondary)]'>
              Weight {formatWeight(weight)}
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className='space-y-4'>
        <div className='grid gap-3 md:grid-cols-3'>
          <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/40 p-3'>
            <p className='text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Base result</p>
            <p className='mt-2 text-sm font-medium text-[var(--to-text-primary)]'>
              Score {formatNumber(result.metrics?.score)} · PF {formatNumber(result.metrics?.profit_factor)}
            </p>
            <p className='mt-1 text-xs text-[var(--to-text-dim)]'>
              Max DD {formatSignedPercent(result.metrics?.max_drawdown_pct)}
            </p>
          </div>
          <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/40 p-3'>
            <p className='text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Validation context</p>
            <p className='mt-2 text-sm font-medium text-[var(--to-text-primary)]'>
              {validationMetrics
                ? `Score ${formatNumber(getMetricValue(validationMetrics, 'score'))}`
                : topTrial
                  ? `Top trial #${topTrial.trial_number ?? '--'}`
                  : 'Validation artifacts pending'}
            </p>
            <p className='mt-1 text-xs text-[var(--to-text-dim)]'>
              {validationMetrics
                ? `PF ${formatNumber(getMetricValue(validationMetrics, 'profit_factor'))} · DD ${formatSignedPercent(getMetricValue(validationMetrics, 'max_drawdown_pct'))}`
                : summarizeTrialWindows(trials)}
            </p>
          </div>
          <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/40 p-3'>
            <p className='text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Forward context</p>
            <p className='mt-2 text-sm font-medium text-[var(--to-text-primary)]'>
              {forwardMetrics
                ? `Score ${formatNumber(getMetricValue(forwardMetrics, 'score'))}`
                : 'Forward metrics pending'}
            </p>
            <p className='mt-1 text-xs text-[var(--to-text-dim)]'>
              {forwardMetrics
                ? `PF ${formatNumber(getMetricValue(forwardMetrics, 'profit_factor'))} · DD ${formatSignedPercent(getMetricValue(forwardMetrics, 'max_drawdown_pct'))}`
                : latestStress
                  ? `The backend has not emitted explicit forward metrics for this symbol yet. Stress coverage is tracked separately under ${latestStress.scenario ?? latestStress.stress_type ?? 'stress context'}.`
                  : 'The backend has not emitted explicit forward metrics for this symbol yet.'}
            </p>
          </div>
        </div>

        <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/20 p-3'>
          <p className='text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Decision reason</p>
          <p className='mt-2 text-sm text-[var(--to-text-secondary)]'>{decisionReason}</p>
        </div>

        <div className='grid gap-3 lg:grid-cols-2'>
          <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/20 p-3'>
            <div className='flex items-center gap-2'>
              <TrendingUp className='h-4 w-4 text-[var(--to-long)]' />
              <p className='text-xs uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Validation trials</p>
            </div>
            {trials.length > 0 ? (
              <div className='mt-3 space-y-2'>
                {trials.slice(0, 3).map((trial, index) => (
                  <div key={trial.id ?? `${trial.symbol}-${trial.trial_number ?? index}`} className='rounded-lg border border-[var(--to-border)]/70 p-2'>
                    <p className='text-sm font-medium text-[var(--to-text-primary)]'>
                      Trial #{trial.trial_number ?? '--'} · {trial.window ?? 'window n/a'}
                    </p>
                    <p className='mt-1 text-xs text-[var(--to-text-dim)]'>
                      Score {formatNumber(getMetricValue(trial.metrics ?? undefined, 'score'))} · PF{' '}
                      {formatNumber(getMetricValue(trial.metrics ?? undefined, 'profit_factor'))} · DD{' '}
                      {formatSignedPercent(getMetricValue(trial.metrics ?? undefined, 'max_drawdown_pct'))}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className='mt-3 text-xs text-[var(--to-text-dim)]'>
                No validation trials stored for this symbol yet. The workspace will show top candidate windows here once trial artifacts are available.
              </p>
            )}
          </div>

          <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/20 p-3'>
            <div className='flex items-center gap-2'>
              <ArrowDownRight className='h-4 w-4 text-[var(--to-short)]' />
              <p className='text-xs uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Stress context</p>
            </div>
            {stressResults.length > 0 ? (
              <div className='mt-3 space-y-2'>
                {stressResults.slice(0, 3).map((stress, index) => (
                  <div key={stress.id ?? `${stress.symbol ?? symbol}-${stress.scenario ?? index}`} className='rounded-lg border border-[var(--to-border)]/70 p-2'>
                    <p className='text-sm font-medium text-[var(--to-text-primary)]'>
                      {stress.scenario ?? stress.stress_type ?? 'stress scenario'}
                    </p>
                    <p className='mt-1 text-xs text-[var(--to-text-dim)]'>
                      Status {stress.status ?? '--'} · DD{' '}
                      {formatSignedPercent(getMetricValue(stress.metrics ?? undefined, 'max_drawdown_pct'))} · PF{' '}
                      {formatNumber(getMetricValue(stress.metrics ?? undefined, 'profit_factor'))}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className='mt-3 text-xs text-[var(--to-text-dim)]'>
                No stress results stored for this pair yet. When spread, slippage, or news scenarios arrive they will appear here.
              </p>
            )}
            <p className='mt-3 text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>
              Scenario coverage: {summarizeStressScenarios(stressResults)}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function OptimizerTimeline({ events }: { events: OptimizerRunEventApi[] }) {
  if (events.length === 0) {
    return <p className='text-xs text-[var(--to-text-dim)]'>No timeline events yet.</p>;
  }

  const structuredEvents = events.filter((event) => event.event_type !== 'log');
  const logEvents = events.filter((event) => event.event_type === 'log');
  const latestStructuredEvent = structuredEvents.at(-1) ?? null;
  const latestLogEvent = logEvents.at(-1) ?? null;

  return (
    <div className='space-y-4'>
      <div className='grid gap-3 md:grid-cols-2 xl:grid-cols-4'>
        <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/50 p-3'>
          <p className='text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Latest signal</p>
          <div className='mt-2 flex flex-wrap items-center gap-2'>
            <Badge className={cn('border', timelineTone(latestStructuredEvent?.event_type ?? 'log'))}>
              {timelineEventLabel(latestStructuredEvent?.event_type ?? 'log')}
            </Badge>
            <span className='text-sm text-[var(--to-text-primary)]'>
              {latestStructuredEvent ? describeTimelineEvent(latestStructuredEvent) : '--'}
            </span>
          </div>
          {latestStructuredEvent?.created_at && (
            <p className='mt-2 text-xs text-[var(--to-text-dim)]'>{formatTimelineTimestamp(latestStructuredEvent.created_at)}</p>
          )}
        </div>
        <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/50 p-3'>
          <p className='text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Latest log</p>
          <div className='mt-2 flex flex-wrap items-center gap-2'>
            <Badge className={cn('border', timelineTone('log'))}>log</Badge>
            <span className='text-sm text-[var(--to-text-primary)]'>
              {latestLogEvent ? describeTimelineEvent(latestLogEvent) : '--'}
            </span>
          </div>
          {latestLogEvent?.created_at && (
            <p className='mt-2 text-xs text-[var(--to-text-dim)]'>{formatTimelineTimestamp(latestLogEvent.created_at)}</p>
          )}
        </div>
        <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/50 p-3'>
          <p className='text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Run events</p>
          <p className='mt-2 text-2xl font-semibold text-[var(--to-text-primary)]'>{structuredEvents.length}</p>
        </div>
        <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/50 p-3'>
          <p className='text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Debug logs</p>
          <p className='mt-2 text-2xl font-semibold text-[var(--to-text-primary)]'>{logEvents.length}</p>
        </div>
      </div>

      <div className='grid gap-4 xl:grid-cols-2'>
        <div className='space-y-2'>
          <p className='text-xs uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Run events</p>
          <div className='space-y-2'>
            {[...structuredEvents].reverse().map((event, index) => (
              <div key={`${event.event_type}-${event.created_at ?? index}`} className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/40 p-3'>
                <div className='flex flex-wrap items-center gap-2 text-xs'>
                  <Badge className={cn('border', timelineTone(event.event_type))}>
                    {timelineEventLabel(event.event_type)}
                  </Badge>
                  {event.symbol && <span className='font-mono text-[var(--to-text-primary)]'>{event.symbol}</span>}
                  {typeof event.worker_id === 'number' && (
                    <span className='text-[var(--to-text-dim)]'>worker-{event.worker_id}</span>
                  )}
                  {event.created_at && <span className='text-[var(--to-text-dim)]'>{formatTimelineTimestamp(event.created_at)}</span>}
                </div>
                <p className='mt-2 text-xs text-[var(--to-text-secondary)]'>{describeTimelineEvent(event)}</p>
              </div>
            ))}
          </div>
        </div>

        <div className='space-y-2'>
          <p className='text-xs uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Debug logs</p>
          <div className='space-y-2'>
            {[...logEvents].reverse().map((event, index) => (
              <div key={`${event.event_type}-${event.created_at ?? index}`} className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/25 p-3'>
                <div className='flex flex-wrap items-center gap-2 text-xs'>
                  <Badge className='border border-[var(--to-border)] bg-transparent text-[var(--to-text-secondary)]'>log</Badge>
                  {event.created_at && <span className='text-[var(--to-text-dim)]'>{formatTimelineTimestamp(event.created_at)}</span>}
                </div>
                <p className='mt-2 text-xs text-[var(--to-text-secondary)]'>
                  {cleanTimelineMessage(String(event.payload?.message ?? ''))}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function OptimizerRunsWorkspace() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [strategyId, setStrategyId] = useState('');
  const [strategyVersion, setStrategyVersion] = useState('');
  const [mode, setMode] = useState<'bayesian' | 'smart' | 'fast' | 'full'>('bayesian');
  const [broker, setBroker] = useState<'vantage' | 'oanda' | 'fxcm'>('vantage');
  const [backtestRange, setBacktestRange] = useState<'30d' | '90d' | '365d' | 'all'>('365d');
  const [workers, setWorkers] = useState('3');
  const [pairs, setPairs] = useState('EURUSD,GBPUSD,XAUUSD');
  const [allPairs, setAllPairs] = useState(true);
  const [nTrials, setNTrials] = useState('25');
  const [ddLimit, setDdLimit] = useState('6');
  const [dryRun, setDryRun] = useState(true);

  const { data: runs = [], isLoading: runsLoading } = useOptimizerRuns();
  const { data: agentStatus } = useAgentStatus();
  const createRun = useCreateOptimizerRun();
  const cancelRun = useCancelOptimizerRun();

  const activeRun = runs.find((run) => run.status === 'running' || run.status === 'queued') ?? null;
  const currentRunId = selectedRunId ?? activeRun?.id ?? runs[0]?.id ?? null;
  const { data: currentRun } = useOptimizerRun(currentRunId);
  const resultsQuery = useOptimizerRunResults(currentRunId);
  const eventsQuery = useOptimizerRunEvents(currentRunId);
  const trialsQuery = useOptimizerRunTrials(currentRunId, selectedSymbol);
  const stressResultsQuery = useOptimizerRunStressResults(currentRunId, selectedSymbol);
  const polledResults = resultsQuery.data ?? [];
  const polledEvents = eventsQuery.data ?? [];
  const polledTrials = trialsQuery.data ?? [];
  const polledStressResults = stressResultsQuery.data ?? [];
  const embeddedResults = getEmbeddedResults(currentRun);
  const embeddedEvents = getEmbeddedEvents(currentRun);
  const embeddedTrials = getEmbeddedTrials(currentRun, selectedSymbol);
  const embeddedStressResults = getEmbeddedStressResults(currentRun, selectedSymbol);
  const results = preferPolledArtifacts(polledResults, embeddedResults, resultsQuery.isFetchedAfterMount ?? false);
  const events = preferPolledArtifacts(polledEvents, embeddedEvents, eventsQuery.isFetchedAfterMount ?? false);
  const trials = preferPolledArtifacts(polledTrials, embeddedTrials, trialsQuery.isFetchedAfterMount ?? false);
  const stressResults = preferPolledArtifacts(
    polledStressResults,
    embeddedStressResults,
    stressResultsQuery.isFetchedAfterMount ?? false,
  );

  useEffect(() => {
    if (!selectedRunId && currentRunId) {
      setSelectedRunId(currentRunId);
    }
  }, [currentRunId, selectedRunId]);

  useEffect(() => {
    if (!strategyId && currentRun?.strategy_id) {
      setStrategyId(currentRun.strategy_id);
    }
    if (!strategyVersion && currentRun?.strategy_version) {
      setStrategyVersion(currentRun.strategy_version);
    }
  }, [currentRun, strategyId, strategyVersion]);

  useEffect(() => {
    const availableSymbols = new Set<string>([
      ...results.map((result) => result.symbol),
      ...Object.keys(currentRun?.portfolio_result?.weights ?? {}),
      ...(currentRun?.summary?.best_symbol ? [currentRun.summary.best_symbol] : []),
    ]);
    if (availableSymbols.size === 0) {
      setSelectedSymbol(null);
      return;
    }
    if (selectedSymbol && availableSymbols.has(selectedSymbol)) {
      return;
    }
    setSelectedSymbol(Array.from(availableSymbols)[0] ?? null);
  }, [currentRun?.portfolio_result?.weights, currentRun?.summary?.best_symbol, results, selectedSymbol]);

  const handleSubmit = () => {
    const payload: OptimizerRunCreateApi = {
      strategy_id: strategyId.trim(),
      strategy_version: strategyVersion.trim(),
      mode,
      workers: Number(workers),
      pairs: allPairs ? ['ALL'] : pairs.split(',').map((item) => item.trim()).filter(Boolean),
      n_trials: Number(nTrials),
      dd_limit: Number(ddLimit),
      dry_run: dryRun,
      broker,
      backtest_range: backtestRange,
    };
    createRun.mutate(payload, {
      onSuccess: (run) => setSelectedRunId(run.id),
    });
  };

  const completedPairs = currentRun?.summary?.completed_pairs ?? 0;
  const failedPairs = currentRun?.summary?.failed_pairs ?? 0;
  const totalPairs = currentRun?.summary?.total_pairs ?? 0;
  const runningPairs = currentRun?.summary?.running_pairs ?? 0;
  const currentStrategyBadge = getStrategyBadge(currentRun);
  const canStartRun = Boolean(strategyId.trim() && strategyVersion.trim()) && !createRun.isPending;
  const portfolioWeights = currentRun?.portfolio_result?.weights ?? {};
  const selectedResult = results.find((result) => result.symbol === selectedSymbol);

  return (
    <div className='space-y-4'>
      <Card>
        <CardHeader>
          <div className='flex items-center justify-between'>
            <CardTitle className='flex items-center gap-2'>
              <Play className='h-4 w-4 text-[var(--to-accent-amber)]' />
              Run launcher
            </CardTitle>
            <div className='flex items-center gap-2 text-xs'>
              {agentStatus?.agent_online ? (
                agentStatus.chrome_ready ? (
                  <Badge className='border border-emerald-500/30 bg-emerald-500/15 text-emerald-300'>
                    <span className='mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-emerald-400' />
                    Agent Ready
                  </Badge>
                ) : (
                  <Badge className='border border-amber-500/30 bg-amber-500/15 text-amber-300'>
                    <span className='mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-amber-400' />
                    Chrome Offline
                  </Badge>
                )
              ) : (
                <Badge className='border border-red-500/30 bg-red-500/15 text-red-300'>
                  <span className='mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-red-400' />
                  Agent Offline
                </Badge>
              )}
            </div>
          </div>
          <CardDescription>Start one optimizer run at a time from the dashboard.</CardDescription>
        </CardHeader>
        <CardContent className='space-y-4'>
          <div className='grid gap-3 md:grid-cols-2 xl:grid-cols-3'>
            <label className='space-y-1 text-xs text-[var(--to-text-secondary)]'>
              <span>Strategy ID</span>
              <Input value={strategyId} onChange={(event) => setStrategyId(event.target.value)} placeholder='liq_sd_v1' />
            </label>
            <label className='space-y-1 text-xs text-[var(--to-text-secondary)]'>
              <span>Strategy version</span>
              <Input value={strategyVersion} onChange={(event) => setStrategyVersion(event.target.value)} placeholder='1' />
            </label>
            <label className='space-y-1 text-xs text-[var(--to-text-secondary)]'>
              <span>Mode</span>
              <select
                value={mode}
                onChange={(event) => setMode(event.target.value as typeof mode)}
                className='h-9 w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 text-sm text-[var(--to-text-primary)]'
              >
                <option value='bayesian'>Bayesian</option>
                <option value='smart'>Smart</option>
                <option value='fast'>Fast</option>
                <option value='full'>Full</option>
              </select>
            </label>
            <label className='space-y-1 text-xs text-[var(--to-text-secondary)]'>
              <span>Broker</span>
              <select
                aria-label='Broker'
                value={broker}
                onChange={(event) => setBroker(event.target.value as typeof broker)}
                className='h-9 w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 text-sm text-[var(--to-text-primary)]'
              >
                <option value='vantage'>Vantage</option>
                <option value='oanda'>OANDA</option>
                <option value='fxcm'>FXCM</option>
              </select>
            </label>
            <label className='space-y-1 text-xs text-[var(--to-text-secondary)]'>
              <span>Backtest range</span>
              <select
                aria-label='Backtest range'
                value={backtestRange}
                onChange={(event) => setBacktestRange(event.target.value as typeof backtestRange)}
                className='h-9 w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 text-sm text-[var(--to-text-primary)]'
              >
                <option value='30d'>Last 30 days</option>
                <option value='90d'>Last 90 days</option>
                <option value='365d'>Last 365 days</option>
                <option value='all'>Entire history</option>
              </select>
            </label>
            <label className='space-y-1 text-xs text-[var(--to-text-secondary)]'>
              <span>Workers</span>
              <Input value={workers} onChange={(event) => setWorkers(event.target.value)} />
            </label>
            <label className='space-y-1 text-xs text-[var(--to-text-secondary)]'>
              <span>Trials</span>
              <Input value={nTrials} onChange={(event) => setNTrials(event.target.value)} />
            </label>
            <label className='space-y-1 text-xs text-[var(--to-text-secondary)] md:col-span-2 xl:col-span-1'>
              <span>Max DD %</span>
              <Input value={ddLimit} onChange={(event) => setDdLimit(event.target.value)} />
            </label>
            <label className='space-y-1 text-xs text-[var(--to-text-secondary)] md:col-span-2'>
              <span>Pairs</span>
              <Input
                value={allPairs ? 'ALL (server default list)' : pairs}
                onChange={(event) => setPairs(event.target.value)}
                disabled={allPairs}
              />
            </label>
          </div>
          <label className='flex items-center gap-2 text-xs text-[var(--to-text-secondary)]'>
            <input type='checkbox' checked={allPairs} onChange={(event) => setAllPairs(event.target.checked)} />
            All pairs
            <span className='text-[10px] text-[var(--to-text-dim)]'>(uses backend default list)</span>
          </label>
          <label className='flex items-center gap-2 text-xs text-[var(--to-text-secondary)]'>
            <input type='checkbox' checked={dryRun} onChange={(event) => setDryRun(event.target.checked)} />
            Dry run
          </label>
          <div className='flex flex-wrap items-center gap-2'>
            <Button onClick={handleSubmit} disabled={!canStartRun}>
              {createRun.isPending ? <Loader2 className='h-4 w-4 animate-spin' /> : <Play className='h-4 w-4' />}
              Start run
            </Button>
            <Button
              variant='outline'
              onClick={() => currentRunId && cancelRun.mutate(currentRunId)}
              disabled={!activeRun || cancelRun.isPending}
            >
              {cancelRun.isPending ? <Loader2 className='h-4 w-4 animate-spin' /> : <Square className='h-4 w-4' />}
              Cancel run
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className='flex items-center gap-2'>
            <Trophy className='h-4 w-4 text-[var(--to-long)]' />
            Active run
          </CardTitle>
          <CardDescription>Latest running or selected historical optimizer run.</CardDescription>
        </CardHeader>
        <CardContent className='grid gap-3 md:grid-cols-2 xl:grid-cols-5'>
          <div className='rounded-lg border border-[var(--to-border)] p-3'>
            <p className='text-[10px] uppercase tracking-[0.15em] text-[var(--to-text-dim)]'>Status</p>
            <div className='mt-2 flex items-center gap-2'>
              <Badge className={cn('border', statusTone(currentRun?.status ?? 'idle'))}>
                {currentRun?.status ?? 'idle'}
              </Badge>
              {currentStrategyBadge ? (
                <Badge className='border border-[var(--to-border)] bg-[var(--to-surface-raised)] text-[var(--to-text-secondary)]'>
                  {currentStrategyBadge}
                </Badge>
              ) : null}
            </div>
          </div>
          <div className='rounded-lg border border-[var(--to-border)] p-3'>
            <p className='text-[10px] uppercase tracking-[0.15em] text-[var(--to-text-dim)]'>Completed pairs</p>
            <p className='mt-2 text-xl font-semibold text-[var(--to-text-primary)]'>{completedPairs}</p>
          </div>
          <div className='rounded-lg border border-[var(--to-border)] p-3'>
            <p className='text-[10px] uppercase tracking-[0.15em] text-[var(--to-text-dim)]'>Running pairs</p>
            <p className='mt-2 text-xl font-semibold text-[var(--to-text-primary)]'>{runningPairs}</p>
          </div>
          <div className='rounded-lg border border-[var(--to-border)] p-3'>
            <p className='text-[10px] uppercase tracking-[0.15em] text-[var(--to-text-dim)]'>Failed pairs</p>
            <p className='mt-2 text-xl font-semibold text-[var(--to-text-primary)]'>{failedPairs}</p>
          </div>
          <div className='rounded-lg border border-[var(--to-border)] p-3'>
            <p className='text-[10px] uppercase tracking-[0.15em] text-[var(--to-text-dim)]'>Broker</p>
            <p className='mt-2 text-sm font-medium text-[var(--to-text-primary)]'>
              {currentRun?.broker ? currentRun.broker.toUpperCase() : 'Unknown'}
            </p>
            <p className='mt-1 text-xs text-[var(--to-text-dim)]'>
              Market: {currentRun?.market ?? 'unknown'}
            </p>
          </div>
          <div className='rounded-lg border border-[var(--to-border)] p-3'>
            <p className='text-[10px] uppercase tracking-[0.15em] text-[var(--to-text-dim)]'>Best result</p>
            <p className='mt-2 text-sm font-medium text-[var(--to-text-primary)]'>
              {currentRun?.summary?.best_symbol ?? '--'} / {formatNumber(currentRun?.summary?.best_score)}
            </p>
            <p className='mt-1 text-xs text-[var(--to-text-dim)]'>Total pairs: {totalPairs}</p>
          </div>
        </CardContent>
      </Card>

      <div className='grid gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.95fr)]'>
        <div className='space-y-4'>
          <PortfolioOverview portfolioResult={currentRun?.portfolio_result} results={results} />

          <Card>
            <CardHeader>
              <CardTitle>Pair analysis</CardTitle>
              <CardDescription>Decision-oriented view of per-pair survivability for the selected run.</CardDescription>
            </CardHeader>
            <CardContent>
              <PairAnalysisTable
                results={results}
                weights={portfolioWeights}
                selectedSymbol={selectedSymbol}
                onSelectSymbol={setSelectedSymbol}
              />
            </CardContent>
          </Card>

          <PairDrilldown
            symbol={selectedSymbol}
            result={selectedResult}
            weight={selectedSymbol ? portfolioWeights[selectedSymbol] : undefined}
            trials={trials}
            stressResults={stressResults}
          />

          <Card>
            <CardHeader>
              <CardTitle>Timeline</CardTitle>
              <CardDescription>Machine-readable event feed and log lines.</CardDescription>
            </CardHeader>
            <CardContent>
              <OptimizerTimeline events={events} />
            </CardContent>
          </Card>
        </div>

        <Card className='h-fit'>
          <CardHeader>
            <CardTitle>Run comparison & history</CardTitle>
            <CardDescription>Select a run to compare portfolio posture, symbol decisions, and timeline context.</CardDescription>
          </CardHeader>
          <CardContent className='space-y-3'>
            {runsLoading ? (
              <p className='text-xs text-[var(--to-text-dim)]'>Loading run history…</p>
            ) : runs.length === 0 ? (
              <p className='text-xs text-[var(--to-text-dim)]'>No optimizer runs yet.</p>
            ) : (
              runs.map((run) => {
                const isSelected = currentRunId === run.id;
                return (
                  <button
                    key={run.id}
                    type='button'
                    onClick={() => setSelectedRunId(run.id)}
                    aria-pressed={isSelected}
                    className={cn(
                      'flex w-full items-start justify-between gap-3 rounded-xl border px-3 py-3 text-left transition-colors',
                      isSelected
                        ? 'border-[var(--to-accent-amber)] bg-[var(--to-accent-amber)]/10 shadow-[0_0_0_1px_rgba(245,158,11,0.18)]'
                        : 'border-[var(--to-border)] hover:bg-[var(--to-surface-raised)]/50'
                    )}
                  >
                    <span className='min-w-0'>
                      <span className='block truncate font-mono text-xs text-[var(--to-text-primary)]'>{run.id}</span>
                      <span className='mt-1 block text-[10px] uppercase tracking-[0.16em] text-[var(--to-text-dim)]'>
                        {(run.broker ?? 'unknown').toUpperCase()} · {run.mode} · {run.pairs.length} pairs
                      </span>
                      <span className='mt-2 block text-xs text-[var(--to-text-secondary)]'>
                        Best {run.summary?.best_symbol ?? '--'} · score {formatNumber(run.summary?.best_score)}
                      </span>
                      {run.portfolio_result ? (
                        <span className='mt-1 block text-xs text-[var(--to-text-dim)]'>
                          DD {formatSignedPercent(run.portfolio_result.combined_max_drawdown_pct)} · daily{' '}
                          {formatSignedPercent(run.portfolio_result.combined_daily_drawdown_pct)}
                        </span>
                      ) : (
                        <span className='mt-1 block text-xs text-[var(--to-text-dim)]'>
                          Portfolio summary pending for this run.
                        </span>
                      )}
                      {getStrategyBadge(run) ? (
                        <span className='mt-2 inline-flex rounded border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-1.5 py-0.5 text-[9px] font-semibold text-[var(--to-text-dim)]'>
                          {getStrategyBadge(run)}
                        </span>
                      ) : null}
                    </span>
                    <Badge className={cn('border', statusTone(run.status))}>{run.status}</Badge>
                  </button>
                );
              })
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
