'use client';

import { useState, useMemo } from 'react';
import {
  ScanLine,
  TrendingUp,
  TrendingDown,
  Minus,
  RefreshCw,
  Filter,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useQuery } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';
import { PanelEmptyState } from '@/components/shared/PanelEmptyState';

// ── Types ─────────────────────────────────────────────────────────────────────

interface ScannerSymbol {
  symbol: string;
  side: 'buy' | 'sell' | 'neutral';
  score: number;
  zone_type: string;
  entry_model: string;
  timeframe: string;
  distance_pips: number;
  last_signal_at: string | null;
  session: string;
}

type SideFilter = 'ALL' | 'buy' | 'sell';
type SortKey = 'score' | 'symbol' | 'distance_pips';

// ── Fetch ─────────────────────────────────────────────────────────────────────

async function fetchScannerData(): Promise<{ symbols: ScannerSymbol[] }> {
  const res = await fetch(`${getApiUrl()}/api/scanner/symbols`, {
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error('Failed to fetch scanner data');
  return res.json();
}

// ── Score Bar ─────────────────────────────────────────────────────────────────

function ScoreBar({ score }: { score: number }) {
  const pct = Math.min(Math.max(score, 0), 100);
  const color = pct >= 75 ? '#0ecb81' : pct >= 50 ? '#f0b90b' : '#f6465d';

  return (
    <div className='flex items-center gap-2'>
      <div className='flex-1 h-1.5 rounded-full bg-[#1e2329] overflow-hidden'>
        <div
          className='h-full rounded-full transition-all'
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span
        className='w-8 text-right text-[10px] tabular-nums font-semibold'
        style={{ color, fontFamily: 'var(--font-mono)' }}
      >
        {pct.toFixed(0)}
      </span>
    </div>
  );
}

// ── Side Badge ────────────────────────────────────────────────────────────────

function SideBadge({ side }: { side: string }) {
  if (side === 'buy') {
    return (
      <span
        className='inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-bold uppercase bg-[#0ecb81]/15 text-[#0ecb81]'
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        <TrendingUp className='h-2.5 w-2.5' /> BUY
      </span>
    );
  }
  if (side === 'sell') {
    return (
      <span
        className='inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-bold uppercase bg-[#f6465d]/15 text-[#f6465d]'
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        <TrendingDown className='h-2.5 w-2.5' /> SELL
      </span>
    );
  }
  return (
    <span
      className='inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-bold uppercase bg-[var(--to-surface-raised)] text-[var(--to-text-dim)]'
      style={{ fontFamily: 'var(--font-mono)' }}
    >
      <Minus className='h-2.5 w-2.5' /> NEUTRAL
    </span>
  );
}

// ── Mock fallback data ────────────────────────────────────────────────────────

const MOCK_SYMBOLS: ScannerSymbol[] = [
  {
    symbol: 'GBPUSD',
    side: 'buy',
    score: 82,
    zone_type: 'demand',
    entry_model: 'RBR',
    timeframe: '5m',
    distance_pips: 12,
    last_signal_at: null,
    session: 'London',
  },
  {
    symbol: 'EURUSD',
    side: 'sell',
    score: 74,
    zone_type: 'supply',
    entry_model: 'DBD',
    timeframe: '15m',
    distance_pips: 8,
    last_signal_at: null,
    session: 'London',
  },
  {
    symbol: 'USDJPY',
    side: 'buy',
    score: 68,
    zone_type: 'demand',
    entry_model: 'RBR',
    timeframe: '5m',
    distance_pips: 22,
    last_signal_at: null,
    session: 'Tokyo',
  },
  {
    symbol: 'GBPJPY',
    side: 'sell',
    score: 61,
    zone_type: 'supply',
    entry_model: 'DBD',
    timeframe: '15m',
    distance_pips: 31,
    last_signal_at: null,
    session: 'London',
  },
  {
    symbol: 'NAS100',
    side: 'buy',
    score: 55,
    zone_type: 'demand',
    entry_model: 'RBR',
    timeframe: '5m',
    distance_pips: 45,
    last_signal_at: null,
    session: 'NY',
  },
  {
    symbol: 'AUDUSD',
    side: 'neutral',
    score: 42,
    zone_type: 'none',
    entry_model: '—',
    timeframe: '—',
    distance_pips: 0,
    last_signal_at: null,
    session: '—',
  },
];

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function ScannerPage() {
  const [sideFilter, setSideFilter] = useState<SideFilter>('ALL');
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortAsc, setSortAsc] = useState(false);

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['scanner-symbols'],
    queryFn: fetchScannerData,
    refetchInterval: 30_000,
    retry: 1,
  });

  // Use mock data if API not available
  const symbols: ScannerSymbol[] = data?.symbols ?? (error ? MOCK_SYMBOLS : []);

  const filtered = useMemo(() => {
    let list = [...symbols];
    if (sideFilter !== 'ALL') list = list.filter((s) => s.side === sideFilter);
    list.sort((a, b) => {
      let diff = 0;
      if (sortKey === 'score') diff = a.score - b.score;
      else if (sortKey === 'symbol') diff = a.symbol.localeCompare(b.symbol);
      else if (sortKey === 'distance_pips')
        diff = a.distance_pips - b.distance_pips;
      return sortAsc ? diff : -diff;
    });
    return list;
  }, [symbols, sideFilter, sortKey, sortAsc]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc((v) => !v);
    else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  const SortIndicator = ({ k }: { k: SortKey }) =>
    sortKey === k ? (
      <span className='text-[var(--to-warning)]'>{sortAsc ? '↑' : '↓'}</span>
    ) : null;

  return (
    <div className='space-y-4'>
      {/* Header */}
      <div className='flex items-start justify-between gap-3 flex-wrap'>
        <div>
          <div className='flex items-center gap-2'>
            <ScanLine className='h-4 w-4 text-[var(--to-accent-blue)]' />
            <h1 className='page-title text-lg font-semibold'>Symbol Scanner</h1>
          </div>
          <p className='page-subtitle mt-0.5 text-xs'>
            Live zone proximity scan across all tracked symbols · refreshes
            every 30s
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className='flex items-center gap-1.5 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-1.5 text-[10px] text-[var(--to-text-secondary)] hover:text-[var(--to-text-primary)] hover:bg-[var(--to-surface-raised)] transition-colors disabled:opacity-50'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          <RefreshCw className={cn('h-3 w-3', isFetching && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* Demo data warning — shown when API is unreachable and mock data is displayed */}
      {error && symbols.length > 0 && (
        <div className='flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-400'>
          <span className='font-bold'>Demo data</span>
          <span className='text-amber-500/80'>· Scanner API unavailable — showing placeholder symbols, not live zone data.</span>
        </div>
      )}

      {/* Summary chips */}
      {!isLoading && symbols.length > 0 && (
        <div className='flex items-center gap-2 flex-wrap'>
          {(['ALL', 'buy', 'sell'] as SideFilter[]).map((f) => {
            const count =
              f === 'ALL'
                ? symbols.length
                : symbols.filter((s) => s.side === f).length;
            return (
              <button
                key={f}
                onClick={() => setSideFilter(f)}
                className={cn(
                  'flex items-center gap-1.5 rounded-full px-3 py-1 text-[10px] font-semibold border transition-colors',
                  sideFilter === f
                    ? f === 'buy'
                      ? 'bg-[#0ecb81]/15 text-[#0ecb81] border-[#0ecb81]/30'
                      : f === 'sell'
                      ? 'bg-[#f6465d]/15 text-[#f6465d] border-[#f6465d]/30'
                      : 'bg-[var(--to-warning)]/15 text-[var(--to-warning)] border-[var(--to-warning)]/30'
                    : 'bg-transparent text-[var(--to-text-dim)] border-[var(--to-border)] hover:text-[var(--to-text-secondary)]'
                )}
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {f === 'ALL' ? 'All' : f === 'buy' ? '▲ Long' : '▼ Short'}
                <span className='rounded-full bg-current/10 px-1.5 py-0.5 text-[9px]'>
                  {count}
                </span>
              </button>
            );
          })}
          <div
            className='ml-auto flex items-center gap-1.5 text-[10px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            <Filter className='h-3 w-3' />
            {filtered.length} symbols
          </div>
        </div>
      )}

      {/* Table */}
      <div className='glow-card overflow-hidden'>
        {isLoading ? (
          <div className='p-4 space-y-2'>
            {[...Array(6)].map((_, i) => (
              <Skeleton key={i} className='h-10 rounded-lg bg-[var(--to-surface-raised)]/60' />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className='p-4'>
            <PanelEmptyState
              title='No symbols found'
              description='No symbols match the current filter criteria.'
            />
          </div>
        ) : (
          <div className='overflow-x-auto'>
            <table className='w-full text-xs'>
              <thead>
                <tr className='border-b border-[var(--to-border)]'>
                  {[
                    { key: 'symbol' as SortKey, label: 'Symbol' },
                    { key: null, label: 'Side' },
                    { key: 'score' as SortKey, label: 'Score' },
                    { key: null, label: 'Zone' },
                    { key: null, label: 'Model' },
                    { key: null, label: 'TF' },
                    { key: 'distance_pips' as SortKey, label: 'Distance' },
                    { key: null, label: 'Session' },
                  ].map(({ key, label }) => (
                    <th
                      key={label}
                      className={cn(
                        'px-3 py-2.5 text-left text-[9px] font-bold uppercase tracking-wider text-[var(--to-text-dim)]',
                        key &&
                          'cursor-pointer hover:text-[var(--to-text-secondary)] select-none'
                      )}
                      style={{ fontFamily: 'var(--font-mono)' }}
                      onClick={() => key && toggleSort(key)}
                    >
                      {label} {key && <SortIndicator k={key} />}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((sym, i) => (
                  <tr
                    key={sym.symbol}
                    className={cn(
                      'border-b border-[var(--to-border)]/40 last:border-0 transition-colors hover:bg-[var(--to-surface-raised)]/50',
                      i % 2 === 0 ? '' : 'bg-white/[0.01]'
                    )}
                  >
                    <td className='px-3 py-2.5'>
                      <span
                        className='font-bold text-[var(--to-text-primary)]'
                        style={{ fontFamily: 'var(--font-mono)' }}
                      >
                        {sym.symbol}
                      </span>
                    </td>
                    <td className='px-3 py-2.5'>
                      <SideBadge side={sym.side} />
                    </td>
                    <td className='px-3 py-2.5 w-32'>
                      <ScoreBar score={sym.score} />
                    </td>
                    <td className='px-3 py-2.5'>
                      <span
                        className='rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase bg-[var(--to-surface-raised)] text-[var(--to-text-secondary)]'
                        style={{ fontFamily: 'var(--font-mono)' }}
                      >
                        {sym.zone_type || '—'}
                      </span>
                    </td>
                    <td
                      className='px-3 py-2.5 text-[var(--to-text-secondary)]'
                      style={{ fontFamily: 'var(--font-mono)' }}
                    >
                      {sym.entry_model || '—'}
                    </td>
                    <td
                      className='px-3 py-2.5 text-[var(--to-text-dim)]'
                      style={{ fontFamily: 'var(--font-mono)' }}
                    >
                      {sym.timeframe || '—'}
                    </td>
                    <td
                      className='px-3 py-2.5 tabular-nums text-[var(--to-text-secondary)]'
                      style={{ fontFamily: 'var(--font-mono)' }}
                    >
                      {sym.distance_pips > 0
                        ? `${sym.distance_pips} pips`
                        : '—'}
                    </td>
                    <td className='px-3 py-2.5'>
                      {sym.session && sym.session !== '—' ? (
                        <span
                          className='rounded px-1.5 py-0.5 text-[9px] font-semibold bg-indigo-500/10 text-indigo-400'
                          style={{ fontFamily: 'var(--font-mono)' }}
                        >
                          {sym.session}
                        </span>
                      ) : (
                        <span
                          className='text-[var(--to-text-dim)]'
                          style={{ fontFamily: 'var(--font-mono)' }}
                        >
                          —
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {error && (
        <p
          className='text-center text-[10px] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          Showing demo data — scanner API not connected
        </p>
      )}
    </div>
  );
}
