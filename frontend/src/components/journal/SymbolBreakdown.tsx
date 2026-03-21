'use client';

import { useMemo } from 'react';
import { TradingSignal, getPnl, getSymbol } from '@/types/trading';
import { cn } from '@/lib/utils';

interface SymbolBreakdownProps {
  signals: TradingSignal[];
  onSymbolClick: (symbol: string) => void;
}

interface SymbolRow {
  symbol: string;
  total: number;
  closed: number;
  wins: number;
  totalPnl: number;
  winRate: number | null;
  avgPnl: number | null;
  bestPnl: number | null;
  worstPnl: number | null;
}

export function SymbolBreakdown({ signals, onSymbolClick }: SymbolBreakdownProps) {
  const rows = useMemo<SymbolRow[]>(() => {
    const map = new Map<string, SymbolRow>();

    for (const s of signals) {
      const sym = getSymbol(s);
      if (!map.has(sym)) {
        map.set(sym, {
          symbol: sym,
          total: 0,
          closed: 0,
          wins: 0,
          totalPnl: 0,
          winRate: null,
          avgPnl: null,
          bestPnl: null,
          worstPnl: null,
        });
      }
      const row = map.get(sym)!;
      row.total++;
      const pnl = getPnl(s);
      if (pnl != null) {
        row.closed++;
        row.totalPnl += pnl;
        if (pnl > 0) row.wins++;
        row.bestPnl = row.bestPnl == null ? pnl : Math.max(row.bestPnl, pnl);
        row.worstPnl = row.worstPnl == null ? pnl : Math.min(row.worstPnl, pnl);
      }
    }

    return Array.from(map.values())
      .map((r) => ({
        ...r,
        winRate: r.closed > 0 ? (r.wins / r.closed) * 100 : null,
        avgPnl: r.closed > 0 ? r.totalPnl / r.closed : null,
      }))
      .sort((a, b) => b.totalPnl - a.totalPnl);
  }, [signals]);

  if (rows.length === 0) return null;

  // max abs PnL for bar scaling
  const maxAbs = Math.max(...rows.map((r) => Math.abs(r.totalPnl)), 1);

  return (
    <div className='rounded-xl border border-[#2a2e39] bg-[#0d1117] overflow-hidden'>
      <div className='px-4 py-3 border-b border-[#2a2e39]'>
        <span className='font-mono text-[12px] font-semibold text-[var(--to-text-primary)]'>
          Symbol Breakdown
        </span>
        <span className='ml-2 font-mono text-[10px] text-[var(--to-text-dim)]'>
          click to filter
        </span>
      </div>

      <div className='overflow-x-auto'>
        <table className='w-full'>
          <thead>
            <tr className='border-b border-[#2a2e39]'>
              {['Symbol', 'Trades', 'Win %', 'Avg PnL', 'Best', 'Worst', 'Total PnL'].map((h) => (
                <th
                  key={h}
                  className='py-2 px-3 text-left font-mono text-[9px] text-[var(--to-text-dim)] uppercase tracking-wider whitespace-nowrap'
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const pnlPos = row.totalPnl >= 0;
              const barWidth = (Math.abs(row.totalPnl) / maxAbs) * 100;
              return (
                <tr
                  key={row.symbol}
                  onClick={() => onSymbolClick(row.symbol)}
                  className='border-b border-[#2a2e39]/50 cursor-pointer hover:bg-[#1e222d]/60 transition-colors group'
                >
                  <td className='py-2.5 px-3'>
                    <div className='flex items-center gap-2'>
                      <span className='font-mono text-[11px] font-semibold text-[var(--to-text-primary)] group-hover:text-[var(--to-long)] transition-colors'>
                        {row.symbol}
                      </span>
                      {/* PnL bar */}
                      <div className='flex-1 h-1 rounded-full bg-[#2a2e39] min-w-[60px] max-w-[100px]'>
                        <div
                          className={cn(
                            'h-full rounded-full transition-all',
                            pnlPos ? 'bg-[var(--to-long)]' : 'bg-[var(--to-short)]',
                          )}
                          style={{ width: `${barWidth}%` }}
                        />
                      </div>
                    </div>
                  </td>
                  <td className='py-2.5 px-3 font-mono text-[11px] text-[var(--to-text-dim)]'>
                    {row.closed}/{row.total}
                  </td>
                  <td className='py-2.5 px-3'>
                    {row.winRate != null ? (
                      <span
                        className={cn(
                          'font-mono text-[11px] font-semibold',
                          row.winRate >= 50 ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]',
                        )}
                      >
                        {row.winRate.toFixed(0)}%
                      </span>
                    ) : (
                      <span className='font-mono text-[11px] text-[var(--to-text-dim)]'>--</span>
                    )}
                  </td>
                  <td className='py-2.5 px-3'>
                    {row.avgPnl != null ? (
                      <span
                        className={cn(
                          'font-mono text-[11px]',
                          row.avgPnl >= 0 ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]',
                        )}
                      >
                        {row.avgPnl >= 0 ? '+' : ''}${row.avgPnl.toFixed(2)}
                      </span>
                    ) : (
                      <span className='font-mono text-[11px] text-[var(--to-text-dim)]'>--</span>
                    )}
                  </td>
                  <td className='py-2.5 px-3 font-mono text-[11px] text-[var(--to-long)]'>
                    {row.bestPnl != null ? `+$${row.bestPnl.toFixed(2)}` : '--'}
                  </td>
                  <td className='py-2.5 px-3 font-mono text-[11px] text-[var(--to-short)]'>
                    {row.worstPnl != null ? `$${row.worstPnl.toFixed(2)}` : '--'}
                  </td>
                  <td className='py-2.5 px-3'>
                    <span
                      className={cn(
                        'font-mono text-[11px] font-semibold',
                        pnlPos ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]',
                      )}
                    >
                      {pnlPos ? '+' : ''}${row.totalPnl.toFixed(2)}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
