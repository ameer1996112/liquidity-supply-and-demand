'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  BarChart3,
  BookOpen,
  Settings,
  ShieldCheck,
  Crosshair,
  PanelLeftClose,
  PanelLeft,
  Activity,
  Gauge,
  Users,
  LineChart,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSidebar } from '@/providers/SidebarProvider';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

// Terminal removed — Galil terminal view is deprecated
const NAV_ITEMS = [
  { label: 'Dashboard', icon: LayoutDashboard, path: '/' },
  { label: 'Positions', icon: Crosshair, path: '/positions' },
  { label: 'Risk Monitor', icon: Gauge, path: '/risk' },
  { label: 'Accounts', icon: Users, path: '/accounts' },
  { label: 'Analytics', icon: BarChart3, path: '/analytics' },
  { label: 'Backtest', icon: LineChart, path: '/backtest' },
  { label: 'Rules', icon: ShieldCheck, path: '/rules' },
  { label: 'Journal', icon: BookOpen, path: '/journal' },
  { label: 'Settings', icon: Settings, path: '/settings' },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const { isCollapsed, toggleCollapse } = useSidebar();

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          'fixed left-0 top-0 bottom-0 z-40 flex flex-col',
          'border-r border-[var(--to-border)]',
          'bg-[var(--to-bg)]',
          'transition-all duration-200 ease-in-out',
          isCollapsed ? 'w-14' : 'w-56',
        )}
      >
        {/* ── Brand header ─────────────────────────────────────────── */}
        <div
          className={cn(
            'flex h-12 items-center border-b border-[var(--to-border)] px-3',
            isCollapsed ? 'justify-center' : 'justify-between',
          )}
        >
          {!isCollapsed && (
            <div className='flex items-center gap-2'>
              <div className='flex h-7 w-7 items-center justify-center rounded bg-[var(--to-warning)]/15 border border-[var(--to-warning)]/30'>
                <Activity className='h-4 w-4 text-[var(--to-warning)]' />
              </div>
              <div className='flex flex-col leading-tight'>
                <span
                  className='text-[13px] font-semibold tracking-tight text-[var(--to-text-primary)]'
                  style={{ fontFamily: 'var(--font-sans)' }}
                >
                  TradeOps
                </span>
                <span
                  suppressHydrationWarning
                  className='text-[9px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  5M · LIVE
                </span>
              </div>
            </div>
          )}
          {isCollapsed && (
            <div className='flex h-7 w-7 items-center justify-center rounded bg-[var(--to-warning)]/15 border border-[var(--to-warning)]/30'>
              <Activity className='h-4 w-4 text-[var(--to-warning)]' />
            </div>
          )}
        </div>

        {/* ── Navigation ───────────────────────────────────────────── */}
        <nav className='flex-1 space-y-0.5 px-2 py-3'>
          {NAV_ITEMS.map((item) => {
            const isActive =
              item.path === '/'
                ? pathname === '/'
                : pathname.startsWith(item.path);

            const linkContent = (
              <Link
                key={item.path}
                href={item.path}
                className={cn(
                  'group relative flex items-center gap-2.5 rounded-lg px-2.5 py-2',
                  'transition-colors duration-100',
                  isActive
                    ? 'bg-[var(--to-warning)]/10 text-[var(--to-warning)] border border-[var(--to-warning)]/20'
                    : 'border border-transparent text-[var(--to-text-secondary)] hover:bg-[var(--to-surface-raised)] hover:text-[var(--to-text-primary)]',
                  isCollapsed && 'justify-center px-0',
                )}
              >
                {/* Active indicator */}
                {isActive && (
                  <span className='absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r bg-[var(--to-warning)]' />
                )}
                <item.icon
                  className={cn(
                    'h-4 w-4 shrink-0',
                    isActive
                      ? 'text-[var(--to-warning)]'
                      : 'text-[var(--to-text-dim)] group-hover:text-[var(--to-text-secondary)]',
                  )}
                />
                {!isCollapsed && (
                  <span
                    className='text-[12.5px] font-medium'
                    style={{ fontFamily: 'var(--font-sans)' }}
                  >
                    {item.label}
                  </span>
                )}
              </Link>
            );

            if (isCollapsed) {
              return (
                <Tooltip key={item.path}>
                  <TooltipTrigger asChild>{linkContent}</TooltipTrigger>
                  <TooltipContent side='right' sideOffset={8}>
                    {item.label}
                  </TooltipContent>
                </Tooltip>
              );
            }

            return linkContent;
          })}
        </nav>

        {/* ── Footer ───────────────────────────────────────────────── */}
        <div className='border-t border-[var(--to-border)] px-2 pb-3 pt-2 space-y-1'>
          <button
            onClick={toggleCollapse}
            className={cn(
              'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2',
              'border border-transparent text-[var(--to-text-dim)] transition-colors duration-100',
              'hover:bg-[var(--to-surface)] hover:text-[var(--to-text-secondary)]',
              isCollapsed && 'justify-center px-0',
            )}
          >
            {isCollapsed ? (
              <PanelLeft className='h-4 w-4' />
            ) : (
              <>
                <PanelLeftClose className='h-4 w-4' />
                <span
                  className='text-[12px] font-medium'
                  style={{ fontFamily: 'var(--font-sans)' }}
                >
                  Collapse
                </span>
              </>
            )}
          </button>

          {!isCollapsed && (
            <div className='px-2.5 py-1'>
              <span
                className='text-[10px] text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                v3.2 · TradeOps
              </span>
            </div>
          )}
        </div>
      </aside>
    </TooltipProvider>
  );
}
