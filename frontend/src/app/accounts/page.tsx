'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Settings2 } from 'lucide-react';
import { BrokerProfilesPanel } from '@/components/accounts/BrokerProfilesPanel';
import { AccountOverviewList } from '@/components/accounts/AccountOverviewList';
import { useAccountsComparison } from '@/hooks/useAccounts';

export default function AccountsPage() {
  const [credentialsOpen, setCredentialsOpen] = useState(false);
  const { data: accounts = [], isLoading } = useAccountsComparison();

  return (
    <div className='space-y-6'>
      {/* Page header */}
      <div>
        <h1 className='page-title text-lg font-semibold'>Accounts</h1>
        <p className='page-subtitle mt-0.5 text-xs'>
          Overview of all trading accounts. Click an account to view full details.
        </p>
      </div>

      {/* Account overview cards */}
      <AccountOverviewList accounts={accounts} isLoading={isLoading} />

      {/* Credentials management — collapsible */}
      <div className='rounded-xl border border-[var(--to-border)]'>
        <button
          id='credentials-toggle'
          onClick={() => setCredentialsOpen((v) => !v)}
          className='w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-[var(--to-text-secondary)] hover:text-[var(--to-text-primary)] transition-colors'
        >
          <span className='flex items-center gap-2'>
            <Settings2 className='h-4 w-4 text-[var(--to-warning)]' />
            Manage Broker Credentials
          </span>
          {credentialsOpen ? (
            <ChevronUp className='h-4 w-4' />
          ) : (
            <ChevronDown className='h-4 w-4' />
          )}
        </button>

        {credentialsOpen && (
          <div className='border-t border-[var(--to-border)] p-4'>
            <BrokerProfilesPanel />
          </div>
        )}
      </div>
    </div>
  );
}
