'use client';

import { useState, useEffect } from 'react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useQuery } from '@tanstack/react-query';
import { fetchAccountDetail } from '@/lib/api';
import type { AccountComparisonApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Wifi, WifiOff, AlertTriangle } from 'lucide-react';
import { OverviewTab } from '@/components/accounts/detail/OverviewTab';
import { PositionsTab } from '@/components/accounts/detail/PositionsTab';
import { HistoryTab } from '@/components/accounts/detail/HistoryTab';
import { AnalyticsTab } from '@/components/accounts/detail/AnalyticsTab';
import { ChallengeTab } from '@/components/accounts/detail/ChallengeTab';
import { JournalTab } from '@/components/accounts/detail/JournalTab';
import { BrokerProfilesPanel } from '@/components/accounts/BrokerProfilesPanel';
import { Skeleton } from '@/components/ui/skeleton';

interface AccountDrawerProps {
  account: AccountComparisonApi | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialTab?: string;
}

export function AccountDrawer({
  account,
  open,
  onOpenChange,
  initialTab = 'overview',
}: AccountDrawerProps) {
  const [activeTab, setActiveTab] = useState(initialTab);

  // Sync tab when drawer opens or initialTab changes
  useEffect(() => {
    if (open) setActiveTab(initialTab);
  }, [open, initialTab]);

  const isPropFirm =
    account?.account_type === 'Funded' || account?.account_type === 'Eval';

  const { data: accountDetail, isLoading } = useQuery({
    queryKey: ['account-detail', account?.account_name],
    queryFn: () => fetchAccountDetail(account!.account_name),
    enabled: !!account?.account_name && open,
    staleTime: 0,
    refetchOnMount: 'always',
  });

  if (!account) return null;

  const isConnected = account.connection_status === 'connected';

  const typeColors: Record<string, string> = {
    Funded: 'text-[var(--to-long)] bg-[var(--to-long)]/10 border-[var(--to-long)]/20',
    Eval: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    Personal: 'text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] border-[var(--to-border)]',
  };

  const tabs = [
    { value: 'overview', label: 'Overview' },
    { value: 'positions', label: 'Positions' },
    { value: 'history', label: 'History' },
    { value: 'analytics', label: 'Analytics' },
    { value: 'journal', label: 'Journal' },
    ...(isPropFirm ? [{ value: 'challenge', label: 'Challenge' }] : []),
    { value: 'settings', label: 'Settings' },
  ];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side='right'
        className='w-full sm:max-w-[520px] bg-[var(--to-surface)] border-l border-[var(--to-border)] flex flex-col p-0 gap-0'
      >
        {/* ── Header ── */}
        <SheetHeader className='px-5 py-4 border-b border-[var(--to-border)] shrink-0'>
          <div className='flex items-center gap-3'>
            <span
              className={cn(
                'h-2 w-2 rounded-full flex-shrink-0',
                isConnected ? 'bg-[var(--to-long)]' : 'bg-[var(--to-short)]'
              )}
            />
            {isConnected ? (
              <Wifi className='h-3.5 w-3.5 text-[var(--to-long)]' />
            ) : (
              <WifiOff className='h-3.5 w-3.5 text-[var(--to-short)]' />
            )}
            <SheetTitle className='font-mono text-base font-bold text-[var(--to-text-primary)]'>
              {account.account_name}
            </SheetTitle>
            {account.account_type && (
              <span
                className={cn(
                  'px-1.5 py-0.5 text-[9px] font-mono font-bold rounded uppercase tracking-wider border',
                  typeColors[account.account_type] ?? typeColors.Personal
                )}
              >
                {account.account_type}
              </span>
            )}
            <span className='text-[10px] font-mono text-[var(--to-text-dim)]'>
              {(account as any).run_mode ?? 'LIVE'}
            </span>
          </div>
        </SheetHeader>

        {/* ── Tabs ── */}
        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          className='flex flex-col flex-1 min-h-0'
        >
          <TabsList className='shrink-0 w-full justify-start rounded-none border-b border-[var(--to-border)] bg-[var(--to-surface)] px-4 gap-0 h-9'>
            {tabs.map((tab) => (
              <TabsTrigger
                key={tab.value}
                value={tab.value}
                className='rounded-none border-b-2 border-transparent data-[state=active]:border-[var(--to-long)] data-[state=active]:bg-transparent px-3 h-9 text-[11px] font-mono'
              >
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>

          <div className='flex-1 overflow-y-auto min-h-0'>
            <TabsContent value='overview' className='p-4 mt-0'>
              {isLoading ? (
                <DrawerSkeleton />
              ) : (accountDetail || account) ? (
                <OverviewTab account={(accountDetail || account) as any} />
              ) : (
                <DrawerError />
              )}
            </TabsContent>

            <TabsContent value='positions' className='p-4 mt-0'>
              <PositionsTab accountName={account.account_name} />
            </TabsContent>

            <TabsContent value='history' className='p-4 mt-0'>
              <HistoryTab accountName={account.account_name} />
            </TabsContent>

            <TabsContent value='analytics' className='p-4 mt-0'>
              <AnalyticsTab accountName={account.account_name} />
            </TabsContent>

            <TabsContent value='journal' className='p-4 mt-0'>
              <JournalTab accountName={account.account_name} />
            </TabsContent>

            {isPropFirm && (
              <TabsContent value='challenge' className='p-4 mt-0'>
                <ChallengeTab accountName={account.account_name} />
              </TabsContent>
            )}

            <TabsContent value='settings' className='p-4 mt-0'>
              <BrokerProfilesPanel />
            </TabsContent>
          </div>
        </Tabs>
      </SheetContent>
    </Sheet>
  );
}

function DrawerSkeleton() {
  return (
    <div className='space-y-3'>
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className='h-16 w-full rounded skeleton-shimmer' />
      ))}
    </div>
  );
}

function DrawerError() {
  return (
    <div className='flex flex-col items-center gap-2 py-10 text-[var(--to-text-dim)]'>
      <AlertTriangle className='h-5 w-5' />
      <span className='text-xs font-mono'>Failed to load account data</span>
    </div>
  );
}
