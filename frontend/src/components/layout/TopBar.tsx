'use client';

import { useEffect, useMemo, useState } from 'react';
import { usePathname } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import {
  Radio,
  FlaskConical,
  Power,
  Clock,
  Activity,
  Sparkles,
  Globe,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTradingMode } from '@/providers/TradingModeProvider';
import { useRiskStatus, useKillSwitchMutation } from '@/hooks/useRiskStatus';
import { useAccountsComparison } from '@/hooks/useAccounts';
import { useSignalStats } from '@/hooks/useTradingSignals';
import {
  fetchReconcileStatus,
  getApiUrl,
  type ReconcileStatusResponse,
  type AccountDetailApi,
} from '@/lib/api';
import {
  KillSwitchConfirmDialog,
  type KillSwitchMode,
} from '@/components/risk/KillSwitchConfirmDialog';
import { AlertBell } from '@/components/alerts/AlertBell';
import { useShellActions } from '@/providers/ShellActionsProvider';
import { useTimezone, TZ_OPTIONS } from '@/providers/TimezoneProvider';

function DualClock() {
  const [now, setNow] = useState<Date | null>(null);
  const [open, setOpen] = useState(false);
  const { timezone, tzAbbr, setTimezone, formatTime } = useTimezone();

  useEffect(() => {
    const update = () => setNow(new Date());
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    if (!open) return;
    const handler = () => setOpen(false);
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [open]);

  if (!now) return null;

  const utc = now.toLocaleTimeString('en-GB', {
    timeZone: 'UTC',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
  const local = formatTime(now);

  return (
    <div className='relative hidden xl:flex'>
      <button
        type='button'
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        className='flex items-center gap-4 text-[11px] tabular-nums bg-[var(--to-surface-raised)]/30 px-3 py-1.5 rounded-lg border border-white/5 backdrop-blur-sm shadow-sm hover:border-white/10 transition-colors'
        style={{ fontFamily: 'var(--font-mono)' }}
        title='Click to change timezone'
      >
        <div className='flex items-center gap-2'>
          <Clock className='h-3.5 w-3.5 text-[var(--to-accent-purple)]/60' />
          <span className='text-white/80 font-medium'>{utc}</span>
          <span className='text-[var(--to-text-dim)] text-[9px] tracking-widest uppercase'>
            UTC
          </span>
        </div>
        <div className='h-3 w-px bg-white/10' />
        <div className='flex items-center gap-2'>
          <span className='text-white/80 font-medium'>{local}</span>
          <span className='text-[var(--to-text-dim)] text-[9px] tracking-widest uppercase'>
            {tzAbbr}
          </span>
        </div>
      </button>

      {/* Timezone dropdown */}
      {open && (
        <div
          className='absolute left-0 top-full mt-1.5 z-[200] min-w-[200px] rounded-xl border border-white/10 bg-[#0d0f14] shadow-2xl overflow-hidden'
          onClick={(e) => e.stopPropagation()}
        >
          <div className='px-3 py-2 border-b border-white/5'>
            <span
              className='text-[9px] font-bold uppercase tracking-widest text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              Display Timezone
            </span>
          </div>
          {TZ_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type='button'
              onClick={() => {
                setTimezone(opt.value);
                setOpen(false);
              }}
              className={cn(
                'flex w-full items-center justify-between px-3 py-2 text-left text-[11px] transition-colors',
                timezone === opt.value
                  ? 'bg-indigo-500/15 text-indigo-300'
                  : 'text-[var(--to-text-secondary)] hover:bg-white/5 hover:text-white'
              )}
              style={{ fontFamily: 'var(--font-sans)' }}
            >
              <span>{opt.label}</span>
              <span
                className='text-[9px] font-bold tracking-widest text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {opt.abbr}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function formatRelativeTime(input: string | null | undefined): string {
  if (!input) return 'never';
  try {
    const d = new Date(input);
    const diff = Date.now() - d.getTime();
    if (Number.isNaN(diff)) return 'unknown';
    if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
    return d.toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  } catch {
    return 'unknown';
  }
}

function useSystemStatus() {
  const { data: health } = useQuery({
    queryKey: ['topbar-health'],
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) return { status: 'offline' as const };
      const res = await fetch(`${base}/health`, {
        signal: AbortSignal.timeout(3000),
      });
      if (!res.ok) return { status: 'offline' as const };
      return res.json() as Promise<{
        status: 'healthy' | 'degraded' | 'offline';
      }>;
    },
    refetchInterval: 30_000,
    staleTime: 15_000,
  });

  const { data: reconcile } = useQuery<ReconcileStatusResponse>({
    queryKey: ['reconcile-status'],
    queryFn: fetchReconcileStatus,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const isApiUp = health?.status != null && health.status !== 'offline';
  const driftCounts =
    reconcile?.accounts?.map((a) => a.last_reconcile_drift_count ?? 0) ?? [];
  const maxDrift = driftCounts.length ? Math.max(...driftCounts) : 0;
  const hasDrift = maxDrift > 0;

  const lastReconcileAt =
    reconcile?.accounts
      ?.map((a) => a.last_reconcile_time)
      .filter((v): v is string => !!v)
      .sort()
      .slice(-1)[0] ?? null;

  const brokerOk =
    reconcile?.accounts && reconcile.accounts.length > 0
      ? reconcile.accounts.every(
          (a) =>
            (a.connection_status ?? 'online').toLowerCase() !== 'offline' &&
            (a.last_reconcile_drift_count ?? 0) === 0
        )
      : undefined;

  return {
    isApiUp,
    healthStatus: health?.status ?? 'offline',
    hasDrift,
    brokerOk,
    lastReconcileAt,
  };
}

function derivePageMeta(pathname: string): { section: string; title: string } {
  if (pathname === '/') {
    return { section: 'Overview', title: 'Dashboard' };
  }
  if (pathname.startsWith('/positions')) {
    return { section: 'Trading', title: 'Positions' };
  }
  if (pathname.startsWith('/risk')) {
    return { section: 'Monitoring', title: 'Risk Monitor' };
  }
  if (pathname.startsWith('/accounts')) {
    return { section: 'Portfolio', title: 'Accounts' };
  }
  if (pathname.startsWith('/execution-quality')) {
    return { section: 'Monitoring', title: 'Execution Quality' };
  }
  if (pathname.startsWith('/analytics')) {
    return { section: 'Analytics', title: 'Analytics' };
  }
  if (pathname.startsWith('/backtest')) {
    return { section: 'Research', title: 'Backtest' };
  }
  if (pathname.startsWith('/backtests')) {
    return { section: 'Research', title: 'Backtests' };
  }
  if (pathname.startsWith('/strategies')) {
    return { section: 'Strategy', title: 'Strategies' };
  }
  if (pathname.startsWith('/rules')) {
    return { section: 'Config', title: 'Rules' };
  }
  if (pathname.startsWith('/journal')) {
    return { section: 'Review', title: 'Journal' };
  }
  if (pathname.startsWith('/settings')) {
    return { section: 'Config', title: 'Settings' };
  }
  if (pathname.startsWith('/portfolio-risk')) {
    return { section: 'Monitoring', title: 'Portfolio Risk' };
  }
  if (pathname.startsWith('/alerts')) {
    return { section: 'Monitoring', title: 'Alerts' };
  }
  return { section: 'App', title: 'TradeOps' };
}

export function TopBar() {
  const pathname = usePathname();
  const { section, title } = derivePageMeta(pathname);

  const { mode, setMode } = useTradingMode();
  const { data: risk } = useRiskStatus();
  const { data: stats } = useSignalStats();
  const killMutation = useKillSwitchMutation();
  const [killDialogOpen, setKillDialogOpen] = useState(false);
  const [killDialogMode, setKillDialogMode] =
    useState<KillSwitchMode>('engage');

  const { toggleCopilot, toggleMarket, copilotOpen, marketOpen } =
    useShellActions();
  const { data: accounts = [] } = useAccountsComparison();
  const { isApiUp, healthStatus, hasDrift, brokerOk, lastReconcileAt } =
    useSystemStatus();

  const [selectedAccountName, setSelectedAccountName] = useState<string | null>(
    null
  );

  const hasMultipleAccounts = accounts.length > 1;

  const selectedAccount: AccountDetailApi | undefined = useMemo(
    () =>
      selectedAccountName
        ? accounts.find((a) => a.account_name === selectedAccountName)
        : undefined,
    [accounts, selectedAccountName]
  );

  const netLiq =
    selectedAccount?.equity ??
    (risk?.current_equity != null ? risk.current_equity : null);

  const todayPnlFromStats =
    mode === 'PAPER'
      ? stats?.paper_daily_pnl ?? stats?.paper_pnl_24h
      : stats?.live_daily_pnl ?? stats?.live_pnl_24h;

  // Sum daily_pnl across all accounts for Global view.
  // Accounts are populated from the backend which uses MetaAPI balance snapshots
  // (account_status_snapshots: current_balance − start_of_day_balance).
  const accountsTodayPnl = useMemo(() => {
    if (accounts.length === 0) return null;
    return accounts.reduce(
      (sum, acc) => sum + (acc.daily_pnl ?? acc.realized_pnl_today ?? 0),
      0
    );
  }, [accounts]);

  const todayPnl =
    selectedAccount != null
      ? selectedAccount.daily_pnl ?? selectedAccount.realized_pnl_today ?? 0
      : todayPnlFromStats != null
      ? todayPnlFromStats
      : accountsTodayPnl !== null
      ? accountsTodayPnl
      : risk?.live_daily_pnl ?? risk?.daily_pnl ?? 0;

  const todayPnlColor =
    todayPnl == null
      ? 'text-[var(--to-text-secondary)]'
      : todayPnl >= 0
      ? 'text-[var(--to-long)]'
      : 'text-[var(--to-short)]';

  const statusPillTone = (() => {
    if (!isApiUp) return 'offline';
    if (hasDrift || brokerOk === false || healthStatus === 'degraded')
      return 'degraded';
    return 'healthy';
  })();

  const openKillDialog = () => {
    if (!risk) return;
    const modeValue: KillSwitchMode = risk.kill_switch_active
      ? 'reset'
      : 'engage';
    setKillDialogMode(modeValue);
    setKillDialogOpen(true);
  };

  return (
    <header className='topbar-glass flex h-16 shrink-0 items-center justify-between gap-6 px-6 border-b border-white/[0.04] bg-[#09090b]/80 backdrop-blur-xl z-50'>
      {/* Left: Branding/Title Container */}
      <div className='flex min-w-0 flex-1 items-center gap-6'>
        <div className='flex items-center gap-3 shrink-0'>
          {/* Neon Icon Block */}
          <div className='flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#6366f1]/10 to-[#a855f7]/10 border border-white/5 shadow-[0_0_15px_rgba(99,102,241,0.15)] group-hover:shadow-[0_0_25px_rgba(99,102,241,0.25)] transition-all'>
            <Activity className='h-5 w-5 text-indigo-400' />
          </div>
          <div className='flex flex-col justify-center'>
            <span
              className='text-[9px] font-bold uppercase tracking-[0.25em] text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {section}
            </span>
            <span
              className='text-[15px] font-extrabold text-white tracking-tight leading-tight mt-0.5'
              style={{
                fontFamily: 'var(--font-sans)',
                letterSpacing: '-0.02em',
              }}
            >
              {title}
            </span>
          </div>
        </div>
        <DualClock />
      </div>

      {/* Right: Actions & Metrics Container */}
      <div className='flex items-center gap-3'>
        {/* API / Broker Status */}
        <div
          className={cn(
            'hidden items-center gap-2 rounded-lg border px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest sm:flex backdrop-blur-sm shrink-0 whitespace-nowrap',
            statusPillTone === 'healthy' &&
              'border-[#0ecb81]/20 bg-[#0ecb81]/5 text-[#0ecb81]',
            statusPillTone === 'degraded' &&
              'border-amber-500/30 bg-amber-500/10 text-amber-400',
            statusPillTone === 'offline' &&
              'border-[#f23645]/30 bg-[#f23645]/10 text-[#f23645]'
          )}
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          <div className='flex items-center gap-1.5'>
            <span className='relative flex h-2 w-2'>
              {statusPillTone === 'healthy' && (
                <span className='absolute inline-flex h-full w-full animate-ping rounded-full bg-[#0ecb81] opacity-40'></span>
              )}
              <span className='relative inline-flex h-2 w-2 rounded-full bg-current'></span>
            </span>
            API {isApiUp ? 'OK' : 'OFF'}
          </div>
          <div className='h-3 w-px bg-current opacity-30' />
          <span>
            {brokerOk == null
              ? 'BROKER —'
              : brokerOk
              ? 'SYNCED'
              : hasDrift
              ? 'DRIFT'
              : 'ERROR'}
          </span>
        </div>

        {/* Global / Account Selector & Financials */}
        <div className='hidden lg:flex items-center bg-[#09090b] border border-white/5 rounded-xl shadow-inner overflow-hidden shrink-0 whitespace-nowrap'>
          {hasMultipleAccounts && (
            <div className='flex items-center bg-white/[0.02] p-1 border-r border-white/5'>
              <button
                type='button'
                onClick={() => setSelectedAccountName(null)}
                className={cn(
                  'rounded-md px-3 py-1.5 text-[10px] uppercase font-bold tracking-widest transition-all',
                  selectedAccountName === null
                    ? 'bg-white/10 text-white shadow-sm'
                    : 'text-zinc-500 hover:text-zinc-300'
                )}
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                Global
              </button>
              {accounts.map((acc) => (
                <button
                  key={acc.account_name}
                  type='button'
                  onClick={() => setSelectedAccountName(acc.account_name)}
                  className={cn(
                    'rounded-md px-3 py-1.5 text-[10px] uppercase font-bold tracking-widest transition-all',
                    selectedAccountName === acc.account_name
                      ? 'bg-indigo-500/20 text-indigo-300 shadow-sm'
                      : 'text-zinc-500 hover:text-zinc-300'
                  )}
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {acc.account_name}
                </button>
              ))}
            </div>
          )}

          {/* Metrics block */}
          <div
            className='flex items-center gap-4 px-4 py-1.5'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            <div className='flex flex-col items-end justify-center'>
              <span className='text-[9px] text-zinc-500 uppercase tracking-widest leading-none mb-1'>
                Net Liq
              </span>
              <span className='text-[13px] text-white font-semibold leading-none'>
                {netLiq != null
                  ? `$${netLiq.toLocaleString(undefined, {
                      maximumFractionDigits: 0,
                    })}`
                  : '—'}
              </span>
            </div>
            <div className='h-5 w-px bg-white/10' />
            <div className='flex flex-col items-end justify-center'>
              <span className='text-[9px] text-zinc-500 uppercase tracking-widest leading-none mb-1'>
                Today
              </span>
              <span
                className={cn(
                  'text-[13px] font-semibold leading-none tabular-nums',
                  todayPnlColor
                )}
              >
                {todayPnl != null
                  ? `${todayPnl >= 0 ? '+' : ''}$${Math.abs(todayPnl).toFixed(
                      2
                    )}`
                  : '—'}
              </span>
            </div>
          </div>
        </div>

        {/* Action Pills */}
        <div className='flex items-center gap-1.5 bg-[#09090b] border border-white/5 p-1 rounded-xl shadow-inner shrink-0 whitespace-nowrap'>
          {/* Mode Switcher */}
          <div className='flex items-center bg-black/50 rounded-lg p-0.5 border border-white/5'>
            <button
              onClick={() => setMode('LIVE')}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 transition-all outline-none',
                mode === 'LIVE'
                  ? 'bg-[#0ecb81]/15 text-[#0ecb81] shadow-[0_0_10px_rgba(14,203,129,0.15)] ring-1 ring-[#0ecb81]/30'
                  : 'text-zinc-500 hover:text-zinc-300'
              )}
            >
              <Radio className='h-3.5 w-3.5' />
              <span className='text-[10px] font-bold uppercase tracking-widest font-mono'>
                Live
              </span>
            </button>
            <button
              onClick={() => setMode('PAPER')}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 transition-all outline-none',
                mode === 'PAPER'
                  ? 'bg-amber-500/15 text-amber-400 shadow-[0_0_10px_rgba(245,158,11,0.15)] ring-1 ring-amber-500/30'
                  : 'text-zinc-500 hover:text-zinc-300'
              )}
            >
              <FlaskConical className='h-3.5 w-3.5' />
              <span className='text-[10px] font-bold uppercase tracking-widest font-mono'>
                Paper
              </span>
            </button>
          </div>

          <div className='w-px h-6 bg-white/10 mx-1' />

          <button
            onClick={toggleMarket}
            className={cn(
              'flex items-center justify-center p-2 rounded-lg transition-all',
              marketOpen
                ? 'text-[#0ecb81] bg-[#0ecb81]/15 ring-1 ring-[#0ecb81]/30 shadow-[0_0_10px_rgba(14,203,129,0.15)]'
                : 'text-zinc-400 hover:text-[#0ecb81] hover:bg-[#0ecb81]/10'
            )}
            title='Live Markets Panel'
          >
            <Globe className='h-4 w-4' />
          </button>

          <button
            onClick={toggleCopilot}
            className={cn(
              'flex items-center justify-center p-2 rounded-lg transition-all',
              copilotOpen
                ? 'text-indigo-400 bg-indigo-500/15 ring-1 ring-indigo-500/30 shadow-[0_0_10px_rgba(99,102,241,0.15)]'
                : 'text-zinc-400 hover:text-indigo-400 hover:bg-indigo-500/10'
            )}
            title='AI Copilot (⌘/)'
          >
            <Sparkles className='h-4 w-4' />
          </button>

          <div className='flex items-center justify-center p-1'>
            <AlertBell />
          </div>

          <div className='w-px h-6 bg-white/10 mx-1' />

          {/* Kill Switch */}
          <button
            onClick={openKillDialog}
            disabled={killMutation.isPending || !isApiUp}
            className={cn(
              'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest transition-all',
              risk?.kill_switch_active
                ? 'animate-pulse bg-[#f23645]/20 text-[#f23645] ring-1 ring-[#f23645]/50 shadow-[0_0_15px_rgba(242,54,69,0.3)]'
                : 'bg-white/5 text-zinc-400 hover:bg-[#f23645]/15 hover:text-[#f23645] hover:ring-1 hover:ring-[#f23645]/30 disabled:opacity-50'
            )}
            style={{ fontFamily: 'var(--font-mono)' }}
            title={
              !isApiUp
                ? 'Disabled while API is offline'
                : 'Emergency kill switch'
            }
          >
            <Power className='h-3.5 w-3.5' />
            {risk?.kill_switch_active ? 'KILL ON' : 'KILL'}
          </button>
        </div>
      </div>

      <KillSwitchConfirmDialog
        open={killDialogOpen}
        mode={killDialogMode}
        onOpenChange={setKillDialogOpen}
        isPending={killMutation.isPending}
        onConfirm={(reason) => {
          const enabled = killDialogMode === 'engage';
          killMutation.mutate({ enabled, reason });
          setKillDialogOpen(false);
        }}
      />
    </header>
  );
}
