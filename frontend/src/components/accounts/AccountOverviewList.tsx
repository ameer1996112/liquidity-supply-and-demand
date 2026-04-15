'use client';

import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import type { AccountComparisonApi } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';
import { TrendingUp, TrendingDown, Wifi, WifiOff, AlertTriangle, Archive } from 'lucide-react';

interface AccountOverviewListProps {
  accounts: AccountComparisonApi[];
  isLoading?: boolean;
}

function StatusBadge({ status, strategyType }: { status: string; strategyType?: string }) {
  if (status === 'archived') {
    return (
      <span className='flex items-center gap-1 text-[10px] text-[var(--to-text-dim)]'>
        <Archive className='h-3 w-3' /> Archived
      </span>
    );
  }
  if (status === 'connected') {
    return (
      <span className='flex items-center gap-1 text-[10px] text-[var(--to-long)]'>
        <Wifi className='h-3 w-3' /> Connected
      </span>
    );
  }
  if (status === 'error') {
    return (
      <span className='flex items-center gap-1 text-[10px] text-[var(--to-short)]'>
        <AlertTriangle className='h-3 w-3' /> Error
      </span>
    );
  }
  if (strategyType === 'BROKER_PROFILE') {
    return (
      <span className='flex items-center gap-1 text-[10px] text-[var(--to-long)]'>
        <Wifi className='h-3 w-3' /> Enabled for trading
      </span>
    );
  }
  return (
    <span className='flex items-center gap-1 text-[10px] text-[var(--to-warning)]'>
      <WifiOff className='h-3 w-3' /> Disconnected
    </span>
  );
}

function TypeBadge({ type }: { type?: string }) {
  if (!type) return null;
  const cls: Record<string, string> = {
    Funded:
      'text-[var(--to-long)] bg-[var(--to-long)]/10 border-[var(--to-long)]/20',
    Eval: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    Personal:
      'text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] border-[var(--to-border)]',
  };
  return (
    <span
      className={cn(
        'px-1.5 py-0.5 text-[9px] font-mono font-bold rounded uppercase tracking-wider border',
        cls[type] ?? cls.Personal
      )}
    >
      {type}
    </span>
  );
}

function PnlCell({ value, pct }: { value: number; pct: number }) {
  const positive = value >= 0;
  return (
    <div
      className={cn(
        'flex items-center gap-1 font-mono text-xs font-semibold',
        positive ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]'
      )}
    >
      {positive ? (
        <TrendingUp className='h-3 w-3' />
      ) : (
        <TrendingDown className='h-3 w-3' />
      )}
      <span>
        {positive ? '+' : ''}${value.toFixed(2)}
      </span>
      <span className='text-[10px] opacity-75'>
        ({positive ? '+' : ''}
        {pct.toFixed(2)}%)
      </span>
    </div>
  );
}

function AccountCard({ account }: { account: AccountComparisonApi }) {
  const router = useRouter();

  return (
    <button
      id={`account-overview-card-${account.account_name
        .replace(/\s+/g, '-')
        .toLowerCase()}`}
      onClick={() =>
        router.push(`/accounts/${encodeURIComponent(account.account_name)}`)
      }
      className={cn(
        'w-full text-left rounded-xl border p-4 transition-all duration-150 group',
        'hover:shadow-[0_0_16px_rgba(0,0,0,0.25)] hover:border-[var(--to-border)]',
        account.is_archived
          ? 'border-[var(--to-border)] bg-[var(--to-surface-raised)]/40 opacity-60 hover:opacity-80'
          : 'border-[var(--to-border)] bg-[var(--to-surface)]',
        !account.is_archived && account.connection_status !== 'connected' && 'opacity-80'
      )}
    >
      {/* Header */}
      <div className='flex items-start justify-between gap-2 mb-3'>
        <div className='min-w-0'>
          <div className='flex items-center gap-2 flex-wrap'>
            <span className='font-mono font-bold text-sm text-[var(--to-text-primary)] truncate'>
              {account.account_name}
            </span>
            <TypeBadge type={account.account_type} />
            {account.provider && account.provider !== 'Personal' && (
              <span className='text-[9px] text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] border border-[var(--to-border)] rounded px-1.5 py-0.5 font-mono'>
                {account.provider}
              </span>
            )}
          </div>
          <div className='mt-1'>
            <StatusBadge
              status={account.connection_status || 'unknown'}
              strategyType={account.strategy_type}
            />
          </div>
        </div>
        <span className='text-[var(--to-text-dim)] group-hover:text-[var(--to-text-secondary)] transition-colors text-sm flex-shrink-0'>
          →
        </span>
      </div>

      {/* Metrics */}
      <div className='grid grid-cols-3 gap-3'>
        <div>
          <p className='text-[9px] uppercase tracking-wider text-[var(--to-text-dim)] mb-0.5'>
            Balance
          </p>
          <p className='font-mono text-xs font-semibold text-[var(--to-text-primary)]'>
            $
            {account.balance?.toLocaleString(undefined, {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            }) ?? '—'}
          </p>
        </div>
        <div>
          <p className='text-[9px] uppercase tracking-wider text-[var(--to-text-dim)] mb-0.5'>
            Equity
          </p>
          <p className='font-mono text-xs font-semibold text-[var(--to-text-primary)]'>
            $
            {account.equity?.toLocaleString(undefined, {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            }) ?? '—'}
          </p>
        </div>
        <div>
          <p className='text-[9px] uppercase tracking-wider text-[var(--to-text-dim)] mb-0.5'>
            Today
          </p>
          {typeof account.daily_pnl === 'number' ? (
            <PnlCell value={account.daily_pnl} pct={account.daily_pnl_pct ?? 0} />
          ) : (
            <p className='font-mono text-xs text-[var(--to-text-dim)]'>—</p>
          )}
        </div>
      </div>
    </button>
  );
}

export function AccountOverviewList({
  accounts,
  isLoading,
}: AccountOverviewListProps) {
  if (isLoading) {
    return (
      <div className='grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3'>
        {[1, 2, 3].map((i) => (
          <Skeleton
            key={i}
            className='h-28 w-full rounded-xl bg-[var(--to-surface-raised)]/60'
          />
        ))}
      </div>
    );
  }

  if (!accounts.length) {
    return (
      <div className='rounded-xl border border-dashed border-[var(--to-border)] py-12 text-center'>
        <p className='text-sm text-[var(--to-text-dim)]'>No accounts configured</p>
        <p className='text-[11px] text-[var(--to-text-dim)] mt-1'>
          Add an account below to get started
        </p>
      </div>
    );
  }

  const active = accounts.filter((a) => !a.is_archived);
  const archived = accounts.filter((a) => a.is_archived);

  return (
    <div className='space-y-4'>
      <div className='grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3'>
        {active.map((account) => (
          <AccountCard key={account.account_name} account={account} />
        ))}
      </div>

      {archived.length > 0 && (
        <div className='space-y-2'>
          <p className='text-[11px] uppercase tracking-wider text-[var(--to-text-dim)] px-1'>
            Archived — history only
          </p>
          <div className='grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3'>
            {archived.map((account) => (
              <AccountCard key={account.account_name} account={account} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
