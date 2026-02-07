'use client';

import { useState } from 'react';
import {
  useAccountsComparison,
  useAllocationSuggest,
  useExecuteAllocation,
} from '@/hooks/useAccounts';
import { useToast } from '@/components/ui/toast';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PiggyBank, Loader2, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';

export function CapitalAllocator() {
  const { addToast } = useToast();
  const { data: accounts = [] } = useAccountsComparison();
  const [totalCapital, setTotalCapital] = useState(() => {
    const sum = accounts.reduce((a, c) => a + c.balance, 0);
    return sum > 0 ? sum : 100000;
  });
  const { data: plan, isLoading, refetch } = useAllocationSuggest(totalCapital);
  const executeAllocation = useExecuteAllocation();

  const totalFromAccounts = accounts.reduce((a, c) => a + c.balance, 0);

  const handleSuggest = () => {
    if (totalFromAccounts > 0) setTotalCapital(totalFromAccounts);
    refetch();
  };

  const handleExecute = async (accountName: string, allocationUsd: number) => {
    try {
      await executeAllocation.mutateAsync({ accountName, allocationUsd });
      addToast({ title: 'Allocation updated', message: `${accountName}: $${allocationUsd.toLocaleString()}`, severity: 'success', duration: 3000 });
    } catch (err) {
      addToast({ title: 'Failed to execute', message: err instanceof Error ? err.message : 'Check API', severity: 'critical', duration: 5000 });
    }
  };

  return (
    <Card className="border-[#2a2e39] bg-[#1e222d]/50">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <PiggyBank className="h-4 w-4 text-emerald-500" />
          <CardTitle className="text-sm font-medium text-zinc-100">Capital Allocation</CardTitle>
        </div>
        <CardDescription className="text-[11px] text-zinc-500">
          Optimize capital distribution across accounts based on performance.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <label className="text-[10px] text-zinc-500 font-mono block mb-1">Total capital ($)</label>
          <input
            type="number"
            min={1}
            value={totalCapital}
            onChange={(e) => setTotalCapital(parseFloat(e.target.value) || 0)}
            className="w-full px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded text-sm font-mono text-zinc-200"
          />
          {totalFromAccounts > 0 && (
            <p className="text-[10px] text-zinc-600 mt-1">
              Sum of account balances: ${totalFromAccounts.toLocaleString()}
            </p>
          )}
        </div>

        <Button
          variant="outline"
          size="sm"
          className="w-full border-[#2a2e39] text-zinc-400 hover:bg-[#2a2e39] hover:text-zinc-200"
          onClick={handleSuggest}
        >
          <TrendingUp className="h-3.5 w-3.5 mr-2" />
          Suggest allocation
        </Button>

        {isLoading ? (
          <Skeleton className="h-32 w-full bg-[#1e222d]" />
        ) : plan && plan.recommendations.length > 0 ? (
          <div className="space-y-3">
            {plan.expected_portfolio_sharpe != null && (
              <p className="text-[10px] text-zinc-500 font-mono">
                Expected Sharpe: {plan.expected_portfolio_sharpe.toFixed(2)}
              </p>
            )}
            <ul className="space-y-2">
              {plan.recommendations.map((rec) => (
                <li
                  key={rec.account_name}
                  className="flex flex-col gap-1 rounded-lg border border-[#2a2e39] p-3"
                >
                  <span className="font-mono text-xs text-zinc-200">{rec.account_name}</span>
                  <div className="flex justify-between text-[10px] text-zinc-500">
                    <span>Current: ${rec.current_balance.toLocaleString()}</span>
                    <span>Suggested: ${rec.suggested_allocation_usd.toLocaleString()}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span
                      className={cn(
                        'font-mono text-xs font-semibold',
                        rec.change_usd >= 0 ? 'text-[#26a69a]' : 'text-[#ef5350]'
                      )}
                    >
                      {rec.change_usd >= 0 ? '+' : ''}{rec.change_usd.toLocaleString()} ({rec.change_pct >= 0 ? '+' : ''}{rec.change_pct.toFixed(1)}%)
                    </span>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-6 text-xs text-zinc-400 hover:text-emerald-400"
                      disabled={executeAllocation.isPending}
                      onClick={() => handleExecute(rec.account_name, rec.suggested_allocation_usd)}
                    >
                      {executeAllocation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Apply'}
                    </Button>
                  </div>
                  {rec.reason && (
                    <p className="text-[10px] text-zinc-600 line-clamp-2">{rec.reason}</p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="text-xs text-zinc-600 font-mono py-4 text-center">
            {accounts.length === 0
              ? 'Add accounts to see allocation suggestions.'
              : 'No allocation recommendations. Ensure account_strategies has data.'}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
