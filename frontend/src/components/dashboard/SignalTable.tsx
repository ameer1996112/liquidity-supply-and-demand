'use client';

import { useState, useMemo, useCallback } from 'react';
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Brain,
  TrendingUp,
  Wifi,
  AlertTriangle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TradingSignal, SignalStatus } from '@/types/trading';
import type { CouncilSummary } from '@/lib/api';
import type { ActivePosition } from '@/hooks/usePositions';
import { DataTable, type DataTableColumn } from '@/components/shared/DataTable';
import { TableEmptyState } from '@/components/shared/TableStates';
import {
  Mono,
  PnLText,
  Number as MonoNumber,
} from '@/components/ui/typography';

type SortField =
  | 'created_at'
  | 'symbol'
  | 'side'
  | 'entry'
  | 'pnl'
  | 'status'
  | 'score';
type SortDir = 'asc' | 'desc';

type FilterTab = 'all' | 'open' | 'closed' | 'rejected' | 'filtered';

interface SignalTableProps {
  signals: TradingSignal[];
  councilMap?: Record<string, CouncilSummary>;
  brokerMap?: Record<string, ActivePosition>;
  onSelectSignal?: (signal: TradingSignal) => void;
  maxRows?: number;
  className?: string;
}

/** Relative time: "2m ago", "1h ago", etc. */
function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h`;
  return `${Math.floor(diff / 86_400_000)}d`;
}

/** Left-side row accent color based on side (LONG=green, SHORT=red) */
function rowAccentColor(side: string): string {
  const s = side.toLowerCase();
  if (s === 'buy' || s === 'long') return 'bg-[var(--to-long)]';
  if (s === 'sell' || s === 'short') return 'bg-[var(--to-short)]';
  return 'bg-[var(--to-border)]';
}

function CouncilBadge({ summary }: { summary: CouncilSummary | undefined }) {
  if (!summary)
    return (
      <span className='font-mono text-[10px] text-[var(--to-text-dim)]/40'>
        —
      </span>
    );

  const isAllow = summary.recommendation === 'allow';
  const conf = summary.confidence;
  const confColor =
    conf >= 70
      ? 'text-[var(--to-long)]'
      : conf >= 50
      ? 'text-[var(--to-warning)]'
      : 'text-[var(--to-short)]';

  const voteEntries = Object.entries(summary.votes || {});
  const allowCount = voteEntries.filter(([, v]) => v === 'allow').length;
  const blockCount = voteEntries.filter(([, v]) => v === 'block').length;

  return (
    <div className='flex flex-col items-end gap-0.5'>
      <div className='flex items-center gap-1'>
        <Brain
          className={cn(
            'h-3 w-3',
            isAllow ? 'text-[var(--to-long)]/60' : 'text-[var(--to-short)]/60'
          )}
          strokeWidth={1.5}
        />
        <span
          className={cn(
            'font-mono text-[10px] font-bold tabular-nums',
            confColor
          )}
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {conf}%
        </span>
      </div>
      {voteEntries.length > 0 && (
        <span
          className='font-mono text-[9px] tabular-nums text-[var(--to-text-dim)]/60'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {allowCount}✓ {blockCount}✗
        </span>
      )}
    </div>
  );
}

const STATUS_STYLES: Record<
  string,
  { label: string; bg: string; text: string }
> = {
  active: {
    label: 'OPEN',
    bg: 'bg-[var(--to-long)]/12',
    text: 'text-[var(--to-long)]',
  },
  executed: {
    label: 'OPEN',
    bg: 'bg-[var(--to-long)]/12',
    text: 'text-[var(--to-long)]',
  },
  pending: {
    label: 'PENDING',
    bg: 'bg-[var(--to-warning)]/12',
    text: 'text-[var(--to-warning)]',
  },
  closed: {
    label: 'CLOSED',
    bg: 'bg-[var(--to-text-dim)]/12',
    text: 'text-[var(--to-text-dim)]',
  },
  filtered: {
    label: 'FILTERED',
    bg: 'bg-[var(--to-short)]/8',
    text: 'text-[var(--to-short)]/70',
  },
  ai_rejected: {
    label: 'REJECTED',
    bg: 'bg-[var(--to-short)]/12',
    text: 'text-[var(--to-short)]',
  },
  failed: {
    label: 'FAILED',
    bg: 'bg-[var(--to-short)]/12',
    text: 'text-[var(--to-short)]',
  },
};

function isOpenStatus(status: string): boolean {
  const s = String(status).toLowerCase();
  return s === 'active' || s === 'executed' || s === 'pending';
}

function isClosedStatus(status: string): boolean {
  const s = String(status).toLowerCase();
  return s === 'closed';
}

function isRejectedStatus(status: string): boolean {
  const s = String(status).toLowerCase();
  return s === 'ai_rejected' || s === 'failed';
}

function isFilteredStatus(status: string): boolean {
  const s = String(status).toLowerCase();
  return s === 'filtered';
}

function StatusBadge({
  status,
  isStale,
}: {
  status: SignalStatus;
  isStale?: boolean;
}) {
  const normalized = String(status).toLowerCase();
  const style = STATUS_STYLES[normalized] ?? {
    label: String(status).toUpperCase(),
    bg: 'bg-[var(--to-surface-raised)]',
    text: 'text-[var(--to-text-dim)]',
  };

  return (
    <div className='flex flex-col items-start gap-0.5'>
      <span
        className={cn(
          'inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider',
          style.bg,
          style.text
        )}
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        {style.label}
      </span>
      {isStale && (
        <span className='inline-flex items-center gap-0.5 text-[8px] text-[var(--to-warning)]'>
          <AlertTriangle className='h-2 w-2' />
          stale
        </span>
      )}
    </div>
  );
}

function SideBadge({ side }: { side: string }) {
  const isBuy = side.toLowerCase() === 'buy';
  return (
    <span
      className={cn(
        'inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider',
        isBuy
          ? 'bg-[var(--to-long)]/12 text-[var(--to-long)]'
          : 'bg-[var(--to-short)]/12 text-[var(--to-short)]'
      )}
      style={{ fontFamily: 'var(--font-mono)' }}
    >
      {isBuy ? 'LONG' : 'SHORT'}
    </span>
  );
}

function getSortValue(
  signal: TradingSignal,
  field: SortField
): string | number {
  switch (field) {
    case 'created_at':
      return new Date(signal.created_at).getTime();
    case 'symbol':
      return signal.symbol;
    case 'side':
      return signal.side;
    case 'entry':
      return signal.entry ?? signal.price ?? 0;
    case 'pnl':
      return signal.pnl ?? signal.pnl_usd ?? 0;
    case 'status':
      return signal.status;
    case 'score':
      return signal.score ?? signal.ai_confidence ?? 0;
    default:
      return '';
  }
}

const FILTER_TABS: { id: FilterTab; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'open', label: 'Open' },
  { id: 'closed', label: 'Closed' },
  { id: 'rejected', label: 'Rejected' },
  { id: 'filtered', label: 'Filtered' },
];

export function SignalTable({
  signals,
  councilMap = {},
  brokerMap = {},
  onSelectSignal,
  maxRows = 100,
  className,
}: SignalTableProps) {
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [activeFilter, setActiveFilter] = useState<FilterTab>('all');

  const handleSort = useCallback(
    (field: SortField) => {
      if (sortField === field) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortField(field);
        setSortDir('desc');
      }
    },
    [sortField]
  );

  // Tab counts
  const tabCounts = useMemo(() => {
    const counts: Record<FilterTab, number> = {
      all: signals.length,
      open: 0,
      closed: 0,
      rejected: 0,
      filtered: 0,
    };
    for (const s of signals) {
      if (isOpenStatus(s.status)) counts.open++;
      else if (isClosedStatus(s.status)) counts.closed++;
      else if (isRejectedStatus(s.status)) counts.rejected++;
      else if (isFilteredStatus(s.status)) counts.filtered++;
    }
    return counts;
  }, [signals]);

  const filtered = useMemo(() => {
    let list = signals;
    if (activeFilter === 'open') list = list.filter((s) => isOpenStatus(s.status));
    else if (activeFilter === 'closed') list = list.filter((s) => isClosedStatus(s.status));
    else if (activeFilter === 'rejected') list = list.filter((s) => isRejectedStatus(s.status));
    else if (activeFilter === 'filtered') list = list.filter((s) => isFilteredStatus(s.status));
    return list;
  }, [signals, activeFilter]);

  const sorted = useMemo(() => {
    const slice = filtered.slice(0, maxRows);
    return slice.sort((a, b) => {
      const va = getSortValue(a, sortField);
      const vb = getSortValue(b, sortField);
      const cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [filtered, sortField, sortDir, maxRows]);

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  };

  const formatPrice = (v?: number, symbol?: string) => {
    if (v == null) return null;
    const sym = symbol ?? '';
    if (sym.includes('JPY')) return Number(v.toFixed(3));
    return v >= 100 ? Number(v.toFixed(2)) : Number(v.toFixed(5));
  };

  if (signals.length === 0) {
    return (
      <TableEmptyState
        title='No signals yet'
        description='Waiting for the next trading signal from the bot.'
      />
    );
  }

  const SortHeader = ({
    field,
    label,
    align = 'left',
  }: {
    field: SortField;
    label: string;
    align?: 'left' | 'right';
  }) => (
    <button
      type='button'
      className={cn(
        'inline-flex items-center gap-1 w-full',
        align === 'right' && 'justify-end'
      )}
      onClick={() => handleSort(field)}
    >
      <span>{label}</span>
      {sortField === field ? (
        sortDir === 'asc' ? (
          <ArrowUp className='h-2.5 w-2.5' />
        ) : (
          <ArrowDown className='h-2.5 w-2.5' />
        )
      ) : (
        <ArrowUpDown className='h-2.5 w-2.5 opacity-30' />
      )}
    </button>
  );

  const columns: DataTableColumn<TradingSignal>[] = [
    {
      id: 'row_accent',
      align: 'left',
      width: 'w-[3px] p-0',
      header: <span />,
      render: (signal) => (
        <span
          className={cn(
            'animate-slide-in-right block h-full w-[3px] rounded-full',
            rowAccentColor(signal.side)
          )}
          style={{ minHeight: 20 }}
        />
      ),
    },
    {
      id: 'created_at',
      align: 'left',
      width: 'w-[72px]',
      header: <SortHeader field='created_at' label='Time' />,
      render: (signal) => (
        <span
          className='font-mono text-[10px] tabular-nums text-[var(--to-text-primary)]'
          style={{ fontFamily: 'var(--font-mono)' }}
          title={new Date(signal.created_at).toLocaleString()}
        >
          {relativeTime(signal.created_at)}
        </span>
      ),
    },
    {
      id: 'symbol',
      align: 'left',
      width: 'w-[80px]',
      header: <SortHeader field='symbol' label='Pair' />,
      render: (signal) => (
        <Mono size='lg' bold className='text-text-primary'>
          {signal.symbol}
        </Mono>
      ),
    },
    {
      id: 'side',
      align: 'left',
      width: 'w-[60px]',
      header: <SortHeader field='side' label='Side' />,
      render: (signal) => <SideBadge side={signal.side} />,
    },
    {
      id: 'entry',
      align: 'right',
      isNumeric: true,
      width: 'w-[76px]',
      header: <SortHeader field='entry' label='Entry' align='right' />,
      render: (signal) => {
        const broker = brokerMap[String(signal.id)];
        const entry = signal.entry ?? signal.price;
        const currentPrice = broker?.current_price;
        const entryFormatted = formatPrice(entry, signal.symbol);
        const dec = signal.symbol?.includes('JPY') ? 3 : 5;
        const titleText = currentPrice != null
          ? `Entry: ${entryFormatted?.toFixed(dec)} · Live: ${formatPrice(currentPrice, signal.symbol)?.toFixed(dec)}`
          : undefined;
        return (
          <span
            className='font-mono text-[10px] tabular-nums text-text-secondary'
            style={{ fontFamily: 'var(--font-mono)' }}
            title={titleText}
          >
            {currentPrice != null && (
              <Wifi className='inline h-2 w-2 mr-0.5 text-[var(--to-long)]/70' />
            )}
            <MonoNumber
              value={entryFormatted}
              decimals={dec}
              size='sm'
              className='text-text-secondary'
            />
          </span>
        );
      },
    },
    {
      id: 'sl_tp',
      align: 'right',
      isNumeric: true,
      width: 'w-[72px]',
      header: (
        <span className='inline-flex items-center justify-end gap-0.5 w-full text-[10px]'>
          SL / TP
        </span>
      ),
      render: (signal) => {
        const sl = signal.sl ?? signal.stop_loss;
        const tp = signal.tp ?? signal.take_profit;
        const sym = signal.symbol ?? '';
        const dec = sym.includes('JPY') ? 3 : sym.includes('XAU') || sym.includes('GOLD') ? 2 : 5;
        const slStr = sl != null ? sl.toFixed(dec) : '—';
        const tpStr = tp != null ? tp.toFixed(dec) : '—';
        return (
          <span
            className='font-mono text-[9px] tabular-nums'
            style={{ fontFamily: 'var(--font-mono)' }}
            title={`SL: ${slStr} · TP: ${tpStr}`}
          >
            <span className='text-[var(--to-short)]/80'>{slStr}</span>
            <span className='text-[var(--to-text-dim)]/40 mx-0.5'>/</span>
            <span className='text-[var(--to-long)]/80'>{tpStr}</span>
          </span>
        );
      },
    },
    {
      id: 'pnl',
      align: 'right',
      isNumeric: true,
      width: 'w-[80px]',
      header: <SortHeader field='pnl' label='P&L' align='right' />,
      render: (signal) => {
        const broker = brokerMap[String(signal.id)];
        const livePnl = broker?.live_pnl;
        const dbPnl = signal.pnl ?? signal.pnl_usd ?? null;

        if (livePnl != null) {
          const isPos = livePnl >= 0;
          return (
            <span
              className={cn(
                'inline-flex items-center gap-1 font-mono text-[10px] font-bold tabular-nums',
                isPos ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]'
              )}
              style={{ fontFamily: 'var(--font-mono)' }}
              title='Live broker P&L'
            >
              <span className={cn('h-1.5 w-1.5 rounded-full shrink-0 animate-pulse', isPos ? 'bg-[var(--to-long)]' : 'bg-[var(--to-short)]')} />
              {livePnl > 0 ? '+' : ''}{livePnl.toFixed(2)}
            </span>
          );
        }

        return (
          <PnLText
            value={dbPnl}
            variant='currency'
            size='sm'
          />
        );
      },
    },
    {
      id: 'score',
      align: 'right',
      isNumeric: true,
      width: 'w-[52px]',
      header: (
        <button
          type='button'
          className='inline-flex items-center justify-end gap-1 w-full'
          onClick={() => handleSort('score')}
        >
          <TrendingUp className='h-2.5 w-2.5' strokeWidth={1.5} />
          <span>Score</span>
          {sortField === 'score' ? (
            sortDir === 'asc' ? (
              <ArrowUp className='h-2.5 w-2.5' />
            ) : (
              <ArrowDown className='h-2.5 w-2.5' />
            )
          ) : (
            <ArrowUpDown className='h-2.5 w-2.5 opacity-30' />
          )}
        </button>
      ),
      render: (signal) => {
        const score = signal.score ?? signal.ai_confidence;
        if (score == null)
          return (
            <span className='font-mono text-[10px] text-[var(--to-text-dim)]/40'>
              —
            </span>
          );
        const color =
          score >= 70
            ? 'text-[var(--to-long)]'
            : score >= 50
            ? 'text-[var(--to-warning)]'
            : 'text-[var(--to-short)]';
        return (
          <span
            className={cn(
              'font-mono text-[10px] font-bold tabular-nums',
              color
            )}
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {Math.round(score)}
          </span>
        );
      },
    },
    {
      id: 'council',
      align: 'right',
      isNumeric: true,
      width: 'w-[70px]',
      header: (
        <span className='inline-flex items-center justify-end gap-1 w-full'>
          <Brain className='h-2.5 w-2.5' strokeWidth={1.5} />
          <span>Council</span>
        </span>
      ),
      render: (signal) => (
        <CouncilBadge summary={councilMap[String(signal.id)]} />
      ),
    },
    {
      id: 'status',
      align: 'left',
      width: 'w-[80px]',
      header: <SortHeader field='status' label='Status' />,
      render: (signal) => {
        const broker = brokerMap[String(signal.id)];
        return (
          <StatusBadge
            status={signal.status}
            isStale={broker?.is_stale}
          />
        );
      },
    },
  ];

  return (
    <div className={cn('flex flex-col h-full min-h-0', className)}>
      {/* Filter tabs — fixed height */}
      <div className='shrink-0 flex items-center gap-1 px-1 pb-1 flex-wrap'>
        {FILTER_TABS.map((tab) => (
          <button
            key={tab.id}
            type='button'
            onClick={() => setActiveFilter(tab.id)}
            className={cn(
              'inline-flex items-center gap-1 rounded px-2 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-wider transition-colors',
              activeFilter === tab.id
                ? 'bg-[var(--to-accent)]/20 text-[var(--to-accent)]'
                : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]'
            )}
          >
            {tab.label}
            {tabCounts[tab.id] > 0 && (
              <span
                className={cn(
                  'rounded-full px-1 py-px text-[8px] tabular-nums',
                  activeFilter === tab.id
                    ? 'bg-[var(--to-accent)]/30'
                    : 'bg-[var(--to-surface-raised)]'
                )}
              >
                {tabCounts[tab.id]}
              </span>
            )}
          </button>
        ))}
        {Object.keys(brokerMap).length > 0 && (
          <span className='ml-auto inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[8px] text-[var(--to-long)]/70'>
            <Wifi className='h-2.5 w-2.5' />
            broker live
          </span>
        )}
      </div>

      {/* Scrollable table area */}
      <div className='flex-1 min-h-0 overflow-y-auto scrollbar-thin'>
        {sorted.length === 0 ? (
          <TableEmptyState
            title={`No ${activeFilter === 'all' ? '' : activeFilter + ' '}signals`}
            description='Try a different filter.'
          />
        ) : (
          <DataTable
            columns={columns}
            data={sorted}
            compact
            stickyHeader
            getRowId={(signal) => signal.id}
            onRowClick={(signal) => onSelectSignal?.(signal)}
            getRowClassName={(signal) => {
              const broker = brokerMap[String(signal.id)];
              if (broker?.is_stale) return 'opacity-60 border-l-2 border-l-[var(--to-warning)]/50';
              return '';
            }}
          />
        )}
      </div>
    </div>
  );
}
