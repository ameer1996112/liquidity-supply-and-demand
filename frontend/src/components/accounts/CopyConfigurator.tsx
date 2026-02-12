'use client';

import { useState, useCallback } from 'react';
import {
  useTradeCopyRules,
  useCreateTradeCopyRule,
  useToggleTradeCopyRule,
} from '@/hooks/useAccounts';
import { useAccountsComparison } from '@/hooks/useAccounts';
import { useToast } from '@/components/ui/toast';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Copy, Plus, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export function CopyConfigurator() {
  const { addToast } = useToast();
  const { data: accounts = [] } = useAccountsComparison();
  const { data: rules = [], isLoading } = useTradeCopyRules();
  const createRule = useCreateTradeCopyRule();
  const toggleRule = useToggleTradeCopyRule();

  const [showForm, setShowForm] = useState(false);
  const [ruleName, setRuleName] = useState('');
  const [masterAccount, setMasterAccount] = useState('');
  const [slaveAccounts, setSlaveAccounts] = useState<string[]>([]);
  const [scaleByBalance, setScaleByBalance] = useState(true);
  const [riskMultiplier, setRiskMultiplier] = useState(1);

  const accountNames = accounts.map((a) => a.account_name);

  const handleRemoveSlave = useCallback((name: string) => {
    setSlaveAccounts(slaveAccounts.filter((s) => s !== name));
  }, [slaveAccounts]);

  const handleSubmit = useCallback(async () => {
    const name = ruleName.trim() || `Copy: ${masterAccount} → ${slaveAccounts.join(', ')}`;
    if (!masterAccount || slaveAccounts.length === 0) {
      addToast({ title: 'Validation', message: 'Select master and at least one slave account', severity: 'warning', duration: 4000 });
      return;
    }
    try {
      await createRule.mutateAsync({
        rule_name: name,
        master_account_name: masterAccount,
        slave_account_names: slaveAccounts,
        scale_by_balance: scaleByBalance,
        risk_multiplier: riskMultiplier,
        copy_sl_tp: true,
        enabled: true,
      });
      addToast({ title: 'Rule created', message: `Copy ${masterAccount} → ${slaveAccounts.join(', ')}`, severity: 'success', duration: 3000 });
      setShowForm(false);
      setRuleName('');
      setMasterAccount('');
      setSlaveAccounts([]);
    } catch (err) {
      addToast({ title: 'Failed to create rule', message: err instanceof Error ? err.message : 'Check API', severity: 'critical', duration: 6000 });
    }
  }, [ruleName, masterAccount, slaveAccounts, scaleByBalance, riskMultiplier, createRule, addToast]);

  const handleToggle = useCallback(async (ruleId: number, enabled: boolean) => {
    try {
      await toggleRule.mutateAsync({ ruleId, enabled });
      addToast({ title: enabled ? 'Rule enabled' : 'Rule disabled', severity: 'success', duration: 2000 });
    } catch (err) {
      addToast({ title: 'Failed to toggle', message: err instanceof Error ? err.message : 'Check API', severity: 'critical', duration: 4000 });
    }
  }, [toggleRule, addToast]);

  return (
    <Card className="border-[#2a2e39] bg-[#1e222d]/50">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Copy className="h-4 w-4 text-emerald-500" />
            <CardTitle className="text-sm font-medium text-zinc-100">Trade Copy Rules</CardTitle>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="text-zinc-400 hover:text-zinc-200"
            onClick={() => setShowForm(!showForm)}
          >
            <Plus className="h-3.5 w-3.5 mr-1" />
            Add rule
          </Button>
        </div>
        <CardDescription className="text-[11px] text-zinc-500">
          Copy trades from master account to slave accounts with optional scaling.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {showForm && (
          <div className="rounded-lg border border-[#2a2e39] p-4 space-y-3">
            <input
              type="text"
              placeholder="Rule name (optional)"
              value={ruleName}
              onChange={(e) => setRuleName(e.target.value)}
              className="w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm text-zinc-200 font-mono placeholder:text-zinc-600"
            />
            <div>
              <label className="text-[10px] text-zinc-500 font-mono block mb-1">Master account</label>
              <select
                value={masterAccount}
                onChange={(e) => setMasterAccount(e.target.value)}
                className="w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm text-zinc-200 font-mono"
              >
                <option value="">Select master</option>
                {accountNames.map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-[10px] text-zinc-500 font-mono block mb-1">Slave accounts</label>
              <div className="flex gap-2 flex-wrap">
                {slaveAccounts.map((n) => (
                  <span key={n} className="inline-flex items-center gap-1 px-2 py-1 rounded bg-[#2a2e39] text-xs font-mono text-zinc-300">
                    {n}
                    <button type="button" onClick={() => handleRemoveSlave(n)} className="text-zinc-500 hover:text-red-400">×</button>
                  </span>
                ))}
                <select
                  onChange={(e) => {
                    const v = e.target.value;
                    if (v && !slaveAccounts.includes(v)) setSlaveAccounts([...slaveAccounts, v]);
                    e.target.value = '';
                  }}
                  className="px-2 py-1 bg-[#1e222d] border border-[#2a2e39] rounded text-xs font-mono text-zinc-400"
                >
                  <option value="">+ Add slave</option>
                  {accountNames.filter((n) => !slaveAccounts.includes(n)).map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-xs text-zinc-500">
                <input type="checkbox" checked={scaleByBalance} onChange={(e) => setScaleByBalance(e.target.checked)} className="rounded" />
                Scale by balance
              </label>
              <label className="flex items-center gap-2 text-xs text-zinc-500">
                Risk multiplier:
                <input
                  type="number"
                  min={0.1}
                  max={2}
                  step={0.1}
                  value={riskMultiplier}
                  onChange={(e) => setRiskMultiplier(parseFloat(e.target.value) || 1)}
                  className="w-16 px-2 py-1 bg-[#1e222d] border border-[#2a2e39] rounded text-xs font-mono"
                />
              </label>
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleSubmit} disabled={createRule.isPending}>
                {createRule.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                Create rule
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setShowForm(false)}>Cancel</Button>
            </div>
          </div>
        )}

        {isLoading ? (
          <Skeleton className="h-24 w-full bg-[#1e222d]" />
        ) : accountNames.length < 2 ? (
          <p className="text-xs text-zinc-600 font-mono py-4 text-center">
            Add at least 2 accounts to create copy rules (master → slave).
          </p>
        ) : rules.length === 0 ? (
          <p className="text-xs text-zinc-600 font-mono py-4 text-center">
            No copy rules yet. Click &quot;Add rule&quot; to create one.
          </p>
        ) : (
          <ul className="space-y-2">
            {rules.map((rule: any) => (
              <li
                key={rule.id}
                className={cn(
                  'flex items-center justify-between px-3 py-2 rounded-lg border',
                  rule.enabled ? 'border-[#2a2e39] bg-[#1e222d]/50' : 'border-[#2a2e39]/50 bg-[#1e222d]/30 opacity-70'
                )}
              >
                <div>
                  <span className="font-mono text-xs text-zinc-200">{rule.rule_name}</span>
                  <span className="text-[10px] text-zinc-500 ml-2">
                    {rule.master_account_name} → {rule.slave_account_names.join(', ')}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handleToggle(rule.id, !rule.enabled)}
                  className={cn(
                    'font-mono text-[10px] px-2 py-1 rounded transition-colors',
                    rule.enabled ? 'bg-emerald-500/20 text-emerald-400' : 'bg-zinc-700 text-zinc-500'
                  )}
                >
                  {rule.enabled ? 'ON' : 'OFF'}
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
