'use client';

import { useMemo, useState } from 'react';
import { Loader2, ShieldX } from 'lucide-react';

import { GuardGroupList } from '@/components/rules/GuardGroupList';
import {
  type GuardConfig,
  useAccountGuardsConfig,
  useGuardAccounts,
  useUpdateAccountGuard,
} from '@/hooks/useGuards';

export function AccountGuardsView() {
  const { data: accountData, isLoading: accountsLoading, error: accountsError } = useGuardAccounts();
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null);
  const effectiveAccountId = selectedAccountId ?? accountData?.accounts?.[0]?.id ?? null;
  const selectedAccount = useMemo(
    () => accountData?.accounts?.find((account) => account.id === effectiveAccountId) ?? null,
    [accountData, effectiveAccountId],
  );
  const { data, isLoading, error } = useAccountGuardsConfig(effectiveAccountId);
  const updateGuard = useUpdateAccountGuard();

  const handleToggle = (guard: GuardConfig) => {
    if (!effectiveAccountId) return;
    const newValue = !guard.enabled;
    updateGuard.mutate({
      accountId: effectiveAccountId,
      guardId: guard.guard_id,
      value: newValue,
      change_reason: `${newValue ? 'enabled' : 'disabled'} via UI`,
    });
  };

  const handleThresholdUpdate = (guardId: string, key: string, value: number | boolean | string) => {
    if (!effectiveAccountId) return;
    const guard = Object.values(data?.groups || {}).flat().find((g) => g.guard_id === guardId);
    if (!guard) return;
    if (key === '__primary__') {
      updateGuard.mutate({
        accountId: effectiveAccountId,
        guardId,
        value,
        change_reason: 'primary threshold updated via UI',
      });
      return;
    }
    updateGuard.mutate({
      accountId: effectiveAccountId,
      guardId,
      value: guard.enabled,
      thresholds: { [key]: value },
      change_reason: `threshold ${key} updated via UI`,
    });
  };

  if (accountsLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-5 w-5 animate-spin text-[var(--to-text-dim)]" />
        <span className="ml-2.5 text-sm text-[var(--to-text-dim)]">Loading accounts...</span>
      </div>
    );
  }

  if (accountsError || !accountData?.accounts?.length) {
    return (
      <div className="to-panel p-5 border-[#f6465d]/30">
        <div className="flex items-center gap-2 mb-2">
          <ShieldX className="h-4 w-4 text-[#f6465d]" />
          <p className="text-sm font-medium text-[#f6465d]">Failed to load account guards</p>
        </div>
        <p className="text-xs text-[var(--to-text-dim)]">No active broker profiles are available for account-scoped guard management.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="to-panel p-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">Editing account</p>
          <p className="text-sm font-medium text-[var(--to-text-primary)]">{selectedAccount?.name ?? effectiveAccountId}</p>
        </div>
        <label className="flex flex-col gap-1 text-[10px] uppercase tracking-wider text-[var(--to-text-dim)]">
          Account
          <select
            aria-label="Account"
            value={effectiveAccountId ?? ''}
            onChange={(e) => setSelectedAccountId(e.target.value)}
            className="rounded-md border border-[var(--to-border)] bg-[var(--to-bg)] px-3 py-2 text-xs text-[var(--to-text-primary)]"
          >
            {accountData.accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name} ({account.run_mode})
              </option>
            ))}
          </select>
        </label>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin text-[var(--to-text-dim)]" />
          <span className="ml-2.5 text-sm text-[var(--to-text-dim)]">Loading account guards...</span>
        </div>
      ) : error || !data ? (
        <div className="to-panel p-5 border-[#f6465d]/30">
          <div className="flex items-center gap-2 mb-2">
            <ShieldX className="h-4 w-4 text-[#f6465d]" />
            <p className="text-sm font-medium text-[#f6465d]">Failed to load account guard configuration</p>
          </div>
          <p className="text-xs text-[var(--to-text-dim)]">Try switching accounts or refreshing the page.</p>
        </div>
      ) : (
        <GuardGroupList
          data={data}
          scopeLabel={`Account: ${selectedAccount?.name ?? effectiveAccountId}`}
          savingGuards={new Set<string>()}
          onToggle={handleToggle}
          onThresholdUpdate={handleThresholdUpdate}
        />
      )}
    </div>
  );
}
