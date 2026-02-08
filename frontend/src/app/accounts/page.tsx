'use client';

import { useState } from 'react';
import { Users, Plus } from 'lucide-react';
import { EnhancedAccountCard } from '@/components/accounts/EnhancedAccountCard';
import { CopyConfigurator } from '@/components/accounts/CopyConfigurator';
import { CapitalAllocator } from '@/components/accounts/CapitalAllocator';
import { AddAccountForm } from '@/components/accounts/AddAccountForm';
import { useAccountsComparison } from '@/hooks/useAccounts';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useToast } from '@/hooks/use-toast';

export default function AccountsPage() {
  const [showAddForm, setShowAddForm] = useState(false);
  const { data: accounts = [], isLoading, error } = useAccountsComparison();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const deleteAccountMutation = useMutation({
    mutationFn: async (accountName: string) => {
      const response = await fetch(
        `/api/portfolio-control/accounts/${encodeURIComponent(accountName)}`,
        {
          method: 'DELETE',
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to delete account');
      }

      return response.json();
    },
    onSuccess: (data, accountName) => {
      queryClient.invalidateQueries({ queryKey: ['accounts', 'comparison'] });
      toast({
        title: 'Account deleted',
        description: `${accountName} has been removed successfully.`,
      });
    },
    onError: (error: Error, accountName) => {
      toast({
        title: 'Delete failed',
        description: error.message || `Failed to delete ${accountName}`,
        variant: 'destructive',
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

      {/* Account Cards - Side-by-side comparison */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-zinc-300 flex items-center gap-2">
            <Users className="h-4 w-4 text-emerald-500" />
            Account Comparison
          </h2>
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

        {showAddForm && (
          <div className="mb-4">
            <AddAccountForm
              onSuccess={() => setShowAddForm(false)}
              onCancel={() => setShowAddForm(false)}
            />
          </div>
        )}

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
              Click &quot;Add account&quot; above to create one, or add rows to{' '}
              <code className="text-[10px]">account_strategies</code> in Supabase.
              Run migration 009 if needed.
            </p>
          </div>
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
