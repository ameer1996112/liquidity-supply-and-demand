'use client';

import { Plus } from 'lucide-react';
import { AccountGridCard } from './AccountGridCard';
import type { AccountComparisonApi } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';

interface AccountGridProps {
  accounts: AccountComparisonApi[];
  isLoading: boolean;
  onSelectAccount: (account: AccountComparisonApi) => void;
  onAddAccount: () => void;
}

export function AccountGrid({
  accounts,
  isLoading,
  onSelectAccount,
  onAddAccount,
}: AccountGridProps) {
  if (isLoading) {
    return (
      <div className='grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3'>
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton
            key={i}
            className='h-52 rounded-lg border border-[var(--to-border)] skeleton-shimmer'
          />
        ))}
      </div>
    );
  }

  return (
    <div className='grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3'>
      {accounts.map((account) => (
        <AccountGridCard
          key={account.account_name}
          account={account}
          onClick={onSelectAccount}
        />
      ))}

      {/* Add account button */}
      <button
        onClick={onAddAccount}
        className='flex min-h-[140px] flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--to-border)] bg-transparent text-[var(--to-text-dim)] transition-colors hover:border-[var(--to-long)]/50 hover:text-[var(--to-long)]/70 cursor-pointer'
      >
        <Plus className='h-5 w-5' />
        <span className='text-[11px] font-mono'>Add account</span>
      </button>
    </div>
  );
}
