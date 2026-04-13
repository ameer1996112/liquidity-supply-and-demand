'use client';

import { useEffect, useState } from 'react';
import { Loader2, Play, Square, History, ListTree, Trophy } from 'lucide-react';
import { useAgentStatus, useCancelOptimizerRun, useCreateOptimizerRun, useOptimizerRun, useOptimizerRunEvents, useOptimizerRunResults, useOptimizerRuns } from '@/hooks/useOptimizerRuns';
import type { OptimizerRunCreateApi, OptimizerRunEventApi, OptimizerRunResultApi } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

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

function OptimizerResultsTable({ results }: { results: OptimizerRunResultApi[] }) {
  if (results.length === 0) {
    return <p className='text-xs text-[var(--to-text-dim)]'>No symbol results yet.</p>;
  }

  return (
    <div className='overflow-x-auto'>
      <table className='min-w-full text-left text-xs'>
        <thead className='text-[var(--to-text-dim)]'>
          <tr className='border-b border-[var(--to-border)]'>
            <th className='py-2 pr-3'>Symbol</th>
            <th className='py-2 pr-3'>Status</th>
            <th className='py-2 pr-3'>Score</th>
            <th className='py-2 pr-3'>Net PnL</th>
            <th className='py-2 pr-3'>Win Rate</th>
            <th className='py-2 pr-3'>Profit Factor</th>
            <th className='py-2'>Max DD %</th>
          </tr>
        </thead>
        <tbody>
          {results.map((result) => (
            <tr key={result.symbol} className='border-b border-[var(--to-border)]/60'>
              <td className='py-2 pr-3 font-mono text-[var(--to-text-primary)]'>{result.symbol}</td>
              <td className='py-2 pr-3'>
                <Badge className={cn('border', statusTone(result.status))}>{result.status}</Badge>
              </td>
              <td className='py-2 pr-3'>{formatNumber(result.metrics?.score)}</td>
              <td className='py-2 pr-3'>{formatNumber(result.metrics?.net_profit)}</td>
              <td className='py-2 pr-3'>{formatNumber(result.metrics?.win_rate)}</td>
              <td className='py-2 pr-3'>{formatNumber(result.metrics?.profit_factor)}</td>
              <td className='py-2'>{formatNumber(result.metrics?.max_drawdown_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OptimizerTimeline({ events }: { events: OptimizerRunEventApi[] }) {
  if (events.length === 0) {
    return <p className='text-xs text-[var(--to-text-dim)]'>No timeline events yet.</p>;
  }

  return (
    <div className='space-y-2'>
      {events.map((event, index) => (
        <div key={`${event.event_type}-${event.created_at ?? index}`} className='rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)]/40 p-3'>
          <div className='flex flex-wrap items-center gap-2 text-xs'>
            <Badge className='border border-[var(--to-border)] bg-transparent text-[var(--to-text-secondary)]'>
              {event.event_type}
            </Badge>
            {event.symbol && <span className='font-mono text-[var(--to-text-primary)]'>{event.symbol}</span>}
            {typeof event.worker_id === 'number' && (
              <span className='text-[var(--to-text-dim)]'>worker-{event.worker_id}</span>
            )}
            {event.created_at && <span className='text-[var(--to-text-dim)]'>{event.created_at}</span>}
          </div>
          {event.payload?.message && (
            <p className='mt-2 text-xs text-[var(--to-text-secondary)]'>{event.payload.message}</p>
          )}
        </div>
      ))}
    </div>
  );
}

export function OptimizerRunsWorkspace() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [mode, setMode] = useState<'bayesian' | 'smart' | 'fast' | 'full'>('bayesian');
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
  const { data: results = [] } = useOptimizerRunResults(currentRunId);
  const { data: events = [] } = useOptimizerRunEvents(currentRunId);

  useEffect(() => {
    if (!selectedRunId && currentRunId) {
      setSelectedRunId(currentRunId);
    }
  }, [currentRunId, selectedRunId]);

  const handleSubmit = () => {
    const payload: OptimizerRunCreateApi = {
      mode,
      workers: Number(workers),
      pairs: allPairs ? ['ALL'] : pairs.split(',').map((item) => item.trim()).filter(Boolean),
      n_trials: Number(nTrials),
      dd_limit: Number(ddLimit),
      dry_run: dryRun,
    };
    createRun.mutate(payload, {
      onSuccess: (run) => setSelectedRunId(run.id),
    });
  };

  const completedPairs = currentRun?.summary?.completed_pairs ?? 0;
  const failedPairs = currentRun?.summary?.failed_pairs ?? 0;
  const totalPairs = currentRun?.summary?.total_pairs ?? 0;
  const runningPairs = currentRun?.summary?.running_pairs ?? 0;

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
            <Button onClick={handleSubmit} disabled={createRun.isPending}>
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
            <p className='text-[10px] uppercase tracking-[0.15em] text-[var(--to-text-dim)]'>Best result</p>
            <p className='mt-2 text-sm font-medium text-[var(--to-text-primary)]'>
              {currentRun?.summary?.best_symbol ?? '--'} / {formatNumber(currentRun?.summary?.best_score)}
            </p>
            <p className='mt-1 text-xs text-[var(--to-text-dim)]'>Total pairs: {totalPairs}</p>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue='results' className='space-y-3'>
        <TabsList variant='line' className='w-full justify-start'>
          <TabsTrigger value='results'>
            <ListTree className='h-4 w-4' />
            Results
          </TabsTrigger>
          <TabsTrigger value='timeline'>
            <History className='h-4 w-4' />
            Timeline
          </TabsTrigger>
          <TabsTrigger value='history'>History</TabsTrigger>
        </TabsList>

        <TabsContent value='results'>
          <Card>
            <CardHeader>
              <CardTitle>Results</CardTitle>
              <CardDescription>Per-symbol optimizer output for the selected run.</CardDescription>
            </CardHeader>
            <CardContent>
              <OptimizerResultsTable results={results} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value='timeline'>
          <Card>
            <CardHeader>
              <CardTitle>Timeline</CardTitle>
              <CardDescription>Machine-readable event feed and log lines.</CardDescription>
            </CardHeader>
            <CardContent>
              <OptimizerTimeline events={events} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value='history'>
          <Card>
            <CardHeader>
              <CardTitle>History</CardTitle>
              <CardDescription>Select a prior run to inspect details.</CardDescription>
            </CardHeader>
            <CardContent className='space-y-2'>
              {runsLoading ? (
                <p className='text-xs text-[var(--to-text-dim)]'>Loading run history…</p>
              ) : runs.length === 0 ? (
                <p className='text-xs text-[var(--to-text-dim)]'>No optimizer runs yet.</p>
              ) : (
                runs.map((run) => (
                  <button
                    key={run.id}
                    type='button'
                    onClick={() => setSelectedRunId(run.id)}
                    className={cn(
                      'flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left transition-colors',
                      selectedRunId === run.id ? 'border-[var(--to-accent-amber)] bg-[var(--to-accent-amber)]/8' : 'border-[var(--to-border)] hover:bg-[var(--to-surface-raised)]/50'
                    )}
                  >
                    <span className='min-w-0'>
                      <span className='block truncate font-mono text-xs text-[var(--to-text-primary)]'>{run.id}</span>
                      <span className='block text-[10px] text-[var(--to-text-dim)]'>
                        {run.mode} • {run.pairs.length} pairs • {run.workers} workers
                      </span>
                    </span>
                    <Badge className={cn('border', statusTone(run.status))}>{run.status}</Badge>
                  </button>
                ))
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
