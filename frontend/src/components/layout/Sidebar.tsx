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
  Monitor,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSidebar } from '@/providers/SidebarProvider';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

const NAV_ITEMS = [
  { label: 'Dashboard', icon: LayoutDashboard, path: '/' },
  { label: 'Terminal', icon: Monitor, path: '/terminal' },
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
          'border-r border-[rgba(100,124,167,0.36)]',
          'bg-[linear-gradient(180deg,rgba(10,17,35,0.98)_0%,rgba(8,13,25,0.98)_100%)]',
          'shadow-[8px_0_34px_rgba(2,5,14,0.5)]',
          'transition-all duration-200 ease-in-out',
          isCollapsed ? 'w-16' : 'w-60'
        )}
      >
        {/* Header */}
        <div
          className={cn(
            'flex h-14 items-center border-b border-[rgba(90,113,154,0.28)] px-4',
            isCollapsed ? 'justify-center' : 'justify-between'
          )}
        >
          {!isCollapsed && (
            <div className='flex items-center gap-2.5'>
              <div className='flex h-8 w-8 items-center justify-center rounded-xl border border-[rgba(112,137,188,0.42)] bg-[rgba(28,42,69,0.84)] shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]'>
                <Activity className='h-[18px] w-[18px] text-[#3fc7ad]' />
              </div>
              <div className='flex flex-col leading-tight'>
                <span className='text-[13px] font-semibold tracking-tight text-[#edf3fd]'>
                  TradeOps
                </span>
                <span className='text-[10px] uppercase tracking-[0.16em] text-[#8e9dbf]'>
                  Command
                </span>
              </div>
            </div>
          )}
          {isCollapsed && <Activity className='h-5 w-5 text-[#3fc7ad]' />}
        </div>

        {/* Navigation */}
        <nav className='flex-1 space-y-1.5 px-2 py-4'>
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
                  'group relative flex items-center gap-3 rounded-xl px-3 py-2.5',
                  'transition-all duration-150',
                  isActive
                    ? 'border border-[rgba(126,150,198,0.5)] bg-[linear-gradient(135deg,rgba(110,141,255,0.2)_0%,rgba(63,199,173,0.12)_100%)] text-[#f3f7ff] shadow-[0_8px_20px_rgba(7,13,25,0.4)]'
                    : 'border border-transparent text-[#aebbd8] hover:border-[rgba(109,132,176,0.3)] hover:bg-[rgba(24,36,59,0.72)] hover:text-[#eef3fb]',
                  isCollapsed && 'justify-center px-0'
                )}
              >
                {/* Active indicator bar */}
                {isActive && (
                  <div className='absolute -left-[1px] top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r bg-[#7d9cff]' />
                )}
                <item.icon
                  className={cn(
                    'w-[18px] h-[18px] shrink-0',
                    isActive
                      ? 'text-[#a8bcff]'
                      : 'text-[#94a5c9] group-hover:text-[#dbe5fa]'
                  )}
                />
                {!isCollapsed && (
                  <span className='text-[13px] font-medium tracking-[0.01em]'>
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

        {/* Footer */}
        <div className='space-y-2 border-t border-[rgba(90,113,154,0.2)] px-2 pb-3 pt-3'>
          {/* Collapse toggle */}
          <button
            onClick={toggleCollapse}
            className={cn(
              'flex w-full items-center gap-3 rounded-xl px-3 py-2',
              'border border-transparent text-[#aebbd8] transition-colors duration-150',
              'hover:border-[rgba(109,132,176,0.3)] hover:bg-[rgba(24,36,59,0.72)] hover:text-[#eef3fb]',
              isCollapsed && 'justify-center px-0'
            )}
          >
            {isCollapsed ? (
              <PanelLeft className='h-[18px] w-[18px]' />
            ) : (
              <>
                <PanelLeftClose className='h-[18px] w-[18px]' />
                <span className='text-[13px] font-medium'>Collapse</span>
              </>
            )}
          </button>

          {/* Version */}
          {!isCollapsed && (
            <div className='px-3 py-1'>
              <span className='font-mono text-[10px] text-[#7d8db2]'>
                v3.1 • refined UI
              </span>
            </div>
          )}
        </div>
      </aside>
    </TooltipProvider>
  );
}
