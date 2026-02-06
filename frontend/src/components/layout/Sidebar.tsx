'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  BarChart3,
  BookOpen,
  Settings,
  ShieldCheck,
  FlaskConical,
  PanelLeftClose,
  PanelLeft,
  Activity,
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
  { label: 'Analytics', icon: BarChart3, path: '/analytics' },
  { label: 'Rules', icon: ShieldCheck, path: '/rules' },
  { label: 'Journal', icon: BookOpen, path: '/journal' },
  { label: 'Backtest', icon: FlaskConical, path: '/backtest' },
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
          'bg-[#0f1117] border-r border-[#2a2e39]',
          'transition-all duration-200 ease-in-out',
          isCollapsed ? 'w-16' : 'w-56'
        )}
      >
        {/* Header */}
        <div
          className={cn(
            'flex items-center h-14 px-4 border-b border-[#2a2e39]',
            isCollapsed ? 'justify-center' : 'justify-between'
          )}
        >
          {!isCollapsed && (
            <div className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-emerald-500" />
              <span className="font-mono text-sm font-bold text-zinc-100 tracking-tight">
                TradeOps
              </span>
            </div>
          )}
          {isCollapsed && (
            <Activity className="w-5 h-5 text-emerald-500" />
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-2 space-y-1">
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
                  'flex items-center gap-3 px-3 py-2.5 rounded-md',
                  'transition-colors duration-150 group relative',
                  isActive
                    ? 'bg-[#1e222d] text-zinc-100'
                    : 'text-zinc-500 hover:text-zinc-300 hover:bg-[#1e222d]/50',
                  isCollapsed && 'justify-center px-0'
                )}
              >
                {/* Active indicator bar */}
                {isActive && (
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-emerald-500 rounded-r" />
                )}
                <item.icon
                  className={cn(
                    'w-[18px] h-[18px] shrink-0',
                    isActive ? 'text-emerald-500' : 'text-zinc-500 group-hover:text-zinc-400'
                  )}
                />
                {!isCollapsed && (
                  <span className="text-[13px] font-medium">{item.label}</span>
                )}
              </Link>
            );

            if (isCollapsed) {
              return (
                <Tooltip key={item.path}>
                  <TooltipTrigger asChild>{linkContent}</TooltipTrigger>
                  <TooltipContent side="right" sideOffset={8}>
                    {item.label}
                  </TooltipContent>
                </Tooltip>
              );
            }

            return linkContent;
          })}
        </nav>

        {/* Footer */}
        <div className="px-2 pb-3 space-y-2">
          {/* Collapse toggle */}
          <button
            onClick={toggleCollapse}
            className={cn(
              'flex items-center gap-3 w-full px-3 py-2 rounded-md',
              'text-zinc-500 hover:text-zinc-300 hover:bg-[#1e222d]/50',
              'transition-colors duration-150',
              isCollapsed && 'justify-center px-0'
            )}
          >
            {isCollapsed ? (
              <PanelLeft className="w-[18px] h-[18px]" />
            ) : (
              <>
                <PanelLeftClose className="w-[18px] h-[18px]" />
                <span className="text-[13px] font-medium">Collapse</span>
              </>
            )}
          </button>

          {/* Version */}
          {!isCollapsed && (
            <div className="px-3 py-1">
              <span className="text-[10px] text-zinc-600 font-mono">v3.0</span>
            </div>
          )}
        </div>
      </aside>
    </TooltipProvider>
  );
}
