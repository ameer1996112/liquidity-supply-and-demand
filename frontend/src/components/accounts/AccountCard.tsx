'use client';

import { type AccountComparisonApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { TrendingUp, TrendingDown, BarChart3 } from 'lucide-react';
import { PnLText } from '@/components/ui/typography';

interface AccountCardProps {
  account: AccountComparisonApi;
  className?: string;
}

export function AccountCard({ account, className }: AccountCardProps) {
  const dailyPositive = (account.daily_pnl ?? 0) >= 0;
  const winRatePct = (account.win_rate * 100).toFixed(1);

  return (
    <div
      className={cn(
        'tv-card p-4 flex flex-col gap-3',
        className
      )}
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm font-semibold text-[var(--to-text-primary)]">
          {account.account_name}
        </span>
        {account.strategy_type && (
          <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-surface-raised text-text-secondary">
            {account.strategy_type}
          </span>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex justify-between items-baseline">
          <span className="text-[10px] text-[var(--to-text-dim)] font-mono">Balance</span>
          <span className="font-mono text-sm font-bold text-[var(--to-text-primary)] tabular-nums">
            ${account.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </span>
        </div>

        <div className="flex justify-between items-center">
          <span className="text-[10px] text-[var(--to-text-dim)] font-mono">Daily PnL</span>
          <div className="flex items-center gap-1">
            {dailyPositive ? (
              <TrendingUp className="w-3 h-3 text-long" />
            ) : (
              <TrendingDown className="w-3 h-3 text-short" />
            )}
            <span className="font-mono text-xs font-semibold tabular-nums text-text-secondary">
              <PnLText
                value={account.daily_pnl ?? 0}
                variant="currency"
                size="sm"
              />
              <span className="text-[10px] ml-0.5 opacity-80">
                ({dailyPositive ? '+' : ''}{(account.daily_pnl_pct ?? 0).toFixed(2)}%)
              </span>
            </span>
          </div>
        </div>

        <div className="flex justify-between items-center">
          <span className="text-[10px] text-[var(--to-text-dim)] font-mono">Win Rate</span>
          <div className="flex items-center gap-1">
            <BarChart3 className="w-3 h-3 text-[var(--to-text-dim)]" />
            <span className="font-mono text-xs text-[var(--to-text-secondary)] tabular-nums">
              {winRatePct}%
            </span>
          </div>
        </div>

        {account.sharpe_ratio != null && (
          <div className="flex justify-between items-center">
            <span className="text-[10px] text-[var(--to-text-dim)] font-mono">Sharpe</span>
            <span className="font-mono text-xs text-[var(--to-text-dim)] tabular-nums">
              {account.sharpe_ratio.toFixed(2)}
            </span>
          </div>
        )}

        <div className="flex justify-between items-center pt-1 border-t border-panel-border-subtle">
          <span className="text-[10px] text-[var(--to-text-dim)] font-mono">Positions</span>
          <span className="font-mono text-xs text-[var(--to-text-dim)] tabular-nums">
            {account.active_positions}
            {account.total_trades != null ? ` / ${account.total_trades} trades` : ''}
          </span>
        </div>
      </div>
    </div>
  );
}
