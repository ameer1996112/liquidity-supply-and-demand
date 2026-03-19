'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge } from '@/components/ui/badge';
import { TraceDrawer, deriveBrokerStatus } from './TraceDrawer';
import { useTraceDetail } from '@/hooks/usePipelineTraces';
import type { TraceSummary, TraceDetail } from '@/types/execution';
import {
  CheckCircle2,
  XCircle,
  Clock,
  Wifi,
  WifiOff,
  ChevronRight,
  Radio,
} from 'lucide-react';

// ── Helpers ───────────────────────────────────────────────────────────────────

function msColor(ms: number | null | undefined): string {
  if (ms == null) return 'text-slate-600';
  if (ms > 2000) return 'text-red-400';
  if (ms > 500) return 'text-amber-400';
  return 'text-emerald-400';
}

function fmtMs(ms: number | null | undefined): string {
  if (ms == null) return '—';
  if (ms < 1) return '<1 ms';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

function fmtTime(s: string | null | undefined): string {
  if (!s) return '—';
  try {
    const d = new Date(s);
    const now = Date.now();
    const diff = now - d.getTime();
    if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return s;
  }
}

// ── Row status badge ──────────────────────────────────────────────────────────

function TraceStatusIcon({ trace }: { trace: TraceSummary }) {
  if (trace.error_type) {
    return (
      <span title={trace.error_type}>
        <XCircle className='h-3.5 w-3.5 text-red-400' />
      </span>
    );
  }
  // If submitted (has total_ms) treat as completed
  if (trace.total_ms != null) {
    return <CheckCircle2 className='h-3.5 w-3.5 text-emerald-400' />;
  }
  return <Clock className='h-3.5 w-3.5 text-slate-500' />;
}

function SideBadge({ side }: { side: string | null | undefined }) {
  if (!side) return <span className='text-slate-600'>—</span>;
  const isBuy = side.toLowerCase() === 'buy';
  return (
    <span
      className={cn(
        'inline-block rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase',
        isBuy ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400',
      )}
    >
      {side}
    </span>
  );
}

function RunModeBadge({ mode }: { mode: string | null | undefined }) {
  if (!mode) return null;
  const isLive = mode.toUpperCase() === 'LIVE';
  return (
    <span
      className={cn(
        'inline-block rounded px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider',
        isLive
          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
          : 'bg-slate-700/40 text-slate-500 border border-slate-700',
      )}
    >
      {mode}
    </span>
  );
}

// ── Drawer wrapper ─────────────────────────────────────────────────────────────

function TraceDetailDrawer({
  correlationId,
  open,
  onOpenChange,
}: {
  correlationId: string | null;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const { data: detail, isLoading } = useTraceDetail(correlationId);
  return (
    <TraceDrawer
      correlationId={correlationId}
      detail={detail}
      isLoading={isLoading}
      open={open}
      onOpenChange={onOpenChange}
    />
  );
}

// ── Table ─────────────────────────────────────────────────────────────────────

interface TraceTableProps {
  traces: TraceSummary[] | undefined;
  isLoading: boolean;
  error?: Error | null;
  initialSignalId?: number | null;
}

export function TraceTable({
  traces,
  isLoading,
  error,
  initialSignalId,
}: TraceTableProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  function handleRowClick(correlationId: string) {
    setSelectedId(correlationId);
    setDrawerOpen(true);
  }

  useEffect(() => {
    if (!initialSignalId || !Array.isArray(traces) || traces.length === 0) return;
    const match = traces.find((t) => t.signal_id === initialSignalId);
    if (match) {
      setSelectedId(match.correlation_id);
      setDrawerOpen(true);
    }
  }, [initialSignalId, traces]);

  const safeTraces = Array.isArray(traces) ? traces : [];

  return (
    <>
      <div className='relative overflow-hidden rounded border border-[var(--to-border)]'>
        {/* Header */}
        <div
          className='grid gap-2 border-b border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-2'
          style={{ gridTemplateColumns: '28px 80px 68px 1fr 100px 84px 80px 20px' }}
        >
          {(['', 'Symbol', 'Side', 'Correlation ID', 'Account', 'Total', 'Time', ''] as const).map(
            (h, i) => (
              <span
                key={i}
                className='text-[10px] font-medium uppercase tracking-widest text-slate-600'
              >
                {h}
              </span>
            ),
          )}
        </div>

        {/* Rows */}
        {isLoading && (
          <div className='space-y-px'>
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className='flex items-center gap-2 px-3 py-2.5'>
                <Skeleton className='h-3.5 w-3.5 rounded-full bg-slate-800/60' />
                <Skeleton className='h-3 w-16 bg-slate-800/60' />
                <Skeleton className='h-3 w-10 bg-slate-800/60' />
                <Skeleton className='h-3 w-32 bg-slate-800/60' />
                <Skeleton className='h-3 w-20 bg-slate-800/60' />
                <Skeleton className='h-3 w-14 bg-slate-800/60' />
                <Skeleton className='h-3 w-12 bg-slate-800/60' />
              </div>
            ))}
          </div>
        )}

        {error && !isLoading && (
          <div className='flex items-center gap-2 px-4 py-8 text-sm text-red-400'>
            <XCircle className='h-4 w-4' />
            Failed to load traces: {error.message}
          </div>
        )}

        {!isLoading && !error && safeTraces.length === 0 && (
          <div className='flex flex-col items-center justify-center gap-2 py-16 text-slate-500'>
            <Radio className='h-8 w-8 opacity-30' />
            <span className='text-sm'>No pipeline traces yet</span>
            <span className='text-[11px] text-slate-600'>
              Traces appear after signals are processed
            </span>
          </div>
        )}

        {!isLoading && !error && safeTraces.length > 0 && (
          <div className='divide-y divide-[var(--to-border)]'>
            {safeTraces.map((trace) => (
              <button
                key={trace.correlation_id}
                onClick={() => handleRowClick(trace.correlation_id)}
                className={cn(
                  'group grid w-full items-center gap-2 px-3 py-2.5 text-left',
                  'transition-colors hover:bg-[var(--to-surface-raised)]',
                  selectedId === trace.correlation_id && drawerOpen && 'bg-[var(--to-surface-raised)]',
                )}
                style={{ gridTemplateColumns: '28px 80px 68px 1fr 100px 84px 80px 20px' }}
              >
                {/* Status icon */}
                <span className='flex items-center justify-center'>
                  <TraceStatusIcon trace={trace} />
                </span>

                {/* Symbol */}
                <span className='font-mono text-[12px] font-medium text-slate-200'>
                  {trace.symbol ?? '—'}
                </span>

                {/* Side — not in TraceSummary, show run_mode badge instead */}
                <RunModeBadge mode={trace.run_mode} />

                {/* Correlation ID */}
                <span
                  className='truncate font-mono text-[10px] text-slate-500'
                  title={trace.correlation_id}
                >
                  {trace.correlation_id.slice(0, 12)}…
                </span>

                {/* Account */}
                <span className='font-mono text-[10px] text-slate-500 truncate'>
                  {trace.account_id ?? 'default'}
                </span>

                {/* Total ms */}
                <span className={cn('font-mono text-[11px] tabular-nums', msColor(trace.total_ms))}>
                  {fmtMs(trace.total_ms)}
                </span>

                {/* Time ago */}
                <span className='text-[10px] text-slate-600 tabular-nums'>
                  {fmtTime(trace.received_at ?? trace.created_at)}
                </span>

                {/* Chevron */}
                <ChevronRight className='h-3 w-3 text-slate-700 transition-colors group-hover:text-slate-500' />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Lazy-loaded drawer */}
      <TraceDetailDrawer
        correlationId={selectedId}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
      />
    </>
  );
}
