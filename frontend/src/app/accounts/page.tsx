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
    data: accounts = [] as AccountDetailApi[],
    isLoading,
    error,
  } = useAccountsComparison();
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
          // response not JSON (e.g. HTML error page)
        }
        throw new Error(message);
      }

      return response.json();
    },
    onSuccess: (data, accountName) => {
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
    onError: (error: Error, accountName) => {
      addToast({
        title: 'Delete failed',
        message: error.message || `Failed to delete ${accountName}`,
        severity: 'critical',
        duration: 8000,
      });
    },
  });

  const handleDeleteAccount = (accountName: string) => {
    deleteAccountMutation.mutate(accountName);
  };

  return (
    <div className='space-y-6'>
      <div>
        <h1 className='page-title text-xl font-semibold'>
          Multi-Account Manager
        </h1>
        <p className='page-subtitle mt-1 text-sm'>
          Manage multiple broker accounts (Funded, Eval, Personal) and copy
          trading.
        </p>
      </div>

      {error && (
        <div className='rounded-xl border border-[rgba(255,177,79,0.42)] bg-[rgba(255,177,79,0.1)] px-4 py-3 text-sm text-[#ffd495]'>
          Failed to load accounts. Ensure the backend API is running, migrations
          are applied, and <code className='text-xs'>account_strategies</code>{' '}
          or <code className='text-xs'>broker_profiles</code> has data.
        </div>
      )}

      {/* Account Comparison */}
      <section>
        <div className='mb-3 flex items-center justify-between'>
          <h2 className='flex items-center gap-2 text-sm font-medium text-[#dce6fb]'>
            <Users className='h-4 w-4 text-[#2ec9aa]' />
            Account Comparison
          </h2>
          <div className='flex items-center gap-2'>
            {/* View Toggle */}
            <div className='surface-soft flex items-center gap-1 rounded-xl border border-[rgba(95,119,163,0.34)] p-0.5'>
              <button
                onClick={() => setViewMode('table')}
                className={`flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs transition-colors ${
                  viewMode === 'table'
                    ? 'bg-[rgba(46,201,170,0.2)] text-[#2ec9aa]'
                    : 'text-[#9cafd4] hover:text-[#ecf2ff]'
                }`}
              >
                <Table2 className='h-3.5 w-3.5' />
                Table
              </button>
              <button
                onClick={() => setViewMode('cards')}
                className={`flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs transition-colors ${
                  viewMode === 'cards'
                    ? 'bg-[rgba(46,201,170,0.2)] text-[#2ec9aa]'
                    : 'text-[#9cafd4] hover:text-[#ecf2ff]'
                }`}
              >
                <LayoutGrid className='h-3.5 w-3.5' />
                Cards
              </button>
            </div>

            <Button
              variant='outline'
              size='sm'
              className='border-[rgba(95,119,163,0.4)] bg-[rgba(17,26,44,0.9)] text-[#d4e0f9] hover:bg-[rgba(30,45,72,0.9)] hover:text-[#f5f8ff]'
              onClick={() => setShowAddForm(!showAddForm)}
            >
              <Plus className='mr-1.5 h-3.5 w-3.5' />
              Add account
            </Button>
          </div>
        </div>

        {showAddForm && (
          <div className='mb-4'>
            <AddAccountForm
              onSuccess={() => setShowAddForm(false)}
              onCancel={() => setShowAddForm(false)}
            />
          </div>
        )}

        {isLoading ? (
          <div className='space-y-2'>
            {[1, 2, 3].map((i) => (
              <Skeleton
                key={i}
                className='h-16 rounded-xl bg-[rgba(30,45,72,0.72)]'
              />
            ))}
          </div>
        ) : accounts.length === 0 ? (
          <div className='tv-card flex flex-col items-center justify-center py-12 text-[#a9b8d9]'>
            <Users className='mb-3 h-10 w-10 opacity-60' />
            <p className='font-mono text-sm'>No accounts configured</p>
            <p className='mt-1 max-w-md text-center text-xs text-[#8193b9]'>
              Click &quot;Add account&quot; above to create one, or add rows to{' '}
              <code className='text-[10px]'>account_strategies</code> in
              Supabase. Run migration 009 if needed.
            </p>
          </div>
        ) : viewMode === 'table' ? (
          <AccountsTable accounts={accounts} onDelete={handleDeleteAccount} />
        ) : (
          <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3'>
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
      <div className='grid gap-6 md:grid-cols-2'>
        <CopyConfigurator />
        <CapitalAllocator />
      </div>
    </div>
  );
}
