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
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { cn } from '@/lib/utils';
import { formatDistanceToNowStrict } from 'date-fns';
import { ClientDate } from '@/components/ui/ClientDate';
import {
  TrendingUp,
  TrendingDown,
  Zap,
  Search,
  FilterX,
  Ellipsis,
  Copy,
  Eye,
  Check,
} from 'lucide-react';
import { PanelEmptyState } from '@/components/shared/PanelEmptyState';
import { EMPTY_VALUE, formatNumber } from '@/lib/formatters';

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
  detailsMode?: 'drawer' | 'legacy';
}

// ── Derive trigger type from signal fields ────────────────────────────────────
function getTrigger(
  signal: TradingSignal,
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
  isReviewed: boolean;
  onToggleReviewed: (id: string) => void;
  onOpenDetails: (signal: TradingSignal) => void;
}

const SignalRowMemo = memo(function SignalRow({
  signal,
  isReviewed,
  onToggleReviewed,
  onOpenDetails,
}: SignalRowProps) {
  const symbol = getSymbol(signal);
  const side = getSide(signal);
  const pnl = getPnl(signal);
  const isBuy = side === 'buy';
  const isActive = signal.status?.toLowerCase() === 'active';

  return (
    <div
      onClick={() => onOpenDetails(signal)}
      className={cn(
        'group flex cursor-pointer items-center gap-3 border-b border-slate-800/60 px-3 py-3.5 transition-colors data-row',
        isActive && 'border-l-2 border-l-indigo-500',
        isReviewed && 'opacity-70',
      )}
    >
      <div className='min-w-0 flex-1'>
        <div className='flex items-center gap-2'>
          <span
            className='text-xs font-bold text-slate-200'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {symbol}
          </span>
          <ClientDate
            className='text-[10px] text-slate-500 tabular-nums'
            render={() =>
              formatDistanceToNowStrict(new Date(signal.created_at), {
                addSuffix: true,
              })
            }
          />
          <span
            className={cn(
              'inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-bold',
              isBuy ? 'text-emerald-400' : 'text-red-400',
            )}
          >
            {isBuy ? (
              <TrendingUp className='inline h-3 w-3' />
            ) : (
              <TrendingDown className='inline h-3 w-3' />
            )}
          </span>
          <TriggerBadge signal={signal} />
        </div>
        <div className='mt-1'>
          <StatusBadge status={signal.status} pnl={pnl} compact />
        </div>
      </div>

      <div className='text-right'>
        <PnLDisplay pnl={pnl} size='sm' />
      </div>

      <Popover>
        <PopoverTrigger
          onClick={(e) => e.stopPropagation()}
          className='rounded-md p-1 text-slate-500 opacity-0 transition-opacity hover:bg-slate-800 hover:text-slate-200 group-hover:opacity-100'
        >
          <Ellipsis className='h-4 w-4' />
        </PopoverTrigger>
        <PopoverContent className='w-44 border-slate-800 bg-slate-900 p-1.5'>
          <button
            type='button'
            onClick={() => {
              onOpenDetails(signal);
            }}
            className='flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-slate-200 hover:bg-slate-800'
          >
            <Eye className='h-3.5 w-3.5' />
            View details
          </button>
          <button
            type='button'
            onClick={() => navigator.clipboard?.writeText(symbol)}
            className='flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-slate-200 hover:bg-slate-800'
          >
            <Copy className='h-3.5 w-3.5' />
            Copy symbol
          </button>
          <button
            type='button'
            onClick={() =>
              navigator.clipboard?.writeText(JSON.stringify(signal, null, 2))
            }
            className='flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-slate-200 hover:bg-slate-800'
          >
            <Copy className='h-3.5 w-3.5' />
            Copy payload
          </button>
          <button
            type='button'
            onClick={() => onToggleReviewed(signal.id)}
            className='flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-slate-200 hover:bg-slate-800'
          >
            <Check className='h-3.5 w-3.5' />
            {isReviewed ? 'Dismiss review' : 'Mark reviewed'}
          </button>
        </PopoverContent>
      </Popover>
    </div>
  );
});

// ── Main component ────────────────────────────────────────────────────────────

