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
import { Activity, AlertCircle, Zap } from 'lucide-react';
import { DataTable, type DataTableColumn } from '@/components/shared/DataTable';
import {
  TableEmptyState,
  TableSkeleton,
} from '@/components/shared/TableStates';

const columns: DataTableColumn<TradingSignal>[] = [
  {
    id: 'time',
    header: 'Time',
    width: 'w-[90px]',
    render: (signal) => (
      <ClientDate
        className='font-mono text-[11px] text-zinc-500 tabular-nums whitespace-nowrap'
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
        <span className='font-mono text-sm font-bold text-zinc-100 tracking-tight'>
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
              <span className='font-mono text-[11px] text-zinc-500 line-clamp-1 cursor-help'>
                {reason || (
                  <span className='text-zinc-700 italic'>No reason</span>
                )}
              </span>
            </TooltipTrigger>
            {(signal.notes || signal.filter_reason) && (
              <TooltipContent
                side='bottom'
                className='max-w-sm bg-zinc-900 border-zinc-700 text-zinc-300'
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
      <span className='font-mono text-[11px] text-zinc-400 tabular-nums'>
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
// SIGNAL ROW COMPONENT - High Density Table Row
// =============================================================================

interface SignalRowProps {
  signal: TradingSignal;
  onClick: () => void;
}

function SignalRow({ signal, onClick }: SignalRowProps) {
  const symbol = getSymbol(signal);
  const side = getSide(signal);
  const score = getScore(signal);
  const pnl = getPnl(signal);
  const reason = getDisplayReason(signal);
  const normalized = signal.status?.toLowerCase();
  const isActive = normalized === 'active';

  return (
    <tr
      onClick={onClick}
      className={cn(
        'cursor-pointer transition-all duration-150 border-b border-panel-border-subtle',
        'hover:bg-surface-raised hover:shadow-[inset_0_0_0_1px_rgba(59,130,246,0.2)]',
        isActive && 'bg-blue-950/20 border-l-2 border-l-blue-accent',
        !isActive && 'border-l-2 border-l-transparent',
      )}
    >
      {/* Column 1: Time - Relative "2m ago" */}
      <td className='py-2 px-3 w-[90px]'>
        <ClientDate
          className='font-mono text-[11px] text-zinc-500 tabular-nums whitespace-nowrap'
          render={() => formatRelativeTime(new Date(signal.created_at))}
        />
      </td>

      {/* Column 2: Signal - Symbol + Side Badge */}
      <td className='py-2 px-3 w-[140px]'>
        <div className='flex items-center gap-2'>
          <span className='font-mono text-sm font-bold text-zinc-100 tracking-tight'>
            {symbol}
          </span>
          <SideBadge side={side} compact />
        </div>
      </td>

      {/* Column 3: AI Brain - Score Ring + Status Badge */}
      <td className='py-2 px-3 w-[120px]'>
        <div className='flex items-center gap-2'>
          <ScoreRing score={score} size='sm' />
          <StatusBadge status={signal.status} pnl={pnl} compact />
        </div>
      </td>

      {/* Column 4: Reason - Truncated notes (max 40 chars) */}
      <td className='py-2 px-3'>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className='font-mono text-[11px] text-zinc-500 line-clamp-1 cursor-help'>
                {reason || (
                  <span className='text-zinc-700 italic'>No reason</span>
                )}
              </span>
            </TooltipTrigger>
            {(signal.notes || signal.filter_reason) && (
              <TooltipContent
                side='bottom'
                className='max-w-sm bg-zinc-900 border-zinc-700 text-zinc-300'
              >
                <p className='text-xs'>
                  {signal.notes || signal.filter_reason}
                </p>
              </TooltipContent>
            )}
          </Tooltip>
        </TooltipProvider>
      </td>

      {/* Column 5: R:R - Risk/Reward Ratio */}
      <td className='py-2 px-3 w-[70px] text-right'>
        <span className='font-mono text-[11px] text-zinc-400 tabular-nums'>
          {signal.rr_ratio ? `1:${safeFloat(signal.rr_ratio, 1)}` : '--'}
        </span>
      </td>

      {/* Column 6: PnL - Color-coded profit (Green +, Red -) */}
      <td className='py-2 px-3 w-[80px] text-right'>
        <PnLDisplay pnl={pnl} size='sm' />
      </td>
    </tr>
  );
}

// =============================================================================
// MAIN SIGNAL FEED COMPONENT - High Density Terminal Grid
// =============================================================================

interface SignalFeedProps {
  defaultMode?: TradingMode;
  onSelectSignal?: (signal: TradingSignal) => void;
}

/**
 * SignalFeed - High-Density Terminal Grid Component
 *
 * Columns: Time | Signal (Symbol + Side) | AI Brain (Score + Status) | Reason | R:R | PnL
 * Click row to expand detailed Sheet with full JSON.
 * Zero filters - shows ALL signals including ai_rejected and filtered.
 */
export function SignalFeed({ defaultMode, onSelectSignal }: SignalFeedProps) {
  const [inspectedSignal, setInspectedSignal] = useState<TradingSignal | null>(
    null,
  );
  const [inspectorOpen, setInspectorOpen] = useState(false);

  // Fetch ALL signals
  const {
    data: allSignals = [],
    isLoading,
    error,
  } = useTradingSignals(defaultMode);

  // Count signals by status for header stats — single pass
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

  // Handle row click
  const handleRowClick = (signal: TradingSignal) => {
    setInspectedSignal(signal);
    setInspectorOpen(true);
    onSelectSignal?.(signal);
  };

  if (error) {
    return <ErrorState />;
  }

  return (
    <div className='flex flex-col h-full'>
      {/* HEADER - Signal Count Stats */}
      <div className='flex items-center justify-between px-4 py-3 border-b border-zinc-800 bg-zinc-950/50'>
        <div className='flex items-center gap-2'>
          <Zap className='w-4 h-4 text-zinc-500' />
          <span className='font-mono text-xs text-zinc-400 uppercase tracking-wider'>
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

        {/* Quick Stats */}
        <div className='flex items-center gap-4 text-[10px] font-mono'>
          <div className='flex items-center gap-1.5'>
            <span className='w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse' />
            <span className='text-zinc-500'>LIVE</span>
            <span className='text-blue-400 font-bold'>{stats.live}</span>
          </div>
          <div className='flex items-center gap-1.5'>
            <span className='w-1.5 h-1.5 rounded-full bg-rose-500' />
            <span className='text-zinc-500'>VETO</span>
            <span className='text-rose-400 font-bold'>{stats.veto}</span>
          </div>
          <div className='flex items-center gap-1.5'>
            <span className='w-1.5 h-1.5 rounded-full bg-zinc-500' />
            <span className='text-zinc-500'>FILTER</span>
            <span className='text-zinc-400 font-bold'>{stats.filtered}</span>
          </div>
          <div className='flex items-center gap-1.5'>
            <span className='w-1.5 h-1.5 rounded-full bg-emerald-500' />
            <span className='text-zinc-500'>CLOSED</span>
            <span className='text-emerald-400 font-bold'>{stats.closed}</span>
          </div>
          <div className='pl-2 border-l border-zinc-800'>
            <span className='text-zinc-500'>TOTAL</span>
            <span className='text-zinc-300 font-bold ml-1.5'>
              {stats.total}
            </span>
          </div>
        </div>
      </div>

      {/* TABLE GRID */}
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
              const normalized = signal.status?.toLowerCase();
              const isActive = normalized === 'active';
              return cn(
                'border-l-2',
                isActive ? 'bg-blue-950/20 border-l-blue-accent' : 'border-l-transparent',
              );
            }}
          />
        )}
      </ScrollArea>

      {/* FOOTER - Connection Status */}
      <div className='flex items-center justify-between px-4 py-2 border-t border-zinc-800 bg-zinc-950/50'>
        <div className='flex items-center gap-2 text-[10px] font-mono text-zinc-600'>
          <span className='w-1.5 h-1.5 rounded-full bg-emerald-500/70 animate-pulse' />
          <span>Realtime Connected</span>
        </div>
        <span className='text-[10px] font-mono text-zinc-700'>
          Showing {allSignals.length} of 50 max
        </span>
      </div>

      {/* Signal Inspector Sheet */}
      <SignalInspector
        signal={inspectedSignal}
        open={inspectorOpen}
        onOpenChange={setInspectorOpen}
      />
    </div>
  );
}

// Re-export the table view as an alternative
export { SignalFeed as SignalFeedTable };
