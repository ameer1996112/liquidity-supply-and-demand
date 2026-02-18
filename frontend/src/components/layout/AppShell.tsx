'use client';

import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useSidebar } from '@/providers/SidebarProvider';
import { cn } from '@/lib/utils';

export function AppShell({ children }: { children: React.ReactNode }) {
  const { isCollapsed } = useSidebar();

  return (
    <div className='relative min-h-screen bg-grid-overlay'>
      <div className='pointer-events-none absolute inset-0 bg-[radial-gradient(65%_40%_at_12%_0%,rgba(110,141,255,0.14),transparent_60%)]' />
      <Sidebar />
      <div
        className={cn(
          'relative z-10 flex min-h-screen flex-col transition-all duration-200 ease-out',
          isCollapsed ? 'ml-16' : 'ml-60'
        )}
      >
        <TopBar />
        <main className='flex-1 overflow-hidden p-3 sm:p-4 lg:p-6'>
          <div className='mx-auto h-full w-full max-w-[1800px] overflow-hidden rounded-2xl border border-[rgba(110,131,170,0.3)] bg-[rgba(10,16,31,0.62)] shadow-[0_14px_34px_rgba(4,9,20,0.3),inset_0_1px_0_rgba(255,255,255,0.04)] 2xl:max-w-[2000px]'>
            <div className='h-full p-4 sm:p-5 lg:p-6'>{children}</div>
          </div>
        </main>
      </div>
    </div>
  );
}
