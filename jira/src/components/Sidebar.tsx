'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Layers,
  GitBranch,
  Tag,
  Settings,
  Zap,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const NAV = [
  { label: 'Board',    icon: LayoutDashboard, path: '/board' },
  { label: 'Backlog',  icon: Layers,          path: '/backlog' },
  { label: 'Sprints',  icon: GitBranch,       path: '/sprints' },
  { label: 'Labels',   icon: Tag,             path: '/labels' },
  { label: 'Settings', icon: Settings,        path: '/settings' },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex flex-col w-52 shrink-0 border-r border-[#1f2335] bg-[#13161e]">
      {/* Brand */}
      <div className="flex items-center gap-2.5 h-12 px-4 border-b border-[#1f2335]">
        <div className="flex h-6 w-6 items-center justify-center rounded bg-amber-500/15 border border-amber-500/25">
          <Zap className="h-3.5 w-3.5 text-amber-400" />
        </div>
        <div>
          <p className="text-[12px] font-bold text-[#e2e8f0] tracking-tight leading-none">TradeOps</p>
          <p className="text-[9px] font-mono uppercase tracking-widest text-[#475569] leading-none mt-0.5">Issues</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 px-2 space-y-0.5">
        {NAV.map(({ label, icon: Icon, path }) => {
          const active = path === '/' ? pathname === '/' : pathname.startsWith(path);
          return (
            <Link
              key={path}
              href={path}
              className={cn(
                'flex items-center gap-2.5 rounded-md px-3 py-1.5 text-[12px] font-medium transition-all duration-100',
                active
                  ? 'bg-amber-500/10 text-amber-400 border-l-2 border-amber-400 pl-[10px]'
                  : 'text-[#94a3b8] hover:bg-[#1a1d28] hover:text-[#e2e8f0]'
              )}
            >
              <Icon className={cn('h-3.5 w-3.5 shrink-0', active ? 'text-amber-400' : 'text-[#475569]')} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-[#1f2335]">
        <p className="text-[9px] font-mono text-[#475569]">v1.0 · Jira App</p>
      </div>
    </aside>
  );
}
