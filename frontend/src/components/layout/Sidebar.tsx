'use client';

import { useState, useRef, useEffect, type ComponentType } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  BarChart3,
  BookOpen,
  Settings,
  ShieldCheck,
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
  FlaskConical,
  Zap,
  EyeOff,
  AlertTriangle,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSidebar } from '@/providers/SidebarProvider';
import { useConnectionHealth } from '@/hooks/useConnectionHealth';
import { useTradingMode, type TradingMode } from '@/providers/TradingModeProvider';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

const MODE_CONFIG: Record<TradingMode, { label: string; icon: typeof FlaskConical; color: string; bg: string; border: string }> = {
  PAPER:   { label: 'Paper',   icon: FlaskConical, color: 'var(--to-warning)', bg: 'var(--to-warning)', border: 'var(--to-warning)' },
  LIVE:    { label: 'Live',    icon: Zap,          color: 'var(--to-long)',    bg: 'var(--to-long)',    border: 'var(--to-long)'    },
  DRY_RUN: { label: 'Dry Run', icon: EyeOff,       color: 'var(--to-text-dim)', bg: 'var(--to-text-dim)', border: 'var(--to-text-dim)' },
};

const MODES: TradingMode[] = ['PAPER', 'LIVE', 'DRY_RUN'];

