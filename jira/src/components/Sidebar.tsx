'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import {
  LayoutDashboard,
  Layers,
  GitBranch,
  Tag,
  Settings,
  Zap,
  AlertTriangle,
  BarChart3,
  Bot,
  Server,
  TrendingUp,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const NAV = [
  { label: 'Board',      icon: LayoutDashboard, path: '/board' },
  { label: 'Backlog',    icon: Layers,          path: '/backlog' },
  { label: 'Sprints',    icon: GitBranch,       path: '/sprints' },
  { label: 'Labels',     icon: Tag,             path: '/labels' },
  { label: 'Incidents',  icon: AlertTriangle,   path: '/incidents' },
  { label: 'Analytics',  icon: BarChart3,       path: '/analytics' },
  { label: 'AI Assist',  icon: Bot,             path: '/ai-assist' },
  { label: 'Settings',   icon: Settings,        path: '/settings' },
];

interface TradingHealth {
  account: { equity: number; balance: number };
  open_positions: { count: number; unrealised_pnl: number };
  today_trades: { count: number; realised_pnl: number };
  pipeline: { redis: string; worker: string; overall: string };
}

function TradingHealthWidget() {
  const [health, setHealth] = useState<TradingHealth | null>(null);

  useEffect(() => {
    const fetch_ = () => {
      fetch(`${API_BASE}/api/health/trading`)
        .then((r) => r.ok ? r.json() : null)
        .then((d) => d && setHealth(d))
        .catch(() => {});
    };
    fetch_();
    const interval = setInterval(fetch_, 60_000); // refresh every 60s
    return () => clearInterval(interval);
  }, []);

  if (!health) {
    return (
      <div className="px-3 py-3 border-t border-[#1f2335] space-y-1">
        <p className="text-[8px] font-mono uppercase tracking-widest text-[#2d3548]">Trading Health</p>
        <p className="text-[9px] font-mono text-[#2d3548]">Backend offline</p>
      </div>
    );
  }

  const realisedPnl = health.today_trades.realised_pnl;
  const pipelineOk = health.pipeline.overall === 'healthy';

  return (
    <div className="px-3 py-3 border-t border-[#1f2335] space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-[8px] font-mono uppercase tracking-widest text-[#475569]">Trading</p>
        <div className={cn('h-1.5 w-1.5 rounded-full', pipelineOk ? 'bg-emerald-500' : 'bg-rose-500')} title={health.pipeline.overall} />
      </div>

      {/* Equity */}
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1 text-[9px] font-mono text-[#475569]">
          <TrendingUp className="h-2.5 w-2.5" />
          Equity
        </span>
        <span className="text-[9px] font-mono text-[#e2e8f0]">${health.account.equity.toLocaleString()}</span>
      </div>

      {/* Today P&L */}
      <div className="flex items-center justify-between">
        <span className="text-[9px] font-mono text-[#475569]">Today P&L</span>
        <span className={cn('text-[9px] font-mono font-bold', realisedPnl >= 0 ? 'text-emerald-400' : 'text-rose-400')}>
          {realisedPnl >= 0 ? '+' : ''}${realisedPnl.toFixed(2)}
        </span>
      </div>

      {/* Open positions */}
      <div className="flex items-center justify-between">
        <span className="text-[9px] font-mono text-[#475569]">Open</span>
        <span className="text-[9px] font-mono text-[#94a3b8]">{health.open_positions.count} pos</span>
      </div>

      {/* Pipeline status */}
      <div className="flex items-center gap-1.5">
        <span className="text-[8px] font-mono text-[#2d3548]">Redis</span>
        <span className={cn('text-[8px] font-mono', health.pipeline.redis === 'running' ? 'text-emerald-500/70' : 'text-rose-500/70')}>
          {health.pipeline.redis === 'running' ? '✓' : '✗'}
        </span>
        <span className="text-[8px] font-mono text-[#2d3548] ml-1">Worker</span>
        <span className={cn('text-[8px] font-mono', health.pipeline.worker === 'running' ? 'text-emerald-500/70' : 'text-rose-500/70')}>
          {health.pipeline.worker === 'running' ? '✓' : '✗'}
        </span>
      </div>
    </div>
  );
}

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

      {/* Trading Health Widget (HEALTH-01, HEALTH-02, HEALTH-03) */}
      <TradingHealthWidget />

      {/* Footer */}
      <div className="px-4 py-2 border-t border-[#1f2335]">
        <p className="text-[9px] font-mono text-[#475569]">v1.1 · Jira App</p>
      </div>
    </aside>
  );
}
