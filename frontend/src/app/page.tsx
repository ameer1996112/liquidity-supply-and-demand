'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { supabase } from '@/lib/supabase';
import { DashboardView } from '@/components/dashboard/DashboardView';
import { cn } from '@/lib/utils';
import { PageStatusBanner } from '@/components/shared/PageStatusBanner';
import { useConnectionHealth } from '@/hooks/useConnectionHealth';

export default function DashboardPage() {
  const [selectedAccount, setSelectedAccount] = useState<string>('global');
  const { status } = useConnectionHealth();

  const { data: accounts = [] } = useQuery({
    queryKey: ['active-accounts'],
    queryFn: async () => {
      if (!supabase) return [];
      const { data } = await supabase
        .from('account_strategies')
        .select('account_name')
        .eq('is_active', true);
      return (data || []).map((a: { account_name: string }) => a.account_name);
    },
  });

  return (
    <div className='flex h-full min-h-0 flex-col gap-2'>
      <header className='flex shrink-0 items-center justify-between gap-3'>
        <div>
          <h1 className='page-title text-base font-semibold'>Dashboard</h1>
          <p className='page-subtitle text-[11px] hidden sm:block'>
            Live command center · telemetry first · 5-minute zones
          </p>
        </div>
        
        {accounts.length > 0 && (
          <div className='flex items-center rounded-lg border border-panel-border bg-surface p-0.5 ml-4'>
            <button
              onClick={() => setSelectedAccount('global')}
              className={cn(
                'px-3 py-1.5 text-[11px] font-medium rounded-md transition-all border border-transparent',
                selectedAccount === 'global' 
                  ? 'bg-[var(--to-surface-raised)] text-text-primary shadow-sm border-panel-border/50' 
                  : 'text-text-dim hover:text-text-secondary'
              )}
            >
              Global
            </button>
            {accounts.map(acc => (
               <button
                 key={acc}
                 onClick={() => setSelectedAccount(acc)}
                 className={cn(
                   'px-3 py-1.5 text-[11px] font-medium rounded-md transition-all border border-transparent', 
                   selectedAccount === acc 
                     ? 'bg-[var(--to-surface-raised)] text-text-primary shadow-sm border-panel-border/50' 
                     : 'text-text-dim hover:text-text-secondary'
                 )}
               >
                 {acc}
               </button>
            ))}
          </div>
        )}
      </header>

      {/* Page-level health banner is hoisted here so it spans full width above the wrapped DashboardView */}
      <PageStatusBanner status={status} surfaceLabel='Dashboard' />

      <div className='flex-1 min-h-0 overflow-hidden pt-1'>
        <DashboardView
          accountName={selectedAccount === 'global' ? undefined : selectedAccount}
          hideHeader={true}
        />
      </div>
    </div>
  );
}
