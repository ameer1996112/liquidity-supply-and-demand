'use client';

import { AlertSetupWorkspace } from '@/components/alert-setup/AlertSetupWorkspace';

export default function AlertSetupPage() {
  return (
    <div className='space-y-4 animate-fade-in-up'>
      <div className='flex items-start justify-between gap-3'>
        <div>
          <h1 className='page-title text-lg font-semibold'>Alert Setup</h1>
          <p className='page-subtitle mt-0.5 text-xs'>
            Deploy approved pair configs into TradingView alerts and track batch progress.
          </p>
        </div>
        <span className='tf-badge'>OPS</span>
      </div>
      <AlertSetupWorkspace />
    </div>
  );
}
