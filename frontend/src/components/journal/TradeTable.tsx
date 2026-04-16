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
  | 'setup'
  | 'zone'
  | 'model'
  | 'session'
  | 'entry'
  | 'exit'
  | 'slPips'
  | 'score'
  | 'rr'
  | 'pnl'
  | 'size'
  | 'duration';
type SortDir = 'asc' | 'desc';

const COLUMNS: { key: SortKey; label: string; align?: string }[] = [
  { key: 'date', label: 'Date' },
  { key: 'symbol', label: 'Symbol' },
  { key: 'side', label: 'Side' },
  { key: 'status', label: 'Status' },
  { key: 'account', label: 'Account' },
  { key: 'setup', label: 'Setup' },
  { key: 'zone', label: 'Zone' },
  { key: 'model', label: 'Model' },
  { key: 'session', label: 'Session' },
  { key: 'entry', label: 'Entry' },
  { key: 'exit', label: 'Exit' },
  { key: 'size', label: 'Size' },
  { key: 'slPips', label: 'SL Pips' },
  { key: 'score', label: 'AI' },
  { key: 'rr', label: 'R:R' },
  { key: 'duration', label: 'Duration' },
  { key: 'pnl', label: 'PnL' },
];

function getDurationMs(signal: TradingSignal): number {
  if (!signal.closed_at) return -1;
  const startTime = signal.opened_at || signal.created_at;
  return new Date(signal.closed_at).getTime() - new Date(startTime).getTime();
}

export function formatDuration(ms: number): string {
  if (ms < 0) return '--';
  const totalMin = Math.floor(ms / 60000);
  if (totalMin < 60) return `${totalMin}m`;
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  if (h < 24) return m > 0 ? `${h}h ${m}m` : `${h}h`;
  const d = Math.floor(h / 24);
  const rh = h % 24;
  return rh > 0 ? `${d}d ${rh}h` : `${d}d`;
}

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
    case 'setup':
      return signal.setup_evidence?.focus_image?.url ? 1 : 0;
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
    case 'size':
      return signal.position_size ?? 0;
    case 'slPips':
      return signal.sl_pips ?? 0;
    case 'score':
      return getScore(signal) ?? -1;
    case 'rr':
      return signal.rr_ratio ?? 0;
    case 'duration':
      return getDurationMs(signal);
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

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sorted = useMemo(() => {
    return [...signals].sort((a, b) => {
      const aVal = getSortValue(a, sortKey);
      const bVal = getSortValue(b, sortKey);
      const cmp =
        typeof aVal === 'string' && typeof bVal === 'string'
          ? aVal.localeCompare(bVal)
          : Number(aVal) - Number(bVal);
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [signals, sortKey, sortDir]);

  if (signals.length === 0) {
    return (
      <div className='glow-card p-12 flex flex-col items-center justify-center'>
        <span className='text-sm text-[var(--to-text-dim)] font-mono'>
          No trades match your filters
        </span>
      </div>
    );
  }

  return (
    <div className='glow-card overflow-hidden'>
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
