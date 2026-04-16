'use client';

import { Loader2, ShieldX } from 'lucide-react';

import { GuardGroupList } from '@/components/rules/GuardGroupList';
import {
  type GuardConfig,
  useGlobalGuardsConfig,
  useUpdateGlobalGuard,
} from '@/hooks/useGuards';

export function GlobalGuardsView() {
  const { data, isLoading, error } = useGlobalGuardsConfig();
  const updateGuard = useUpdateGlobalGuard();

  const handleToggle = (guard: GuardConfig) => {
    const newValue = !guard.enabled;
    updateGuard.mutate({
      guardId: guard.guard_id,
      value: newValue,
      change_reason: `${newValue ? 'enabled' : 'disabled'} via UI`,
    });
  };

  const handleThresholdUpdate = (guardId: string, key: string, value: number | boolean) => {
    const guard = Object.values(data?.groups || {}).flat().find((g) => g.guard_id === guardId);
    if (!guard) return;
    if (key === '__primary__') {
      updateGuard.mutate({
        guardId,
        value,
        change_reason: 'primary threshold updated via UI',
      });
      return;
    }
    updateGuard.mutate({
      guardId,
      value: guard.enabled,
      thresholds: { [key]: value },
      change_reason: `threshold ${key} updated via UI`,
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-5 w-5 animate-spin text-[var(--to-text-dim)]" />
        <span className="ml-2.5 text-sm text-[var(--to-text-dim)]">Loading global guards...</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="to-panel p-5 border-[#f6465d]/30">
        <div className="flex items-center gap-2 mb-2">
          <ShieldX className="h-4 w-4 text-[#f6465d]" />
          <p className="text-sm font-medium text-[#f6465d]">Failed to load global guards</p>
        </div>
        <p className="text-xs text-[var(--to-text-dim)]">Check your API connection and try refreshing.</p>
      </div>
    );
  }

  return (
    <GuardGroupList
      data={data}
      scopeLabel="Global"
      savingGuards={new Set<string>()}
      onToggle={handleToggle}
      onThresholdUpdate={handleThresholdUpdate}
    />
  );
}
