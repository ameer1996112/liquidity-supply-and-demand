'use client';

import { useEffect, useState } from 'react';
import { History, ListTree, Loader2, Play, SlidersHorizontal, Square, Trophy } from 'lucide-react';
import {
  useAlertApprovedConfigs,
  useAlertBatches,
  useAlertBatch,
  useAlertBatchEvents,
  useAlertBatchResults,
  useAlertRunnerStatus,
  useCancelAlertBatch,
  useCreateAlertBatch,
} from '@/hooks/useAlertSetup';
import type {
  AlertApprovedConfigApi,
  AlertBatchEventApi,
  AlertBatchResultApi,
  AlertBatchCreateApi,
  AlertSetupPresetMode,
} from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

const PRESET_OPTIONS: Array<{
  mode: AlertSetupPresetMode;
  label: string;
  description: string;
}> = [
  { mode: 'top3', label: 'Top 3', description: 'Fastest approved shortlist' },
  { mode: 'top5', label: 'Top 5', description: 'Balanced deployment basket' },
  { mode: 'approved', label: 'Approved', description: 'All approved configs' },
  { mode: 'custom', label: 'Custom', description: 'Comma-separated symbol list' },
];

const TIMEFRAME_OPTIONS = ['1m', '5m', '15m', '1h'];

function statusTone(status: string) {
  if (status === 'completed' || status === 'created') return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
  if (status === 'running' || status === 'queued') return 'bg-amber-500/15 text-amber-300 border-amber-500/30';
  if (status === 'cancelled' || status === 'interrupted' || status === 'skipped') {
    return 'bg-slate-500/15 text-slate-300 border-slate-500/30';
  }
  return 'bg-red-500/15 text-red-300 border-red-500/30';
}

function formatNumber(value: number | null | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '--';
  return value.toFixed(2);
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
    case 'batch_started':
      return 'Batch started';
    case 'pair_started':
      return 'Pair started';
    case 'alert_created':
      return 'Alert created';
    case 'pair_completed':
      return 'Pair completed';
    case 'pair_failed':
      return 'Pair failed';
    case 'batch_finished':
      return 'Batch finished';
    case 'batch_cancelled':
      return 'Batch cancelled';
    case 'log':
      return 'Log';
    default:
      return eventType.replace(/_/g, ' ');
  }
}

function timelineTone(eventType: string) {
  if (eventType === 'pair_failed' || eventType === 'batch_finished') {
    return 'border-red-500/30 bg-red-500/10 text-red-200';
  }
  if (eventType === 'alert_created' || eventType === 'pair_completed') {
    return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200';
  }
  if (eventType === 'pair_started' || eventType === 'batch_started') {
    return 'border-amber-500/30 bg-amber-500/10 text-amber-200';
  }
  if (eventType === 'batch_cancelled') {
    return 'border-slate-500/30 bg-slate-500/10 text-slate-200';
  }
  return 'border-[var(--to-border)] bg-transparent text-[var(--to-text-secondary)]';
}

function describeTimelineEvent(event: AlertBatchEventApi) {
  switch (event.event_type) {
    case 'batch_started':
      return event.payload?.source_mode
        ? `Mode ${event.payload.source_mode} · ${event.payload?.pairs?.length ?? '--'} pairs`
        : 'Batch started';
    case 'pair_started':
      return event.pair ? `Preparing ${event.pair}` : 'Pair started';
    case 'alert_created':
      return event.pair
        ? `${event.pair} alert saved${event.payload?.alert_name ? ` · ${event.payload.alert_name}` : ''}${event.payload?.alert_id ? ` (${event.payload.alert_id})` : ''}`
        : 'Alert created';
    case 'pair_completed':
      if (!event.pair) return 'Pair completed';
      if (event.payload?.skipped_existing) {
        return `${event.pair} skipped · alert already exists`;
      }
      return `${event.pair} alert created`;
    case 'pair_failed':
      return event.pair
        ? `${event.pair} failed${event.payload?.error_message ? ` · ${event.payload.error_message}` : ''}`
        : 'Pair failed';
    case 'batch_finished':
      return event.payload?.status ? `Batch ${event.payload.status}` : 'Batch finished';
    case 'batch_cancelled':
      return 'Batch cancelled';
    case 'log':
      return cleanTimelineMessage(String(event.payload?.message ?? 'log'));
    default:
      return cleanTimelineMessage(String(event.payload?.message ?? event.event_type));
  }
}

