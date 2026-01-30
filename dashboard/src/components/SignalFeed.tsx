'use client';

import { useTradingSignals } from '@/hooks/useTradingSignals';
import { TradingSignal, TradingMode } from '@/types/trading';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import {
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
  TrendingUp,
  TrendingDown,
  ShieldX,
  Filter,
  Radio,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';

interface SignalFeedProps {
  mode?: TradingMode;
  onSelectSignal?: (signal: TradingSignal) => void;
}

// Status badge component with beautiful styling
function getStatusBadge(status: TradingSignal['status']) {
  const normalizedStatus = status?.toLowerCase();

  switch (normalizedStatus) {
    case 'active':
      return (
        <Badge
          className={cn(
            'bg-blue-500/20 text-blue-400 border-blue-500/30',
            'hover:bg-blue-500/30 font-semibold text-[10px] uppercase tracking-wider',
            'animate-pulse'
          )}
        >
          <Radio className="w-3 h-3 mr-1" />
          LIVE
        </Badge>
      );
    case 'executed':
      return (
        <Badge
          className={cn(
            'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
            'hover:bg-emerald-500/30 font-semibold text-[10px] uppercase tracking-wider'
          )}
        >
          <CheckCircle2 className="w-3 h-3 mr-1" />
          FILLED
        </Badge>
      );
    case 'ai_rejected':
      return (
        <Badge
          className={cn(
            'bg-red-500/20 text-red-400 border-red-500/30',
            'hover:bg-red-500/30 font-semibold text-[10px] uppercase tracking-wider'
          )}
        >
          <ShieldX className="w-3 h-3 mr-1" />
          AI VETO
        </Badge>
      );
    case 'filtered':
      return (
        <Badge
          className={cn(
            'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',
            'hover:bg-zinc-500/30 font-semibold text-[10px] uppercase tracking-wider'
          )}
        >
          <Filter className="w-3 h-3 mr-1" />
          FILTERED
        </Badge>
      );
    case 'failed':
      return (
        <Badge
          className={cn(
            'bg-red-500/20 text-red-400 border-red-500/30',
            'hover:bg-red-500/30 font-semibold text-[10px] uppercase tracking-wider'
          )}
        >
          <XCircle className="w-3 h-3 mr-1" />
          FAILED
        </Badge>
      );
    case 'pending':
      return (
        <Badge
          className={cn(
            'bg-amber-500/20 text-amber-400 border-amber-500/30',
            'hover:bg-amber-500/30 font-semibold text-[10px] uppercase tracking-wider'
          )}
        >
          <Clock className="w-3 h-3 mr-1" />
          PENDING
        </Badge>
      );
    default:
      return (
        <Badge
          className={cn(
            'bg-zinc-500/20 text-zinc-500 border-zinc-500/30',
            'hover:bg-zinc-500/30 font-semibold text-[10px] uppercase tracking-wider'
          )}
        >
          <AlertCircle className="w-3 h-3 mr-1" />
          {status || 'UNKNOWN'}
        </Badge>
      );
  }
}

// Confidence bar component
function ConfidenceBar({ value }: { value: number }) {
  const getColor = (v: number) => {
    if (v >= 80) return 'bg-emerald-500';
    if (v >= 60) return 'bg-amber-500';
    return 'bg-red-500';
  };

  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all', getColor(value))}
          style={{ width: `${value}%` }}
        />
      </div>
      <span className="font-mono text-xs text-zinc-400">{value}</span>
    </div>
  );
}

// Side badge component
function SideBadge({ action }: { action: TradingSignal['action'] }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        'font-mono text-[10px] font-bold px-2 py-0.5 border-0',
        action === 'BUY'
          ? 'bg-emerald-500/20 text-emerald-400'
          : 'bg-red-500/20 text-red-400'
      )}
    >
      {action}
    </Badge>
  );
}

// PnL display component
function PnLDisplay({ pnl, percentage }: { pnl?: number; percentage?: number }) {
  if (pnl === undefined) {
    return <span className="text-zinc-500 text-xs">—</span>;
  }

  const isPositive = pnl >= 0;

  return (
    <div className="flex flex-col items-end">
      <span
        className={cn(
          'font-mono text-xs font-semibold',
          isPositive ? 'text-emerald-400' : 'text-red-400'
        )}
      >
        {isPositive ? '+' : ''}${pnl.toFixed(2)}
      </span>
      {percentage !== undefined && (
        <span
          className={cn(
            'font-mono text-[10px]',
            isPositive ? 'text-emerald-400/70' : 'text-red-400/70'
          )}
        >
          {isPositive ? '+' : ''}{percentage.toFixed(2)}%
        </span>
      )}
    </div>
  );
}

// Reason display component for rejected/filtered signals
function ReasonDisplay({ status, filterReason }: { status: TradingSignal['status']; filterReason: string | null }) {
  const normalizedStatus = status?.toLowerCase();
  const showReason = normalizedStatus === 'ai_rejected' || normalizedStatus === 'filtered';

  if (!showReason || !filterReason) {
    return <span className="text-zinc-600 text-xs">—</span>;
  }

  return (
    <span className="text-xs text-zinc-400 max-w-[200px] truncate block" title={filterReason}>
      {filterReason}
    </span>
  );
}

