'use client';

import { useState, useMemo, memo } from 'react';
import { useTradingSignals } from '@/hooks/useTradingSignals';
import {
  TradingSignal,
  TradingMode,
  getSymbol,
  getSide,
  getScore,
  getPnl,
} from '@/types/trading';
import { ScoreRing } from '@/components/SignalCard';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { PnLDisplay } from '@/components/shared/PnLDisplay';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';
import { formatDistanceToNowStrict } from 'date-fns';
import { TrendingUp, TrendingDown, Activity, Zap } from 'lucide-react';

type FilterTab = 'all' | 'active' | 'wins' | 'losses' | 'rejects';

const FILTER_TABS: { key: FilterTab; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'active', label: 'Active' },
  { key: 'wins', label: 'Wins' },
  { key: 'losses', label: 'Losses' },
  { key: 'rejects', label: 'Rejects' },
];

interface RecentSignalsPanelProps {
  mode?: TradingMode;
  onSelectSignal: (signal: TradingSignal) => void;
}

// ============================================================================
// MEMOIZED ROW COMPONENT
// ============================================================================

interface SignalRowProps {
  signal: TradingSignal;
  onClick: () => void;
}

const SignalRowMemo = memo(function SignalRow({
  signal,
  onClick,
}: SignalRowProps) {
  const symbol = getSymbol(signal);
  const side = getSide(signal);
  const score = getScore(signal);
  const pnl = getPnl(signal);
  const isBuy = side === 'buy';
  const isActive = signal.status?.toLowerCase() === 'active';

  return (
    <TableRow
      onClick={onClick}
      className={cn(
        'cursor-pointer border-b border-[#2a2e39]/50 transition-colors',
        'hover:bg-[#2a2e39]/40',
        isActive && 'border-l-2 border-l-[#2962ff]',
      )}
    >
      <TableCell className='py-2 px-3'>
        <span className='font-mono text-[10px] text-zinc-600 tabular-nums'>
          {formatDistanceToNowStrict(new Date(signal.created_at), {
            addSuffix: true,
          })}
        </span>
      </TableCell>
      <TableCell className='py-2 px-3'>
        <div className='flex items-center gap-1.5'>
          <span className='font-mono text-xs font-bold text-zinc-200'>
            {symbol}
          </span>
          {(() => {
            const runMode = (
              signal.run_mode ||
              signal.mode ||
              ''
            ).toUpperCase();
            if (runMode === 'LIVE')
              return (
                <Badge className='font-mono text-[8px] font-bold px-1 py-0 bg-[#ef5350]/15 text-[#ef5350] border-[#ef5350]/30 border'>
                  L
                </Badge>
              );
            if (runMode === 'PAPER')
              return (
                <Badge className='font-mono text-[8px] font-bold px-1 py-0 bg-[#2962ff]/15 text-[#2962ff] border-[#2962ff]/30 border'>
                  P
                </Badge>
              );
            return null;
          })()}
          <span
            className={cn(
              'text-[9px] font-bold',
              isBuy ? 'text-[#26a69a]' : 'text-[#ef5350]',
            )}
          >
            {isBuy ? (
              <TrendingUp className='w-3 h-3 inline' />
            ) : (
              <TrendingDown className='w-3 h-3 inline' />
            )}
          </span>
        </div>
      </TableCell>
      <TableCell className='py-2 px-3'>
        <StatusBadge status={signal.status} pnl={pnl} compact />
      </TableCell>
      <TableCell className='py-2 px-3'>
        <ScoreRing score={score} size='sm' />
      </TableCell>
      <TableCell className='py-2 px-3 text-right'>
        <span className='font-mono text-[10px] text-zinc-500 tabular-nums'>
          {signal.rr_ratio ? `1:${signal.rr_ratio.toFixed(1)}` : '--'}
        </span>
      </TableCell>
      <TableCell className='py-2 px-3 text-right'>
        <PnLDisplay pnl={pnl} size='sm' />
      </TableCell>
    </TableRow>
  );
});

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export function RecentSignalsPanel({
  mode,
  onSelectSignal,
}: RecentSignalsPanelProps) {
  const [activeFilter, setActiveFilter] = useState<FilterTab>('all');
  const { data: signals = [], isLoading } = useTradingSignals(mode);

  const filtered = useMemo(() => {
    switch (activeFilter) {
      case 'active':
        return signals.filter((s) => {
          const st = s.status?.toLowerCase();
          return st === 'active' || st === 'executed';
        });
      case 'wins':
        return signals.filter((s) => {
          const p = getPnl(s);
          return p != null && p > 0;
        });
      case 'losses':
        return signals.filter((s) => {
          const p = getPnl(s);
          return p != null && p < 0;
        });
      case 'rejects':
        return signals.filter((s) => {
          const st = s.status?.toLowerCase();
          return st === 'ai_rejected' || st === 'filtered';
        });
      default:
        return signals;
    }
  }, [signals, activeFilter]);

  return (
    <div className='tv-card flex flex-col h-full'>
      {/* Header */}
      <div className='flex items-center justify-between px-4 py-3 border-b border-[#2a2e39]'>
        <div className='flex items-center gap-2'>
          <Zap className='w-4 h-4 text-zinc-500' />
          <span className='font-mono text-xs font-semibold text-zinc-300 uppercase tracking-wider'>
            Recent Signals
          </span>
        </div>
        <span className='font-mono text-[10px] text-zinc-600'>
          {filtered.length} of {signals.length}
        </span>
      </div>

      {/* Filter Tabs */}
      <div className='flex flex-wrap items-center gap-1 px-4 py-2 border-b border-[#2a2e39]'>
        {FILTER_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveFilter(tab.key)}
            className={cn(
              'font-mono text-[10px] px-3 py-1 rounded transition-colors whitespace-nowrap',
              activeFilter === tab.key
                ? 'bg-[#2a2e39] text-zinc-200'
                : 'text-zinc-600 hover:text-zinc-400 hover:bg-[#2a2e39]/50',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <ScrollArea className='flex-1'>
        {isLoading ? (
          <div className='space-y-1 p-2'>
            {[...Array(6)].map((_, i) => (
              <Skeleton key={i} className='h-10 w-full bg-[#1e222d]' />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className='flex flex-col items-center justify-center py-16'>
            <Activity className='w-8 h-8 text-zinc-700 mb-3' />
            <span className='text-xs text-zinc-600 font-mono'>
              No signals match filter
            </span>
          </div>
        ) : (
          <Table className='table-dense'>
            <TableHeader>
              <TableRow className='border-b border-[#2a2e39] hover:bg-transparent'>
                <TableHead className='font-mono text-[9px] text-zinc-600 uppercase tracking-wider py-1.5 px-3 w-[80px]'>
                  Time
                </TableHead>
                <TableHead className='font-mono text-[9px] text-zinc-600 uppercase tracking-wider py-1.5 px-3 w-[120px]'>
                  Signal
                </TableHead>
                <TableHead className='font-mono text-[9px] text-zinc-600 uppercase tracking-wider py-1.5 px-3 w-[100px]'>
                  Status
                </TableHead>
                <TableHead className='font-mono text-[9px] text-zinc-600 uppercase tracking-wider py-1.5 px-3 w-[50px]'>
                  AI
                </TableHead>
                <TableHead className='font-mono text-[9px] text-zinc-600 uppercase tracking-wider py-1.5 px-3 w-[55px] text-right'>
                  R:R
                </TableHead>
                <TableHead className='font-mono text-[9px] text-zinc-600 uppercase tracking-wider py-1.5 px-3 w-[70px] text-right'>
                  PnL
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((signal) => (
                <SignalRowMemo
                  key={signal.id}
                  signal={signal}
                  onClick={() => onSelectSignal(signal)}
                />
              ))}
            </TableBody>
          </Table>
        )}
      </ScrollArea>
    </div>
  );
}