export function RecentSignalsPanel({
  mode,
  onSelectSignal,
  detailsMode = 'drawer',
}: RecentSignalsPanelProps) {
  const [activeFilter, setActiveFilter] = useState<FilterTab>('all');
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(
    null,
  );
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [reviewedIds, setReviewedIds] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const { data: signals = [], isLoading } = useTradingSignals(mode);
  const PAGE_SIZE = 25;

  const openDetails = (signal: TradingSignal) => {
    if (detailsMode === 'legacy') {
      setSelectedSignal(signal);
      setDetailsOpen(true);
      return;
    }

    onSelectSignal(signal);
  };

  const toggleReviewed = (id: string) => {
    setReviewedIds((prev) =>
      prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id],
    );
  };

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
          return (
            st === 'ai_rejected' ||
            st === 'filtered' ||
            st === 'symbol_blacklisted' ||
            st === 'risk_rejected' ||
            st === 'kill_switch_blocked' ||
            st === 'staleness_rejected' ||
            st === 'received' ||
            st === 'execution_failed'
          );
        });
      default:
        return signals;
    }
  }, [signals, activeFilter]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pagedSignals = useMemo(
    () => filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [filtered, page],
  );

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
                : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300',
            )}
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className='min-h-0 flex-1 overflow-hidden'>
        <ScrollArea className='h-full'>
          {isLoading ? (
            <div className='space-y-1 p-2'>
              {[...Array(6)].map((_, i) => (
                <Skeleton key={i} className='h-6 w-full bg-slate-800/60' />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <PanelEmptyState
              icon={
                activeFilter === 'all' ? (
                  <Search className='h-4 w-4' />
                ) : (
                  <FilterX className='h-4 w-4' />
                )
              }
              title={
                activeFilter === 'all'
                  ? 'No signals yet'
                  : `No ${activeFilter} signals`
              }
              description='Signals will appear here as soon as they are generated'
            />
          ) : (
            <div className='divide-y divide-slate-800/60'>
              {pagedSignals.map((signal) => (
                <SignalRowMemo
                  key={signal.id}
                  signal={signal}
                  isReviewed={reviewedIds.includes(signal.id)}
                  onToggleReviewed={toggleReviewed}
                  onOpenDetails={openDetails}
                />
              ))}
            </div>
          )}
        </ScrollArea>
      </div>

      {!isLoading && filtered.length > PAGE_SIZE && (
        <div className='tv-divider flex items-center justify-between border-t px-3 py-2'>
          <span className='text-[10px] text-slate-500'>
            Page {page}/{totalPages}
          </span>
          <div className='flex items-center gap-1'>
            <button
              type='button'
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className='rounded border border-slate-700 px-2 py-0.5 text-[10px] text-slate-300 disabled:opacity-40'
            >
              Prev
            </button>
            <button
              type='button'
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              className='rounded border border-slate-700 px-2 py-0.5 text-[10px] text-slate-300 disabled:opacity-40'
            >
              Next
            </button>
          </div>
        </div>
      )}

      {detailsMode === 'legacy' && (
        <Sheet open={detailsOpen} onOpenChange={setDetailsOpen}>
          <SheetContent
            side='right'
            data-testid='legacy-signal-details-panel'
            className='w-full border-slate-800 bg-slate-950 p-0 sm:max-w-lg'
          >
            <SheetHeader className='space-y-2 border-b border-slate-800 px-5 py-4 text-left'>
              <SheetTitle className='text-base font-semibold text-slate-100'>
                Signal details
              </SheetTitle>
              <SheetDescription className='text-xs text-slate-400'>
                {selectedSignal
                  ? `${getSymbol(selectedSignal)} · ${selectedSignal.status}`
                  : 'No signal selected'}
              </SheetDescription>
            </SheetHeader>

            {selectedSignal && (
              <ScrollArea className='h-[calc(100vh-88px)]'>
                <div className='space-y-5 px-5 py-4 text-sm text-slate-200'>
                  <div className='rounded-lg border border-slate-800 bg-slate-900/40 p-3'>
                    <div className='flex flex-wrap items-center justify-between gap-3'>
                      <div>
                        <p className='text-[11px] uppercase tracking-wide text-slate-500'>
                          Instrument
                        </p>
                        <p className='mt-1 text-lg font-semibold tracking-wide text-slate-100'>
                          {getSymbol(selectedSignal)}
                        </p>
                      </div>
                      <div className='flex items-center gap-2'>
                        <StatusBadge
                          status={selectedSignal.status}
                          pnl={getPnl(selectedSignal)}
                          compact
                        />
                        <TriggerBadge signal={selectedSignal} />
                      </div>
                    </div>
                  </div>

                  <div className='grid grid-cols-2 gap-3'>
                    <div className='rounded-lg border border-slate-800/90 bg-slate-900/25 p-3'>
                      <p className='text-[10px] uppercase tracking-wide text-slate-500'>
                        Direction
                      </p>
                      <p className='mt-1 font-mono text-sm text-slate-100'>
                        {getSide(selectedSignal).toUpperCase()}
                      </p>
                    </div>
                    <div className='rounded-lg border border-slate-800/90 bg-slate-900/25 p-3'>
                      <p className='text-[10px] uppercase tracking-wide text-slate-500'>
                        Trigger
                      </p>
                      <p className='mt-1 font-mono text-sm text-slate-100'>
                        {getTrigger(selectedSignal) ?? EMPTY_VALUE}
                      </p>
                    </div>
                    <div className='rounded-lg border border-slate-800/90 bg-slate-900/25 p-3'>
                      <p className='text-[10px] uppercase tracking-wide text-slate-500'>
                        Risk:Reward
                      </p>
                      <p className='mt-1 font-mono text-sm text-slate-100'>
                        {selectedSignal.rr_ratio
                          ? `1:${formatNumber(selectedSignal.rr_ratio, {
                              decimals: 1,
                            })}`
                          : EMPTY_VALUE}
                      </p>
                    </div>
                    <div className='rounded-lg border border-slate-800/90 bg-slate-900/25 p-3'>
                      <p className='text-[10px] uppercase tracking-wide text-slate-500'>
                        PnL
                      </p>
                      <div className='mt-1 font-mono text-sm text-slate-100'>
                        <PnLDisplay pnl={getPnl(selectedSignal)} size='md' />
                      </div>
                    </div>
                    <div className='col-span-2 rounded-lg border border-slate-800/90 bg-slate-900/25 p-3'>
                      <p className='text-[10px] uppercase tracking-wide text-slate-500'>
                        Timestamp
                      </p>
                      <ClientDate
                        className='mt-1 font-mono text-sm text-slate-200 block'
                        render={() =>
                          new Date(selectedSignal.created_at).toLocaleString()
                        }
                      />
                    </div>
                  </div>

                  <div className='rounded-lg border border-slate-800 bg-slate-900/25 p-3'>
                    <p className='text-[10px] uppercase tracking-wide text-slate-500'>
                      Rationale
                    </p>
                    <p className='mt-2 leading-6 text-slate-300'>
                      {selectedSignal.notes ||
                        selectedSignal.filter_reason ||
                        EMPTY_VALUE}
                    </p>
                  </div>
                </div>
              </ScrollArea>
            )}
          </SheetContent>
        </Sheet>
      )}
    </div>
  );
}
