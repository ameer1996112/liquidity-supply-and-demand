'use client';

import { useState, useMemo, useCallback } from 'react';
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TradingSignal, SignalStatus } from '@/types/trading';

type SortField = 'created_at' | 'symbol' | 'side' | 'entry' | 'pnl' | 'status';
type SortDir = 'asc' | 'desc';

interface SignalTableProps {
  signals: TradingSignal[];
  onSelectSignal?: (signal: TradingSignal) => void;
  maxRows?: number;
  className?: string;
}

const STATUS_STYLES: Record<string, { label: string; bg: string; text: string }> = {
  active: { label: 'OPEN', bg: 'bg-[var(--to-long)]/12', text: 'text-[var(--to-long)]' },
  executed: { label: 'OPEN', bg: 'bg-[var(--to-long)]/12', text: 'text-[var(--to-long)]' },
  pending: { label: 'PENDING', bg: 'bg-[var(--to-warning)]/12', text: 'text-[var(--to-warning)]' },
  closed: { label: 'CLOSED', bg: 'bg-[var(--to-text-dim)]/12', text: 'text-[var(--to-text-dim)]' },
  filtered: { label: 'FILTERED', bg: 'bg-[var(--to-short)]/8', text: 'text-[var(--to-short)]/70' },
  ai_rejected: { label: 'REJECTED', bg: 'bg-[var(--to-short)]/12', text: 'text-[var(--to-short)]' },
  failed: { label: 'FAILED', bg: 'bg-[var(--to-short)]/12', text: 'text-[var(--to-short)]' },
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

type Column = {
  key: SortField;
  label: string;
  align?: 'left' | 'right';
  width?: string;
};

const COLUMNS: Column[] = [
  { key: 'created_at', label: 'Time', width: 'w-[80px]' },
  { key: 'symbol', label: 'Pair', width: 'w-[80px]' },
  { key: 'side', label: 'Side', width: 'w-[60px]' },
  { key: 'entry', label: 'Entry', align: 'right', width: 'w-[80px]' },
  { key: 'pnl', label: 'P&L', align: 'right', width: 'w-[80px]' },
  { key: 'status', label: 'Status', width: 'w-[80px]' },
];

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
    if (v == null) return '—';
    return v >= 100 ? v.toFixed(2) : v.toFixed(5);
  };

  const formatPnl = (v?: number | null) => {
    if (v == null) return '—';
    const sign = v >= 0 ? '+' : '';
    return `${sign}$${v.toFixed(2)}`;
  };

  if (signals.length === 0) {
    return (
      <div className={cn('flex flex-col items-center justify-center py-8', className)}>
        <p
          className='text-[11px] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          No signals yet
        </p>
      </div>
    );
  }

  return (
    <div className={cn('overflow-auto scrollbar-thin', className)}>
      <table className='w-full table-dense'>
        <thead>
          <tr className='border-b border-[var(--to-border)]'>
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                className={cn(
                  'cursor-pointer select-none whitespace-nowrap px-2 py-1.5 text-[9px] font-semibold uppercase tracking-wider text-[var(--to-text-dim)]',
                  col.align === 'right' ? 'text-right' : 'text-left',
                  col.width,
                )}
                style={{ fontFamily: 'var(--font-mono)' }}
                onClick={() => handleSort(col.key)}
              >
                <span className='inline-flex items-center gap-1'>
                  {col.label}
                  {sortField === col.key ? (
                    sortDir === 'asc' ? (
                      <ArrowUp className='h-2.5 w-2.5' />
                    ) : (
                      <ArrowDown className='h-2.5 w-2.5' />
                    )
                  ) : (
                    <ArrowUpDown className='h-2.5 w-2.5 opacity-30' />
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((signal) => {
            const pnlVal = signal.pnl ?? signal.pnl_usd ?? null;
            return (
              <tr
                key={signal.id}
                className='data-row cursor-pointer border-b border-[var(--to-border-subtle)]'
                onClick={() => onSelectSignal?.(signal)}
              >
                <td
                  className='whitespace-nowrap px-2 py-1.5 text-[11px] tabular-nums text-[var(--to-text-secondary)]'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {formatTime(signal.created_at)}
                </td>
                <td
                  className='whitespace-nowrap px-2 py-1.5 text-[11px] font-semibold text-[var(--to-text-primary)]'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {signal.symbol}
                </td>
                <td className='px-2 py-1.5'>
                  <SideBadge side={signal.side} />
                </td>
                <td
                  className='whitespace-nowrap px-2 py-1.5 text-right text-[11px] tabular-nums text-[var(--to-text-secondary)]'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {formatPrice(signal.entry ?? signal.price)}
                </td>
                <td
                  className={cn(
                    'whitespace-nowrap px-2 py-1.5 text-right text-[11px] font-semibold tabular-nums',
                    pnlVal != null && pnlVal > 0
                      ? 'text-[var(--to-long)]'
                      : pnlVal != null && pnlVal < 0
                        ? 'text-[var(--to-short)]'
                        : 'text-[var(--to-text-dim)]',
                  )}
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {formatPnl(pnlVal)}
                </td>
                <td className='px-2 py-1.5'>
                  <StatusBadge status={signal.status} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
