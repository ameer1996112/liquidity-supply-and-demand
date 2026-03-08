'use client';

import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import type { BucketStats } from '@/hooks/usePerformanceAnalytics';
import { PanelEmptyState } from '@/components/shared/PanelEmptyState';
import { Target } from 'lucide-react';

interface SymbolPerformanceTableProps {
  data: Record<string, BucketStats>;
}

export function SymbolPerformanceTable({ data }: SymbolPerformanceTableProps) {
  const rows = useMemo(() => {
    return Object.entries(data)
      .filter(([, b]) => b.count >= 1)
      .map(([symbol, b]) => ({
        symbol,
        trades: b.count,
        wins: b.wins,
        losses: b.losses,
        winRate: b.win_rate,
        pnl: b.pnl,
        avgPnl: b.count > 0 ? b.pnl / b.count : 0,
      }))
      .sort((a, b) => b.pnl - a.pnl);
  }, [data]);

  if (rows.length === 0) {
    return (
      <div className='tv-card p-4'>
        <PanelEmptyState
          title='No symbol data'
          description='Trade more symbols to see performance breakdown.'
        />
      </div>
    );
  }

  const maxAbsPnl = Math.max(...rows.map((r) => Math.abs(r.pnl)), 1);

  return (
    <div className='tv-card'>
      {/* Header */}
      <div className='flex items-center gap-2 border-b border-[var(--to-border)] px-4 py-3'>
        <div className='flex h-7 w-7 items-center justify-center rounded-lg bg-[#3b82f6]/15 border border-[#3b82f6]/25'>
          <Target className='h-3.5 w-3.5 text-[#3b82f6]' />
        </div>
        <div>
          <p className='panel-label'>Symbol Performance</p>
          <p
            className='mt-0.5 text-[10px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            {rows.length} symbols traded
          </p>
        </div>
      </div>

      {/* Table */}
      <div className='overflow-x-auto'>
        <table className='w-full'>
          <thead>
            <tr className='border-b border-[var(--to-border)]'>
              {[
                'Symbol',
                'Trades',
                'W/L',
                'Win Rate',
                'Avg PnL',
                'Total PnL',
              ].map((h) => (
                <th
                  key={h}
                  className='px-4 py-2 text-left text-[9px] font-bold uppercase tracking-[0.15em] text-[var(--to-text-dim)]'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => {
              const winRateColor =
                row.winRate >= 60
                  ? '#0ecb81'
                  : row.winRate >= 50
                  ? '#f0b90b'
                  : '#f6465d';
              const pnlColor = row.pnl >= 0 ? '#0ecb81' : '#f6465d';
              const barWidth = (Math.abs(row.pnl) / maxAbsPnl) * 100;

              return (
                <tr
                  key={row.symbol}
                  className={cn(
                    'border-b border-[var(--to-border)]/50 transition-colors hover:bg-[var(--to-surface-raised)]/40',
                    idx === 0 && 'bg-[#0ecb81]/3'
                  )}
                >
                  {/* Symbol */}
                  <td className='px-4 py-2.5'>
                    <div className='flex items-center gap-2'>
                      {idx === 0 && (
                        <span
                          className='rounded px-1 py-0.5 text-[8px] font-black uppercase tracking-wider text-[#0ecb81]'
                          style={{
                            background: '#0ecb8115',
                            border: '1px solid #0ecb8125',
                            fontFamily: 'var(--font-mono)',
                          }}
                        >
                          TOP
                        </span>
                      )}
                      <span
                        className='text-[11px] font-bold text-[var(--to-text-primary)]'
                        style={{ fontFamily: 'var(--font-mono)' }}
                      >
                        {row.symbol}
                      </span>
                    </div>
                  </td>

                  {/* Trades */}
                  <td className='px-4 py-2.5'>
                    <span
                      className='text-[11px] tabular-nums text-[var(--to-text-secondary)]'
                      style={{ fontFamily: 'var(--font-mono)' }}
                    >
                      {row.trades}
                    </span>
                  </td>

                  {/* W/L */}
                  <td className='px-4 py-2.5'>
                    <span
                      className='text-[11px] tabular-nums'
                      style={{ fontFamily: 'var(--font-mono)' }}
                    >
                      <span className='text-[#0ecb81]'>{row.wins}</span>
                      <span className='text-[var(--to-text-dim)]'>/</span>
                      <span className='text-[#f6465d]'>{row.losses}</span>
                    </span>
                  </td>

                  {/* Win Rate with bar */}
                  <td className='px-4 py-2.5'>
                    <div className='flex items-center gap-2'>
                      <span
                        className='w-10 text-[11px] font-bold tabular-nums'
                        style={{
                          color: winRateColor,
                          fontFamily: 'var(--font-mono)',
                        }}
                      >
                        {row.winRate.toFixed(0)}%
                      </span>
                      <div className='h-1.5 w-16 overflow-hidden rounded-full bg-[#1e2329]'>
                        <div
                          className='h-full rounded-full transition-all duration-500'
                          style={{
                            width: `${Math.min(row.winRate, 100)}%`,
                            backgroundColor: winRateColor,
                          }}
                        />
                      </div>
                    </div>
                  </td>

                  {/* Avg PnL */}
                  <td className='px-4 py-2.5'>
                    <span
                      className='text-[11px] tabular-nums'
                      style={{
                        color: row.avgPnl >= 0 ? '#0ecb81' : '#f6465d',
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      {row.avgPnl >= 0 ? '+' : ''}${row.avgPnl.toFixed(2)}
                    </span>
                  </td>

                  {/* Total PnL with bar */}
                  <td className='px-4 py-2.5'>
                    <div className='flex items-center gap-2'>
                      <span
                        className='w-20 text-[11px] font-bold tabular-nums'
                        style={{
                          color: pnlColor,
                          fontFamily: 'var(--font-mono)',
                        }}
                      >
                        {row.pnl >= 0 ? '+' : ''}${row.pnl.toFixed(2)}
                      </span>
                      <div className='h-1.5 w-20 overflow-hidden rounded-full bg-[#1e2329]'>
                        <div
                          className='h-full rounded-full transition-all duration-500'
                          style={{
                            width: `${barWidth}%`,
                            backgroundColor: pnlColor,
                            opacity: 0.7,
                          }}
                        />
                      </div>
                    </div>
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
