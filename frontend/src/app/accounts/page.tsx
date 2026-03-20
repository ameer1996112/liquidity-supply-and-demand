'use client';

import { useState } from 'react';
import { Users, Plus, Table2, LayoutGrid } from 'lucide-react';
import { EnhancedAccountCard } from '@/components/accounts/EnhancedAccountCard';
import { AccountsTable } from '@/components/accounts/AccountsTable';
import { CopyConfigurator } from '@/components/accounts/CopyConfigurator';
import { CapitalAllocator } from '@/components/accounts/CapitalAllocator';
import { AddAccountForm } from '@/components/accounts/AddAccountForm';
import { useAccountsComparison } from '@/hooks/useAccounts';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useToast } from '@/components/ui/toast';
import { getPortfolioControlUrl, type AccountDetailApi } from '@/lib/api';

type ViewMode = 'table' | 'cards';

export default function AccountsPage() {
  const [showAddForm, setShowAddForm] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const {
    data: rawAccounts = [] as AccountDetailApi[],
    isLoading,
    error,
  } = useAccountsComparison();
  const accounts = Array.isArray(rawAccounts) ? rawAccounts : [] as AccountDetailApi[];
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const deleteAccountMutation = useMutation({
    mutationFn: async (accountName: string) => {
      const url = getPortfolioControlUrl(
        `/accounts/${encodeURIComponent(accountName)}`
      );
      if (!url) throw new Error('Backend API URL not configured');
      const response = await fetch(url, { method: 'DELETE' });

      if (!response.ok) {
        let message = `Delete failed (${response.status})`;
        try {
          const body = await response.json();
          const detail =
            typeof body?.detail === 'string'
              ? body.detail
              : body?.detail?.join?.(' ') ?? body?.message;
          if (detail) message = detail;
        } catch {
          // response not JSON
        }
        throw new Error(message);
      }

      return response.json();
    },
    onSuccess: (_data, accountName) => {
      queryClient.invalidateQueries({
        queryKey: ['portfolio-control', 'accounts', 'comparison'],
      });
      addToast({
        title: 'Account deleted',
        message: `${accountName} has been removed successfully.`,
        severity: 'success',
        duration: 5000,
      });
    },
    onError: (err: Error, accountName) => {
      addToast({
        title: 'Delete failed',
        message: err.message || `Failed to delete ${accountName}`,
        severity: 'critical',
        duration: 8000,
      });
    },
  });

  const handleDeleteAccount = (accountName: string) => {
    deleteAccountMutation.mutate(accountName);
  };

  return (
    <div className='space-y-4'>
      {/* Header */}
      <div>
        <h1 className='page-title text-lg font-semibold'>
          Multi-Account Manager
        </h1>
        <p className='page-subtitle mt-0.5 text-xs'>
          Manage multiple broker accounts (Funded, Eval, Personal) and copy
          trading.
        </p>
      </div>

      {/* Error banner */}
      {error && (
        <div className='rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 text-xs text-amber-300'>
          Failed to load accounts. Ensure the backend API is running and
          migrations are applied.
        </div>
      )}

      {/* Account Comparison */}
      <section>
        <div className='mb-3 flex items-center justify-between'>
          <div className='flex items-center gap-2'>
            <Users className='h-3.5 w-3.5 text-[var(--to-text-dim)]' />
            <h2
              className='text-sm font-medium text-[var(--to-text-secondary)]'
              style={{ fontFamily: 'var(--font-sans)' }}
            >
              Account Comparison
            </h2>
          </div>
          <div className='flex items-center gap-2'>
            {/* View toggle */}
            <div className='surface-soft flex items-center gap-0.5 rounded-lg p-0.5'>
              <button
                onClick={() => setViewMode('table')}
                className={`flex items-center gap-1 rounded-md px-2.5 py-1 text-[11px] transition-colors ${
                  viewMode === 'table'
                    ? 'bg-indigo-600/20 text-indigo-300'
                    : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]'
                }`}
                style={{ fontFamily: 'var(--font-sans)' }}
              >
                <Table2 className='h-3 w-3' />
                Table
              </button>
              <button
                onClick={() => setViewMode('cards')}
                className={`flex items-center gap-1 rounded-md px-2.5 py-1 text-[11px] transition-colors ${
                  viewMode === 'cards'
                    ? 'bg-indigo-600/20 text-indigo-300'
                    : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]'
                }`}
                style={{ fontFamily: 'var(--font-sans)' }}
              >
                <LayoutGrid className='h-3 w-3' />
                Cards
              </button>
            </div>

            <Button
              variant='outline'
              size='sm'
              className='h-7 border-[var(--to-border)] bg-[var(--to-surface)] text-[var(--to-text-secondary)] hover:bg-[var(--to-surface-raised)] hover:text-[var(--to-text-primary)] text-xs'
              onClick={() => setShowAddForm(!showAddForm)}
            >
              <Plus className='mr-1 h-3 w-3' />
              Add account
            </Button>
          </div>
        </div>

        {showAddForm && (
          <div className='mb-3'>
            <AddAccountForm
              onSuccess={() => setShowAddForm(false)}
              onCancel={() => setShowAddForm(false)}
            />
          </div>
        )}

        {isLoading ? (
          <div className='space-y-2'>
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className='h-14 rounded-lg bg-[var(--to-surface-raised)]/60' />
            ))}
          </div>
        ) : accounts.length === 0 ? (
          <div className='glow-card'>
            <div className='empty-state py-14'>
              <span className='empty-state-text'>
                [ NO ACCOUNTS CONFIGURED ]
              </span>
              <span
                className='mt-1 text-[10px] text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                click &quot;Add account&quot; above or add rows to
                account_strategies
              </span>
            </div>
          </div>
        ) : viewMode === 'table' ? (
          <AccountsTable accounts={accounts} onDelete={handleDeleteAccount} />
        ) : (
          <div className='grid gap-3 sm:grid-cols-2 lg:grid-cols-3'>
            {accounts.map((account: AccountDetailApi) => (
              <EnhancedAccountCard
                key={account.account_name}
                account={account}
                onDelete={handleDeleteAccount}
              />
            ))}
          </div>
        )}
      </section>

      {/* Copy Configurator & Capital Allocator */}
      <div className='grid gap-4 md:grid-cols-2'>
        <CopyConfigurator />
        <CapitalAllocator />
      </div>
    </div>
  );
}
