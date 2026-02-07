'use client';

import { Users } from 'lucide-react';
import { AccountCard } from '@/components/accounts/AccountCard';
import { CopyConfigurator } from '@/components/accounts/CopyConfigurator';
import { CapitalAllocator } from '@/components/accounts/CapitalAllocator';
import { useAccountsComparison } from '@/hooks/useAccounts';
import { Skeleton } from '@/components/ui/skeleton';

export default function AccountsPage() {
  const { data: accounts = [], isLoading, error } = useAccountsComparison();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-zinc-100">
          Multi-Account Manager
        </h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          Manage multiple broker accounts (Funded, Eval, Personal) and copy
          trading.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-600">
          Failed to load accounts. Ensure the backend API is running, migrations
          are applied, and <code className="text-xs">account_strategies</code> or{' '}
          <code className="text-xs">broker_profiles</code> has data.
        </div>
      )}

      {/* Account Cards - Side-by-side comparison */}
      <section>
        <h2 className="text-sm font-medium text-zinc-300 mb-3 flex items-center gap-2">
          <Users className="h-4 w-4 text-emerald-500" />
          Account Comparison
        </h2>
        {isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-48 rounded-lg bg-[#1e222d]" />
            ))}
          </div>
        ) : accounts.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-lg border border-[#2a2e39] bg-[#1e222d]/50 py-12 text-zinc-500">
            <Users className="h-10 w-10 mb-3 opacity-50" />
            <p className="text-sm font-mono">No accounts configured</p>
            <p className="text-xs text-zinc-600 mt-1 max-w-md text-center">
              Add rows to <code className="text-[10px]">account_strategies</code> or{' '}
              <code className="text-[10px]">broker_profiles</code> and link them.
              Run migration 009 if needed.
            </p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {accounts.map((account) => (
              <AccountCard key={account.account_name} account={account} />
            ))}
          </div>
        )}
      </section>

      {/* Copy Configurator & Capital Allocator */}
      <div className="grid gap-6 md:grid-cols-2">
        <CopyConfigurator />
        <CapitalAllocator />
      </div>
    </div>
  );
}