// Table row skeleton
function SignalRowSkeleton() {
  return (
    <TableRow className="border-zinc-800/50">
      <TableCell>
        <Skeleton className="h-4 w-16 bg-zinc-800" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-4 w-14 bg-zinc-800" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-4 w-10 bg-zinc-800" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-4 w-20 bg-zinc-800" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-5 w-16 bg-zinc-800" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-4 w-24 bg-zinc-800" />
      </TableCell>
      <TableCell>
        <Skeleton className="h-4 w-12 bg-zinc-800" />
      </TableCell>
    </TableRow>
  );
}

// Empty state component
function EmptyState({ mode }: { mode?: TradingMode }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-12 h-12 rounded-full bg-zinc-800/50 flex items-center justify-center mb-4">
        <Clock className="w-6 h-6 text-zinc-500" />
      </div>
      <h3 className="font-mono text-sm text-zinc-300 mb-1">No Signals</h3>
      <p className="text-xs text-zinc-500 max-w-xs">
        {mode
          ? `No ${mode.toLowerCase()} signals have been generated yet.`
          : 'Waiting for trading signals from the bot...'}
      </p>
    </div>
  );
}

export function SignalFeed({ mode, onSelectSignal }: SignalFeedProps) {
  const { data: signals = [], isLoading, error } = useTradingSignals();

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 text-red-400">
        <AlertCircle className="w-5 h-5 mr-2" />
        <span className="font-mono text-sm">Error loading signals</span>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="rounded-lg border border-zinc-800/50 bg-zinc-950/50">
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-800/50 hover:bg-transparent">
              <TableHead className="text-zinc-500 text-xs font-mono uppercase">
                Time
              </TableHead>
              <TableHead className="text-zinc-500 text-xs font-mono uppercase">
                Asset
              </TableHead>
              <TableHead className="text-zinc-500 text-xs font-mono uppercase">
                Side
              </TableHead>
              <TableHead className="text-zinc-500 text-xs font-mono uppercase">
                Confidence
              </TableHead>
              <TableHead className="text-zinc-500 text-xs font-mono uppercase">
                Status
              </TableHead>
              <TableHead className="text-zinc-500 text-xs font-mono uppercase">
                Reason
              </TableHead>
              <TableHead className="text-zinc-500 text-xs font-mono uppercase text-right">
                PnL
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {[...Array(8)].map((_, i) => (
              <SignalRowSkeleton key={i} />
            ))}
          </TableBody>
        </Table>
      </div>
    );
  }

  if (signals.length === 0) {
    return <EmptyState mode={mode} />;
  }

  return (
    <div className="rounded-lg border border-zinc-800/50 bg-zinc-950/50 overflow-hidden">
      <ScrollArea className="h-[calc(100vh-220px)]">
        <Table>
          <TableHeader className="sticky top-0 bg-zinc-950/95 backdrop-blur-sm z-10">
            <TableRow className="border-zinc-800/50 hover:bg-transparent">
              <TableHead className="text-zinc-500 text-xs font-mono uppercase w-24">
                Time
              </TableHead>
              <TableHead className="text-zinc-500 text-xs font-mono uppercase w-20">
                Asset
              </TableHead>
              <TableHead className="text-zinc-500 text-xs font-mono uppercase w-16">
                Side
              </TableHead>
              <TableHead className="text-zinc-500 text-xs font-mono uppercase w-28">
                Confidence
              </TableHead>
              <TableHead className="text-zinc-500 text-xs font-mono uppercase w-24">
                Status
              </TableHead>
              <TableHead className="text-zinc-500 text-xs font-mono uppercase w-48">
                Reason
              </TableHead>
              <TableHead className="text-zinc-500 text-xs font-mono uppercase text-right w-20">
                PnL
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {signals.map((signal) => (
              <TableRow
                key={signal.id}
                onClick={() => onSelectSignal?.(signal)}
                className={cn(
                  'border-zinc-800/30 cursor-pointer transition-colors',
                  'hover:bg-zinc-800/20',
                  signal.status?.toLowerCase() === 'active' && 'bg-blue-500/5'
                )}
              >
                <TableCell className="py-2.5">
                  <span className="font-mono text-xs text-zinc-400">
                    {formatDistanceToNow(new Date(signal.created_at), {
                      addSuffix: true,
                    })}
                  </span>
                </TableCell>
                <TableCell className="py-2.5">
                  <span className="font-mono text-sm font-semibold text-zinc-100">
                    {signal.ticker}
                  </span>
                </TableCell>
                <TableCell className="py-2.5">
                  <SideBadge action={signal.action} />
                </TableCell>
                <TableCell className="py-2.5">
                  <ConfidenceBar value={signal.ai_confidence} />
                </TableCell>
                <TableCell className="py-2.5">
                  {getStatusBadge(signal.status)}
                </TableCell>
                <TableCell className="py-2.5">
                  <ReasonDisplay status={signal.status} filterReason={signal.filter_reason} />
                </TableCell>
                <TableCell className="py-2.5 text-right">
                  <PnLDisplay
                    pnl={signal.pnl}
                    percentage={signal.pnl_percentage}
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ScrollArea>
    </div>
  );
}
