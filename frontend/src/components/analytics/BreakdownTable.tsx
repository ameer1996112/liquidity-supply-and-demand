'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import type { BucketStats } from '@/hooks/usePerformanceAnalytics';
import { ArrowUpDown } from 'lucide-react';

interface BreakdownTableProps {
  title: string;
  data: Record<string, BucketStats>;
}

type SortKey = 'key' | 'count' | 'wins' | 'losses' | 'win_rate' | 'pnl';

export function BreakdownTable({ title, data }: BreakdownTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('pnl');
  const [sortAsc, setSortAsc] = useState(false);

  const entries = Object.entries(data);
  const sorted = [...entries].sort(([aKey, aVal], [bKey, bVal]) => {
    let aV: number | string;
    let bV: number | string;

    if (sortKey === 'key') {
      aV = aKey;
      bV = bKey;
    } else {
      aV = aVal[sortKey];
      bV = bVal[sortKey];
    }

    if (aV < bV) return sortAsc ? -1 : 1;
    if (aV > bV) return sortAsc ? 1 : -1;
    return 0;
  });

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  if (entries.length === 0) {
    return (
      <div className="tv-card p-6 text-center">
        <span className="text-xs text-zinc-600 font-mono">No data</span>
      </div>
    );
  }

  return (
    <div className="tv-card">
      <div className="px-4 py-3 border-b border-[#2a2e39]">
        <span className="font-mono text-xs text-zinc-400 uppercase tracking-wider">
          {title}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#2a2e39]">
              {(
                [
                  ['key', 'Dimension'],
                  ['count', 'Trades'],
                  ['wins', 'Wins'],
                  ['losses', 'Losses'],
                  ['win_rate', 'Win %'],
                  ['pnl', 'PnL'],
                ] as [SortKey, string][]
              ).map(([key, label]) => (
                <th
                  key={key}
                  onClick={() => toggleSort(key)}
                  className="px-3 py-2 text-left text-[10px] text-zinc-500 font-mono uppercase tracking-wider cursor-pointer hover:text-zinc-300 transition-colors"
                >
                  <span className="flex items-center gap-1">
                    {label}
                    <ArrowUpDown className="w-2.5 h-2.5" />
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map(([key, stats]) => (
              <tr
                key={key}
                className="border-b border-[#2a2e39] last:border-b-0 hover:bg-[#1e222d]/50"
              >
                <td className="px-3 py-2 font-mono text-xs text-zinc-300">
                  {key}
                </td>
                <td className="px-3 py-2 font-mono text-xs tabular-nums text-zinc-400">
                  {stats.count}
                </td>
                <td className="px-3 py-2 font-mono text-xs tabular-nums text-[#26a69a]">
                  {stats.wins}
                </td>
                <td className="px-3 py-2 font-mono text-xs tabular-nums text-[#ef5350]">
                  {stats.losses}
                </td>
                <td className="px-3 py-2 font-mono text-xs tabular-nums text-zinc-300">
                  {stats.win_rate.toFixed(1)}%
                </td>
                <td
                  className={cn(
                    'px-3 py-2 font-mono text-xs font-semibold tabular-nums',
                    stats.pnl > 0 && 'text-[#26a69a]',
                    stats.pnl < 0 && 'text-[#ef5350]',
                    stats.pnl === 0 && 'text-zinc-500',
                  )}
                >
                  {stats.pnl >= 0 ? '+' : ''}${stats.pnl.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
