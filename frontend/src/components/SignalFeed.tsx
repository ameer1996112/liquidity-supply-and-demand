'use client';

import { useState, useMemo } from 'react';
import { useTradingSignals } from '@/hooks/useTradingSignals';
import {
  TradingSignal,
  TradingMode,
  getSymbol,
  getSide,
  getScore,
  getPnl,
} from '@/types/trading';
import { SignalInspector } from '@/components/SignalInspector';
import { ScoreRing } from '@/components/SignalCard';
import { StatusBadge, SideBadge, PnLDisplay } from '@/components/shared';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { safeFloat, getDisplayReason, formatRelativeTime } from '@/lib/format';
import { ClientDate } from '@/components/ui/ClientDate';
import { AlertCircle, Zap } from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/shared/DataTable';
import {
  TableEmptyState,
  TableSkeleton,
} from '@/components/shared/TableStates';

// =============================================================================
// COLUMN DEFINITIONS — module-level (static, never recreated)
// =============================================================================

const columns: DataTableColumn<TradingSignal>[] = [
  {
    id: 'time',
    header: 'Time',
    width: 'w-[90px]',
    render: (signal) => (
      <ClientDate
        className='font-mono text-[11px] text-[var(--to-text-dim)] tabular-nums whitespace-nowrap'
        render={() => formatRelativeTime(new Date(signal.created_at))}
      />
    ),
  },
  {
    id: 'signal',
    header: 'Signal',
    width: 'w-[140px]',
    render: (signal) => (
      <div className='flex items-center gap-2'>
        <span className='font-mono text-sm font-bold text-[var(--to-text-primary)] tracking-tight'>
          {getSymbol(signal)}
        </span>
        <SideBadge side={getSide(signal)} compact />
      </div>
    ),
  },
  {
    id: 'ai_brain',
    header: 'AI Brain',
    width: 'w-[120px]',
    render: (signal) => (
      <div className='flex items-center gap-2'>
        <ScoreRing score={getScore(signal)} size='sm' />
        <StatusBadge status={signal.status} pnl={getPnl(signal)} compact />
        {signal.status?.toLowerCase() === 'execution_failed' && (
          <div title='Trade approved but not executed in MetaTrader'>
            <AlertCircle className='h-3 w-3 text-orange-400 shrink-0' />
          </div>
        )}
      </div>
    ),
  },
  {
    id: 'reason',
    header: 'Reason',
    render: (signal) => {
      const reason = getDisplayReason(signal);
      return (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className='font-mono text-[11px] text-[var(--to-text-dim)] line-clamp-1 cursor-help'>
                {reason || (
                  <span className='text-[var(--to-text-dim)] italic'>No reason</span>
                )}
              </span>
            </TooltipTrigger>
            {(signal.notes || signal.filter_reason) && (
              <TooltipContent
                side='bottom'
                className='max-w-sm bg-[var(--to-surface)] border-[var(--to-border)] text-[var(--to-text-secondary)]'
              >
                <p className='text-xs'>
                  {signal.notes || signal.filter_reason}
                </p>
              </TooltipContent>
            )}
          </Tooltip>
        </TooltipProvider>
      );
    },
  },
  {
    id: 'rr_ratio',
    header: 'R:R',
    width: 'w-[70px]',
    align: 'right',
    isNumeric: true,
    render: (signal) => (
      <span className='font-mono text-[11px] text-[var(--to-text-dim)] tabular-nums'>
        {signal.rr_ratio ? `1:${safeFloat(signal.rr_ratio, 1)}` : '--'}
      </span>
    ),
  },
  {
    id: 'pnl',
    header: 'PnL',
    width: 'w-[80px]',
    align: 'right',
    isNumeric: true,
    render: (signal) => <PnLDisplay pnl={getPnl(signal)} size='sm' />,
  },
];

// =============================================================================
// ERROR STATE
// =============================================================================

function ErrorState() {
  return (
    <div className='flex items-center gap-2 rounded border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200'>
      <AlertCircle className='h-4 w-4 flex-shrink-0' />
      <div className='flex flex-col'>
        <span className='font-mono text-[11px] font-semibold uppercase tracking-wider'>
          Connection Error
        </span>
        <span className='font-mono text-[10px] text-rose-100/80'>
          Failed to establish data feed. Check connection and retry.
        </span>
      </div>
    </div>
  );
}

// =============================================================================
// MAIN SIGNAL FEED COMPONENT — High-Density Terminal Grid
// =============================================================================

interface SignalFeedProps {
  defaultMode?: TradingMode;
  onSelectSignal?: (signal: TradingSignal) => void;
}

/**
 * SignalFeed — High-density terminal table of all signals.
 *
 * Columns: Time | Signal (Symbol + Side) | AI Brain (Score + Status) | Reason | R:R | PnL
 * Click any row to open the SignalInspector drawer.
 * Shows ALL signals — no filters — including ai_rejected and filtered.
 */
