'use client';

import { useState } from 'react';
import { TradingSignal, getPnl, getSymbol, getSide } from '@/types/trading';
import { Search } from 'lucide-react';
import { fetchSignals } from '@/lib/supabase';
import { useQuery } from '@tanstack/react-query';
import { format, subDays, isAfter } from 'date-fns';
import { PnLText } from '@/components/ui/typography';

// ── Types and constants ────────────────────────────────────────────────────────

type ScanMode = 'best' | 'worst' | 'active' | 'rejected' | 'recent';

interface ScanFilter {
  mode: ScanMode;
  minScore: number;
  days: number;
  symbol: string;
}

const SCAN_MODES: { key: ScanMode; label: string; color: string }[] = [
  { key: 'best', label: '🏆 Best Trades', color: '#0ecb81' },
  { key: 'worst', label: '💸 Worst Trades', color: '#f6465d' },
  { key: 'active', label: '⚡ Active Signals', color: '#3b82f6' },
  { key: 'rejected', label: '❌ Rejected', color: '#848e9c' },
  { key: 'recent', label: '🕐 Most Recent', color: '#a78bfa' },
];

// ── Score Bar ─────────────────────────────────────────────────────────────────

function ScoreBar({ score }: { score: number }) {
  const color = score >= 80 ? '#0ecb81' : score >= 60 ? '#f0b90b' : '#f6465d';
  return (
    <div className='flex items-center gap-2'>
      <div className='flex-1 h-1 rounded-full bg-[var(--to-surface-raised)]'>
        <div
          className='h-full rounded-full transition-all'
          style={{ width: `${score}%`, backgroundColor: color }}
        />
      </div>
      <span className='text-[10px] font-mono tabular-nums' style={{ color }}>
        {score}
      </span>
    </div>
  );
}

// ── Signal Row ────────────────────────────────────────────────────────────────

function SignalRow({ signal }: { signal: TradingSignal }) {
  const pnl = getPnl(signal);
  const sym = getSymbol(signal);
  const side = getSide(signal);
  const score =
    (signal.score ?? signal.ai_reasoning)
      ? typeof signal.ai_reasoning !== 'string'
        ? (((signal.ai_reasoning as Record<string, unknown>)
            ?.zone_score as number) ?? null)
        : null
      : null;

  return (
    <div className='flex items-center gap-3 px-3 py-2.5 border-b border-[var(--to-border)] hover:bg-[var(--to-surface-raised)] transition-colors'>
      <div className='flex-1 min-w-0'>
        <div className='flex items-center gap-2 mb-1'>
          <span className='font-mono font-semibold text-[12px] text-[var(--to-text-primary)]'>
            {sym}
          </span>
          <span
            className='px-1.5 py-0.5 rounded text-[9px] font-bold'
            style={{
              backgroundColor: side === 'buy' ? '#0ecb8120' : '#f6465d20',
              color: side === 'buy' ? '#0ecb81' : '#f6465d',
            }}
          >
            {side.toUpperCase()}
          </span>
          <span
            className='px-1.5 py-0.5 rounded text-[9px] font-mono'
            style={{
              backgroundColor: 'var(--to-surface-raised)',
              color: 'var(--to-text-dim)',
            }}
          >
            {(signal.status || '').replace('_', ' ').toUpperCase()}
          </span>
        </div>
        {score != null && <ScoreBar score={score} />}
      </div>
      <div className='text-right shrink-0'>
        {pnl != null ? (
          <PnLText value={pnl} variant='currency' size='sm' />
        ) : (
          <span className='text-[11px] text-[var(--to-text-dim)] font-mono'>
            {signal.entry != null ? `@ ${signal.entry}` : '—'}
          </span>
        )}
        <div className='text-[9px] text-[var(--to-text-dim)] font-mono mt-0.5'>
          {format(new Date(signal.created_at), 'MMM dd HH:mm')}
        </div>
      </div>
    </div>
  );
}

// ── Main Scanner ──────────────────────────────────────────────────────────────

