'use client';

import { usePathname } from 'next/navigation';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useSidebar } from '@/providers/SidebarProvider';
import { cn } from '@/lib/utils';
import { useConnectionHealth } from '@/hooks/useConnectionHealth';
import { WifiOff } from 'lucide-react';

/** Routes that bypass the shell and render fullscreen (no sidebar/topbar). */
const FULLSCREEN_ROUTES = ['/terminal'] as const;

/** Sidebar width tokens — kept in sync with Sidebar.tsx w-56 / w-14. */
const SIDEBAR_WIDTH = {
  expanded: 'ml-56',
  collapsed: 'ml-14',
} as const;

/** Maximum content column width — prevents over-stretching on ultra-wide. */
const CONTENT_MAX_W = 'max-w-[1800px] 2xl:max-w-[2000px]';

export function AppShell({ children }: { children: React.ReactNode }) {
  const { isCollapsed } = useSidebar();
  const pathname = usePathname();
  const { status } = useConnectionHealth();
  const isOffline = status === 'offline';

  if (FULLSCREEN_ROUTES.some((r) => pathname.startsWith(r))) {
    return <>{children}</>;
  }

  return (
    <div className='relative min-h-screen bg-background'>
      <Sidebar />

      <div
        className={cn(
          'relative flex min-h-screen flex-col',
          'transition-[margin-left] duration-200 ease-out',
          isCollapsed ? SIDEBAR_WIDTH.collapsed : SIDEBAR_WIDTH.expanded,
        )}
      >
        <TopBar />

        {isOffline && (
          <div className='border-b border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-1.5 text-[11px] text-[var(--to-text-secondary)]'>
            <div className={cn('mx-auto flex w-full items-center justify-between gap-2', CONTENT_MAX_W)}>
              <div className='flex items-center gap-2'>
                <WifiOff className='h-3 w-3 text-[var(--to-short)]' />
                <span className='font-semibold'>Offline / API unreachable</span>
                <span className='hidden text-[10px] text-[var(--to-text-dim)] sm:inline'>
                  Using last known data. Automatic retries will continue in the background.
                </span>
              </div>
              <span
                className='hidden font-mono text-[10px] tabular-nums text-[var(--to-text-dim)] sm:inline'
                suppressHydrationWarning
              >
                {new Date().toLocaleTimeString('en-GB', {
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                  hour12: false,
                })}
              </span>
            </div>
          </div>
        )}

        <main className='flex-1 overflow-hidden p-3 sm:p-4'>
          <div className={cn('mx-auto h-full w-full', CONTENT_MAX_W)}>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