export function SignalFeed({ defaultMode, onSelectSignal }: SignalFeedProps) {
  const [inspectedSignal, setInspectedSignal] = useState<TradingSignal | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);

  const {
    data: allSignals = [],
    isLoading,
    error,
  } = useTradingSignals(defaultMode);

  // Count signals by category — single pass over the array
  const stats = useMemo(() => {
    const counts = { live: 0, veto: 0, filtered: 0, closed: 0 };
    for (const s of allSignals) {
      const st = s.status?.toLowerCase();
      if (st === 'active') counts.live++;
      else if (st === 'ai_rejected') counts.veto++;
      else if (st === 'filtered') counts.filtered++;
      else if (st === 'closed' || st === 'executed') counts.closed++;
    }
    return { ...counts, total: allSignals.length };
  }, [allSignals]);

  const handleRowClick = (signal: TradingSignal) => {
    setInspectedSignal(signal);
    setInspectorOpen(true);
    onSelectSignal?.(signal);
  };

  if (error) return <ErrorState />;

  return (
    <div className='flex flex-col h-full'>
      {/* Header — signal count stats */}
      <div className='flex items-center justify-between px-4 py-3 border-b border-zinc-800 bg-zinc-950/50'>
        <div className='flex items-center gap-2'>
          <Zap className='w-4 h-4 text-[var(--to-text-dim)]' />
          <span className='font-mono text-xs text-[var(--to-text-dim)] uppercase tracking-wider'>
            Signal Feed
          </span>
          {defaultMode && (
            <Badge
              className={cn(
                'font-mono text-[9px] uppercase border-0 px-1.5 py-0.5',
                defaultMode === 'LIVE'
                  ? 'bg-blue-500/20 text-blue-400'
                  : 'bg-amber-500/20 text-amber-400',
              )}
            >
              {defaultMode}
            </Badge>
          )}
        </div>

        <div className='flex items-center gap-4 text-[10px] font-mono'>
          <div className='flex items-center gap-1.5'>
            <span className='w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse' />
            <span className='text-[var(--to-text-dim)]'>LIVE</span>
            <span className='text-blue-400 font-bold'>{stats.live}</span>
          </div>
          <div className='flex items-center gap-1.5'>
            <span className='w-1.5 h-1.5 rounded-full bg-rose-500' />
            <span className='text-[var(--to-text-dim)]'>VETO</span>
            <span className='text-rose-400 font-bold'>{stats.veto}</span>
          </div>
          <div className='flex items-center gap-1.5'>
            <span className='w-1.5 h-1.5 rounded-full bg-zinc-500' />
            <span className='text-[var(--to-text-dim)]'>FILTER</span>
            <span className='text-[var(--to-text-dim)] font-bold'>{stats.filtered}</span>
          </div>
          <div className='flex items-center gap-1.5'>
            <span className='w-1.5 h-1.5 rounded-full bg-emerald-500' />
            <span className='text-[var(--to-text-dim)]'>CLOSED</span>
            <span className='text-[var(--to-long)] font-bold'>{stats.closed}</span>
          </div>
          <div className='pl-2 border-l border-zinc-800'>
            <span className='text-[var(--to-text-dim)]'>TOTAL</span>
            <span className='text-[var(--to-text-secondary)] font-bold ml-1.5'>
              {stats.total}
            </span>
          </div>
        </div>
      </div>

      {/* Table */}
      <ScrollArea className='flex-1'>
        {isLoading ? (
          <TableSkeleton rowCount={8} columnCount={6} className='px-4 py-3' />
        ) : allSignals.length === 0 ? (
          <TableEmptyState
            title='No Signals Found'
            description={
              defaultMode === 'LIVE'
                ? 'Awaiting live trading signals from the bot...'
                : defaultMode === 'PAPER'
                  ? 'No paper trading signals in the queue.'
                  : 'Monitoring for incoming signals...'
            }
          />
        ) : (
          <DataTable<TradingSignal>
            columns={columns}
            data={allSignals}
            compact
            stickyHeader
            getRowId={(signal) => signal.id}
            onRowClick={handleRowClick}
            tableClassName='table-dense'
            getRowClassName={(signal) => {
              const isActive = signal.status?.toLowerCase() === 'active';
              return cn(
                'border-l-2',
                isActive ? 'bg-blue-950/20 border-l-blue-accent' : 'border-l-transparent',
              );
            }}
          />
        )}
      </ScrollArea>

      {/* Footer */}
      <div className='flex items-center justify-between px-4 py-2 border-t border-zinc-800 bg-zinc-950/50'>
        <div className='flex items-center gap-2 text-[10px] font-mono text-[var(--to-text-dim)]'>
          <span className='w-1.5 h-1.5 rounded-full bg-emerald-500/70 animate-pulse' />
          <span>Realtime Connected</span>
        </div>
        <span className='text-[10px] font-mono text-[var(--to-text-dim)]'>
          Showing {allSignals.length} of 200 max
        </span>
      </div>

      <SignalInspector
        signal={inspectedSignal}
        open={inspectorOpen}
        onOpenChange={setInspectorOpen}
      />
    </div>
  );
}

// Re-export alias for backward compatibility
export { SignalFeed as SignalFeedTable };
