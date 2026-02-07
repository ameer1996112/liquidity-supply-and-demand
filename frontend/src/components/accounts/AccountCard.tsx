'use client';

import { type AccountComparisonApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { TrendingUp, TrendingDown, BarChart3 } from 'lucide-react';

interface AccountCardProps {
  account: AccountComparisonApi;
  className?: string;
}

export function AccountCard({ account, className }: AccountCardProps) {
  const dailyPositive = account.daily_pnl >= 0;
  const winRatePct = (account.win_rate * 100).toFixed(1);

  return (
    <div
      className={cn(
        'tv-card p-4 flex flex-col gap-3',
        className
      )}
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm font-semibold text-zinc-200">
          {account.account_name}
        </span>
        {account.strategy_type && (
          <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#2a2e39] text-zinc-500">
            {account.strategy_type}
          </span>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex justify-between items-baseline">
          <span className="text-[10px] text-zinc-600 font-mono">Balance</span>
          <span className="font-mono text-sm font-bold text-zinc-100 tabular-nums">
            ${account.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </span>
        </div>

        <div className="flex justify-between items-center">
          <span className="text-[10px] text-zinc-600 font-mono">Daily PnL</span>
          <div className="flex items-center gap-1">
            {dailyPositive ? (
              <TrendingUp className="w-3 h-3 text-[#26a69a]" />
            ) : (
              <TrendingDown className="w-3 h-3 text-[#ef5350]" />
            )}
            <span
              className={cn(
                'font-mono text-xs font-semibold tabular-nums',
                dailyPositive ? 'text-[#26a69a]' : 'text-[#ef5350]'
              )}
            >
              {dailyPositive ? '+' : ''}${account.daily_pnl.toFixed(2)}
              <span className="text-[10px] ml-0.5 opacity-80">
                ({dailyPositive ? '+' : ''}{account.daily_pnl_pct.toFixed(2)}%)
              </span>
            </span>
          </div>
        </div>

        <div className="flex justify-between items-center">
          <span className="text-[10px] text-zinc-600 font-mono">Win Rate</span>
          <div className="flex items-center gap-1">
            <BarChart3 className="w-3 h-3 text-zinc-500" />
            <span className="font-mono text-xs text-zinc-300 tabular-nums">
              {winRatePct}%
            </span>
          </div>
        </div>

        {account.sharpe_ratio != null && (
          <div className="flex justify-between items-center">
            <span className="text-[10px] text-zinc-600 font-mono">Sharpe</span>
            <span className="font-mono text-xs text-zinc-400 tabular-nums">
              {account.sharpe_ratio.toFixed(2)}
            </span>
          </div>
        )}

        <div className="flex justify-between items-center pt-1 border-t border-[#2a2e39]">
          <span className="text-[10px] text-zinc-600 font-mono">Positions</span>
          <span className="font-mono text-xs text-zinc-400 tabular-nums">
            {account.active_positions}
            {account.total_trades != null ? ` / ${account.total_trades} trades` : ''}
          </span>
        </div>
      </div>
    </div>
  );
}
