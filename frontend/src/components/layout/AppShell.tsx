'use client';

import { usePathname } from 'next/navigation';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useSidebar } from '@/providers/SidebarProvider';
import { cn } from '@/lib/utils';

const FULLSCREEN_ROUTES = ['/terminal'];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { isCollapsed } = useSidebar();
  const pathname = usePathname();

  if (FULLSCREEN_ROUTES.some((r) => pathname.startsWith(r))) {
    return <>{children}</>;
  }

  return (
    <div className='relative min-h-screen bg-[var(--to-bg)]'>
      <Sidebar />
      <div
        className={cn(
          'relative flex min-h-screen flex-col transition-[margin-left] duration-200 ease-out',
          isCollapsed ? 'ml-14' : 'ml-56',
        )}
      >
        <TopBar />
        <main className='flex-1 overflow-hidden p-3 sm:p-4'>
          <div className='mx-auto h-full w-full max-w-[1800px] 2xl:max-w-[2000px]'>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
