'use client';

import type { ComponentType } from 'react';
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
  Timer,
  SlidersHorizontal,
  Bell,
  Trophy,
  ScanLine,
  ClipboardList,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSidebar } from '@/providers/SidebarProvider';
import { useConnectionHealth } from '@/hooks/useConnectionHealth';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

/** Small connection status pill shown at the bottom of the sidebar. */
function ConnectionPill() {
  const { status } = useConnectionHealth();
  const isHealthy = status === 'healthy';
  const isDegraded = status === 'degraded';

  return (
    <div className='mx-1 mb-1 flex items-center gap-2 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)]/50 px-2.5 py-1.5'>
      <span
        className={cn(
          'h-1.5 w-1.5 rounded-full flex-shrink-0',
          isHealthy
            ? 'bg-[var(--to-long)] shadow-[0_0_6px_rgba(14,203,129,0.7)] pulse-active'
            : isDegraded
            ? 'bg-[var(--to-warning)] badge-pulse'
            : 'bg-[var(--to-short)]'
        )}
      />
      <span
        className='text-[10px] font-medium text-[var(--to-text-dim)]'
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        {isHealthy ? 'Connected' : isDegraded ? 'Degraded' : 'Offline'}
      </span>
    </div>
  );
}

type NavItem = {
  label: string;
  icon: ComponentType<{ className?: string }>;
  path: string;
};

type NavGroup = {
  id: string;
  label: string;
  items: NavItem[];
};

// Terminal removed — Galil terminal view is deprecated
const NAV_GROUPS: NavGroup[] = [
  {
    id: 'overview',
    label: 'Overview',
    items: [{ label: 'Dashboard', icon: LayoutDashboard, path: '/' }],
  },
  {
    id: 'trading',
    label: 'Trading',
    items: [
      { label: 'Positions', icon: Crosshair, path: '/positions' },
      { label: 'Accounts', icon: Users, path: '/accounts' },
      { label: 'Exec Quality', icon: Timer, path: '/execution-quality' },
    ],
  },
  {
    id: 'monitoring',
    label: 'Monitoring',
    items: [
      { label: 'Risk Monitor', icon: Gauge, path: '/risk' },
      { label: 'Scanner', icon: ScanLine, path: '/scanner' },
      { label: 'Alerts', icon: Bell, path: '/alerts' },
      { label: 'Prop Firm', icon: Trophy, path: '/prop-firm' },
    ],
  },
  {
    id: 'analytics',
    label: 'Analytics',
    items: [
      { label: 'Analytics', icon: BarChart3, path: '/analytics' },
      { label: 'Backtest', icon: LineChart, path: '/backtest' },
    ],
  },
  {
    id: 'strategy',
    label: 'Strategy',
    items: [
      { label: 'Strategies', icon: SlidersHorizontal, path: '/strategies' },
      { label: 'Rules', icon: ShieldCheck, path: '/rules' },
    ],
  },
  {
    id: 'ops',
    label: 'Ops',
    items: [
      { label: 'Tickets', icon: ClipboardList, path: '/tickets' },
      { label: 'Journal', icon: BookOpen, path: '/journal' },
      { label: 'Settings', icon: Settings, path: '/settings' },
    ],
  },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const { isCollapsed, toggleCollapse } = useSidebar();

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          'fixed left-0 top-0 bottom-0 z-40 hidden md:flex flex-col sidebar-glass',
          'transition-all duration-200 ease-in-out',
          isCollapsed ? 'w-14' : 'w-56'
        )}
      >
        {/* ── Brand header ─────────────────────────────────────────── */}
        <div
          className={cn(
            'flex h-12 items-center border-b border-[var(--to-border)] px-3',
            isCollapsed ? 'justify-center' : 'justify-between'
          )}
        >
          {!isCollapsed && (
            <div className='flex items-center gap-2'>
              <div
                className='flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--to-warning)]/12 border border-[var(--to-warning)]/25'
                style={{ boxShadow: '0 0 10px rgba(240,185,11,0.25)' }}
              >
                <Activity className='h-4 w-4 text-[var(--to-warning)]' />
              </div>
              <div className='flex flex-col leading-tight'>
                <span
                  className='text-[13px] font-bold tracking-tight text-[var(--to-text-primary)]'
                  style={{
                    fontFamily: 'var(--font-sans)',
                    letterSpacing: '-0.02em',
                  }}
                >
                  TradeOps
                </span>
                <span
                  suppressHydrationWarning
                  className='text-[9px] uppercase tracking-[0.2em] text-[var(--to-text-dim)]'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  5M · LIVE
                </span>
              </div>
            </div>
          )}
          {isCollapsed && (
            <div
              className='flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--to-warning)]/12 border border-[var(--to-warning)]/25'
              style={{ boxShadow: '0 0 10px rgba(240,185,11,0.25)' }}
            >
              <Activity className='h-4 w-4 text-[var(--to-warning)]' />
            </div>
          )}
        </div>

        {/* ── Navigation ───────────────────────────────────────────── */}
        <nav className='flex-1 space-y-3 px-2 py-3'>
          {NAV_GROUPS.map((group) => (
            <div key={group.id} className='space-y-1.5'>
              {!isCollapsed && (
                <div
                  className='px-2.5 pb-0.5 pt-1 text-[9px] uppercase tracking-[0.2em] text-[var(--to-text-dim)] flex items-center gap-2'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  <span className='flex-1 h-px bg-[var(--to-border)]' />
                  {group.label}
                  <span className='flex-1 h-px bg-[var(--to-border)]' />
                </div>
              )}
              <div className='space-y-0.5'>
                {group.items.map((item) => {
                  const isActive =
                    item.path === '/'
                      ? pathname === '/'
                      : pathname.startsWith(item.path);

                  const linkContent = (
                    <Link
                      key={item.path}
                      href={item.path}
                      className={cn(
                        'group relative flex items-center gap-2.5 rounded-lg px-2.5 py-1.5',
                        'transition-all duration-150',
                        isActive
                          ? 'bg-[var(--to-warning)]/10 text-[var(--to-warning)] border-l-[3px] border-l-[var(--to-warning)]/70 border-t-0 border-r-0 border-b-0 pl-[7px] pr-2.5'
                          : 'border border-transparent text-[var(--to-text-secondary)] hover:bg-[var(--to-surface-raised)]/60 hover:text-[var(--to-text-primary)]',
                        isCollapsed && 'justify-center px-0'
                      )}
                    >
                      {isActive && <span className='nav-active-glow' />}
                      <item.icon
                        className={cn(
                          'h-4 w-4 shrink-0',
                          isActive
                            ? 'text-[var(--to-warning)]'
                            : 'text-[var(--to-text-dim)] group-hover:text-[var(--to-text-secondary)]'
                        )}
                      />
                      {!isCollapsed && (
                        <span
                          className='text-[12px] font-medium'
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
              </div>
            </div>
          ))}
        </nav>

        {/* ── Footer ───────────────────────────────────────────────── */}
        <div className='border-t border-[var(--to-border)] px-2 pb-3 pt-2 space-y-1'>
          {/* Connection status pill */}
          {!isCollapsed && <ConnectionPill />}

          <button
            onClick={toggleCollapse}
            className={cn(
              'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2',
              'border border-transparent text-[var(--to-text-dim)] transition-colors duration-100',
              'hover:bg-[var(--to-surface)] hover:text-[var(--to-text-secondary)]',
              isCollapsed && 'justify-center px-0'
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
