'use client';

import { useState, useMemo, memo } from 'react';
import { useTradingSignals } from '@/hooks/useTradingSignals';
import {
  TradingSignal,
  TradingMode,
  getSymbol,
  getSide,
  getPnl,
} from '@/types/trading';
import { isSignalOpen } from '@/domain/metrics/tradingMetrics';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { PnLDisplay } from '@/components/shared/PnLDisplay';
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

// ── Derive trigger type from signal fields ────────────────────────────────────
function getTrigger(
  signal: TradingSignal
): 'FLIP' | 'BoC' | 'DIR_CLOSE' | null {
  const entryModel = (signal.entry_model ?? '').toLowerCase();
  const exitType = (signal.exit_type ?? '').toLowerCase();

  if (
    exitType.includes('dir') ||
    exitType.includes('close') ||
    entryModel.includes('dir')
  ) {
    return 'DIR_CLOSE';
  }
  if (entryModel.includes('boc') || entryModel.includes('break')) {
    return 'BoC';
  }
  if (entryModel.includes('flip') || entryModel.includes('zone')) {
    return 'FLIP';
  }
  // Fallback: infer from zone_type
  if (signal.zone_type) return 'FLIP';
  return null;
}

function TriggerBadge({ signal }: { signal: TradingSignal }) {
  const trigger = getTrigger(signal);
  if (!trigger)
    return <span className='text-slate-600 font-mono text-[9px]'>—</span>;

  if (trigger === 'FLIP') return <span className='trigger-flip'>FLIP</span>;
  if (trigger === 'BoC') return <span className='trigger-boc'>BoC</span>;
  if (trigger === 'DIR_CLOSE')
    return <span className='trigger-dir-close'>DIR CLOSE</span>;
  return null;
}

// ── Memoized row ─────────────────────────────────────────────────────────────

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
  const pnl = getPnl(signal);
  const isBuy = side === 'buy';
  const isActive = signal.status?.toLowerCase() === 'active';

  return (
    <TableRow
      onClick={onClick}
      className={cn(
        'cursor-pointer border-b border-slate-800/60 transition-colors data-row',
        isActive && 'border-l-2 border-l-indigo-500'
      )}
    >
      {/* Time */}
      <TableCell className='px-2 py-1.5'>
        <span
          className='text-[10px] text-slate-600 tabular-nums'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {formatDistanceToNowStrict(new Date(signal.created_at), {
            addSuffix: true,
          })}
        </span>
      </TableCell>

      {/* Symbol + side */}
      <TableCell className='px-2 py-1.5'>
        <div className='flex items-center gap-1.5'>
          {isActive && (
            <span className='status-dot status-dot-active pulse-active' />
          )}
          <span
            className='text-xs font-bold text-slate-200'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {symbol}
          </span>
          <span
            className={cn(
              'text-[9px] font-bold',
              isBuy ? 'text-emerald-400' : 'text-red-400'
            )}
          >
            {isBuy ? (
              <TrendingUp className='inline h-3 w-3' />
            ) : (
              <TrendingDown className='inline h-3 w-3' />
            )}
          </span>
        </div>
      </TableCell>

      {/* Trigger */}
      <TableCell className='px-2 py-1.5'>
        <TriggerBadge signal={signal} />
      </TableCell>

      {/* Status */}
      <TableCell className='px-2 py-1.5'>
        <StatusBadge status={signal.status} pnl={pnl} compact />
      </TableCell>

      {/* R:R */}
      <TableCell className='px-2 py-1.5 text-right'>
        <span
          className='text-[10px] text-slate-500 tabular-nums'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {signal.rr_ratio ? `1:${signal.rr_ratio.toFixed(1)}` : '—'}
        </span>
      </TableCell>

      {/* PnL */}
      <TableCell className='px-2 py-1.5 text-right'>
        <PnLDisplay pnl={pnl} size='sm' />
      </TableCell>
    </TableRow>
  );
});

// ── Main component ────────────────────────────────────────────────────────────

export function RecentSignalsPanel({
  mode,
  onSelectSignal,
}: RecentSignalsPanelProps) {
  const [activeFilter, setActiveFilter] = useState<FilterTab>('all');
  const { data: signals = [], isLoading } = useTradingSignals(mode);

  const filtered = useMemo(() => {
    switch (activeFilter) {
      case 'active':
        return signals.filter(isSignalOpen);
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
          <Zap className='h-3.5 w-3.5 text-indigo-400' />
          <span
            className='panel-label'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            Recent Signals
          </span>
        </div>
        <span
          className='text-[10px] text-slate-500 tabular-nums'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {filtered.length}/{signals.length}
        </span>
      </div>

      {/* Filter tabs */}
      <div className='tv-divider flex shrink-0 items-center gap-1 border-b px-3 py-1.5'>
        {FILTER_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveFilter(tab.key)}
            className={cn(
              'whitespace-nowrap rounded px-2 py-0.5 transition-colors',
              'text-[10px] font-medium',
              activeFilter === tab.key
                ? 'bg-indigo-600/20 text-indigo-300'
                : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300'
            )}
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className='min-h-0 flex-1 overflow-hidden'>
        <ScrollArea className='h-full'>
          {isLoading ? (
            <div className='space-y-1 p-2'>
              {[...Array(6)].map((_, i) => (
                <Skeleton key={i} className='h-6 w-full bg-slate-800/60' />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className='empty-state py-12'>
              <span className='empty-state-text'>[ AWAITING 5M SIGNAL ]</span>
              <span
                className='mt-1 text-[10px] text-slate-700'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {activeFilter !== 'all'
                  ? `no ${activeFilter} signals`
                  : 'no signals match filter'}
              </span>
            </div>
          ) : (
            <Table className='table-dense table-fixed min-w-[560px]'>
              <TableHeader>
                <TableRow className='tv-divider border-b hover:bg-transparent'>
                  <TableHead
                    className='w-[18%] px-2 py-1.5 text-[9px] uppercase tracking-wider text-slate-600'
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    Time
                  </TableHead>
                  <TableHead
                    className='w-[18%] px-2 py-1.5 text-[9px] uppercase tracking-wider text-slate-600'
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    Signal
                  </TableHead>
                  <TableHead
                    className='w-[16%] px-2 py-1.5 text-[9px] uppercase tracking-wider text-slate-600'
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    Trigger
                  </TableHead>
                  <TableHead
                    className='w-[18%] px-2 py-1.5 text-[9px] uppercase tracking-wider text-slate-600'
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    Status
                  </TableHead>
                  <TableHead
                    className='w-[14%] px-2 py-1.5 text-right text-[9px] uppercase tracking-wider text-slate-600'
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    R:R
                  </TableHead>
                  <TableHead
                    className='w-[16%] px-2 py-1.5 text-right text-[9px] uppercase tracking-wider text-slate-600'
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
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
