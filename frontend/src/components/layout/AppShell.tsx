'use client';

import { useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { CommandPalette } from './CommandPalette';
import { AICopilot } from '@/components/copilot/AICopilot';
import { LiveMarketPanel } from '@/components/market/LiveMarketPanel';
import { useSidebar } from '@/providers/SidebarProvider';
import { useShellActions } from '@/providers/ShellActionsProvider';
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
  const {
    copilotOpen,
    marketOpen,
    openCopilot,
    closeCopilot,
    toggleMarket,
    closeMarket,
  } = useShellActions();

  // ⌘/ to toggle AI Copilot — keyboard shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === '/') {
        e.preventDefault();
        openCopilot();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [openCopilot]);

  if (FULLSCREEN_ROUTES.some((r) => pathname.startsWith(r))) {
    return <>{children}</>;
  }

  return (
    <>
      <CommandPalette />
      <AICopilot open={copilotOpen} onClose={closeCopilot} />
      <LiveMarketPanel open={marketOpen} onClose={closeMarket} />
      <div className='relative min-h-screen bg-background'>
        <Sidebar />

        <div
          className={cn(
            'relative flex min-h-screen flex-col',
            'transition-[margin-left] duration-200 ease-out',
            isCollapsed ? SIDEBAR_WIDTH.collapsed : SIDEBAR_WIDTH.expanded
          )}
        >
          <TopBar />

          {isOffline && (
            <div className='border-b border-[var(--to-border)] bg-[var(--to-surface)] px-3 py-1.5 text-[11px] text-[var(--to-text-secondary)]'>
              <div
                className={cn(
                  'mx-auto flex w-full items-center justify-between gap-2',
                  CONTENT_MAX_W
                )}
              >
                <div className='flex items-center gap-2'>
                  <WifiOff className='h-3 w-3 text-[var(--to-short)]' />
                  <span className='font-semibold'>
                    Offline / API unreachable
                  </span>
                  <span className='hidden text-[10px] text-[var(--to-text-dim)] sm:inline'>
                    Using last known data. Automatic retries will continue in
                    the background.
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

          {/* Page content — keyed by pathname for fade-in-up transition on route change */}
          <main className='flex-1 overflow-hidden p-3 sm:p-4'>
            <div
              key={pathname}
              className={cn(
                'mx-auto h-full w-full animate-fade-in-up',
                CONTENT_MAX_W
              )}
            >
              {children}
            </div>
          </main>
        </div>
      </div>
    </>
  );
}
