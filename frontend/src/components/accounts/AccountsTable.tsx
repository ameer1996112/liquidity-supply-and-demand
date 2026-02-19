'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Eye,
  Pause,
  Play,
  RefreshCw,
  Settings,
  Trash2,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { syncAccount, type AccountComparisonApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { toPercentFromRatioOrPercent } from '@/domain/metrics/tradingMetrics';

interface AccountsTableProps {
  accounts: AccountComparisonApi[];
  onDelete: (accountName: string) => void;
}

export function AccountsTable({ accounts, onDelete }: AccountsTableProps) {
  const router = useRouter();
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [sortBy, setSortBy] = useState<
    'name' | 'balance' | 'daily_pnl' | 'total_pnl'
  >('name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  const syncMutation = useMutation({
    mutationFn: syncAccount,
    onSuccess: (_, accountName) => {
      queryClient.invalidateQueries({
        queryKey: ['portfolio-control', 'accounts', 'comparison'],
      });
      addToast({
        title: 'Account synced',
        message: `${accountName} synced successfully`,
        severity: 'success',
        duration: 4000,
      });
    },
    onError: (error: Error, accountName) => {
      addToast({
        title: 'Sync failed',
        message: error.message || `Failed to sync ${accountName}`,
        severity: 'critical',
        duration: 6000,
      });
    },
  });

  const sortedAccounts = [...accounts].sort((a, b) => {
    let aVal: any;
    let bVal: any;

    switch (sortBy) {
      case 'balance':
        aVal = a.balance;
        bVal = b.balance;
        break;
      case 'daily_pnl':
        aVal = a.daily_pnl ?? 0;
        bVal = b.daily_pnl ?? 0;
        break;
      case 'total_pnl':
        // Calculate total from all trades (not yet implemented, use balance as proxy)
        aVal = a.balance;
        bVal = b.balance;
        break;
      default:
        aVal = a.account_name;
        bVal = b.account_name;
    }

    if (sortOrder === 'asc') {
      return aVal > bVal ? 1 : -1;
    } else {
      return aVal < bVal ? 1 : -1;
    }
  });

  return (
    <div className='tv-card overflow-hidden'>
      <div className='overflow-x-auto'>
        <table className='w-full text-sm'>
          <thead>
            <tr className='border-b border-[#2a2e39] bg-[#1e222d]/50'>
              <th className='text-left px-4 py-3 text-xs font-mono text-zinc-500'>
                <button
                  onClick={() => {
                    setSortBy('name');
                    setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                  }}
                  className='hover:text-zinc-300'
                >
                  Account
                </button>
              </th>
              <th className='text-left px-4 py-3 text-xs font-mono text-zinc-500'>
                Type
              </th>
              <th className='text-left px-4 py-3 text-xs font-mono text-zinc-500'>
                Connection
              </th>
              <th className='text-right px-4 py-3 text-xs font-mono text-zinc-500'>
                <button
                  onClick={() => {
                    setSortBy('balance');
                    setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                  }}
                  className='hover:text-zinc-300'
                >
                  Balance
                </button>
              </th>
              <th className='text-right px-4 py-3 text-xs font-mono text-zinc-500'>
                Equity
              </th>
              <th className='text-right px-4 py-3 text-xs font-mono text-zinc-500'>
                <button
                  onClick={() => {
                    setSortBy('daily_pnl');
                    setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
                  }}
                  className='hover:text-zinc-300'
                >
                  Today P&L
                </button>
              </th>
              <th className='text-center px-4 py-3 text-xs font-mono text-zinc-500'>
                Positions
              </th>
              <th className='text-right px-4 py-3 text-xs font-mono text-zinc-500'>
                Win Rate
              </th>
              <th className='text-right px-4 py-3 text-xs font-mono text-zinc-500'>
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedAccounts.map((account) => {
              const isPaused = account.pause_trading ?? false;
              const dailyPositive = (account.daily_pnl ?? 0) >= 0;
              const winRatePct = toPercentFromRatioOrPercent(account.win_rate);
              const winRateClass =
                winRatePct >= 50 ? 'text-[#26a69a]' : 'text-[#ef5350]';

              return (
                <tr
                  key={account.account_name}
                  className={cn(
                    'border-b border-[#2a2e39] hover:bg-[#1e222d]/30 transition-colors',
                    isPaused && 'opacity-60'
                  )}
                >
                  {/* Account Name */}
                  <td className='px-4 py-3'>
                    <div className='flex items-center gap-2'>
                      <button
                        onClick={() =>
                          router.push(
                            `/accounts/${encodeURIComponent(
                              account.account_name
                            )}`
                          )
                        }
                        className='font-mono text-xs text-zinc-200 hover:text-emerald-400 hover:underline'
                      >
                        {account.account_name}
                      </button>
                      {account.provider && account.provider !== 'Personal' && (
                        <span className='px-1.5 py-0.5 text-[9px] font-mono rounded bg-blue-500/10 text-blue-400 border border-blue-500/20'>
                          {account.provider}
                        </span>
                      )}
                      {isPaused && <Pause className='h-3 w-3 text-amber-500' />}
                    </div>
                  </td>

                  {/* Type */}
                  <td className='px-4 py-3'>
                    {account.account_type ? (
                      <span
                        className={cn(
                          'px-2 py-0.5 text-[10px] font-mono rounded',
                          account.account_type === 'Eval' &&
                            'bg-amber-500/10 text-amber-400 border border-amber-500/20',
                          account.account_type === 'Funded' &&
                            'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
                          account.account_type === 'Personal' &&
                            'bg-zinc-700/30 text-zinc-400'
                        )}
                      >
                        {account.account_type}
                      </span>
                    ) : (
                      <span className='text-xs text-zinc-600'>-</span>
                    )}
                  </td>

                  {/* Connection */}
                  <td className='px-4 py-3'>
                    <span className='flex items-center gap-1.5 text-xs text-zinc-500'>
                      <span className='relative flex h-2 w-2'>
                        <span className='relative inline-flex rounded-full h-2 w-2 bg-zinc-600'></span>
                      </span>
                      N/A
                    </span>
                  </td>

                  {/* Balance */}
                  <td className='px-4 py-3 text-right font-mono text-xs text-zinc-200'>
                    $
                    {account.balance.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                    })}
                  </td>

                  {/* Equity */}
                  <td className='px-4 py-3 text-right font-mono text-xs text-zinc-300'>
                    $
                    {(account.equity || account.balance).toLocaleString(
                      undefined,
                      { minimumFractionDigits: 2 }
                    )}
                  </td>

                  {/* Today P&L */}
                  <td className='px-4 py-3 text-right'>
                    <div className='flex items-center justify-end gap-1'>
                      {dailyPositive ? (
                        <TrendingUp className='w-3 h-3 text-[#26a69a]' />
                      ) : (
                        <TrendingDown className='w-3 h-3 text-[#ef5350]' />
                      )}
                      <span
                        className={cn(
                          'font-mono text-xs font-semibold',
                          dailyPositive ? 'text-[#26a69a]' : 'text-[#ef5350]'
                        )}
                      >
                        {dailyPositive ? '+' : ''}$
                        {(account.daily_pnl ?? 0).toFixed(2)}
                        <span className='text-[9px] ml-0.5 opacity-80'>
                          ({dailyPositive ? '+' : ''}
                          {(account.daily_pnl_pct ?? 0).toFixed(2)}%)
                        </span>
                      </span>
                    </div>
                  </td>

                  {/* Positions */}
                  <td className='px-4 py-3 text-center'>
                    <span className='font-mono text-xs text-zinc-400'>
                      {account.active_positions} / {account.max_positions || 3}
                    </span>
                  </td>

                  {/* Win Rate */}
                  <td className='px-4 py-3 text-right'>
                    <span
                      className={cn(
                        'font-mono text-xs font-medium',
                        winRateClass
                      )}
                    >
                      {winRatePct.toFixed(1)}%
                    </span>
                  </td>

                  {/* Actions */}
                  <td className='px-4 py-3'>
                    <div className='flex items-center justify-end gap-1'>
                      <button
                        onClick={() =>
                          router.push(
                            `/accounts/${encodeURIComponent(
                              account.account_name
                            )}`
                          )
                        }
                        className='p-1.5 rounded hover:bg-[#2a2e39] text-zinc-500 hover:text-zinc-300 transition-colors'
                        title='View Details'
                      >
                        <Eye className='h-3.5 w-3.5' />
                      </button>
                      <button
                        onClick={() =>
                          syncMutation.mutate(account.account_name)
                        }
                        disabled={syncMutation.isPending}
                        className='p-1.5 rounded hover:bg-[#2a2e39] text-zinc-500 hover:text-emerald-400 transition-colors disabled:opacity-50'
                        title='Resync Now'
                      >
                        <RefreshCw
                          className={cn(
                            'h-3.5 w-3.5',
                            syncMutation.isPending && 'animate-spin'
                          )}
                        />
                      </button>
                      <button
                        onClick={() => onDelete(account.account_name)}
                        className='p-1.5 rounded hover:bg-[#2a2e39] text-zinc-500 hover:text-red-500 transition-colors'
                        title='Delete Account'
                      >
                        <Trash2 className='h-3.5 w-3.5' />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {accounts.length === 0 && (
        <div className='px-4 py-12 text-center text-xs text-zinc-600'>
          No accounts to display
        </div>
      )}
    </div>
  );
}
