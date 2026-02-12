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

type Tab = 'overview' | 'positions' | 'history' | 'analytics' | 'journal';

export default function AccountDetailPage() {
  const params = useParams();
  const router = useRouter();
  const accountName = decodeURIComponent(params.account_name as string);
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const { addToast } = useToast();
  const queryClient = useQueryClient();

  // Fetch account details
  const { data: account, isLoading, error } = useQuery({
    queryKey: ['account-detail', accountName],
    queryFn: () => fetchAccountDetail(accountName),
    staleTime: 30_000,
  });

  // Sync mutation
  const syncMutation = useMutation({
    mutationFn: () => syncAccount(accountName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['account-detail', accountName] });
      queryClient.invalidateQueries({ queryKey: ['portfolio-control', 'accounts', 'comparison'] });
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

  const connectionStatus = (account?.connection_status || 'not_configured') as 'connected' | 'disconnected' | 'error' | 'not_configured';
  const connectionColor = {
    connected: 'text-emerald-500',
    disconnected: 'text-amber-500',
    error: 'text-red-500',
    not_configured: 'text-zinc-500',
  }[connectionStatus];

  const connectionLabel = {
    connected: 'Connected',
    disconnected: 'Disconnected',
    error: 'Error',
    not_configured: 'Not Configured',
  }[connectionStatus];

  if (error) {
    return (
      <div className="space-y-4">
        <Button
          variant="ghost"
          size="sm"
          className="text-zinc-400 hover:text-zinc-200"
          onClick={() => router.push('/accounts')}
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Accounts
        </Button>
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 px-4 py-3 text-sm text-red-600">
          Failed to load account details: {(error as Error).message}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            className="text-zinc-400 hover:text-zinc-200"
            onClick={() => router.push('/accounts')}
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>

          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-semibold text-zinc-100">
                {isLoading ? <Skeleton className="h-6 w-48 bg-[#1e222d]" /> : accountName}
              </h1>
              {!isLoading && account && (
                <>
                  {account.account_type && (
                    <span className="px-2 py-0.5 text-xs font-mono rounded bg-[#2a2e39] text-zinc-400">
                      {account.account_type}
                    </span>
                  )}
                  {account.provider && account.provider !== 'Personal' && (
                    <span className="px-2 py-0.5 text-xs font-mono rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                      {account.provider}
                    </span>
                  )}
                  <span className={`flex items-center gap-1.5 text-xs font-mono ${connectionColor}`}>
                    <span className="relative flex h-2 w-2">
                      <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${connectionStatus === 'connected' ? 'bg-emerald-500' : 'bg-amber-500'} opacity-75`}></span>
                      <span className={`relative inline-flex rounded-full h-2 w-2 ${connectionStatus === 'connected' ? 'bg-emerald-500' : connectionStatus === 'error' ? 'bg-red-500' : 'bg-amber-500'}`}></span>
                    </span>
                    {connectionLabel}
                  </span>
                </>
              )}
            </div>

            {/* Key Metrics Row */}
            {!isLoading && account && (
              <div className="flex items-center gap-4 mt-2 text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-zinc-500 text-xs">Balance:</span>
                  <span className="font-mono font-semibold text-zinc-200">
                    ${account.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="h-3 w-px bg-zinc-700"></div>
                <div className="flex items-center gap-2">
                  <span className="text-zinc-500 text-xs">Equity:</span>
                  <span className="font-mono font-semibold text-zinc-200">
                    ${account.equity?.toLocaleString(undefined, { minimumFractionDigits: 2 }) || account.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="h-3 w-px bg-zinc-700"></div>
                <div className="flex items-center gap-2">
                  <span className="text-zinc-500 text-xs">Today:</span>
                  <span className={`font-mono font-semibold ${account.daily_pnl >= 0 ? 'text-[#26a69a]' : 'text-[#ef5350]'}`}>
                    {account.daily_pnl >= 0 ? '+' : ''}${account.daily_pnl.toFixed(2)}
                    <span className="text-xs ml-1 opacity-80">
                      ({account.daily_pnl >= 0 ? '+' : ''}{account.daily_pnl_pct.toFixed(2)}%)
                    </span>
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        <Button
          variant="outline"
          size="sm"
          className="border-[#2a2e39] text-zinc-400 hover:bg-[#2a2e39] hover:text-zinc-200"
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
        >
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
          Refresh Now
        </Button>
      </div>

      {/* Tabs */}
      <div className="border-b border-[#2a2e39]">
        <nav className="flex gap-6">
          {(['overview', 'positions', 'history', 'analytics', 'journal'] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`
                px-1 py-2 text-sm font-medium border-b-2 transition-colors
                ${activeTab === tab
                  ? 'border-emerald-500 text-emerald-500'
                  : 'border-transparent text-zinc-500 hover:text-zinc-300 hover:border-zinc-700'
                }
              `}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div>
        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-24 bg-[#1e222d]" />
            <Skeleton className="h-48 bg-[#1e222d]" />
          </div>
        ) : account ? (
          <>
            {activeTab === 'overview' && <OverviewTab account={account} />}
            {activeTab === 'positions' && <PositionsTab accountName={accountName} />}
            {activeTab === 'history' && <HistoryTab accountName={accountName} />}
            {activeTab === 'analytics' && <AnalyticsTab accountName={accountName} />}
            {activeTab === 'journal' && <JournalTab accountName={accountName} />}
          </>
        ) : null}
      </div>
    </div>
  );
}
