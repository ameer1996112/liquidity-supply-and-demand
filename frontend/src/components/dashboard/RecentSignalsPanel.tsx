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
import { TrendingUp, TrendingDown, Zap } from 'lucide-react';

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
        'cursor-pointer border-b border-[rgba(76,94,128,0.35)] transition-colors',
        'hover:bg-[rgba(41,56,86,0.38)]',
        isActive && 'border-l-2 border-l-[#8ca5ff]'
      )}
    >
      <TableCell className='px-2.5 py-1'>
        <span className='font-mono text-[10px] text-zinc-600 tabular-nums'>
          {formatDistanceToNowStrict(new Date(signal.created_at), {
            addSuffix: true,
          })}
        </span>
      </TableCell>
      <TableCell className='px-2.5 py-1'>
        <div className='flex items-center gap-1.5'>
          {isActive && (
            <span className='status-dot status-dot-active pulse-active' />
          )}
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
              isBuy ? 'text-[#26a69a]' : 'text-[#ef5350]'
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
      <TableCell className='px-2.5 py-1'>
        <StatusBadge status={signal.status} pnl={pnl} compact />
      </TableCell>
      <TableCell className='px-2.5 py-1'>
        <ScoreRing score={score} size='sm' />
      </TableCell>
      <TableCell className='px-2.5 py-1 text-right'>
        <span className='font-mono text-[10px] text-zinc-500 tabular-nums'>
          {signal.rr_ratio ? `1:${signal.rr_ratio.toFixed(1)}` : '--'}
        </span>
      </TableCell>
      <TableCell className='px-2.5 py-1 text-right'>
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
    <div className='tv-card flex h-full min-w-0 flex-col overflow-hidden'>
      {/* Header */}
      <div className='tv-divider flex shrink-0 items-center justify-between border-b px-3 py-2'>
        <div className='flex items-center gap-2'>
          <Zap className='h-3.5 w-3.5 text-[#8ca5ff]' />
          <span className='text-[11px] font-semibold uppercase tracking-[0.12em] text-[#c7d4ed]'>
            Recent Signals
          </span>
        </div>
        <span className='font-mono text-[10px] text-[#8fa1c3]'>
          {filtered.length} of {signals.length}
        </span>
      </div>

      {/* Filter Tabs */}
      <div className='tv-divider flex shrink-0 flex-wrap items-center gap-1 border-b px-3 py-1.5'>
        {FILTER_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveFilter(tab.key)}
            className={cn(
              'whitespace-nowrap rounded px-2.5 py-0.5 font-mono text-[10px] transition-colors',
              activeFilter === tab.key
                ? 'bg-[#6e8dff] text-white'
                : 'bg-[rgba(22,33,56,0.6)] text-[#93a4c6] hover:bg-[rgba(35,50,79,0.8)] hover:text-[#dce7fb]'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Table - ScrollArea now properly constrained */}
      <div className='flex-1 min-h-0 overflow-hidden'>
        <ScrollArea className='h-full'>
          {isLoading ? (
            <div className='space-y-1 p-2'>
              {[...Array(6)].map((_, i) => (
                <Skeleton
                  key={i}
                  className='h-6 w-full bg-[rgba(31,45,74,0.55)]'
                />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className='flex flex-col items-center justify-center py-10 text-center'>
              <div className='radar-scan mb-3' />
              <span className='font-mono text-[11px] text-[#a1b1cf]'>
                Scanning market
              </span>
              <span className='mt-1 text-[10px] text-[#7888ab]'>
                No signals match current filter
              </span>
            </div>
          ) : (
            <Table className='table-dense table-fixed min-w-[980px]'>
              <TableHeader>
                <TableRow className='tv-divider border-b hover:bg-transparent'>
                  <TableHead className='w-[16%] px-2.5 py-1 font-mono text-[9px] uppercase tracking-wider text-[#7f90b3]'>
                    Time
                  </TableHead>
                  <TableHead className='w-[18%] px-2.5 py-1 font-mono text-[9px] uppercase tracking-wider text-[#7f90b3]'>
                    Signal
                  </TableHead>
                  <TableHead className='w-[18%] px-2.5 py-1 font-mono text-[9px] uppercase tracking-wider text-[#7f90b3]'>
                    Status
                  </TableHead>
                  <TableHead className='w-[14%] px-2.5 py-1 font-mono text-[9px] uppercase tracking-wider text-[#7f90b3]'>
                    AI
                  </TableHead>
                  <TableHead className='w-[16%] px-2.5 py-1 text-right font-mono text-[9px] uppercase tracking-wider text-[#7f90b3]'>
                    R:R
                  </TableHead>
                  <TableHead className='w-[18%] px-2.5 py-1 text-right font-mono text-[9px] uppercase tracking-wider text-[#7f90b3]'>
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
    </div>
  );
}
