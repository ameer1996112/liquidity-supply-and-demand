'use client';

import { useEffect, useMemo, useState } from 'react';
import { usePathname } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import {
  Radio,
  FlaskConical,
  Wifi,
  WifiOff,
  Power,
  Clock,
  Activity,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTradingMode } from '@/providers/TradingModeProvider';
import { useRiskStatus, useKillSwitchMutation } from '@/hooks/useRiskStatus';
import { useAccountsComparison } from '@/hooks/useAccounts';
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

function DualClock() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  if (!now) return null;

  const utc = now.toLocaleTimeString('en-GB', {
    timeZone: 'UTC',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
  const israel = now.toLocaleTimeString('en-GB', {
    timeZone: 'Asia/Jerusalem',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });

  return (
    <div
      className='hidden items-center gap-3 text-[10px] tabular-nums sm:flex'
      style={{ fontFamily: 'var(--font-mono)' }}
    >
      <div className='flex items-center gap-1.5 text-[var(--to-text-dim)]'>
        <Clock className='h-3 w-3' />
        <span className='text-[var(--to-text-secondary)]'>{utc}</span>
        <span className='text-[var(--to-text-dim)]'>UTC</span>
      </div>
      <span className='text-[var(--to-border)]'>|</span>
      <div className='flex items-center gap-1.5 text-[var(--to-text-dim)]'>
        <span className='text-[var(--to-text-secondary)]'>{israel}</span>
        <span className='text-[var(--to-text-dim)]'>IL</span>
      </div>
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
            (a.last_reconcile_drift_count ?? 0) === 0,
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
  const killMutation = useKillSwitchMutation();
  const [killDialogOpen, setKillDialogOpen] = useState(false);
  const [killDialogMode, setKillDialogMode] = useState<KillSwitchMode>('engage');

  const { data: accounts = [] } = useAccountsComparison();
  const { isApiUp, healthStatus, hasDrift, brokerOk, lastReconcileAt } =
    useSystemStatus();

  const [selectedAccountName, setSelectedAccountName] = useState<string | null>(
    null,
  );

  const hasMultipleAccounts = accounts.length > 1;

  const selectedAccount: AccountDetailApi | undefined = useMemo(
    () =>
      selectedAccountName
        ? accounts.find((a) => a.account_name === selectedAccountName)
        : undefined,
    [accounts, selectedAccountName],
  );

  const netLiq =
    selectedAccount?.equity ??
    (risk?.current_equity != null ? risk.current_equity : null);

  const todayPnl =
    selectedAccount != null
      ? selectedAccount.daily_pnl ??
        selectedAccount.realized_pnl_today ??
        0
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
    <header className='flex h-10 shrink-0 items-center justify-between border-b border-[var(--to-border)] bg-[var(--to-bg)] px-3'>
      {/* Left: Breadcrumb + title + clocks */}
      <div className='flex min-w-0 items-center gap-3'>
        <div className='min-w-0'>
          <div
            className='flex items-center gap-1 text-[9px] uppercase tracking-[0.18em] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            <span>{section}</span>
            <span className='text-[var(--to-border)]'>/</span>
            <span className='text-[var(--to-text-secondary)]'>{title}</span>
          </div>
          <div className='flex items-center gap-1.5'>
            <span
              className='truncate text-[13px] font-semibold text-[var(--to-text-primary)]'
              style={{ fontFamily: 'var(--font-sans)' }}
            >
              {title}
            </span>
            <Activity className='h-3 w-3 text-[var(--to-text-dim)]' />
          </div>
        </div>
        <DualClock />
      </div>

      {/* Right: System status, account scope, PnL, mode, kill switch */}
      <div className='flex items-center gap-2'>
        {/* System status pill */}
        <div
          className={cn(
            'hidden items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[9px] uppercase tracking-[0.16em] sm:flex',
            statusPillTone === 'healthy' &&
              'border-[var(--to-long)]/25 bg-[var(--to-long)]/5 text-[var(--to-long)]',
            statusPillTone === 'degraded' &&
              'border-amber-500/30 bg-amber-500/10 text-amber-300',
            statusPillTone === 'offline' &&
              'border-[var(--to-short)]/30 bg-[var(--to-short)]/10 text-[var(--to-short)]',
          )}
          style={{ fontFamily: 'var(--font-mono)' }}
          suppressHydrationWarning
        >
          <span className='flex items-center gap-1'>
            <span className='inline-flex h-1.5 w-1.5 rounded-full bg-current' />
            API&nbsp;{isApiUp ? 'OK' : 'DOWN'}
          </span>
          <span className='text-[var(--to-border)]'>•</span>
          <span>
            Broker{' '}
            {brokerOk == null
              ? '—'
              : brokerOk
                ? 'synced'
                : hasDrift
                  ? 'drift'
                  : 'issue'}
          </span>
          <span className='text-[var(--to-border)]'>•</span>
          <span>
            Last&nbsp;reconcile&nbsp;
            <span className='text-[var(--to-text-secondary)]'>
              {formatRelativeTime(lastReconcileAt)}
            </span>
          </span>
        </div>

        {/* Account scope + Net Liq / Today PnL */}
        <div className='hidden items-center gap-2 md:flex'>
          {hasMultipleAccounts && (
            <div className='flex items-center rounded-full border border-[var(--to-border)] bg-[var(--to-surface)] p-0.5'>
              <button
                type='button'
                onClick={() => setSelectedAccountName(null)}
                className={cn(
                  'rounded-full px-2.5 py-0.5 text-[9px] uppercase tracking-[0.16em]',
                  selectedAccountName === null
                    ? 'bg-[var(--to-surface-raised)] text-[var(--to-text-primary)]'
                    : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]',
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
                    'rounded-full px-2.5 py-0.5 text-[9px] uppercase tracking-[0.16em]',
                    selectedAccountName === acc.account_name
                      ? 'bg-[var(--to-accent-blue)]/20 text-blue-300'
                      : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]',
                  )}
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {acc.account_name}
                </button>
              ))}
            </div>
          )}

          <div
            className='flex items-center gap-2 rounded border border-[var(--to-border)] bg-[var(--to-surface)] px-2.5 py-1'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            <div className='flex items-center gap-1.5 text-[10px] tabular-nums'>
              <span className='text-[var(--to-text-dim)]'>Net&nbsp;Liq</span>
              <span className='text-[var(--to-text-secondary)]'>
                {netLiq != null
                  ? `$${netLiq.toLocaleString(undefined, {
                      maximumFractionDigits: 0,
                    })}`
                  : '—'}
              </span>
            </div>
            <span className='h-3 w-px bg-[var(--to-border)]/60' />
            <div className='flex items-center gap-1.5 text-[10px] tabular-nums'>
              <span className='text-[var(--to-text-dim)]'>Today</span>
              <span className={todayPnlColor}>
                {todayPnl != null
                  ? `${todayPnl >= 0 ? '+' : ''}$${Math.abs(todayPnl).toFixed(2)}`
                  : '—'}
              </span>
            </div>
          </div>
        </div>

        {/* Mode toggle */}
        <div className='flex items-center rounded border border-[var(--to-border)] bg-[var(--to-surface)] p-0.5'>
          <button
            onClick={() => setMode('LIVE')}
            className={cn(
              'flex items-center gap-1 rounded px-2 py-0.5 transition-colors',
              mode === 'LIVE'
                ? 'bg-[var(--to-long)]/12 text-[var(--to-long)]'
                : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]',
            )}
          >
            <Radio className='h-3 w-3' />
            <span
              className='text-[10px] font-semibold uppercase tracking-wider'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              Live
            </span>
          </button>
          <button
            onClick={() => setMode('PAPER')}
            className={cn(
              'flex items-center gap-1 rounded px-2 py-0.5 transition-colors',
              mode === 'PAPER'
                ? 'bg-[var(--to-warning)]/12 text-[var(--to-warning)]'
                : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]',
            )}
          >
            <FlaskConical className='h-3 w-3' />
            <span
              className='text-[10px] font-semibold uppercase tracking-wider'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              Paper
            </span>
          </button>
        </div>

        {/* Alert bell */}
        <AlertBell />

        {/* Kill switch */}
        <button
          onClick={openKillDialog}
          disabled={killMutation.isPending || !isApiUp}
          className={cn(
            'flex items-center gap-1 rounded border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider transition-all',
            risk?.kill_switch_active
              ? 'animate-pulse border-[var(--to-short)] bg-[var(--to-short)]/20 text-[var(--to-short)]'
              : 'border-[var(--to-border)] bg-[var(--to-surface)] text-[var(--to-text-dim)] hover:border-[var(--to-short)]/50 hover:text-[var(--to-short)] disabled:opacity-60 disabled:cursor-not-allowed',
          )}
          style={{ fontFamily: 'var(--font-mono)' }}
          title={
            !isApiUp
              ? 'Emergency trading kill switch (disabled while API is offline)'
              : 'Emergency trading kill switch'
          }
        >
          <Power className='h-3 w-3' />
          {risk?.kill_switch_active ? 'KILL ON' : 'Kill'}
        </button>
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