/** Modal: typed confirmation before enabling LIVE trading. */
function LiveConfirmModal({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
  const [typed, setTyped] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const confirmed = typed === 'LIVE';

  useEffect(() => {
    // Trap focus in the modal
    inputRef.current?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onCancel]);

  return (
    /* Backdrop */
    <div
      className='fixed inset-0 z-50 flex items-center justify-center'
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
    >
      {/* Modal */}
      <div
        className='relative w-full max-w-sm rounded-xl border p-6 shadow-2xl'
        style={{
          background: '#0f0a0a',
          borderColor: 'rgba(239,68,68,0.35)',
          boxShadow: '0 0 40px rgba(239,68,68,0.15), 0 25px 50px rgba(0,0,0,0.5)',
        }}
      >
        {/* Close button */}
        <button
          onClick={onCancel}
          className='absolute right-3 top-3 rounded-md p-1 text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)] transition-colors'
        >
          <X className='h-4 w-4' />
        </button>

        {/* Header */}
        <div className='mb-4 flex items-center gap-3'>
          <div className='flex h-9 w-9 items-center justify-center rounded-full' style={{ background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)' }}>
            <AlertTriangle className='h-5 w-5' style={{ color: '#ef4444' }} />
          </div>
          <div>
            <h2 className='text-sm font-semibold text-[var(--to-text-primary)]'>Enable Live Trading</h2>
            <p className='text-[10px] text-[var(--to-text-dim)] mt-0.5' style={{ fontFamily: 'var(--font-mono)' }}>Real orders · MetaTrader</p>
          </div>
        </div>

        {/* Body */}
        <p className='mb-4 text-[11px] text-[var(--to-text-secondary)] leading-relaxed'>
          Switching to <span className='font-semibold text-[var(--to-text-primary)]'>LIVE</span> mode
          will place <strong>real orders</strong> on your connected MetaTrader account on the
          next incoming webhook signal. This cannot be undone mid-trade.
        </p>

        {/* Typed confirmation */}
        <label className='mb-1.5 block text-[10px] uppercase tracking-widest text-[var(--to-text-dim)]' style={{ fontFamily: 'var(--font-mono)' }}>
          Type <span className='font-bold text-[#ef4444]'>LIVE</span> to confirm
        </label>
        <input
          ref={inputRef}
          type='text'
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          placeholder='LIVE'
          autoComplete='off'
          spellCheck={false}
          className='mb-4 w-full rounded-lg border px-3 py-2 text-sm font-mono text-[var(--to-text-primary)] outline-none transition-colors'
          style={{
            background: 'rgba(239,68,68,0.05)',
            borderColor: confirmed ? 'rgba(239,68,68,0.6)' : 'var(--to-border)',
          }}
          onKeyDown={(e) => { if (e.key === 'Enter' && confirmed) onConfirm(); }}
        />

        {/* Actions */}
        <div className='flex gap-2'>
          <button
            onClick={onCancel}
            className='flex-1 rounded-lg border border-[var(--to-border)] py-2 text-xs font-medium text-[var(--to-text-secondary)] transition-colors hover:bg-[var(--to-surface-raised)]'
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={!confirmed}
            className='flex-1 rounded-lg py-2 text-xs font-semibold transition-all'
            style={{
              background: confirmed ? 'rgba(239,68,68,0.9)' : 'rgba(239,68,68,0.2)',
              color: confirmed ? '#fff' : 'rgba(239,68,68,0.4)',
              cursor: confirmed ? 'pointer' : 'not-allowed',
              border: '1px solid rgba(239,68,68,0.4)',
            }}
          >
            {confirmed ? '⚡ Enable Live' : 'Confirm ▶'}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Trading mode toggle — controls the system-level run mode (PAPER/LIVE/DRY_RUN). */
function TradingModeToggle({ collapsed }: { collapsed: boolean }) {
  const { mode, isSaving, setMode } = useTradingMode();
  const [showLiveModal, setShowLiveModal] = useState(false);
  const active = MODE_CONFIG[mode] ?? MODE_CONFIG.PAPER;
  const ActiveIcon = active.icon;

  function handleModeClick(m: TradingMode) {
    if (m === 'LIVE' && mode !== 'LIVE') {
      setShowLiveModal(true);
    } else {
      setMode(m);
    }
  }

  function handleLiveConfirm() {
    setShowLiveModal(false);
    setMode('LIVE');
  }

  if (collapsed) {
    return (
      <>
        {showLiveModal && (
          <LiveConfirmModal
            onConfirm={handleLiveConfirm}
            onCancel={() => setShowLiveModal(false)}
          />
        )}
        <Tooltip>
          <TooltipTrigger asChild>
            <div
              className='mx-auto flex h-7 w-7 items-center justify-center rounded-lg cursor-default'
              style={{ background: `${active.bg}18`, border: `1px solid ${active.border}30` }}
            >
              <ActiveIcon className='h-3.5 w-3.5' style={{ color: active.color }} />
            </div>
          </TooltipTrigger>
          <TooltipContent side='right' sideOffset={8}>
            Mode: {active.label}
          </TooltipContent>
        </Tooltip>
      </>
    );
  }

  return (
    <>
      {showLiveModal && (
        <LiveConfirmModal
          onConfirm={handleLiveConfirm}
          onCancel={() => setShowLiveModal(false)}
        />
      )}
      <div className='mx-1 mb-1 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)]/50 px-2 py-1.5'>
        <div
          className='mb-1.5 text-[9px] uppercase tracking-[0.2em] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          Mode
        </div>
        <div className='flex gap-1'>
          {MODES.map((m) => {
            const cfg = MODE_CONFIG[m];
            const Icon = cfg.icon;
            const isActive = mode === m;
            return (
              <button
                key={m}
                disabled={isSaving}
                onClick={() => handleModeClick(m)}
                className={cn(
                  'flex flex-1 items-center justify-center gap-1 rounded-md py-1 text-[10px] font-medium transition-all duration-150',
                  isActive
                    ? 'opacity-100'
                    : 'opacity-40 hover:opacity-70'
                )}
                style={isActive ? {
                  background: `${cfg.bg}18`,
                  border: `1px solid ${cfg.border}40`,
                  color: cfg.color,
                } : {
                  background: 'transparent',
                  border: '1px solid transparent',
                  color: 'var(--to-text-dim)',
                }}
              >
                <Icon className='h-3 w-3 shrink-0' />
                {cfg.label}
              </button>
            );
          })}
        </div>
      </div>
    </>
  );
}


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
      { label: 'Accounts', icon: Users, path: '/accounts' },
      { label: 'Exec Quality', icon: Timer, path: '/execution-quality' },
    ],
  },
  {
    id: 'monitoring',
    label: 'Monitoring',
    items: [
      { label: 'Risk Monitor', icon: Gauge, path: '/risk' },
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
      { label: 'Journal', icon: BookOpen, path: '/journal' },
      { label: 'Notifications', icon: Bell, path: '/notifications' },
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
          {/* Trading mode toggle */}
          <TradingModeToggle collapsed={isCollapsed} />
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
