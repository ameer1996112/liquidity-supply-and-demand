'use client';

import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useSidebar } from '@/providers/SidebarProvider';
import { cn } from '@/lib/utils';

export function AppShell({ children }: { children: React.ReactNode }) {
  const { isCollapsed } = useSidebar();

  return (
    <div className='relative min-h-screen bg-grid-overlay'>
      <div className='pointer-events-none absolute inset-0 bg-[radial-gradient(65%_40%_at_12%_0%,rgba(95,131,255,0.16),transparent_60%)]' />
      <Sidebar />
      <div
        className={cn(
          'relative z-10 flex min-h-screen flex-col transition-all duration-200 ease-out',
          isCollapsed ? 'ml-16' : 'ml-60'
        )}
      >
        <TopBar />
        <main className='flex-1 overflow-hidden p-3 sm:p-4 lg:p-6'>
          <div className='h-full overflow-hidden rounded-2xl border border-[rgba(94,117,161,0.28)] bg-[rgba(8,13,24,0.55)] shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]'>
            <div className='h-full p-4 sm:p-5 lg:p-6'>{children}</div>
          </div>
        </main>
      </div>
    </div>
  );
}
