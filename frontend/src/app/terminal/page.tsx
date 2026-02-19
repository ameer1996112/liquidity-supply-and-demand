'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/**
 * The legacy Galil terminal view has been removed.
 * Redirect to the main TradeOps dashboard.
 */
export default function TerminalPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/');
  }, [router]);

  return (
    <div
      className='flex h-screen items-center justify-center'
      style={{ backgroundColor: '#0F172A' }}
    >
      <span
        className='text-[11px] text-slate-600'
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        [ REDIRECTING TO DASHBOARD ]
      </span>
    </div>
  );
}
