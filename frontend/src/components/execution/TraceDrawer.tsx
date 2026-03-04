'use client';

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Wifi,
  WifiOff,
  ShieldCheck,
  Zap,
  Radio,
} from 'lucide-react';
import type { TraceDetail, TraceHops, TraceBrokerStatus } from '@/types/execution';

// ── Helpers ───────────────────────────────────────────────────────────────────

function parseIso(s: string | null | undefined): Date | null {
  if (!s) return null;
  try {
    return new Date(s);
  } catch {
    return null;
  }
}

function diffMs(start: string | null | undefined, end: string | null | undefined): number | null {
  const s = parseIso(start);
  const e = parseIso(end);
  if (!s || !e) return null;
  const ms = e.getTime() - s.getTime();
  return ms >= 0 ? ms : null;
}

function fmtMs(ms: number | null): string {
  if (ms == null) return '—';
  if (ms < 1) return '<1 ms';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

function fmtTs(s: string | null | undefined): string {
  if (!s) return '—';
  try {
    return new Date(s).toISOString().replace('T', ' ').replace('Z', ' UTC').slice(0, 26);
  } catch {
    return s;
  }
}

/** Derive badge states from the trace detail */
export function deriveBrokerStatus(detail: TraceDetail): TraceBrokerStatus {
  const hops = detail.hops ?? {};
  const broker_connected = !!hops.broker_ack_at;
  const broker_confirmed = !!hops.broker_confirmed_at;
  // "missing on broker": we submitted to exec but never got a broker ACK and there's no error
  const missing_on_broker =
    !!hops.exec_submitted_at && !hops.broker_ack_at && !detail.error_type;
  return { broker_connected, broker_confirmed, missing_on_broker };
}

// ── Subcomponents ─────────────────────────────────────────────────────────────

function BrokerBadges({ status, errorType }: { status: TraceBrokerStatus; errorType?: string | null }) {
  return (
    <div className='flex flex-wrap gap-1.5'>
      {status.broker_connected && (
        <span className='inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'>
          <Wifi className='h-2.5 w-2.5' />
          broker_connected
        </span>
      )}
      {status.broker_confirmed && (
        <span className='inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20'>
          <CheckCircle2 className='h-2.5 w-2.5' />
          broker_confirmed
        </span>
      )}
      {status.missing_on_broker && (
        <span className='inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20'>
          <WifiOff className='h-2.5 w-2.5' />
          missing_on_broker
        </span>
      )}
      {errorType && (
        <span className='inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium bg-red-500/10 text-red-400 border border-red-500/20'>
          <XCircle className='h-2.5 w-2.5' />
          {errorType}
        </span>
      )}
      {!status.broker_connected && !status.missing_on_broker && !errorType && (
        <span className='inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium bg-slate-700/40 text-slate-400 border border-slate-700/40'>
          <Radio className='h-2.5 w-2.5' />
          signal_only
        </span>
      )}
    </div>
  );
}

interface HopRow {
  label: string;
  icon: React.ReactNode;
  ts: string | null | undefined;
  deltaLabel: string;
  deltaMs: number | null;
  highlight?: boolean;
}

function HopLine({ hop }: { hop: HopRow }) {
  const hasTs = !!hop.ts;
  return (
    <div className={cn('group relative flex gap-3 pb-4 last:pb-0', !hasTs && 'opacity-40')}>
      {/* Timeline track */}
      <div className='flex flex-col items-center'>
        <div
          className={cn(
            'flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[10px]',
            hasTs
              ? hop.highlight
                ? 'border-red-500/40 bg-red-500/10 text-red-400'
                : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
              : 'border-slate-700 bg-slate-900 text-slate-600',
          )}
        >
          {hop.icon}
        </div>
        <div className='mt-1 w-px flex-1 bg-slate-800 group-last:hidden' />
      </div>

      {/* Content */}
      <div className='flex-1 pt-0.5'>
        <div className='flex items-baseline justify-between gap-2'>
          <span className='text-[11px] font-medium text-slate-300'>{hop.label}</span>
          {hop.deltaMs != null && (
            <span
              className={cn(
                'font-mono text-[10px] tabular-nums',
                hop.deltaMs > 1000
                  ? 'text-red-400'
                  : hop.deltaMs > 200
                    ? 'text-amber-400'
                    : 'text-emerald-400',
              )}
            >
              +{fmtMs(hop.deltaMs)}
            </span>
          )}
        </div>
        <span
          className='font-mono text-[10px] text-slate-500'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {fmtTs(hop.ts)}
        </span>
        {hop.deltaMs != null && (
          <div className='mt-1 text-[10px] text-slate-600'>{hop.deltaLabel}</div>
        )}
      </div>
    </div>
  );
}

function DurationRow({ label, ms, emphasis }: { label: string; ms: number | null; emphasis?: boolean }) {
  return (
    <div className='flex items-center justify-between py-1'>
      <span className={cn('text-[11px]', emphasis ? 'font-medium text-slate-200' : 'text-slate-500')}>
        {label}
      </span>
      <span
        className={cn(
          'font-mono text-[11px] tabular-nums',
          ms == null
            ? 'text-slate-600'
            : ms > 1000
              ? 'text-red-400'
              : ms > 200
                ? 'text-amber-400'
                : 'text-emerald-400',
          emphasis && 'text-[12px] font-bold',
        )}
      >
        {fmtMs(ms)}
      </span>
    </div>
  );
}

// ── Main drawer ───────────────────────────────────────────────────────────────

interface TraceDrawerProps {
  correlationId: string | null;
  detail: TraceDetail | null | undefined;
  isLoading: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function TraceDrawer({
  correlationId,
  detail,
  isLoading,
  open,
  onOpenChange,
}: TraceDrawerProps) {
  const hops: TraceHops = detail?.hops ?? {};
  const status = detail ? deriveBrokerStatus(detail) : null;

  // Build the ordered hop timeline
  const timeline: HopRow[] = [
    {
      label: 'Signal Received',
      icon: <Zap className='h-3 w-3' />,
      ts: hops.received_at,
      deltaLabel: 'webhook arrived',
      deltaMs: null,
    },
    {
      label: 'Enqueued to Redis',
      icon: <Clock className='h-3 w-3' />,
      ts: hops.enqueued_at,
      deltaLabel: 'time to enqueue',
      deltaMs: diffMs(hops.received_at, hops.enqueued_at),
    },
    {
      label: 'Worker Dequeued',
      icon: <Clock className='h-3 w-3' />,
      ts: hops.dequeued_at,
      deltaLabel: 'queue wait',
      deltaMs: diffMs(hops.enqueued_at, hops.dequeued_at),
    },
    {
      label: 'Validated',
      icon: <ShieldCheck className='h-3 w-3' />,
      ts: hops.validated_at,
      deltaLabel: 'validation time',
      deltaMs: diffMs(hops.dequeued_at, hops.validated_at),
    },
    {
      label: 'Risk Started',
      icon: <ShieldCheck className='h-3 w-3' />,
      ts: hops.risk_started_at,
      deltaLabel: 'pre-risk gap',
      deltaMs: diffMs(hops.validated_at ?? hops.dequeued_at, hops.risk_started_at),
    },
    {
      label: 'Risk Finished',
      icon: <ShieldCheck className='h-3 w-3' />,
      ts: hops.risk_finished_at,
      deltaLabel: 'risk/AI decision time',
      deltaMs: diffMs(hops.risk_started_at, hops.risk_finished_at),
    },
    {
      label: 'Exec Started',
      icon: <Zap className='h-3 w-3' />,
      ts: hops.exec_started_at,
      deltaLabel: 'pre-execution gap',
      deltaMs: diffMs(hops.risk_finished_at, hops.exec_started_at),
    },
    {
      label: 'Exec Submitted',
      icon: <Zap className='h-3 w-3' />,
      ts: hops.exec_submitted_at,
      deltaLabel: 'execution time',
      deltaMs: diffMs(hops.exec_started_at, hops.exec_submitted_at),
    },
    {
      label: 'Broker ACK',
      icon: <Wifi className='h-3 w-3' />,
      ts: hops.broker_ack_at,
      deltaLabel: 'broker connect time',
      deltaMs: diffMs(hops.exec_submitted_at, hops.broker_ack_at),
    },
    {
      label: 'Broker Confirmed',
      icon: <CheckCircle2 className='h-3 w-3' />,
      ts: hops.broker_confirmed_at,
      deltaLabel: 'broker fill time',
      deltaMs: diffMs(hops.broker_ack_at, hops.broker_confirmed_at),
    },
    {
      label: 'Reconciled',
      icon: <CheckCircle2 className='h-3 w-3' />,
      ts: hops.reconciled_at,
      deltaLabel: 'post-fill reconcile',
      deltaMs: diffMs(hops.broker_confirmed_at, hops.reconciled_at),
    },
    ...(hops.error_at
      ? [
          {
            label: 'Error',
            icon: <XCircle className='h-3 w-3' />,
            ts: hops.error_at,
            deltaLabel: 'errored at',
            deltaMs: diffMs(hops.received_at, hops.error_at),
            highlight: true,
          },
        ]
      : []),
  ];

  const queueWait = diffMs(hops.enqueued_at, hops.dequeued_at);
  const riskMs = diffMs(hops.risk_started_at, hops.risk_finished_at);
  const execMs = diffMs(hops.exec_started_at, hops.exec_submitted_at);
  const brokerConnectMs = diffMs(hops.exec_submitted_at, hops.broker_ack_at);
  const brokerFillMs = diffMs(hops.broker_ack_at, hops.broker_confirmed_at);
  const totalMs = detail?.total_ms ?? diffMs(hops.received_at, hops.exec_submitted_at ?? hops.error_at);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side='right'
        className='w-full border-l border-[var(--to-border)] bg-[#0b0e11] p-0 sm:max-w-[520px]'
      >
        <SheetHeader className='border-b border-[var(--to-border)] px-5 py-4'>
          <SheetTitle className='flex items-center gap-2 text-sm font-medium text-slate-100'>
            <Clock className='h-4 w-4 text-[var(--to-accent-blue)]' />
            Pipeline Trace
            {detail && (
              <span className='ml-1 rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-slate-400'>
                {detail.correlation_id.slice(0, 8)}…
              </span>
            )}
          </SheetTitle>
          <SheetDescription className='text-[11px] text-slate-500'>
            {detail
              ? `${detail.symbol ?? '—'} · ${detail.run_mode ?? '—'} · account: ${detail.account_id ?? 'default'}`
              : 'Loading trace…'}
          </SheetDescription>
        </SheetHeader>

        <ScrollArea className='h-[calc(100vh-80px)]'>
          {isLoading && (
            <div className='space-y-3 p-5'>
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className='h-10 w-full bg-slate-800/60' />
              ))}
            </div>
          )}

          {!isLoading && detail && (
            <div className='space-y-5 p-5'>
              {/* Broker status badges */}
              {status && (
                <div>
                  <div className='mb-2 text-[10px] uppercase tracking-widest text-slate-600'>
                    Broker Status
                  </div>
                  <BrokerBadges status={status} errorType={detail.error_type} />
                </div>
              )}

              {/* Error message */}
              {detail.error_type && (
                <div className='rounded border border-red-500/20 bg-red-500/5 px-3 py-2'>
                  <div className='flex items-center gap-1.5 text-[11px] font-medium text-red-400'>
                    <AlertTriangle className='h-3.5 w-3.5' />
                    {detail.error_type}
                  </div>
                  {detail.error_message && (
                    <p className='mt-1 font-mono text-[10px] text-red-300/70'>
                      {detail.error_message}
                    </p>
                  )}
                </div>
              )}

              <Separator className='bg-slate-800' />

              {/* Duration breakdown */}
              <div>
                <div className='mb-2 text-[10px] uppercase tracking-widest text-slate-600'>
                  Duration Breakdown
                </div>
                <div className='rounded border border-slate-800 bg-slate-900/50 px-3 py-2 space-y-0.5'>
                  <DurationRow label='Queue wait' ms={queueWait} />
                  <DurationRow label='Risk / AI' ms={riskMs} />
                  <DurationRow label='Execution' ms={execMs} />
                  <DurationRow label='Broker connect' ms={brokerConnectMs} />
                  <DurationRow label='Broker fill' ms={brokerFillMs} />
                  <Separator className='my-1 bg-slate-800' />
                  <DurationRow label='Total end-to-end' ms={totalMs} emphasis />
                </div>
              </div>

              <Separator className='bg-slate-800' />

              {/* Hop timeline */}
              <div>
                <div className='mb-3 text-[10px] uppercase tracking-widest text-slate-600'>
                  Hop Timeline
                </div>
                <div>
                  {timeline.map((hop, i) => (
                    <HopLine key={i} hop={hop} />
                  ))}
                </div>
              </div>

              {/* Signal ID reference */}
              {detail.signal_id && (
                <>
                  <Separator className='bg-slate-800' />
                  <div className='text-[10px] text-slate-600'>
                    Signal ID:{' '}
                    <span className='font-mono text-slate-400'>{detail.signal_id}</span>
                    {' · '}Correlation:{' '}
                    <span className='font-mono text-[9px] text-slate-500 break-all'>
                      {detail.correlation_id}
                    </span>
                  </div>
                </>
              )}
            </div>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
