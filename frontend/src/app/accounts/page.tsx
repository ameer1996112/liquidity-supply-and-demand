'use client';

import { BrokerProfilesPanel } from '@/components/accounts/BrokerProfilesPanel';

export default function AccountsPage() {
  return (
    <div className='space-y-4'>
      <div>
        <h1 className='page-title text-lg font-semibold'>Broker Accounts</h1>
        <p className='page-subtitle mt-0.5 text-xs'>
          Manage MetaAPI credentials and select the active trading account.
        </p>
      </div>

      <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface)] p-4'>
        <BrokerProfilesPanel />
      </div>
    </div>
  );
}
