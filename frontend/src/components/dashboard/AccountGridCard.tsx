'use client';

import { cn } from '@/lib/utils';
import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  WifiOff,
} from 'lucide-react';
import type { AccountComparisonApi } from '@/lib/api';

interface AccountGridCardProps {
  account: AccountComparisonApi;
  onClick: (account: AccountComparisonApi) => void;
}

// Returns 'normal' | 'warning' | 'danger' based on drawdown proximity
// Using a conservative 10% max drawdown threshold as default
function getDrawdownState(
  current: number | null | undefined
): 'normal' | 'warning' | 'danger' {
  if (!current || current <= 0) return 'normal';
  if (current >= 9) return 'danger';   // >= 90% of 10% limit
  if (current >= 7) return 'warning';  // >= 70% of 10% limit
  return 'normal';
}

export function AccountGridCard({ account, onClick }: AccountGridCardProps) {
  const isPropFirm =
    account.account_type === 'Funded' || account.account_type === 'Eval';
  const isConnected = account.connection_status === 'connected';
  const pnlPositive = (account.daily_pnl ?? 0) >= 0;

  const ddState = getDrawdownState(account.max_drawdown_pct);

  const borderClass = {
    normal: 'border-[var(--to-border)]',
    warning: 'border-amber-500/60',
    danger: 'border-[var(--to-short)]/80',
  }[ddState];

  const glowClass = {
    normal: '',
    warning: 'shadow-[0_0_12px_rgba(245,158,11,0.15)]',
    danger: 'shadow-[0_0_16px_rgba(239,83,80,0.25)] animate-pulse-slow',
  }[ddState];

  const typeColors: Record<string, string> = {
    Funded: 'text-[var(--to-long)] bg-[var(--to-long)]/10 border-[var(--to-long)]/20',
    Eval: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    Personal: 'text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] border-[var(--to-border)]',
  };

  const winRatePct = account.win_rate
    ? account.win_rate > 1
      ? account.win_rate
      : account.win_rate * 100
    : 0;

  return (
    <div
      onClick={() => onClick(account)}
      className={cn(
        'flex flex-col rounded-lg border bg-[var(--to-surface)] cursor-pointer',
        'transition-all duration-150 hover:bg-[var(--to-surface-raised)] hover:-translate-y-0.5',
        borderClass,
        glowClass
      )}
    >
      {/* ── Header ── */}
      <div className='flex items-center justify-between px-4 py-3 border-b border-[var(--to-border)]'>
        <div className='flex items-center gap-2 min-w-0'>
          <span
            className={cn(
              'h-1.5 w-1.5 rounded-full flex-shrink-0',
              isConnected ? 'bg-[var(--to-long)]' : 'bg-[var(--to-short)]'
            )}
          />
          <span className='font-mono text-sm font-bold text-[var(--to-text-primary)] truncate'>
            {account.account_name}
          </span>
          {!isConnected && (
            <WifiOff className='h-3 w-3 text-[var(--to-short)] flex-shrink-0' />
          )}
        </div>
        <div className='flex items-center gap-1.5 flex-shrink-0 ml-2'>
          {ddState !== 'normal' && (
            <AlertTriangle
              className={cn(
                'h-3 w-3',
                ddState === 'danger' ? 'text-[var(--to-short)]' : 'text-amber-400'
              )}
            />
          )}
          {account.account_type && (
            <span
              className={cn(
                'px-1.5 py-0.5 text-[9px] font-mono font-bold rounded uppercase tracking-wider border',
                typeColors[account.account_type] ?? typeColors.Personal
              )}
            >
              {account.account_type}
            </span>
          )}
        </div>
      </div>

      {/* ── Balance & PnL ── */}
      <div className='px-4 py-3 border-b border-[var(--to-border)]'>
        <div className='flex items-baseline justify-between mb-2'>
          <span className='text-[10px] text-[var(--to-text-dim)] font-mono'>Balance</span>
          <span className='font-mono text-base font-bold text-[var(--to-text-primary)] tabular-nums'>
            ${(account.balance ?? 0).toLocaleString(undefined, {
              minimumFractionDigits: 0,
              maximumFractionDigits: 0,
            })}
          </span>
        </div>
        <div className='flex items-center justify-between'>
          <span className='text-[10px] text-[var(--to-text-dim)] font-mono'>Today P&L</span>
          <div className='flex items-center gap-1'>
            {pnlPositive ? (
              <TrendingUp className='h-3 w-3 text-[var(--to-long)]' />
            ) : (
              <TrendingDown className='h-3 w-3 text-[var(--to-short)]' />
            )}
            <span
              className={cn(
                'font-mono text-sm font-bold tabular-nums',
                pnlPositive ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]'
              )}
            >
              {pnlPositive ? '+' : ''}${Math.abs(account.daily_pnl ?? 0).toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* ── Key Stats ── */}
      <div className='grid grid-cols-3 divide-x divide-[var(--to-border)]'>
        <StatCell label='Win Rate' value={`${winRatePct.toFixed(0)}%`} />
        <StatCell label='Positions' value={String(account.active_positions ?? account.open_positions ?? 0)} />
        <StatCell label='Trades' value={String(account.total_trades ?? 0)} />
      </div>

      {/* ── Prop Firm Drawdown (conditional) ── */}
      {isPropFirm && account.max_drawdown_pct != null && (
        <div className='px-4 py-3 border-t border-[var(--to-border)] space-y-2'>
          <ProgressRow
            label='Max Drawdown'
            current={Math.abs(account.max_drawdown_pct)}
            limit={10}
            state={ddState}
          />
        </div>
      )}
    </div>
  );
}

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div className='flex flex-col items-center py-2.5 gap-0.5'>
      <span className='text-[9px] text-[var(--to-text-dim)] font-mono'>{label}</span>
      <span className='font-mono text-xs font-semibold text-[var(--to-text-secondary)] tabular-nums'>
        {value}
      </span>
    </div>
  );
}

function ProgressRow({
  label,
  current,
  limit,
  state,
}: {
  label: string;
  current: number;
  limit: number;
  state: 'normal' | 'warning' | 'danger';
}) {
  const pct = limit > 0 ? Math.min((current / limit) * 100, 100) : 0;
  const barColor =
    state === 'danger'
      ? 'bg-[var(--to-short)]'
      : state === 'warning'
      ? 'bg-amber-400'
      : 'bg-[var(--to-long)]/50';

  const checkIcon =
    state === 'danger' ? '✗' : state === 'warning' ? '⚠' : '✓';

  const checkColor =
    state === 'danger'
      ? 'text-[var(--to-short)]'
      : state === 'warning'
      ? 'text-amber-400'
      : 'text-[var(--to-long)]';

  return (
    <div className='space-y-1'>
      <div className='flex items-center justify-between'>
        <span className='text-[9px] text-[var(--to-text-dim)] font-mono'>{label}</span>
        <div className='flex items-center gap-1'>
          <span className='text-[10px] text-[var(--to-text-secondary)] font-mono tabular-nums'>
            {current.toFixed(1)}% / {limit}%
          </span>
          <span className={cn('text-[10px] font-bold', checkColor)}>{checkIcon}</span>
        </div>
      </div>
      <div className='h-1 w-full rounded-full bg-[var(--to-surface-raised)] overflow-hidden'>
        <div
          className={cn('h-full rounded-full transition-all', barColor)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
