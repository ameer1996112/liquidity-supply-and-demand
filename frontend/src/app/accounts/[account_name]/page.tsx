'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { fetchAccountDetail, syncAccount } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';
import { OverviewTab } from '@/components/accounts/detail/OverviewTab';
import { PositionsTab } from '@/components/accounts/detail/PositionsTab';
import { HistoryTab } from '@/components/accounts/detail/HistoryTab';
import { AnalyticsTab } from '@/components/accounts/detail/AnalyticsTab';
import { JournalTab } from '@/components/accounts/detail/JournalTab';
import { ChallengeTab } from '@/components/accounts/detail/ChallengeTab';

type Tab = 'overview' | 'positions' | 'history' | 'analytics' | 'journal' | 'challenge';

export default function AccountDetailPage() {
  const params = useParams();
  const router = useRouter();
  const accountName = decodeURIComponent(params.account_name as string);
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const { addToast } = useToast();
  const queryClient = useQueryClient();

  // Fetch account details
  const {
    data: account,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['account-detail', accountName],
    queryFn: () => fetchAccountDetail(accountName),
    staleTime: 30_000,
  });

  // Sync mutation
  const syncMutation = useMutation({
    mutationFn: () => syncAccount(accountName),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['account-detail', accountName],
      });
      queryClient.invalidateQueries({
        queryKey: ['portfolio-control', 'accounts', 'comparison'],
      });
      addToast({
        title: 'Account synced',
        message: `${accountName} synced successfully with MetaAPI`,
        severity: 'success',
        duration: 5000,
      });
    },
    onError: (error: Error) => {
      addToast({
        title: 'Sync failed',
        message: error.message || `Failed to sync ${accountName}`,
        severity: 'critical',
        duration: 8000,
      });
    },
  });

  const connectionStatus = (account?.connection_status || 'not_configured') as
    | 'connected'
    | 'disconnected'
    | 'error'
    | 'not_configured';
  const connectionColor = {
    connected: 'text-[var(--to-long)]',
    disconnected: 'text-[var(--to-warning)]',
    error: 'text-[var(--to-short)]',
    not_configured: 'text-[var(--to-text-dim)]',
  }[connectionStatus];

  const connectionLabel = {
    connected: 'Connected',
    disconnected: 'Disconnected',
    error: 'Error',
    not_configured: 'Not Configured',
  }[connectionStatus];

  if (error) {
    return (
      <div className='space-y-4'>
        <Button
          variant='ghost'
          size='sm'
          className='text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)]'
          onClick={() => router.push('/accounts')}
        >
          <ArrowLeft className='mr-2 h-4 w-4' />
          Back to Accounts
        </Button>
        <div className='rounded-lg border border-[var(--to-short)]/30 bg-[var(--to-short)]/10 px-4 py-3 text-sm text-[var(--to-short)]'>
          Failed to load account details: {(error as Error).message}
        </div>
      </div>
    );
  }

  return (
    <div className='space-y-4'>
      {/* Header */}
      <div className='flex items-center justify-between'>
        <div className='flex items-center gap-4'>
          <Button
            variant='ghost'
            size='sm'
            className='text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)]'
            onClick={() => router.push('/accounts')}
          >
            <ArrowLeft className='mr-2 h-4 w-4' />
            Back
          </Button>

          <div>
            <div className='flex items-center gap-3'>
              <h1 className='page-title text-lg font-semibold'>
                {isLoading ? (
                  <Skeleton className='h-6 w-48 bg-[var(--to-surface-raised)]/60' />
                ) : (
                  accountName
                )}
              </h1>
              {!isLoading && account && (
                <>
                  {account.account_type && (
                    <span className='rounded bg-[var(--to-surface-raised)] px-2 py-0.5 text-xs font-mono text-[var(--to-text-secondary)]'>
                      {account.account_type}
                    </span>
                  )}
                  {account.provider && account.provider !== 'Personal' && (
                    <span className='rounded border border-indigo-500/20 bg-indigo-500/10 px-2 py-0.5 text-xs font-mono text-indigo-300'>
                      {account.provider}
                    </span>
                  )}
                  <span
                    className={`flex items-center gap-1.5 text-xs font-mono ${connectionColor}`}
                  >
                    <span className='relative flex h-2 w-2'>
                      <span
                        className={`animate-ping absolute inline-flex h-full w-full rounded-full ${
                          connectionStatus === 'connected'
                            ? 'bg-[var(--to-long)]'
                            : 'bg-[var(--to-warning)]'
                        } opacity-75`}
                      ></span>
                      <span
                        className={`relative inline-flex rounded-full h-2 w-2 ${
                          connectionStatus === 'connected'
                            ? 'bg-[var(--to-long)]'
                            : connectionStatus === 'error'
                            ? 'bg-[var(--to-short)]'
                            : 'bg-[var(--to-warning)]'
                        }`}
                      ></span>
                    </span>
                    {connectionLabel}
                  </span>
                </>
              )}
            </div>

            {/* Key Metrics Row */}
            {!isLoading && account && (
              <div className='mt-2 flex items-center gap-4 text-sm'>
                <div className='flex items-center gap-2'>
                  <span className='text-xs text-[var(--to-text-dim)]'>Balance:</span>
                  <span className='font-mono font-semibold text-[var(--to-text-primary)]'>
                    $
                    {account.balance.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                    })}
                  </span>
                </div>
                <div className='h-3 w-px bg-[var(--to-border)]'></div>
                <div className='flex items-center gap-2'>
                  <span className='text-xs text-[var(--to-text-dim)]'>Equity:</span>
                  <span className='font-mono font-semibold text-[var(--to-text-primary)]'>
                    $
                    {account.equity?.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                    }) ||
                      account.balance.toLocaleString(undefined, {
                        minimumFractionDigits: 2,
                      })}
                  </span>
                </div>
                <div className='h-3 w-px bg-[var(--to-border)]'></div>
                <div className='flex items-center gap-2'>
                  <span className='text-xs text-[var(--to-text-dim)]'>Today:</span>
                  <span
                    className={`font-mono font-semibold ${
                      account.daily_pnl >= 0
                        ? 'text-[var(--to-long)]'
                        : 'text-[var(--to-short)]'
                    }`}
                  >
                    {account.daily_pnl >= 0 ? '+' : ''}$
                    {account.daily_pnl.toFixed(2)}
                    <span className='ml-1 text-xs opacity-80'>
                      ({account.daily_pnl >= 0 ? '+' : ''}
                      {account.daily_pnl_pct.toFixed(2)}%)
                    </span>
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        <Button
          variant='outline'
          size='sm'
          className='border-[var(--to-border)] text-[var(--to-text-dim)] hover:bg-[var(--to-surface-raised)] hover:text-[var(--to-text-primary)]'
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
        >
          <RefreshCw
            className={`mr-1.5 h-3.5 w-3.5 ${
              syncMutation.isPending ? 'animate-spin' : ''
            }`}
          />
          Refresh Now
        </Button>
      </div>

      {/* Tabs */}
      <div className='border-b border-[var(--to-border)]'>
        <nav className='flex gap-6'>
          {(
            [
              'overview',
              'positions',
              'history',
              'analytics',
              'journal',
              ...(account?.account_type === 'Eval' || account?.account_type === 'Funded' ? ['challenge'] : []),
            ] as Tab[]
          ).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`
                px-1 py-2 text-sm font-medium border-b-2 transition-colors
                ${
                  activeTab === tab
                    ? 'border-indigo-400 text-indigo-300'
                    : 'border-transparent text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] hover:border-[var(--to-border)]'
                }
              `}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className='tv-card p-3'>
        {isLoading ? (
          <div className='space-y-4'>
            <Skeleton className='h-24 bg-[var(--to-surface-raised)]/60' />
            <Skeleton className='h-48 bg-[var(--to-surface-raised)]/60' />
          </div>
        ) : account ? (
          <>
            {activeTab === 'overview' && <OverviewTab account={account} />}
            {activeTab === 'positions' && (
              <PositionsTab accountName={accountName} />
            )}
            {activeTab === 'history' && (
              <HistoryTab accountName={accountName} />
            )}
            {activeTab === 'analytics' && (
              <AnalyticsTab accountName={accountName} />
            )}
            {activeTab === 'journal' && (
              <JournalTab accountName={accountName} />
            )}
            {activeTab === 'challenge' && (
              <ChallengeTab accountName={accountName} />
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}
