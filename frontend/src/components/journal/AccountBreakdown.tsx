'use client';

import { useMemo } from 'react';
import { TradingSignal, getPnl } from '@/types/trading';
import { cn } from '@/lib/utils';

interface AccountBreakdownProps {
  signals: TradingSignal[];
  activeAccount: string | null;
  onAccountSelect: (account: string | null) => void;
}

interface AccountRow {
  name: string;
  total: number;
  closed: number;
  wins: number;
  totalPnl: number;
  winRate: number | null;
  avgPnl: number | null;
}

export function AccountBreakdown({
  signals,
  activeAccount,
  onAccountSelect,
}: AccountBreakdownProps) {
  const rows = useMemo<AccountRow[]>(() => {
    const map = new Map<string, AccountRow>();

    for (const s of signals) {
      const name = s.account_name ?? 'Unknown';
      if (!map.has(name)) {
        map.set(name, { name, total: 0, closed: 0, wins: 0, totalPnl: 0, winRate: null, avgPnl: null });
      }
      const row = map.get(name)!;
      row.total++;
      const pnl = getPnl(s);
      if (pnl != null) {
        row.closed++;
        row.totalPnl += pnl;
        if (pnl > 0) row.wins++;
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

  return (
    <div className='rounded-xl border border-[#2a2e39] bg-[#0d1117] overflow-hidden'>
      {/* Header */}
      <div className='flex items-center justify-between px-4 py-3 border-b border-[#2a2e39]'>
        <span className='font-mono text-[12px] font-semibold text-[var(--to-text-primary)]'>
          Account Breakdown
        </span>
        {activeAccount && (
          <button
            onClick={() => onAccountSelect(null)}
            className='font-mono text-[10px] text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] transition-colors'
          >
            Clear filter ×
          </button>
        )}
      </div>

      {/* Table */}
      <div className='overflow-x-auto'>
        <table className='w-full'>
          <thead>
            <tr className='border-b border-[#2a2e39]'>
              {['Account', 'Trades', 'Closed', 'Win %', 'Avg PnL', 'Total PnL'].map((h) => (
                <th
                  key={h}
                  className='py-2 px-3 text-left font-mono text-[9px] text-[var(--to-text-dim)] uppercase tracking-wider'
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const isActive = activeAccount === row.name;
              const pnlPos = row.totalPnl >= 0;
              return (
                <tr
                  key={row.name}
                  onClick={() => onAccountSelect(isActive ? null : row.name)}
                  className={cn(
                    'border-b border-[#2a2e39]/50 cursor-pointer transition-colors hover:bg-[#1e222d]/60',
                    isActive && 'bg-[var(--to-long)]/5 border-l-2 border-l-[var(--to-long)]',
                  )}
                >
                  <td className='py-2.5 px-3'>
                    <span className='font-mono text-[11px] text-[var(--to-text-primary)]'>
                      {row.name}
                    </span>
                  </td>
                  <td className='py-2.5 px-3 font-mono text-[11px] text-[var(--to-text-dim)]'>
                    {row.total}
                  </td>
                  <td className='py-2.5 px-3 font-mono text-[11px] text-[var(--to-text-dim)]'>
                    {row.closed}
                  </td>
                  <td className='py-2.5 px-3'>
                    {row.winRate != null ? (
                      <span
                        className={cn(
                          'font-mono text-[11px] font-semibold',
                          row.winRate >= 50 ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]',
                        )}
                      >
                        {row.winRate.toFixed(1)}%
                      </span>
                    ) : (
                      <span className='text-[var(--to-text-dim)] text-[11px] font-mono'>--</span>
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
                      <span className='text-[var(--to-text-dim)] text-[11px] font-mono'>--</span>
                    )}
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
