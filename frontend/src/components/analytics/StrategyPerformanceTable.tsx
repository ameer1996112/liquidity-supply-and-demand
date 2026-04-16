'use client';

import { cn } from '@/lib/utils';
import { PanelEmptyState } from '@/components/shared/PanelEmptyState';
import { Layers3 } from 'lucide-react';

interface StrategyPerformanceRow {
  strategyId: string;
  strategyVersion: string | null;
  label: string;
  pnl: number;
  count: number;
  wins: number;
  losses: number;
  winRate: number;
  avgPnl: number;
}

interface StrategyPerformanceTableProps {
  data: StrategyPerformanceRow[];
}

export function StrategyPerformanceTable({
  data,
}: StrategyPerformanceTableProps) {
  const rows = data.filter((row) => row.count >= 1);

  if (rows.length === 0) {
    return (
      <div className='glow-card p-4'>
        <PanelEmptyState
          title='No strategy data'
          description='Fresh strategy-tagged trades will appear here.'
        />
      </div>
    );
  }

  const maxAbsPnl = Math.max(...rows.map((row) => Math.abs(row.pnl)), 1);

  return (
    <div className='glow-card'>
      <div className='flex items-center gap-2 border-b border-[var(--to-border)] px-4 py-3'>
        <div className='flex h-7 w-7 items-center justify-center rounded-lg border border-[var(--to-accent)]/25 bg-[var(--to-accent)]/12'>
          <Layers3 className='h-3.5 w-3.5 text-[var(--to-accent)]' />
        </div>
        <div>
          <p className='panel-label'>Strategy Performance</p>
          <p
            className='mt-0.5 text-[10px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            {rows.length} strategy versions with realized PnL
          </p>
        </div>
      </div>

      <div className='overflow-x-auto'>
        <table className='w-full'>
          <thead>
            <tr className='border-b border-[var(--to-border)]'>
              {[
                'Strategy',
                'Trades',
                'W/L',
                'Win Rate',
                'Avg PnL',
                'Total PnL',
              ].map((header) => (
                <th
                  key={header}
                  className='px-4 py-2 text-left text-[9px] font-bold uppercase tracking-[0.15em] text-[var(--to-text-dim)]'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => {
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
                  key={`${row.strategyId}-${row.strategyVersion ?? 'none'}`}
                  className={cn(
                    'border-b border-[var(--to-border)]/50 transition-colors hover:bg-[var(--to-surface-raised)]/40',
                    index === 0 && 'bg-[var(--to-accent)]/5'
                  )}
                >
                  <td className='px-4 py-2.5'>
                    <div className='flex items-center gap-2'>
                      {index === 0 && (
                        <span
                          className='rounded px-1 py-0.5 text-[8px] font-black uppercase tracking-wider text-[var(--to-accent)]'
                          style={{
                            background:
                              'color-mix(in srgb, var(--to-accent) 12%, transparent)',
                            border:
                              '1px solid color-mix(in srgb, var(--to-accent) 25%, transparent)',
                            fontFamily: 'var(--font-mono)',
                          }}
                        >
                          Lead
                        </span>
                      )}
                      <div className='flex flex-col gap-0.5'>
                        <span
                          className='text-[11px] font-bold text-[var(--to-text-primary)]'
                          style={{ fontFamily: 'var(--font-mono)' }}
                        >
                          {row.strategyId}
                        </span>
                        <span
                          className='text-[9px] text-[var(--to-text-dim)]'
                          style={{ fontFamily: 'var(--font-mono)' }}
                        >
                          {row.strategyVersion ? `Version ${row.strategyVersion}` : 'Version not set'}
                        </span>
                      </div>
                    </div>
                  </td>
                  <td className='px-4 py-2.5'>
                    <span
                      className='text-[11px] tabular-nums text-[var(--to-text-secondary)]'
                      style={{ fontFamily: 'var(--font-mono)' }}
                    >
                      {row.count}
                    </span>
                  </td>
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
