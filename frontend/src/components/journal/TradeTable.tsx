'use client';

import { useState, useMemo } from 'react';
import { TradingSignal, getSymbol, getScore, getPnl } from '@/types/trading';
import { ExpandableTradeRow } from './ExpandableTradeRow';
import { cn } from '@/lib/utils';
import { ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';

interface TradeTableProps {
  signals: TradingSignal[];
  onInspect: (signal: TradingSignal) => void;
}

type SortKey =
  | 'date'
  | 'symbol'
  | 'side'
  | 'status'
  | 'account'
  | 'zone'
  | 'model'
  | 'session'
  | 'entry'
  | 'exit'
  | 'slPips'
  | 'score'
  | 'rr'
  | 'pnl';
type SortDir = 'asc' | 'desc';

const COLUMNS: { key: SortKey; label: string; align?: string }[] = [
  { key: 'date', label: 'Date' },
  { key: 'symbol', label: 'Symbol' },
  { key: 'side', label: 'Side' },
  { key: 'status', label: 'Status' },
  { key: 'account', label: 'Account' },
  { key: 'zone', label: 'Zone' },
  { key: 'model', label: 'Model' },
  { key: 'session', label: 'Session' },
  { key: 'entry', label: 'Entry' },
  { key: 'exit', label: 'Exit' },
  { key: 'slPips', label: 'SL Pips' },
  { key: 'score', label: 'AI' },
  { key: 'rr', label: 'R:R' },
  { key: 'pnl', label: 'PnL' },
];

function getSortValue(signal: TradingSignal, key: SortKey): number | string {
  switch (key) {
    case 'date':
      return new Date(signal.created_at).getTime();
    case 'symbol':
      return getSymbol(signal);
    case 'side':
      return signal.side || '';
    case 'status':
      return signal.status || '';
    case 'account':
      return signal.account_name || '';
    case 'zone':
      return signal.zone_type || '';
    case 'model':
      return signal.entry_model || '';
    case 'session':
      return signal.session ?? -1;
    case 'entry':
      return signal.price ?? signal.entry ?? 0;
    case 'exit':
      return signal.exit_price ?? 0;
    case 'slPips':
      return signal.sl_pips ?? 0;
    case 'score':
      return getScore(signal) ?? -1;
    case 'rr':
      return signal.rr_ratio ?? 0;
    case 'pnl':
      return getPnl(signal) ?? 0;
    default:
      return 0;
  }
}

type ModeFilter = 'all' | 'LIVE' | 'PAPER';

export function TradeTable({ signals, onInspect }: TradeTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('date');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [modeFilter, setModeFilter] = useState<ModeFilter>('all');

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const filtered = useMemo(() => {
    if (modeFilter === 'all') return signals;
    return signals.filter((s) => {
      const mode = (s.run_mode || s.mode || '').toUpperCase();
      return mode === modeFilter;
    });
  }, [signals, modeFilter]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const aVal = getSortValue(a, sortKey);
      const bVal = getSortValue(b, sortKey);
      const cmp =
        typeof aVal === 'string' && typeof bVal === 'string'
          ? aVal.localeCompare(bVal)
          : Number(aVal) - Number(bVal);
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [filtered, sortKey, sortDir]);

  if (signals.length === 0) {
    return (
      <div className='tv-card p-12 flex flex-col items-center justify-center'>
        <span className='text-sm text-[var(--to-text-dim)] font-mono'>
          No trades match your filters
        </span>
      </div>
    );
  }

  return (
    <div className='tv-card overflow-hidden'>
      {/* Mode Filter Toggle */}
      <div className='flex items-center gap-1 px-3 py-2 border-b border-[#2a2e39]'>
        {(['all', 'LIVE', 'PAPER'] as ModeFilter[]).map((mode) => (
          <button
            key={mode}
            onClick={() => setModeFilter(mode)}
            className={cn(
              'font-mono text-[10px] px-2.5 py-1 rounded transition-colors',
              modeFilter === mode
                ? mode === 'LIVE'
                  ? 'bg-[var(--to-long)]/20 text-[var(--to-long)]'
                  : mode === 'PAPER'
                  ? 'bg-blue-500/20 text-blue-400'
                  : 'bg-[var(--to-surface-raised)]/50 text-[var(--to-text-secondary)]'
                : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] hover:bg-[var(--to-surface-raised)]/50'
            )}
          >
            {mode === 'all'
              ? 'All'
              : mode === 'LIVE'
              ? 'Live Only'
              : 'Paper Only'}
          </button>
        ))}
        {modeFilter !== 'all' && (
          <span className='ml-2 text-[10px] text-[var(--to-text-dim)] font-mono'>
            {filtered.length}/{signals.length}
          </span>
        )}
      </div>

      {/* Single flat table — no nested virtualization */}
      <div className='overflow-x-auto'>
        <div className='overflow-y-auto' style={{ maxHeight: 600 }}>
          <table className='w-full'>
            <thead className='sticky top-0 z-10 bg-[#0d1117]'>
              <tr className='border-b border-[#2a2e39]'>
                {COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    onClick={() => handleSort(col.key)}
                    className='py-2.5 px-3 text-left cursor-pointer select-none group whitespace-nowrap'
                  >
                    <div className='flex items-center gap-1'>
                      <span className='font-mono text-[10px] text-[var(--to-text-dim)] uppercase tracking-wider group-hover:text-[var(--to-text-secondary)] transition-colors'>
                        {col.label}
                      </span>
                      {sortKey === col.key ? (
                        sortDir === 'asc' ? (
                          <ArrowUp className='w-3 h-3 text-[var(--to-text-dim)]' />
                        ) : (
                          <ArrowDown className='w-3 h-3 text-[var(--to-text-dim)]' />
                        )
                      ) : (
                        <ArrowUpDown className='w-3 h-3 text-[var(--to-text-dim)] group-hover:text-[var(--to-text-dim)] transition-colors' />
                      )}
                    </div>
                  </th>
                ))}
                {/* Note + Expand columns */}
                <th className='py-2.5 px-3 w-8' />
                <th className='py-2.5 px-3 w-8' />
              </tr>
            </thead>
            <tbody>
              {sorted.map((signal) => (
                <ExpandableTradeRow
                  key={signal.id}
                  signal={signal}
                  onInspect={onInspect}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