function presetLabel(mode: AlertSetupPresetMode) {
  return PRESET_OPTIONS.find((option) => option.mode === mode)?.label ?? mode;
}

function parseCustomPairs(value: string) {
  return Array.from(
    new Set(
      value
        .split(',')
        .map((item) => item.trim().toUpperCase())
        .filter(Boolean)
    )
  );
}

function getApprovedConfigs(configs: AlertApprovedConfigApi[]) {
  return [...configs]
    .filter((config) => config.status === 'approved')
    .sort((left, right) => (left.rank ?? Number.MAX_SAFE_INTEGER) - (right.rank ?? Number.MAX_SAFE_INTEGER));
}

function AlertResultsTable({ results }: { results: AlertBatchResultApi[] }) {
  if (results.length === 0) {
    return <p className='text-xs text-[var(--to-text-dim)]'>No alert results yet.</p>;
  }

  return (
    <div className='overflow-x-auto'>
      <table className='min-w-full text-left text-xs'>
        <thead className='text-[var(--to-text-dim)]'>
          <tr className='border-b border-[var(--to-border)]'>
            <th className='py-2 pr-3'>Pair</th>
            <th className='py-2 pr-3'>Status</th>
            <th className='py-2 pr-3'>Alert Name</th>
            <th className='py-2 pr-3'>Risk</th>
            <th className='py-2 pr-3'>Timeframe</th>
            <th className='py-2 pr-3'>Alert ID</th>
            <th className='py-2'>Error</th>
          </tr>
        </thead>
        <tbody>
          {results.map((result) => (
            <tr key={result.pair} className='border-b border-[var(--to-border)]/60'>
              <td className='py-2 pr-3 font-mono text-[var(--to-text-primary)]'>{result.pair}</td>
              <td className='py-2 pr-3'>
                <Badge className={cn('border', statusTone(result.status))}>{result.status}</Badge>
              </td>
              <td className='py-2 pr-3 text-[var(--to-text-primary)]'>{result.alert_name ?? '--'}</td>
              <td className='py-2 pr-3'>{formatNumber(result.risk_weight)}</td>
              <td className='py-2 pr-3'>{result.timeframe ?? '--'}</td>
              <td className='py-2 pr-3 font-mono text-[var(--to-text-primary)]'>{result.alert_id ?? '--'}</td>
              <td className='py-2 text-[var(--to-text-secondary)]'>{result.error_message ?? '--'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AlertTimeline({ events }: { events: AlertBatchEventApi[] }) {
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
            <p className='mt-2 text-xs text-[var(--to-text-dim)]'>
              {formatTimelineTimestamp(latestStructuredEvent.created_at)}
            </p>
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
            <p className='mt-2 text-xs text-[var(--to-text-dim)]'>
              {formatTimelineTimestamp(latestLogEvent.created_at)}
            </p>
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
              <div
                key={`${event.event_type}-${event.created_at ?? index}`}
                className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/40 p-3'
              >
                <div className='flex flex-wrap items-center gap-2 text-xs'>
                  <Badge className={cn('border', timelineTone(event.event_type))}>
                    {timelineEventLabel(event.event_type)}
                  </Badge>
                  {event.pair && <span className='font-mono text-[var(--to-text-primary)]'>{event.pair}</span>}
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
              <div
                key={`${event.event_type}-${event.created_at ?? index}`}
                className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/25 p-3'
              >
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

function ApprovedConfigsTable({ configs }: { configs: AlertApprovedConfigApi[] }) {
  if (configs.length === 0) {
    return <p className='text-xs text-[var(--to-text-dim)]'>No approved configs available yet.</p>;
  }

  return (
    <div className='overflow-x-auto'>
      <table className='min-w-full text-left text-xs'>
        <thead className='text-[var(--to-text-dim)]'>
          <tr className='border-b border-[var(--to-border)]'>
            <th className='py-2 pr-3'>Rank</th>
            <th className='py-2 pr-3'>Pair</th>
            <th className='py-2 pr-3'>Timeframe</th>
            <th className='py-2 pr-3'>Score</th>
            <th className='py-2 pr-3'>PF</th>
            <th className='py-2 pr-3'>Max DD %</th>
            <th className='py-2 pr-3'>Risk</th>
            <th className='py-2'>Source Run</th>
          </tr>
        </thead>
        <tbody>
          {configs.map((config) => (
            <tr key={`${config.pair}-${config.timeframe}`} className='border-b border-[var(--to-border)]/60'>
              <td className='py-2 pr-3 text-[var(--to-text-dim)]'>{config.rank ?? '--'}</td>
              <td className='py-2 pr-3 font-mono text-[var(--to-text-primary)]'>{config.pair}</td>
              <td className='py-2 pr-3'>{config.timeframe}</td>
              <td className='py-2 pr-3'>{formatNumber(config.score ?? undefined)}</td>
              <td className='py-2 pr-3'>{formatNumber(config.profit_factor ?? undefined)}</td>
              <td className='py-2 pr-3'>{formatNumber(config.max_drawdown_pct ?? undefined)}</td>
              <td className='py-2 pr-3'>{formatNumber(config.risk_weight ?? undefined)}x</td>
              <td className='py-2 font-mono text-[var(--to-text-primary)]'>{config.source_run_id ?? '--'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AlertSetupWorkspace() {
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
  const [presetMode, setPresetMode] = useState<AlertSetupPresetMode>('approved');
  const [timeframe, setTimeframe] = useState('5m');
  const [alertNamePrefix, setAlertNamePrefix] = useState('TradeOps');
  const [webhookUrl, setWebhookUrl] = useState('');
  const [customPairs, setCustomPairs] = useState('USDJPY,GBPUSD,GBPNZD,XAUUSD');
  const [useApprovedWeights, setUseApprovedWeights] = useState(true);

  const { data: batches = [], isLoading: batchesLoading } = useAlertBatches();
  const { data: approvedConfigs = [] } = useAlertApprovedConfigs();
  const { data: runnerStatus } = useAlertRunnerStatus();
  const createBatch = useCreateAlertBatch();
  const cancelBatch = useCancelAlertBatch();

  const approvedPairs = getApprovedConfigs(approvedConfigs);
  const selectedPairs =
    presetMode === 'top3'
      ? approvedPairs.slice(0, 3).map((config) => config.pair)
      : presetMode === 'top5'
        ? approvedPairs.slice(0, 5).map((config) => config.pair)
        : presetMode === 'approved'
          ? approvedPairs.map((config) => config.pair)
          : parseCustomPairs(customPairs);

  const activeBatch = batches.find((batch) => batch.status === 'running' || batch.status === 'queued') ?? null;
  const currentBatchId = selectedBatchId ?? activeBatch?.id ?? batches[0]?.id ?? null;
  const { data: currentBatch } = useAlertBatch(currentBatchId);
  const { data: results = [] } = useAlertBatchResults(currentBatchId);
  const { data: events = [] } = useAlertBatchEvents(currentBatchId);

  useEffect(() => {
    if (!selectedBatchId && currentBatchId) {
      setSelectedBatchId(currentBatchId);
    }
  }, [currentBatchId, selectedBatchId]);

  const selectedPreview = selectedPairs.map((pair) => {
    const match = approvedPairs.find((config) => config.pair === pair);
    return {
      pair,
      timeframe: match?.timeframe ?? timeframe,
      status: match?.status ?? 'candidate',
      rank: match?.rank ?? null,
      risk_weight: useApprovedWeights ? match?.risk_weight ?? 1 : 1,
      score: match?.score ?? null,
      profit_factor: match?.profit_factor ?? null,
      max_drawdown_pct: match?.max_drawdown_pct ?? null,
      source_run_id: match?.source_run_id ?? null,
    };
  });

  const totalPairs = currentBatch?.summary?.total_pairs ?? selectedPairs.length;
  const completedPairs = currentBatch?.summary?.completed_pairs ?? 0;
  const failedPairs = currentBatch?.summary?.failed_pairs ?? 0;
  const runningPairs = currentBatch?.summary?.running_pairs ?? 0;
  const createdAlerts = currentBatch?.summary?.created_alerts ?? 0;
  const skippedPairs = currentBatch?.summary?.skipped_pairs ?? 0;
  const finishedPairs = completedPairs + failedPairs + skippedPairs;
  const progressPct = totalPairs > 0 ? Math.min(100, Math.round((finishedPairs / totalPairs) * 100)) : 0;

  function handleSubmit() {
    const payload: AlertBatchCreateApi = {
      source_mode: presetMode,
      pairs: selectedPairs,
      timeframe,
      alert_name_prefix: alertNamePrefix.trim() || undefined,
      webhook_url: webhookUrl.trim() || undefined,
      use_approved_weights: useApprovedWeights,
      pair_risk_weights: Object.fromEntries(
        selectedPreview.map((item) => [item.pair, Number(item.risk_weight ?? 1)])
      ),
    };

    createBatch.mutate(payload, {
      onSuccess: (batch) => setSelectedBatchId(batch.id),
    });
  }

  return (
    <div className='space-y-4'>
      <Card>
        <CardHeader>
          <div className='flex items-center justify-between gap-3'>
            <CardTitle className='flex items-center gap-2'>
              <SlidersHorizontal className='h-4 w-4 text-[var(--to-accent-amber)]' />
              Alert Setup runner
            </CardTitle>
            <div className='flex items-center gap-2 text-xs'>
              {runnerStatus?.agent_online ? (
                runnerStatus.chrome_ready ? (
                  <Badge className='border border-emerald-500/30 bg-emerald-500/15 text-emerald-300'>
                    <span className='mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-emerald-400' />
                    Runner Ready
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
                  Runner Offline
                </Badge>
              )}
            </div>
          </div>
          <CardDescription>
            Deploy approved pair configs into TradingView alerts one batch at a time.
          </CardDescription>
        </CardHeader>
        <CardContent className='space-y-4'>
          <div className='grid gap-3 md:grid-cols-2 xl:grid-cols-3'>
            <div className='space-y-1 text-xs text-[var(--to-text-secondary)] md:col-span-2 xl:col-span-3'>
              <span>Preset</span>
              <div className='grid gap-2 sm:grid-cols-2 xl:grid-cols-4'>
                {PRESET_OPTIONS.map((option) => {
                  const isActive = presetMode === option.mode;
                  return (
                    <button
                      key={option.mode}
                      type='button'
                      onClick={() => setPresetMode(option.mode)}
                      className={cn(
                        'rounded-lg border px-3 py-2 text-left transition-colors',
                        isActive
                          ? 'border-[var(--to-accent-amber)] bg-[var(--to-accent-amber)]/10'
                          : 'border-[var(--to-border)] hover:bg-[var(--to-surface-raised)]/50'
                      )}
                    >
                      <span className='block text-sm font-medium text-[var(--to-text-primary)]'>{option.label}</span>
                      <span className='mt-0.5 block text-[10px] text-[var(--to-text-dim)]'>{option.description}</span>
                    </button>
                  );
                })}
              </div>
            </div>
            <label className='space-y-1 text-xs text-[var(--to-text-secondary)]'>
              <span>Timeframe</span>
              <select
                value={timeframe}
                onChange={(event) => setTimeframe(event.target.value)}
                className='h-9 w-full rounded-md border border-[var(--to-border)] bg-[var(--to-surface)] px-3 text-sm text-[var(--to-text-primary)]'
              >
                {TIMEFRAME_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <label className='space-y-1 text-xs text-[var(--to-text-secondary)]'>
              <span>Alert name prefix</span>
              <Input value={alertNamePrefix} onChange={(event) => setAlertNamePrefix(event.target.value)} />
            </label>
            <label className='space-y-1 text-xs text-[var(--to-text-secondary)] md:col-span-2 xl:col-span-1'>
              <span>Webhook URL</span>
              <Input
                value={webhookUrl}
                onChange={(event) => setWebhookUrl(event.target.value)}
                placeholder='https://...'
              />
            </label>
            <label className='flex items-center gap-2 text-xs text-[var(--to-text-secondary)] md:col-span-2 xl:col-span-3'>
              <input
                type='checkbox'
                checked={useApprovedWeights}
                onChange={(event) => setUseApprovedWeights(event.target.checked)}
              />
              Use approved risk weights
              <span className='text-[10px] text-[var(--to-text-dim)]'>(0.25x / 0.50x / 0.75x source weights)</span>
            </label>
          </div>

          {presetMode === 'custom' && (
            <label className='space-y-1 text-xs text-[var(--to-text-secondary)]'>
              <span>Custom pairs</span>
              <Input
                value={customPairs}
                onChange={(event) => setCustomPairs(event.target.value)}
                placeholder='USDJPY,GBPUSD,XAUUSD'
              />
            </label>
          )}

          <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/40 p-4'>
            <div className='flex items-center justify-between gap-3'>
              <div>
                <p className='text-[10px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>Selected pairs</p>
                <p className='mt-1 text-sm text-[var(--to-text-secondary)]'>
                  {presetLabel(presetMode)} · {selectedPairs.length} pairs · {timeframe}
                </p>
              </div>
              <Badge className='border border-[var(--to-border)] bg-transparent text-[var(--to-text-secondary)]'>
                Approved preview
              </Badge>
            </div>
            <div className='mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4'>
              {selectedPreview.length === 0 ? (
                <p className='text-xs text-[var(--to-text-dim)]'>No pairs selected yet.</p>
              ) : (
                selectedPreview.map((item) => (
                  <div key={item.pair} className='rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)]/50 p-3'>
                    <div className='flex items-center justify-between gap-2'>
                      <span className='font-mono text-sm text-[var(--to-text-primary)]'>{item.pair}</span>
                      <Badge className={cn('border', statusTone(item.status))}>{item.status}</Badge>
                    </div>
                    <p className='mt-2 text-xs text-[var(--to-text-secondary)]'>
                      {item.timeframe} · risk {formatNumber(item.risk_weight)}x
                    </p>
                    <p className='mt-1 text-[10px] text-[var(--to-text-dim)]'>
                      Score {formatNumber(item.score ?? undefined)} · PF {formatNumber(item.profit_factor ?? undefined)} · DD {formatNumber(item.max_drawdown_pct ?? undefined)}%
                    </p>
                    <p className='mt-1 text-[10px] text-[var(--to-text-dim)]'>
                      Source {item.source_run_id ?? '--'} · rank {item.rank ?? '--'}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className='flex flex-wrap items-center gap-2'>
            <Button onClick={handleSubmit} disabled={createBatch.isPending || selectedPairs.length === 0}>
              {createBatch.isPending ? <Loader2 className='h-4 w-4 animate-spin' /> : <Play className='h-4 w-4' />}
              Start batch
            </Button>
            <Button
              variant='outline'
              onClick={() => currentBatchId && cancelBatch.mutate(currentBatchId)}
              disabled={!activeBatch || cancelBatch.isPending}
            >
              {cancelBatch.isPending ? <Loader2 className='h-4 w-4 animate-spin' /> : <Square className='h-4 w-4' />}
              Cancel batch
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className='flex items-center gap-2'>
            <Trophy className='h-4 w-4 text-[var(--to-long)]' />
            Active batch
          </CardTitle>
          <CardDescription>Latest running or selected historical alert batch.</CardDescription>
        </CardHeader>
        <CardContent className='space-y-4'>
          <div className='grid gap-3 md:grid-cols-2 xl:grid-cols-5'>
            <div className='rounded-lg border border-[var(--to-border)] p-3'>
              <p className='text-[10px] uppercase tracking-[0.15em] text-[var(--to-text-dim)]'>Status</p>
              <div className='mt-2 flex items-center gap-2'>
                <Badge className={cn('border', statusTone(currentBatch?.status ?? 'idle'))}>
                  {currentBatch?.status ?? 'idle'}
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
              <p className='text-[10px] uppercase tracking-[0.15em] text-[var(--to-text-dim)]'>Alerts created</p>
              <p className='mt-2 text-sm font-medium text-[var(--to-text-primary)]'>{createdAlerts}</p>
              <p className='mt-1 text-xs text-[var(--to-text-dim)]'>Total pairs: {totalPairs}</p>
            </div>
          </div>

          <div className='space-y-2'>
            <div className='flex items-center justify-between gap-2 text-xs text-[var(--to-text-dim)]'>
              <span>Progress</span>
              <span>{progressPct}%</span>
            </div>
            <div className='h-2 overflow-hidden rounded-full bg-[var(--to-surface)]'>
              <div
                className='h-full rounded-full bg-gradient-to-r from-[var(--to-warning)] to-[var(--to-long)] transition-all'
                style={{ width: `${progressPct}%` }}
              />
            </div>
            {currentBatch?.summary?.best_pair && (
              <p className='text-xs text-[var(--to-text-dim)]'>
                Best pair: <span className='font-mono text-[var(--to-text-primary)]'>{currentBatch.summary.best_pair}</span>
                {typeof currentBatch.summary.best_score === 'number' && (
                  <span className='ml-2'>score {formatNumber(currentBatch.summary.best_score)}</span>
                )}
              </p>
            )}
            {currentBatch?.summary?.error_message && (
              <p className='text-xs text-red-300'>Error: {currentBatch.summary.error_message}</p>
            )}
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
          <TabsTrigger value='approved'>Approved</TabsTrigger>
        </TabsList>

        <TabsContent value='results'>
          <Card>
            <CardHeader>
              <CardTitle>Results</CardTitle>
              <CardDescription>Per-pair alert creation output for the selected batch.</CardDescription>
            </CardHeader>
            <CardContent>
              <AlertResultsTable results={results} />
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
              <AlertTimeline events={events} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value='history'>
          <Card>
            <CardHeader>
              <CardTitle>History</CardTitle>
              <CardDescription>Select a prior batch to inspect details.</CardDescription>
            </CardHeader>
            <CardContent className='space-y-2'>
              {batchesLoading ? (
                <p className='text-xs text-[var(--to-text-dim)]'>Loading batch history…</p>
              ) : batches.length === 0 ? (
                <p className='text-xs text-[var(--to-text-dim)]'>No alert batches yet.</p>
              ) : (
                batches.map((batch) => (
                  (() => {
                    const batchPairs = batch.pairs ?? [];
                    return (
                  <button
                    key={batch.id}
                    type='button'
                    onClick={() => setSelectedBatchId(batch.id)}
                    className={cn(
                      'flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left transition-colors',
                      selectedBatchId === batch.id
                        ? 'border-[var(--to-accent-amber)] bg-[var(--to-accent-amber)]/8'
                        : 'border-[var(--to-border)] hover:bg-[var(--to-surface-raised)]/50'
                    )}
                  >
                    <span className='min-w-0'>
                      <span className='block truncate font-mono text-xs text-[var(--to-text-primary)]'>{batch.id}</span>
                      <span className='block text-[10px] text-[var(--to-text-dim)]'>
                        {presetLabel(batch.source_mode)} • {batchPairs.length} pairs • {batch.timeframe}
                      </span>
                    </span>
                    <Badge className={cn('border', statusTone(batch.status))}>{batch.status}</Badge>
                  </button>
                    );
                  })()
                ))
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value='approved'>
          <Card>
            <CardHeader>
              <CardTitle>Approved configs</CardTitle>
              <CardDescription>Source list used for presets and alert deployment.</CardDescription>
            </CardHeader>
            <CardContent>
              <ApprovedConfigsTable configs={approvedConfigs} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
