'use client';

import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useSidebar } from '@/providers/SidebarProvider';
import { cn } from '@/lib/utils';

export function AppShell({ children }: { children: React.ReactNode }) {
  const { isCollapsed } = useSidebar();

  return (
    <div className='min-h-screen bg-[#131722]'>
      <Sidebar />
      <div
        className={cn(
          'flex flex-col min-h-screen transition-all duration-200',
          isCollapsed ? 'ml-16' : 'ml-56',
        )}
      >
        <TopBar />
        <main className='flex-1 p-6 overflow-hidden'>{children}</main>
      </div>
    </div>
  );
}