export function SymbolScanner() {
  const [filter, setFilter] = useState<ScanFilter>({
    mode: 'best',
    minScore: 0,
    days: 30,
    symbol: '',
  });

  const { data: allSignals = [], isLoading } = useQuery({
    queryKey: ['scanner-signals'],
    queryFn: () => fetchSignals({ limit: 500 }),
    staleTime: 5 * 60_000,
  });

  const filtered = (() => {
    const cutoff = subDays(new Date(), filter.days);
    let base = (allSignals as TradingSignal[]).filter((s) => {
      if (!isAfter(new Date(s.created_at), cutoff)) return false;
      if (
        filter.symbol &&
        !getSymbol(s).toUpperCase().includes(filter.symbol.toUpperCase())
      )
        return false;
      const score =
        s.score ??
        (s.ai_reasoning && typeof s.ai_reasoning !== 'string'
          ? ((s.ai_reasoning as Record<string, unknown>).zone_score as number)
          : null);
      if (filter.minScore > 0 && (score == null || score < filter.minScore))
        return false;
      return true;
    });

    switch (filter.mode) {
      case 'best':
        return base
          .filter((s) => getPnl(s) != null)
          .sort((a, b) => (getPnl(b) ?? 0) - (getPnl(a) ?? 0))
          .slice(0, 20);
      case 'worst':
        return base
          .filter((s) => getPnl(s) != null)
          .sort((a, b) => (getPnl(a) ?? 0) - (getPnl(b) ?? 0))
          .slice(0, 20);
      case 'active':
        return base
          .filter(
            (s) =>
              ['active', 'open', 'executed'].includes(
                (s.status || '').toLowerCase(),
              ) && !s.closed_at,
          )
          .sort(
            (a, b) =>
              new Date(b.created_at).getTime() -
              new Date(a.created_at).getTime(),
          )
          .slice(0, 20);
      case 'rejected':
        return base
          .filter((s) =>
            ['ai_rejected', 'filtered'].includes(
              (s.status || '').toLowerCase(),
            ),
          )
          .sort(
            (a, b) =>
              new Date(b.created_at).getTime() -
              new Date(a.created_at).getTime(),
          )
          .slice(0, 20);
      case 'recent':
      default:
        return [...base]
          .sort(
            (a, b) =>
              new Date(b.created_at).getTime() -
              new Date(a.created_at).getTime(),
          )
          .slice(0, 20);
    }
  })();

  const totalProfit = filtered
    .filter((s) => (getPnl(s) ?? 0) > 0)
    .reduce((acc, s) => acc + (getPnl(s) ?? 0), 0);
  const totalLoss = filtered
    .filter((s) => (getPnl(s) ?? 0) < 0)
    .reduce((acc, s) => acc + (getPnl(s) ?? 0), 0);

  return (
    <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface)] overflow-hidden'>
      {/* Header */}
      <div className='px-4 py-3.5 border-b border-[var(--to-border)]'>
        <div className='flex items-center gap-2 mb-3'>
          <Search className='h-4 w-4 text-[#a78bfa]' />
          <span className='text-[13px] font-semibold text-[var(--to-text-primary)]'>
            Symbol Scanner
          </span>
          <span className='ml-auto text-[10px] text-[var(--to-text-dim)] font-mono'>
            {filtered.length} results
          </span>
        </div>
        {/* Scan Mode chips */}
        <div className='flex flex-wrap gap-1.5 mb-3'>
          {SCAN_MODES.map((m) => (
            <button
              key={m.key}
              onClick={() => setFilter((f) => ({ ...f, mode: m.key }))}
              className='rounded-full border px-2.5 py-1 text-[10px] transition-all'
              style={{
                borderColor:
                  filter.mode === m.key ? m.color : 'var(--to-border)',
                backgroundColor:
                  filter.mode === m.key
                    ? `${m.color}15`
                    : 'var(--to-surface-raised)',
                color:
                  filter.mode === m.key ? m.color : 'var(--to-text-secondary)',
              }}
            >
              {m.label}
            </button>
          ))}
        </div>
        {/* Filter row */}
        <div className='flex items-center gap-2'>
          <div className='relative flex-1'>
            <Search className='absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-[var(--to-text-dim)]' />
            <input
              value={filter.symbol}
              onChange={(e) =>
                setFilter((f) => ({ ...f, symbol: e.target.value }))
              }
              placeholder='Filter by symbol…'
              className='w-full rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] pl-7 pr-3 py-1.5 text-[11px] text-[var(--to-text-primary)] placeholder:text-[var(--to-text-dim)] outline-none focus:border-[#a78bfa]/50'
            />
          </div>
          <select
            value={filter.days}
            onChange={(e) =>
              setFilter((f) => ({ ...f, days: Number(e.target.value) }))
            }
            className='rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-2 py-1.5 text-[11px] text-[var(--to-text-secondary)] outline-none'
          >
            <option value={7}>7d</option>
            <option value={14}>14d</option>
            <option value={30}>30d</option>
            <option value={90}>90d</option>
            <option value={365}>1yr</option>
          </select>
          <select
            value={filter.minScore}
            onChange={(e) =>
              setFilter((f) => ({ ...f, minScore: Number(e.target.value) }))
            }
            className='rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-2 py-1.5 text-[11px] text-[var(--to-text-secondary)] outline-none'
          >
            <option value={0}>All scores</option>
            <option value={60}>Score ≥ 60</option>
            <option value={70}>Score ≥ 70</option>
            <option value={80}>Score ≥ 80</option>
            <option value={90}>Score ≥ 90</option>
          </select>
        </div>
      </div>

      {/* Summary bar */}
      {filtered.some((s) => getPnl(s) != null) && (
        <div className='flex items-center gap-4 px-4 py-2 border-b border-[var(--to-border)] bg-[var(--to-surface-raised)]'>
          <span className='text-[10px] text-[var(--to-text-dim)] font-mono'>
            Filtered results:
          </span>
          {totalProfit > 0 && (
            <span className='text-[10px] font-mono font-semibold text-[#0ecb81]'>
              +${totalProfit.toFixed(2)} wins
            </span>
          )}
          {totalLoss < 0 && (
            <span className='text-[10px] font-mono font-semibold text-[#f6465d]'>
              -${Math.abs(totalLoss).toFixed(2)} losses
            </span>
          )}
          <span className='text-[10px] font-mono text-[var(--to-text-dim)] ml-auto'>
            Net:{' '}
            <span
              style={{
                color: totalProfit + totalLoss >= 0 ? '#0ecb81' : '#f6465d',
              }}
            >
              ${(totalProfit + totalLoss).toFixed(2)}
            </span>
          </span>
        </div>
      )}

      {/* Results */}
      <div className='max-h-96 overflow-y-auto scrollbar-thin'>
        {isLoading ? (
          <div className='flex items-center justify-center py-12'>
            <div className='h-6 w-6 rounded-full border-2 border-[#a78bfa] border-t-transparent animate-spin' />
          </div>
        ) : filtered.length === 0 ? (
          <div className='text-center py-12 text-[12px] text-[var(--to-text-dim)]'>
            No signals match the current filters
          </div>
        ) : (
          filtered.map((sig) => <SignalRow key={sig.id} signal={sig} />)
        )}
      </div>
    </div>
  );
}
