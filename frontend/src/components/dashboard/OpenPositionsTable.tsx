'use client';

import { useMemo, useState } from 'react';
import { cn } from '@/lib/utils';
import { ChevronDown } from 'lucide-react';
import type { ActivePosition } from '@/hooks/usePositions';

interface OpenPositionsTableProps {
  positions: ActivePosition[];
  isLoading: boolean;
  isFallback?: boolean;
  onRowClick?: () => void;
}

type SortKey = 'pnl' | 'duration' | 'symbol';

export function OpenPositionsTable({
  positions,
  isLoading,
  isFallback = false,
  onRowClick,
}: OpenPositionsTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('pnl');

  const grouped = useMemo(() => {
    const sorted = [...positions].sort((a, b) => {
      if (sortKey === 'pnl') return (b.live_pnl ?? 0) - (a.live_pnl ?? 0);
      if (sortKey === 'symbol') return (a.symbol ?? '').localeCompare(b.symbol ?? '');
      if (sortKey === 'duration') return b.hold_duration_seconds - a.hold_duration_seconds;
      return 0;
    });

    const groups = new Map<string, ActivePosition[]>();
    for (const position of sorted) {
      const accountName = position.account_name?.trim() || 'Unassigned';
      const existing = groups.get(accountName);
      if (existing) {
        existing.push(position);
      } else {
        groups.set(accountName, [position]);
      }
    }

    return Array.from(groups.entries()).sort((left, right) => left[0].localeCompare(right[0]));
  }, [positions, sortKey]);

  function formatDuration(seconds: number): string {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  }

  const SortHeader = ({ label, sk }: { label: string; sk: SortKey }) => (
    <th
      className='cursor-pointer select-none px-3 py-2 text-left text-[9px] uppercase tracking-widest text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] transition-colors'
      onClick={() => setSortKey(sk)}
    >
      <span className='flex items-center gap-1'>
        {label}
        {sortKey === sk && <ChevronDown className='h-2.5 w-2.5' />}
      </span>
    </th>
  );

  return (
    <section className='glow-card overflow-hidden'>
      <div className='to-panel-header'>
        <div className='flex items-center gap-2'>
          <span className='panel-label'>Open Positions</span>
          <span className='rounded-full bg-[var(--to-surface-raised)] border border-[var(--to-border)] px-2 py-0.5 font-mono text-[9px] tabular-nums text-[var(--to-text-dim)]'>
            {positions.length}
          </span>
          {isFallback && positions.length > 0 ? (
            <span className='rounded-full border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>
              Signal fallback
            </span>
          ) : null}
        </div>
      </div>

      {isLoading ? (
        <div className='px-4 py-6 text-center text-[11px] text-[var(--to-text-dim)] font-mono'>
          Loading positions...
        </div>
      ) : grouped.length === 0 ? (
        <div className='px-4 py-6 text-center text-[11px] text-[var(--to-text-dim)] font-mono'>
          No open positions
        </div>
      ) : (
        <div className='overflow-x-auto'>
          <table className='w-full text-xs'>
            <thead className='border-b border-[var(--to-border)] bg-[var(--to-surface)]'>
              <tr>
                <SortHeader label='Symbol' sk='symbol' />
                <th className='px-3 py-2 text-left text-[9px] uppercase tracking-widest text-[var(--to-text-dim)]'>
                  Side
                </th>
                <th className='px-3 py-2 text-left text-[9px] uppercase tracking-widest text-[var(--to-text-dim)]'>
                  Size
                </th>
                <th className='px-3 py-2 text-right text-[9px] uppercase tracking-widest text-[var(--to-text-dim)]'>
                  Entry
                </th>
                <SortHeader label='P&L' sk='pnl' />
                <SortHeader label='Duration' sk='duration' />
              </tr>
            </thead>
            {grouped.map(([accountName, accountPositions]) => (
              <tbody key={accountName} className='divide-y divide-[var(--to-border)]'>
                <tr key={`${accountName}-header`} className='bg-[var(--to-surface)]/70'>
                  <td
                    colSpan={6}
                    className='px-3 py-2 font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--to-text-dim)]'
                  >
                    <span className='flex items-center justify-between gap-3'>
                      <span>{accountName}</span>
                      <span className='rounded-full border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-2 py-0.5 text-[9px] tabular-nums text-[var(--to-text-secondary)]'>
                        {accountPositions.length} open
                      </span>
                    </span>
                  </td>
                </tr>
                {accountPositions.map((pos) => {
                  const pnlPositive = (pos.live_pnl ?? 0) >= 0;
                  const isLong = pos.side?.toUpperCase() === 'BUY' || pos.side?.toUpperCase() === 'LONG';
                  return (
                    <tr
                      key={pos.id}
                      className='hover:bg-[var(--to-surface-raised)] transition-colors cursor-pointer'
                      onClick={() => onRowClick?.()}
                    >
                      <td className='px-3 py-2 font-mono font-semibold text-[var(--to-text-primary)]'>
                        <div className='flex flex-col gap-1'>
                          <span>{pos.symbol}</span>
                          <span className='text-[9px] font-medium uppercase tracking-[0.18em] text-[var(--to-text-dim)]'>
                            {accountName}
                          </span>
                        </div>
                      </td>
                      <td className='px-3 py-2'>
                        <span
                          className={cn(
                            'flex items-center gap-0.5 font-mono text-[10px] font-bold',
                            isLong ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]'
                          )}
                        >
                          <span className='h-1.5 w-1.5 rounded-full bg-current' />
                          {isLong ? 'LONG' : 'SHORT'}
                        </span>
                      </td>
                      <td className='px-3 py-2 font-mono text-[var(--to-text-secondary)] tabular-nums'>
                        {(pos.size ?? 0).toFixed(2)}L
                      </td>
                      <td className='px-3 py-2 text-right font-mono text-[var(--to-text-secondary)] tabular-nums'>
                        {pos.entry != null ? pos.entry.toFixed(5) : '—'}
                      </td>
                      <td className='px-3 py-2'>
                        <span
                          className={cn(
                            'font-mono font-bold tabular-nums',
                            pnlPositive ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]'
                          )}
                        >
                          {pnlPositive ? '+' : ''}${Math.abs(pos.live_pnl ?? 0).toFixed(2)}
                        </span>
                      </td>
                      <td className='px-3 py-2 font-mono text-[var(--to-text-dim)] tabular-nums'>
                        {formatDuration(pos.hold_duration_seconds)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            ))}
          </table>
        </div>
      )}
    </section>
  );
}
