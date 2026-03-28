'use client';

import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import type { AccountComparisonApi } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';

interface AccountStripProps {
  accounts: AccountComparisonApi[];
  isLoading?: boolean;
}

function ConnectionDot({ status }: { status: string }) {
  const cls =
    status === 'connected'
      ? 'bg-[var(--to-long)]'
      : status === 'error'
      ? 'bg-[var(--to-short)]'
      : 'bg-[var(--to-warning)]';

  const label =
    status === 'connected'
      ? 'Connected'
      : status === 'error'
      ? 'Error'
      : 'Disconnected';

  const textCls =
    status === 'connected'
      ? 'text-[var(--to-long)]'
      : status === 'error'
      ? 'text-[var(--to-short)]'
      : 'text-[var(--to-warning)]';

  return (
    <span className='flex items-center gap-1.5'>
      <span className={cn('h-1.5 w-1.5 rounded-full flex-shrink-0', cls)} />
      <span className={cn('text-[10px] font-mono', textCls)}>{label}</span>
    </span>
  );
}

export function AccountStrip({ accounts, isLoading }: AccountStripProps) {
  const router = useRouter();

  if (isLoading) {
    return (
      <div className='space-y-1'>
        {[1, 2, 3].map((i) => (
          <Skeleton
            key={i}
            className='h-8 w-full rounded-lg bg-[var(--to-surface-raised)]/60'
          />
        ))}
      </div>
    );
  }

  if (!accounts.length) {
    return (
      <div className='rounded-lg border border-dashed border-[var(--to-border)] py-4 text-center'>
        <p className='text-xs text-[var(--to-text-dim)]'>No accounts configured</p>
      </div>
    );
  }

  return (
    <div className='rounded-xl border border-[var(--to-border)] overflow-hidden'>
      {accounts.map((account, idx) => (
        <button
          key={account.account_name}
          id={`account-strip-row-${account.account_name.replace(/\s+/g, '-').toLowerCase()}`}
          onClick={() =>
            router.push(`/accounts/${encodeURIComponent(account.account_name)}`)
          }
          className={cn(
            'w-full flex items-center justify-between px-3 py-2 text-left transition-colors',
            'hover:bg-[var(--to-surface-raised)] group',
            idx !== accounts.length - 1 && 'border-b border-[var(--to-border)]'
          )}
        >
          <div className='flex items-center gap-3 min-w-0'>
            <ConnectionDot status={account.connection_status || 'unknown'} />
            <span className='font-mono text-xs font-semibold text-[var(--to-text-primary)] truncate'>
              {account.account_name}
            </span>
            {account.account_type && (
              <span className='hidden sm:inline text-[9px] text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] border border-[var(--to-border)] rounded px-1.5 py-0.5 font-mono'>
                {account.account_type}
              </span>
            )}
          </div>
          <div className='flex items-center gap-4 flex-shrink-0'>
            <span className='font-mono text-xs text-[var(--to-text-secondary)]'>
              $
              {account.balance?.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              }) ?? '—'}
            </span>
            <span className='text-[var(--to-text-dim)] group-hover:text-[var(--to-text-secondary)] transition-colors text-[10px]'>
              →
            </span>
          </div>
        </button>
      ))}
    </div>
  );
}
