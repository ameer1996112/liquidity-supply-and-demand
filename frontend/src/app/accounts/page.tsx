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
import { getPortfolioControlUrl } from '@/lib/api';

type ViewMode = 'table' | 'cards';

export default function AccountsPage() {
  const [showAddForm, setShowAddForm] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const { data: accounts = [], isLoading, error } = useAccountsComparison();
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const deleteAccountMutation = useMutation({
    mutationFn: async (accountName: string) => {
      const url = getPortfolioControlUrl(`/accounts/${encodeURIComponent(accountName)}`);
      if (!url) throw new Error('Backend API URL not configured');
      const response = await fetch(url, { method: 'DELETE' });

      if (!response.ok) {
        let message = `Delete failed (${response.status})`;
        try {
          const body = await response.json();
          const detail = typeof body?.detail === 'string' ? body.detail : body?.detail?.join?.(' ') ?? body?.message;
          if (detail) message = detail;
        } catch {
          // response not JSON (e.g. HTML error page)
        }
        throw new Error(message);
      }

      return response.json();
    },
    onSuccess: (data, accountName) => {
      queryClient.invalidateQueries({ queryKey: ['portfolio-control', 'accounts', 'comparison'] });
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

      {/* Account Comparison */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-zinc-300 flex items-center gap-2">
            <Users className="h-4 w-4 text-emerald-500" />
            Account Comparison
          </h2>
          <div className="flex items-center gap-2">
            {/* View Toggle */}
            <div className="flex items-center gap-1 rounded border border-[#2a2e39] bg-[#1e222d] p-0.5">
              <button
                onClick={() => setViewMode('table')}
                className={`px-2 py-1 rounded text-xs flex items-center gap-1 transition-colors ${
                  viewMode === 'table'
                    ? 'bg-emerald-500/20 text-emerald-400'
                    : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                <Table2 className="h-3.5 w-3.5" />
                Table
              </button>
              <button
                onClick={() => setViewMode('cards')}
                className={`px-2 py-1 rounded text-xs flex items-center gap-1 transition-colors ${
                  viewMode === 'cards'
                    ? 'bg-emerald-500/20 text-emerald-400'
                    : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                <LayoutGrid className="h-3.5 w-3.5" />
                Cards
              </button>
            </div>

            <Button
              variant="outline"
              size="sm"
              className="border-[#2a2e39] text-zinc-400 hover:bg-[#2a2e39] hover:text-zinc-200"
              onClick={() => setShowAddForm(!showAddForm)}
            >
              <Plus className="h-3.5 w-3.5 mr-1.5" />
              Add account
            </Button>
          </div>
        </div>

        {showAddForm && (
          <div className="mb-4">
            <AddAccountForm
              onSuccess={() => setShowAddForm(false)}
              onCancel={() => setShowAddForm(false)}
            />
          </div>
        )}

        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-16 rounded-lg bg-[#1e222d]" />
            ))}
          </div>
        ) : accounts.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-lg border border-[#2a2e39] bg-[#1e222d]/50 py-12 text-zinc-500">
            <Users className="h-10 w-10 mb-3 opacity-50" />
            <p className="text-sm font-mono">No accounts configured</p>
            <p className="text-xs text-zinc-600 mt-1 max-w-md text-center">
              Click &quot;Add account&quot; above to create one, or add rows to{' '}
              <code className="text-[10px]">account_strategies</code> in Supabase.
              Run migration 009 if needed.
            </p>
          </div>
        ) : viewMode === 'table' ? (
          <AccountsTable accounts={accounts} onDelete={handleDeleteAccount} />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {accounts.map((account) => (
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
      <div className="grid gap-6 md:grid-cols-2">
        <CopyConfigurator />
        <CapitalAllocator />
      </div>
    </div>
  );
}
