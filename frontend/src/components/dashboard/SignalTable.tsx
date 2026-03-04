'use client';

import { useState, useMemo, useCallback } from 'react';
import { ArrowUpDown, ArrowUp, ArrowDown, Brain } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TradingSignal, SignalStatus } from '@/types/trading';
import type { CouncilSummary } from '@/lib/api';
import {
  DataTable,
  type DataTableColumn,
} from '@/components/shared/DataTable';
import { TableEmptyState } from '@/components/shared/TableStates';
import { Mono, PnLText, Number as MonoNumber } from '@/components/ui/typography';

type SortField = 'created_at' | 'symbol' | 'side' | 'entry' | 'pnl' | 'status';
type SortDir = 'asc' | 'desc';

interface SignalTableProps {
  signals: TradingSignal[];
  councilMap?: Record<string, CouncilSummary>;
  onSelectSignal?: (signal: TradingSignal) => void;
  maxRows?: number;
  className?: string;
}

function CouncilBadge({ summary }: { summary: CouncilSummary | undefined }) {
  if (!summary) return <span className='font-mono text-[10px] text-[var(--to-text-dim)]/40'>—</span>;

  const isAllow = summary.recommendation === 'allow';
  const conf = summary.confidence;
  const confColor = conf >= 70 ? 'text-[var(--to-long)]' : conf >= 50 ? 'text-[var(--to-warning)]' : 'text-[var(--to-short)]';

  // Count bull/bear/risk votes from the votes dict
  const voteEntries = Object.entries(summary.votes || {});
  const allowCount = voteEntries.filter(([, v]) => v === 'allow').length;
  const blockCount = voteEntries.filter(([, v]) => v === 'block').length;

  return (
    <div className='flex flex-col items-end gap-0.5'>
      <div className='flex items-center gap-1'>
        <Brain
          className={cn('h-3 w-3', isAllow ? 'text-[var(--to-long)]/60' : 'text-[var(--to-short)]/60')}
          strokeWidth={1.5}
        />
        <span
          className={cn('font-mono text-[10px] font-bold tabular-nums', confColor)}
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

function StatusBadge({ status }: { status: SignalStatus }) {
  const normalized = String(status).toLowerCase();
  const style = STATUS_STYLES[normalized] ?? {
    label: String(status).toUpperCase(),
    bg: 'bg-[var(--to-surface-raised)]',
    text: 'text-[var(--to-text-dim)]',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider',
        style.bg,
        style.text,
      )}
      style={{ fontFamily: 'var(--font-mono)' }}
    >
      {style.label}
    </span>
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
          : 'bg-[var(--to-short)]/12 text-[var(--to-short)]',
      )}
      style={{ fontFamily: 'var(--font-mono)' }}
    >
      {isBuy ? 'LONG' : 'SHORT'}
    </span>
  );
}

function getSortValue(signal: TradingSignal, field: SortField): string | number {
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
    default:
      return '';
  }
}

export function SignalTable({
  signals,
  councilMap = {},
  onSelectSignal,
  maxRows = 50,
  className,
}: SignalTableProps) {
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const handleSort = useCallback(
    (field: SortField) => {
      if (sortField === field) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortField(field);
        setSortDir('desc');
      }
    },
    [sortField],
  );

  const sorted = useMemo(() => {
    const slice = signals.slice(0, maxRows);
    return slice.sort((a, b) => {
      const va = getSortValue(a, sortField);
      const vb = getSortValue(b, sortField);
      const cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [signals, sortField, sortDir, maxRows]);

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  };

  const formatPrice = (v?: number) => {
    if (v == null) return null;
    return v >= 100 ? Number(v.toFixed(2)) : Number(v.toFixed(5));
  };

  const formatPnl = (v?: number | null) => {
    if (v == null) return null;
    return v;
  };

  if (signals.length === 0) {
    return (
      <TableEmptyState
        title='No signals yet'
        description='Waiting for the next trading signal from the bot.'
      />
    );
  }

  const columns: DataTableColumn<TradingSignal>[] = [
    {
      id: 'created_at',
      align: 'left',
      width: 'w-[80px]',
      header: (
        <button
          type='button'
          className='inline-flex items-center gap-1'
          onClick={() => handleSort('created_at')}
        >
          <span>Time</span>
          {sortField === 'created_at' ? (
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
      render: (signal) => (
        <Mono
          size='sm'
          className='text-text-secondary'
        >
          {formatTime(signal.created_at)}
        </Mono>
      ),
    },
    {
      id: 'symbol',
      align: 'left',
      width: 'w-[80px]',
      header: (
        <button
          type='button'
          className='inline-flex items-center gap-1'
          onClick={() => handleSort('symbol')}
        >
          <span>Pair</span>
          {sortField === 'symbol' ? (
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
      render: (signal) => (
        <Mono
          size='lg'
          bold
          className='text-text-primary'
        >
          {signal.symbol}
        </Mono>
      ),
    },
    {
      id: 'side',
      align: 'left',
      width: 'w-[60px]',
      header: (
        <button
          type='button'
          className='inline-flex items-center gap-1'
          onClick={() => handleSort('side')}
        >
          <span>Side</span>
          {sortField === 'side' ? (
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
      render: (signal) => <SideBadge side={signal.side} />,
    },
    {
      id: 'entry',
      align: 'right',
      isNumeric: true,
      width: 'w-[80px]',
      header: (
        <button
          type='button'
          className='inline-flex items-center justify-end gap-1 w-full'
          onClick={() => handleSort('entry')}
        >
          <span>Entry</span>
          {sortField === 'entry' ? (
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
      render: (signal) => (
        <MonoNumber
          value={formatPrice(signal.entry ?? signal.price)}
          decimals={signal.symbol.includes('JPY') ? 3 : 5}
          size='sm'
          className='text-text-secondary'
        />
      ),
    },
    {
      id: 'pnl',
      align: 'right',
      isNumeric: true,
      width: 'w-[80px]',
      header: (
        <button
          type='button'
          className='inline-flex items-center justify-end gap-1 w-full'
          onClick={() => handleSort('pnl')}
        >
          <span>P&amp;L</span>
          {sortField === 'pnl' ? (
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
      render: (signal) => (
        <PnLText
          value={formatPnl(signal.pnl ?? signal.pnl_usd ?? null)}
          variant='currency'
          size='sm'
        />
      ),
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
      header: (
        <button
          type='button'
          className='inline-flex items-center gap-1'
          onClick={() => handleSort('status')}
        >
          <span>Status</span>
          {sortField === 'status' ? (
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
      render: (signal) => <StatusBadge status={signal.status} />,
    },
  ];

  return (
    <DataTable
      columns={columns}
      data={sorted}
      compact
      stickyHeader={false}
      className={className}
      getRowId={(signal) => signal.id}
      onRowClick={(signal) => onSelectSignal?.(signal)}
    />
  );
}
