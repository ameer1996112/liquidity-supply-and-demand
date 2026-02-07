'use client';

import { useState } from 'react';
import { useCreateAccountStrategy } from '@/hooks/useAccountsSupabase';
import { useToast } from '@/components/ui/toast';
import { Button } from '@/components/ui/button';
import { Plus, Loader2, X } from 'lucide-react';

interface AddAccountFormProps {
  onSuccess?: () => void;
  onCancel?: () => void;
}

export function AddAccountForm({ onSuccess, onCancel }: AddAccountFormProps) {
  const { addToast } = useToast();
  const createAccount = useCreateAccountStrategy();
  const [accountName, setAccountName] = useState('');
  const [strategyType, setStrategyType] = useState('BALANCED');
  const [riskPercent, setRiskPercent] = useState(1);
  const [maxPositions, setMaxPositions] = useState(3);
  const [allocatedCapital, setAllocatedCapital] = useState(10000);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = accountName.trim();
    if (!name) {
      addToast({ title: 'Validation', message: 'Account name is required', severity: 'warning', duration: 3000 });
      return;
    }
    try {
      await createAccount.mutateAsync({
        account_name: name,
        strategy_type: strategyType,
        risk_percent: riskPercent,
        max_positions: maxPositions,
        allocated_capital_usd: allocatedCapital,
      });
      addToast({ title: 'Account added', message: `${name} created successfully`, severity: 'success', duration: 3000 });
      setAccountName('');
      setStrategyType('BALANCED');
      setRiskPercent(1);
      setMaxPositions(3);
      setAllocatedCapital(10000);
      onSuccess?.();
    } catch (err) {
      addToast({
        title: 'Failed to add account',
        message: err instanceof Error ? err.message : 'Check Supabase config and RLS',
        severity: 'critical',
        duration: 6000,
      });
    }
  };

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border border-[#2a2e39] bg-[#1e222d]/80 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-200">Add account</h3>
        {onCancel && (
          <button type="button" onClick={onCancel} className="text-zinc-500 hover:text-zinc-300">
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div>
        <label className="text-[10px] text-zinc-500 font-mono block mb-1">Account name *</label>
        <input
          type="text"
          value={accountName}
          onChange={(e) => setAccountName(e.target.value)}
          placeholder="e.g. FTMO Challenge, MyFundedFX"
          className="w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm text-zinc-200 font-mono placeholder:text-zinc-600 focus:outline-none focus:border-zinc-500"
          required
        />
      </div>

      <div>
        <label className="text-[10px] text-zinc-500 font-mono block mb-1">Strategy type</label>
        <select
          value={strategyType}
          onChange={(e) => setStrategyType(e.target.value)}
          className="w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm text-zinc-200 font-mono"
        >
          <option value="CONSERVATIVE">Conservative</option>
          <option value="BALANCED">Balanced</option>
          <option value="AGGRESSIVE">Aggressive</option>
          <option value="CUSTOM">Custom</option>
        </select>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-[10px] text-zinc-500 font-mono block mb-1">Risk %</label>
          <input
            type="number"
            min={0.1}
            max={5}
            step={0.1}
            value={riskPercent}
            onChange={(e) => setRiskPercent(parseFloat(e.target.value) || 0)}
            className="w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-zinc-200"
          />
        </div>
        <div>
          <label className="text-[10px] text-zinc-500 font-mono block mb-1">Max positions</label>
          <input
            type="number"
            min={1}
            max={10}
            value={maxPositions}
            onChange={(e) => setMaxPositions(parseInt(e.target.value, 10) || 0)}
            className="w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-zinc-200"
          />
        </div>
      </div>

      <div>
        <label className="text-[10px] text-zinc-500 font-mono block mb-1">Allocated capital ($)</label>
        <input
          type="number"
          min={0}
          step={100}
          value={allocatedCapital}
          onChange={(e) => setAllocatedCapital(parseFloat(e.target.value) || 0)}
          className="w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-zinc-200"
        />
      </div>

      <div className="flex gap-2 pt-2">
        <Button type="submit" size="sm" disabled={createAccount.isPending}>
          {createAccount.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-2" /> : <Plus className="h-3.5 w-3.5 mr-2" />}
          Add account
        </Button>
        {onCancel && (
          <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}
