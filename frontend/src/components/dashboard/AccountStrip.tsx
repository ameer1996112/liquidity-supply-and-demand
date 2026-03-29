'use client';

import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import type { AccountComparisonApi } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';

interface AccountStripProps {
  accounts: AccountComparisonApi[];
  isLoading?: boolean;
  /** Which account is currently selected (filters signal table below) */
  activeAccount?: string | undefined;
  /** Called when user clicks a row — pass account_name to filter, or undefined to clear */
  onAccountSelect?: (accountName: string | undefined) => void;
  /** Signal counts per account_name — shown as badge on each row */
  signalCounts?: Record<string, number>;
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

export function AccountStrip({
  accounts,
  isLoading,
  activeAccount,
  onAccountSelect,
  signalCounts = {},
}: AccountStripProps) {
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
      {accounts.map((account, idx) => {
        const isActive = activeAccount === account.account_name;
        const sigCount = signalCounts[account.account_name] ?? 0;

        return (
          <div
            key={account.account_name}
            className={cn(
              'w-full flex items-center justify-between px-3 py-2 transition-colors',
              idx !== accounts.length - 1 && 'border-b border-[var(--to-border)]',
              isActive
                ? 'bg-[var(--to-surface-raised)]'
                : 'hover:bg-[var(--to-surface-raised)]/60',
            )}
          >
            {/* Left: click to filter signals */}
            <button
              id={`account-strip-filter-${account.account_name.replace(/\s+/g, '-').toLowerCase()}`}
              onClick={() =>
                onAccountSelect?.(isActive ? undefined : account.account_name)
              }
              className='flex items-center gap-3 min-w-0 flex-1 text-left'
            >
              <ConnectionDot status={account.connection_status || 'unknown'} />
              <span
                className={cn(
                  'font-mono text-xs font-semibold truncate transition-colors',
                  isActive
                    ? 'text-[var(--to-text-primary)]'
                    : 'text-[var(--to-text-secondary)]',
                )}
              >
                {account.account_name}
              </span>
              {account.account_type && (
                <span className='hidden sm:inline text-[9px] text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] border border-[var(--to-border)] rounded px-1.5 py-0.5 font-mono'>
                  {account.account_type}
                </span>
              )}
              {/* Signal count badge */}
              {sigCount > 0 && (
                <span
                  className={cn(
                    'text-[9px] font-mono px-1.5 py-0.5 rounded-full border tabular-nums',
                    isActive
                      ? 'bg-[var(--to-long)]/15 border-[var(--to-long)]/30 text-[var(--to-long)]'
                      : 'bg-[var(--to-surface-raised)] border-[var(--to-border)] text-[var(--to-text-dim)]',
                  )}
                >
                  {sigCount}
                </span>
              )}
            </button>

            {/* Right: balance + navigate arrow */}
            <div className='flex items-center gap-3 flex-shrink-0 pl-2'>
              <span className='font-mono text-xs text-[var(--to-text-secondary)]'>
                $
                {account.balance?.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                }) ?? '—'}
              </span>
              <button
                id={`account-strip-nav-${account.account_name.replace(/\s+/g, '-').toLowerCase()}`}
                onClick={() =>
                  router.push(`/accounts/${encodeURIComponent(account.account_name)}`)
                }
                className='text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)] transition-colors text-[11px] px-1'
                title={`Go to ${account.account_name} details`}
              >
                →
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
