'use client';

import type { ComponentType } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Crosshair,
  Gauge,
  Trophy,
  MoreHorizontal,
  Users,
  Timer,
  Bell,
  BarChart3,
  PlaySquare,
  SlidersHorizontal,
  BookOpen,
  Settings,
} from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';

type NavItem = {
  label: string;
  icon: ComponentType<{ className?: string }>;
  path: string;
};

/** Primary 4 items always visible in the bottom bar */
const PRIMARY_ITEMS: NavItem[] = [
  { label: 'Dashboard', icon: LayoutDashboard, path: '/' },
  { label: 'Risk', icon: Gauge, path: '/risk' },
  { label: 'Prop Firm', icon: Trophy, path: '/prop-firm' },
];

/** Overflow items accessible via the "More" sheet drawer */
const OVERFLOW_ITEMS: NavItem[] = [
  { label: 'Accounts', icon: Users, path: '/accounts' },
  { label: 'Exec Quality', icon: Timer, path: '/execution-quality' },
  { label: 'Alerts', icon: Bell, path: '/alerts' },
  { label: 'Analytics', icon: BarChart3, path: '/analytics' },
  { label: 'Alert Setup', icon: Bell, path: '/alert-setup' },
  { label: 'Optimizer', icon: PlaySquare, path: '/optimizer' },
  { label: 'Strategies', icon: SlidersHorizontal, path: '/strategies' },
  { label: 'Journal', icon: BookOpen, path: '/journal' },
  { label: 'Settings', icon: Settings, path: '/settings' },
];

function NavButton({
  item,
  isActive,
  onClick,
}: {
  item: NavItem;
  isActive: boolean;
  onClick?: () => void;
}) {
  return (
    <Link
      href={item.path}
      onClick={onClick}
      className={cn(
        'flex flex-col items-center justify-center gap-0.5 flex-1 h-full',
        'transition-all duration-150',
        isActive
          ? 'text-[var(--to-warning)]'
          : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]'
      )}
    >
      <item.icon
        className={cn(
          'h-5 w-5 shrink-0',
          isActive && 'drop-shadow-[0_0_6px_rgba(240,185,11,0.7)]'
        )}
      />
      <span
        className={cn(
          'text-[10px] leading-tight',
          isActive ? 'font-semibold' : 'font-medium'
        )}
        style={{ fontFamily: 'var(--font-sans)' }}
      >
        {item.label}
      </span>
    </Link>
  );
}

export function MobileNav() {
  const pathname = usePathname();
  const [sheetOpen, setSheetOpen] = useState(false);

  const isOverflowActive = OVERFLOW_ITEMS.some((item) =>
    item.path === '/'
      ? pathname === '/'
      : pathname.startsWith(item.path)
  );

  return (
    <nav
      className={cn(
        'fixed bottom-0 left-0 right-0 z-50 md:hidden',
        'glass-panel border-t border-[var(--to-border)]',
        'h-16 flex items-stretch px-2',
        'pb-[env(safe-area-inset-bottom,0px)]'
      )}
    >
      {PRIMARY_ITEMS.map((item) => {
        const isActive =
          item.path === '/'
            ? pathname === '/'
            : pathname.startsWith(item.path);
        return (
          <NavButton
            key={item.path}
            item={item}
            isActive={isActive}
          />
        );
      })}

      {/* More — slide-up Sheet drawer */}
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetTrigger asChild>
          <button
            className={cn(
              'flex flex-col items-center justify-center gap-0.5 flex-1 h-full',
              'transition-all duration-150',
              isOverflowActive
                ? 'text-[var(--to-warning)]'
                : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]'
            )}
          >
            <MoreHorizontal
              className={cn(
                'h-5 w-5 shrink-0',
                isOverflowActive &&
                  'drop-shadow-[0_0_6px_rgba(240,185,11,0.7)]'
              )}
            />
            <span
              className={cn(
                'text-[10px] leading-tight',
                isOverflowActive ? 'font-semibold' : 'font-medium'
              )}
              style={{ fontFamily: 'var(--font-sans)' }}
            >
              More
            </span>
          </button>
        </SheetTrigger>
        <SheetContent
          side='bottom'
          className='glass-panel border-t border-[var(--to-border)] rounded-t-xl pb-[env(safe-area-inset-bottom,16px)]'
        >
          <SheetHeader className='mb-4'>
            <SheetTitle
              className='text-[13px] font-semibold text-[var(--to-text-secondary)] uppercase tracking-[0.15em]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              More
            </SheetTitle>
          </SheetHeader>
          <div className='grid grid-cols-4 gap-2'>
            {OVERFLOW_ITEMS.map((item) => {
              const isActive =
                item.path === '/'
                  ? pathname === '/'
                  : pathname.startsWith(item.path);
              return (
                <NavButton
                  key={item.path}
                  item={item}
                  isActive={isActive}
                  onClick={() => setSheetOpen(false)}
                />
              );
            })}
          </div>
        </SheetContent>
      </Sheet>
    </nav>
  );
}
