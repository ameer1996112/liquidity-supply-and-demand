'use client';

import { useMemo } from 'react';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table';
import { useState } from 'react';
import { useTradingSignals } from '@/hooks/useTradingSignals';
import { TradingSignal, TradingMode, getSymbol, getSide, getPnl } from '@/types/trading';
import { isSignalOpen } from '@/domain/metrics/tradingMetrics';
import { Skeleton } from '@/components/ui/skeleton';
import { Radio, Activity, ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { PanelEmptyState } from '@/components/shared/PanelEmptyState';
import { EMPTY_VALUE, formatNumber, normalizeNegativeZero } from '@/lib/formatters';
import { ClientDate } from '@/components/ui/ClientDate';
import { formatDistanceToNowStrict } from 'date-fns';
import { TrendingUp, TrendingDown } from 'lucide-react';

// ── Interfaces ────────────────────────────────────────────────────────────────

interface ActiveTradesPanelProps {
  mode?: TradingMode;
  onSelectSignal: (signal: TradingSignal) => void;
  compact?: boolean;
}

// ── Column definitions ────────────────────────────────────────────────────────

const col = createColumnHelper<TradingSignal>();

function SideCell({ signal }: { signal: TradingSignal }) {
  const side = getSide(signal);
  const isBuy = side === 'buy';
  return (
    <div className='flex items-center gap-1.5'>
      <span className='font-mono text-xs font-bold text-[var(--to-text-primary)]'>
        {getSymbol(signal)}
      </span>
      <span
        className={cn(
          'inline-flex items-center gap-0.5 rounded px-1 py-0 font-mono text-[9px] font-bold',
          isBuy
            ? 'bg-[var(--to-long)]/15 text-[var(--to-long)]'
            : 'bg-[var(--to-short)]/15 text-[var(--to-short)]',
        )}
      >
        {isBuy ? <TrendingUp className='h-2.5 w-2.5' /> : <TrendingDown className='h-2.5 w-2.5' />}
        {side.toUpperCase()}
      </span>
    </div>
  );
}

function TriggerCell({ signal }: { signal: TradingSignal }) {
  const entryModel = (signal.entry_model ?? '').toLowerCase();
  const exitType = (signal.exit_type ?? '').toLowerCase();
  let label: string | null = null;
  let cls = '';

  if (exitType.includes('dir') || entryModel.includes('dir')) { label = 'DIR'; cls = 'trigger-dir-close'; }
  else if (entryModel.includes('boc') || entryModel.includes('break')) { label = 'BoC'; cls = 'trigger-boc'; }
  else if (entryModel.includes('flip') || entryModel.includes('zone') || signal.zone_type) { label = 'FLIP'; cls = 'trigger-flip'; }

  if (!label) return <span className='text-[var(--to-text-dim)]'>—</span>;
  return <span className={cn('rounded px-1.5 py-0 text-[9px] font-bold', cls)}>{label}</span>;
}

function EntryCell({ signal }: { signal: TradingSignal }) {
  const entry = signal.price ?? signal.entry;
  const symbol = getSymbol(signal);
  return (
    <span className='font-mono text-[11px] tabular-nums text-[var(--to-text-secondary)]'>
      {entry != null ? Number(entry).toFixed(symbol.includes('JPY') ? 3 : 5) : EMPTY_VALUE}
    </span>
  );
}

function RrCell({ signal }: { signal: TradingSignal }) {
  return (
    <span className='font-mono text-[11px] tabular-nums text-[var(--to-text-dim)]'>
      {signal.rr_ratio ? `1:${formatNumber(signal.rr_ratio, { decimals: 1 })}` : EMPTY_VALUE}
    </span>
  );
}

function AgeCell({ signal }: { signal: TradingSignal }) {
  return (
    <ClientDate
      className='font-mono text-[10px] tabular-nums text-[var(--to-text-dim)]'
      render={() =>
        formatDistanceToNowStrict(new Date(signal.created_at), { addSuffix: false })
      }
    />
  );
}

function PnlCell({ signal }: { signal: TradingSignal }) {
  const pnl = normalizeNegativeZero(getPnl(signal));
  if (pnl == null) {
    return <span className='font-mono text-xs text-[var(--to-text-dim)]'>{EMPTY_VALUE}</span>;
  }
  return (
    <span
      className={cn(
        'font-mono text-xs font-bold tabular-nums',
        pnl >= 0 ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]',
      )}
    >
      {pnl > 0 ? '+' : ''}{formatNumber(pnl, { decimals: 2 })}
    </span>
  );
}

