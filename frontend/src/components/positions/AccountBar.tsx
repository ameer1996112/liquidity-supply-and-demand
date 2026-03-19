'use client';

import { useAccountStatus } from '@/hooks/usePositions';
import { cn } from '@/lib/utils';
import { Wallet } from 'lucide-react';

export function AccountMetric({
  label,
  value,
  colored,
}: {
  label: string;
  value: string;
  colored?: 'green' | 'red';
}) {
  return (
    <div className='flex flex-col items-center gap-0.5'>
      <span className='text-[10px] uppercase tracking-wider text-[var(--to-text-dim)] font-mono'>
        {label}
      </span>
      <span
        className={cn(
          'font-mono text-sm font-semibold tabular-nums',
          colored === 'green' && 'text-[var(--to-long)]',
          colored === 'red' && 'text-[var(--to-short)]',
          !colored && 'text-[var(--to-text-primary)]'
        )}
      >
        {value}
      </span>
    </div>
  );
}

export function AccountBar() {
  const { data: account } = useAccountStatus();

  if (!account) return null;

  const marginColor =
    account.margin_level_pct > 200
      ? 'green'
      : account.margin_level_pct > 100
        ? undefined
        : 'red';

  return (
    <div className='tv-card'>
      <div className='px-4 py-3 flex items-center gap-6'>
        <div className='flex items-center gap-2'>
          <Wallet className='w-4 h-4 text-[var(--to-text-dim)]' />
          <span className='font-mono text-xs text-[var(--to-text-dim)] uppercase tracking-wider'>
            Account
          </span>
        </div>

        <div className='flex items-center gap-6 ml-auto'>
          <AccountMetric
            label="Balance"
            value={`$${account.balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}`}
          />
          <AccountMetric
            label="Equity"
            value={`$${account.equity.toLocaleString('en-US', { minimumFractionDigits: 2 })}`}
            colored={account.equity >= account.balance ? 'green' : 'red'}
          />
          <AccountMetric
            label="Free Margin"
            value={`$${account.free_margin.toLocaleString('en-US', { minimumFractionDigits: 2 })}`}
          />
          <AccountMetric
            label="Margin Used"
            value={`$${account.margin_used.toLocaleString('en-US', { minimumFractionDigits: 2 })}`}
          />
          <AccountMetric
            label="Margin Level"
            value={`${account.margin_level_pct.toFixed(1)}%`}
            colored={marginColor as 'green' | 'red' | undefined}
          />
          <AccountMetric
            label="Positions"
            value={String(account.active_positions_count)}
          />
        </div>
      </div>
    </div>
  );
}