const COLUMNS = [
  col.display({
    id: 'symbol',
    header: 'Symbol',
    cell: ({ row }) => <SideCell signal={row.original} />,
  }),
  col.display({
    id: 'trigger',
    header: 'Type',
    cell: ({ row }) => <TriggerCell signal={row.original} />,
  }),
  col.display({
    id: 'entry',
    header: 'Entry',
    cell: ({ row }) => <EntryCell signal={row.original} />,
  }),
  col.display({
    id: 'rr',
    header: 'R:R',
    cell: ({ row }) => <RrCell signal={row.original} />,
  }),
  col.display({
    id: 'age',
    header: 'Age',
    cell: ({ row }) => <AgeCell signal={row.original} />,
  }),
  col.accessor((row) => normalizeNegativeZero(getPnl(row)) ?? -Infinity, {
    id: 'pnl',
    header: 'PnL',
    cell: ({ row }) => <PnlCell signal={row.original} />,
  }),
];

// ── Sort icon helper ──────────────────────────────────────────────────────────

function SortIcon({ isSorted }: { isSorted: false | 'asc' | 'desc' }) {
  if (isSorted === 'asc') return <ChevronUp className='h-3 w-3' />;
  if (isSorted === 'desc') return <ChevronDown className='h-3 w-3' />;
  return <ChevronsUpDown className='h-3 w-3 opacity-30' />;
}

// ── Panel ─────────────────────────────────────────────────────────────────────

export function ActiveTradesPanel({ mode, onSelectSignal, compact = false }: ActiveTradesPanelProps) {
  const { data: signals = [], isLoading } = useTradingSignals(mode);
  const [sorting, setSorting] = useState<SortingState>([]);

  const activeTrades = useMemo(() => signals.filter(isSignalOpen), [signals]);

  const table = useReactTable({
    data: activeTrades,
    columns: COLUMNS,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className='to-panel flex h-full min-h-0 flex-col overflow-hidden'>

      {/* Header */}
      <div className='to-panel-header'>
        <div className='flex items-center gap-2'>
          <Radio className='h-3.5 w-3.5 text-[var(--to-accent-blue)]' />
          <span className='panel-label'>Active Positions</span>
        </div>
        <span
          className={cn(
            'rounded px-2 py-0.5 font-mono text-[10px] font-bold tabular-nums',
            activeTrades.length > 0
              ? 'bg-[var(--to-accent-blue)]/15 text-[var(--to-accent-blue)]'
              : 'bg-[var(--to-surface-raised)] text-[var(--to-text-dim)]',
          )}
        >
          {activeTrades.length}
        </span>
      </div>

      {/* Body */}
      <div className={cn('scrollbar-thin min-h-0 flex-1 overflow-y-auto', compact && 'py-0')}>
        {isLoading ? (
          <div className='space-y-1.5 p-2'>
            {Array.from({ length: 3 }, (_, i) => (
              <Skeleton key={i} className='h-8 w-full rounded bg-[var(--to-surface-raised)]/60' />
            ))}
          </div>
        ) : activeTrades.length === 0 ? (
          <PanelEmptyState
            icon={<Activity className='h-4 w-4' />}
            title='No active positions'
            description={
              compact
                ? 'Waiting for the next valid setup'
                : 'Waiting for valid 5m entry confirmations'
            }
          />
        ) : (
          <table className='w-full'>
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id} className='border-b border-[var(--to-border)]'>
                  {hg.headers.map((header) => (
                    <th
                      key={header.id}
                      onClick={header.column.getToggleSortingHandler()}
                      className={cn(
                        'px-2 py-1 text-left',
                        'kpi-meta select-none',
                        header.column.getCanSort() && 'cursor-pointer hover:text-[var(--to-text-secondary)]',
                      )}
                    >
                      <span className='inline-flex items-center gap-1'>
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {header.column.getCanSort() && (
                          <SortIcon isSorted={header.column.getIsSorted()} />
                        )}
                      </span>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => onSelectSignal(row.original)}
                  className={cn(
                    'border-b border-[var(--to-border-subtle)] last:border-0',
                    'cursor-pointer transition-colors duration-100',
                    'hover:bg-[var(--to-surface-raised)]',
                    'border-l-2 border-l-[var(--to-accent-blue)]/30',
                  )}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className='px-2 py-1.5 align-middle'>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
