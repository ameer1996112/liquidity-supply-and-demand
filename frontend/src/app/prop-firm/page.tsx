'use client';

import { useMemo, useState } from 'react';
import {
  Trophy,
  XCircle,
  Clock,
  RefreshCw,
  ChevronRight,
  DollarSign,
  AlertTriangle,
  CheckCircle,
  Activity,
  Calendar,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { CalendarPnlView } from '@/components/journal/CalendarPnlView';
import {
  usePropFirmMetrics,
  usePropFirmHistory,
  usePropFirmMtm,
  useResetPropFirmDaily,
} from '@/hooks/usePropFirm';
import { useAccountsComparison } from '@/hooks/useAccounts';
import { fetchSignals } from '@/lib/supabase';
import { useQuery } from '@tanstack/react-query';
import { format, subDays, startOfDay } from 'date-fns';
import { getPnl, getSymbol, TradingSignal } from '@/types/trading';
import { StatCard } from '@/components/dashboard/StatCard';
import { CircularGauge } from '@/components/ui/CircularGauge';

function normalizeSession(value: unknown): string {
  if (value == null) return 'Unknown';
  if (typeof value === 'number') {
    if (value === 0) return 'Asia';
    if (value === 1) return 'London';
    if (value === 2) return 'New York';
    if (value === 3) return 'Off-Session';
  }
  const s = String(value).toLowerCase();
  if (s.includes('asia')) return 'Asia';
  if (s.includes('london')) return 'London';
  if (s.includes('new') || s.includes('ny')) return 'New York';
  return String(value);
}

function getSignalSession(signal: TradingSignal): string {
  const s = signal as TradingSignal & { session?: unknown };
  if (s.session != null) return normalizeSession(s.session);
  const ai = signal.ai_reasoning as unknown;
  if (
    ai &&
    typeof ai === 'object' &&
    'session' in (ai as Record<string, unknown>)
  ) {
    return normalizeSession((ai as Record<string, unknown>).session);
  }
  return 'Unknown';
}

function getSignalAccount(signal: TradingSignal): string {
  const s = signal as TradingSignal & {
    account_name?: string;
    account?: string;
    account_id?: string;
  };
  return s.account_name || s.account || s.account_id || 'default';
}

function isClosedSignal(signal: TradingSignal): boolean {
  const st = String(signal.status || '').toLowerCase();
  return (st === 'closed' || st === 'executed') && getPnl(signal) != null;
}

function computeHealthScore(
  dailyPct: number,
  dailyLimit: number,
  trailingPct: number,
  trailingLimit: number,
  consistencyPct: number,
  consistencyLimit: number,
  safeToTrade: boolean,
  currentProfitPct: number
) {
  if (!safeToTrade) return 0;
  let score = 100;
  score -= (dailyPct / Math.max(dailyLimit, 0.01)) * 30;
  score -= (trailingPct / Math.max(trailingLimit, 0.01)) * 30;
  if (consistencyPct > consistencyLimit * 0.8) score -= 20;
  else if (consistencyPct > consistencyLimit * 0.6) score -= 10;
  if (currentProfitPct > 0) score += Math.min(currentProfitPct * 2, 10);
  return Math.max(0, Math.min(100, Math.round(score)));
}

function PhaseBadge({ phase }: { phase: string }) {
  const labels: Record<string, { label: string; color: string }> = {
    phase1: { label: 'Phase 1', color: '#3b82f6' },
    phase2: { label: 'Phase 2', color: '#a78bfa' },
    funded: { label: 'Funded', color: '#0ecb81' },
  };
  const meta = labels[phase] ?? {
    label: phase.toUpperCase(),
    color: '#848e9c',
  };
  return (
    <span
      className='inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold uppercase tracking-wider font-mono'
      style={{
        backgroundColor: `${meta.color}18`,
        border: `1px solid ${meta.color}40`,
        color: meta.color,
      }}
    >
      <Trophy className='h-3 w-3' />
      {meta.label}
    </span>
  );
}

export default function PropFirmPage() {
  const [selectedAccount, setSelectedAccount] = useState<string>('default');
  const [historyDays, setHistoryDays] = useState(7);
  const [analyticsRange, setAnalyticsRange] = useState<7 | 14 | 30>(14);
  const [symbolFilter, setSymbolFilter] = useState<string>('ALL');
  const [sessionFilter, setSessionFilter] = useState<string>('ALL');
  const [dowFilter, setDowFilter] = useState<string>('ALL');

  const { data: accounts = [] } = useAccountsComparison();
  const accountOptions = useMemo(
    () =>
      Array.from(new Set(['default', ...accounts.map((a) => a.account_name)])),
    [accounts]
  );

  const {
    data: metricsData,
    isLoading: metricsLoading,
    error: metricsError,
    dataUpdatedAt,
  } = usePropFirmMetrics(selectedAccount);

  const { data: historyData, isLoading: historyLoading } = usePropFirmHistory(
    selectedAccount,
    historyDays
  );
  const { data: mtmData, isLoading: mtmLoading } =
    usePropFirmMtm(selectedAccount);
  const resetMutation = useResetPropFirmDaily(selectedAccount);

  const { data: allSignals = [] } = useQuery({
    queryKey: ['prop-firm-analytics-signals', selectedAccount, analyticsRange],
    queryFn: () => fetchSignals({ limit: 1200 }),
    staleTime: 60_000,
  });

  const cutoff = useMemo(
    () => startOfDay(subDays(new Date(), analyticsRange - 1)),
    [analyticsRange]
  );

  const filteredSignals = useMemo(() => {
    return allSignals
      .filter((s) => new Date(s.created_at) >= cutoff)
      .filter((s) =>
        selectedAccount === 'default'
          ? true
          : getSignalAccount(s) === selectedAccount
      )
      .filter((s) =>
        symbolFilter === 'ALL' ? true : getSymbol(s) === symbolFilter
      )
      .filter((s) =>
        sessionFilter === 'ALL' ? true : getSignalSession(s) === sessionFilter
      )
      .filter((s) => {
        if (dowFilter === 'ALL') return true;
        const dow = new Date(s.created_at).toLocaleDateString('en-US', {
          weekday: 'short',
        });
        return dow === dowFilter;
      });
  }, [
    allSignals,
    cutoff,
    selectedAccount,
    symbolFilter,
    sessionFilter,
    dowFilter,
  ]);

  const analyticsDaily = useMemo(() => {
    const map = new Map<
      string,
      {
        date: string;
        positions: number;
        wins: number;
        losses: number;
        pnl: number;
      }
    >();
    for (const s of filteredSignals) {
      const d = format(new Date(s.created_at), 'MMM dd');
      if (!map.has(d))
        map.set(d, { date: d, positions: 0, wins: 0, losses: 0, pnl: 0 });
      const row = map.get(d)!;
      row.positions += 1;
      if (isClosedSignal(s)) {
        const pnl = getPnl(s) ?? 0;
        row.pnl += pnl;
        if (pnl > 0) row.wins += 1;
        else row.losses += 1;
      }
    }
    return Array.from(map.values()).map((r) => ({
      ...r,
      winRate: r.wins + r.losses > 0 ? (r.wins / (r.wins + r.losses)) * 100 : 0,
    }));
  }, [filteredSignals]);

  const summary = useMemo(() => {
    const closed = filteredSignals.filter(isClosedSignal);
    const pnl = closed.reduce((acc, s) => acc + (getPnl(s) ?? 0), 0);
    const wins = closed.filter((s) => (getPnl(s) ?? 0) > 0).length;
    const wr = closed.length ? (wins / closed.length) * 100 : 0;

    let bestDay = { date: '—', pnl: -Infinity };
    let worstDay = { date: '—', pnl: Infinity };
    for (const d of analyticsDaily) {
      if (d.pnl > bestDay.pnl) bestDay = { date: d.date, pnl: d.pnl };
      if (d.pnl < worstDay.pnl) worstDay = { date: d.date, pnl: d.pnl };
    }

    return {
      totalPositions: filteredSignals.length,
      closedTrades: closed.length,
      winRate: wr,
      totalPnl: pnl,
      bestDay: bestDay.pnl === -Infinity ? { date: '—', pnl: 0 } : bestDay,
      worstDay: worstDay.pnl === Infinity ? { date: '—', pnl: 0 } : worstDay,
    };
  }, [filteredSignals, analyticsDaily]);

  if (metricsLoading) {
    return (
      <div className='p-6 text-[var(--to-text-dim)]'>
        Loading challenge data…
      </div>
    );
  }

  if (metricsError || !metricsData) {
    return (
      <div className='flex-1 p-6'>
        <div className='rounded-xl border border-[#f6465d]/40 bg-[#f6465d]/8 p-6 flex items-start gap-3'>
          <XCircle className='h-5 w-5 text-[#f6465d] mt-0.5 shrink-0' />
          <div>
            <div className='font-semibold text-[#f6465d]'>
              Failed to load prop firm metrics
            </div>
            <div className='text-sm text-[var(--to-text-secondary)] mt-1'>
              {metricsError instanceof Error
                ? metricsError.message
                : 'Backend may be offline or prop firm tracker not configured.'}
            </div>
          </div>
        </div>
      </div>
    );
  }

  const { metrics, evaluation_phase, account_name } = metricsData;
  const { equity, daily_pnl, drawdown, status, consistency } = metrics;

  const safeEquity = {
    daily_start_balance: equity?.daily_start_balance ?? 0,
    current_equity: equity?.current_equity ?? 0,
  };
  const safeDailyPnl = {
    closed: daily_pnl?.closed ?? 0,
    floating: daily_pnl?.floating ?? 0,
    total: daily_pnl?.total ?? 0,
  };
  const safeDrawdown = {
    daily_pct: drawdown?.daily_pct ?? 0,
    daily_limit_pct: drawdown?.daily_limit_pct ?? 0,
    trailing_pct: drawdown?.trailing_pct ?? 0,
    trailing_limit_pct: drawdown?.trailing_limit_pct ?? 0,
  };
  const safeConsistency = {
    best_day_pct: consistency?.best_day_pct ?? 0,
    limit_pct: consistency?.limit_pct ?? 0,
  };

  const currentProfitPct =
    safeEquity.current_equity > safeEquity.daily_start_balance
      ? ((safeEquity.current_equity - safeEquity.daily_start_balance) /
          Math.max(safeEquity.daily_start_balance, 1)) *
        100
      : 0;

  const healthScore = computeHealthScore(
    safeDrawdown.daily_pct,
    safeDrawdown.daily_limit_pct,
    safeDrawdown.trailing_pct,
    safeDrawdown.trailing_limit_pct,
    safeConsistency.best_day_pct,
    safeConsistency.limit_pct,
    status.safe_to_trade,
    currentProfitPct
  );

  const accountGrowthPct =
    safeEquity.daily_start_balance > 0
      ? ((safeEquity.current_equity - safeEquity.daily_start_balance) /
          safeEquity.daily_start_balance) *
        100
      : 0;

  return (
    <div className='flex-1 space-y-6 p-6 animate-fade-in-up'>
      {/* Header Section */}
      <div className='glass-panel p-6'>
        <div className='flex flex-col md:flex-row md:items-center md:justify-between gap-4'>
          <div className='space-y-3'>
            <div className='flex items-center gap-3'>
              <div className='flex h-12 w-12 items-center justify-center rounded-xl border border-[var(--to-warning)]/30 bg-[var(--to-warning)]/10'>
                <Trophy className='h-6 w-6 text-[var(--to-warning)]' />
              </div>
              <div>
                <h1 className='text-[22px] font-black text-[var(--to-text-primary)] tracking-tight'>
                  Prop Firm Challenge
                </h1>
                <div className='flex items-center gap-2 mt-1'>
                  <span className='text-[12px] text-[var(--to-text-secondary)] font-mono'>
                    {account_name}
                  </span>
                  <ChevronRight className='h-3 w-3 text-[var(--to-text-dim)]' />
                  <PhaseBadge phase={evaluation_phase} />
                  {metrics.days_remaining !== null && (
                    <div className='flex items-center gap-1 ml-2 text-[11px] text-[var(--to-text-dim)] font-mono'>
                      <Clock className='h-3 w-3' />
                      {metrics.days_remaining} days remaining
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className='flex items-center gap-1.5 flex-wrap'>
              <span className='text-[11px] text-[var(--to-text-dim)] font-mono mr-1'>
                Account:
              </span>
              {accountOptions.map((acc) => (
                <button
                  key={acc}
                  onClick={() => setSelectedAccount(acc)}
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-[11px] font-bold font-mono uppercase tracking-wide transition-all border',
                    selectedAccount === acc
                      ? 'text-[#3b82f6] border-[#3b82f6]/40 bg-[#3b82f6]/15'
                      : 'text-[var(--to-text-dim)] border-[var(--to-border)] hover:text-[var(--to-text-secondary)]'
                  )}
                >
                  {acc}
                </button>
              ))}
            </div>
          </div>

          <div className='flex items-center gap-3'>
            {dataUpdatedAt && (
              <span className='text-[11px] text-[var(--to-text-dim)] font-mono'>
                Updated {format(new Date(dataUpdatedAt), 'HH:mm:ss')}
              </span>
            )}
            <button
              onClick={() => resetMutation.mutate()}
              disabled={resetMutation.isPending}
              className='flex items-center gap-1.5 px-4 py-2 rounded-lg border border-[var(--to-border)] text-[12px] text-[var(--to-text-secondary)] hover:bg-[var(--to-surface-raised)] transition-colors'
            >
              <RefreshCw
                className={cn(
                  'h-3.5 w-3.5',
                  resetMutation.isPending && 'animate-spin'
                )}
              />
              Reset Daily
            </button>
          </div>
        </div>
      </div>

      {/* Challenge Health Score & Account Overview */}
      <div className='grid grid-cols-1 lg:grid-cols-3 gap-4'>
        <div className='glass-panel p-6 lg:col-span-1'>
          <div className='flex flex-col items-center'>
            <h3 className='text-[13px] font-bold text-[var(--to-text-secondary)] uppercase tracking-widest font-mono mb-4'>
              Challenge Health
            </h3>

            <div className='relative'>
              <div className='absolute inset-0 flex items-center justify-center'>
                <div className='text-center'>
                  <div
                    className={cn(
                      'text-[32px] font-bold font-mono',
                      healthScore > 80
                        ? 'text-[#0ecb81]'
                        : healthScore > 50
                        ? 'text-[#f0b90b]'
                        : 'text-[#f6465d]'
                    )}
                  >
                    {healthScore}
                  </div>
                  <div className='text-[11px] text-[var(--to-text-dim)] mt-1'>
                    {healthScore > 80
                      ? 'Excellent'
                      : healthScore > 50
                      ? 'Caution'
                      : 'At Risk'}
                  </div>
                </div>
              </div>
              <svg width='180' height='180' viewBox='0 0 100 100'>
                <circle
                  cx='50'
                  cy='50'
                  r='45'
                  fill='none'
                  stroke='#1e2329'
                  strokeWidth='8'
                />
                <circle
                  cx='50'
                  cy='50'
                  r='45'
                  fill='none'
                  stroke={
                    healthScore > 80
                      ? '#0ecb81'
                      : healthScore > 50
                      ? '#f0b90b'
                      : '#f6465d'
                  }
                  strokeWidth='8'
                  strokeLinecap='round'
                  strokeDasharray={`${healthScore * 2.83} ${
                    283 - healthScore * 2.83
                  }`}
                  strokeDashoffset='70'
                  style={{
                    transition: 'stroke-dasharray 0.6s ease, stroke 0.4s ease',
                    filter: `drop-shadow(0 0 4px ${
                      healthScore > 80
                        ? '#0ecb8160'
                        : healthScore > 50
                        ? '#f0b90b60'
                        : '#f6465d60'
                    })`,
                  }}
                />
              </svg>
            </div>

            <div className='mt-4 text-center'>
              <div className='text-[13px] text-[var(--to-text-secondary)]'>
                {status.safe_to_trade ? (
                  <div className='flex items-center justify-center gap-1.5 text-[#0ecb81]'>
                    <CheckCircle className='h-4 w-4' />
                    <span>Safe to Trade</span>
                  </div>
                ) : (
                  <div className='flex items-center justify-center gap-1.5 text-[#f6465d]'>
                    <AlertTriangle className='h-4 w-4' />
                    <span>Trading Restricted</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className='glass-panel p-6 lg:col-span-2'>
          <h3 className='text-[13px] font-bold text-[var(--to-text-secondary)] uppercase tracking-widest font-mono mb-4'>
            Account Overview
          </h3>

          <div className='grid grid-cols-2 md:grid-cols-4 gap-4'>
            <StatCard
              label='Starting Balance'
              value={`$${safeEquity.daily_start_balance.toLocaleString()}`}
              icon={DollarSign}
              variant='default'
            />

            <StatCard
              label='Current Equity'
              value={`$${safeEquity.current_equity.toLocaleString()}`}
              icon={DollarSign}
              variant={accountGrowthPct >= 0 ? 'profit' : 'loss'}
              subValue={`${
                accountGrowthPct >= 0 ? '+' : ''
              }${accountGrowthPct.toFixed(2)}%`}
              trend={accountGrowthPct >= 0 ? 'up' : 'down'}
            />

            <StatCard
              label='Daily P&L'
              value={`${
                safeDailyPnl.total >= 0 ? '+' : ''
              }$${safeDailyPnl.total.toLocaleString()}`}
              icon={Activity}
              variant={safeDailyPnl.total >= 0 ? 'profit' : 'loss'}
              subValue={`Closed: ${
                safeDailyPnl.closed >= 0 ? '+' : ''
              }$${safeDailyPnl.closed.toLocaleString()}`}
            />

            <StatCard
              label='Floating P&L'
              value={`${
                safeDailyPnl.floating >= 0 ? '+' : ''
              }$${safeDailyPnl.floating.toLocaleString()}`}
              icon={Activity}
              variant={safeDailyPnl.floating >= 0 ? 'profit' : 'loss'}
            />
          </div>
        </div>
      </div>

      {/* Challenge Metrics */}
      <div className='glass-panel p-6'>
        <h3 className='text-[13px] font-bold text-[var(--to-text-secondary)] uppercase tracking-widest font-mono mb-4'>
          Challenge Metrics
        </h3>

        <div className='grid grid-cols-1 md:grid-cols-3 gap-6'>
          <div className='flex flex-col items-center'>
            <CircularGauge
              value={safeDrawdown.daily_pct}
              limit={safeDrawdown.daily_limit_pct}
              label='Daily Drawdown'
              sublabel={`Limit: ${safeDrawdown.daily_limit_pct}%`}
              size={150}
              colorZones={[
                { at: 0, color: '#0ecb81' },
                { at: safeDrawdown.daily_limit_pct * 0.6, color: '#f0b90b' },
                { at: safeDrawdown.daily_limit_pct * 0.8, color: '#f6465d' },
              ]}
            />
            <div className='mt-2 text-[12px] text-[var(--to-text-secondary)]'>
              {safeDrawdown.daily_pct < safeDrawdown.daily_limit_pct * 0.6 ? (
                <span className='text-[#0ecb81]'>Safe Zone</span>
              ) : safeDrawdown.daily_pct <
                safeDrawdown.daily_limit_pct * 0.8 ? (
                <span className='text-[#f0b90b]'>Caution Zone</span>
              ) : (
                <span className='text-[#f6465d]'>Danger Zone</span>
              )}
            </div>
          </div>

          <div className='flex flex-col items-center'>
            <CircularGauge
              value={safeDrawdown.trailing_pct}
              limit={safeDrawdown.trailing_limit_pct}
              label='Max Drawdown'
              sublabel={`Limit: ${safeDrawdown.trailing_limit_pct}%`}
              size={150}
              colorZones={[
                { at: 0, color: '#0ecb81' },
                { at: safeDrawdown.trailing_limit_pct * 0.6, color: '#f0b90b' },
                { at: safeDrawdown.trailing_limit_pct * 0.8, color: '#f6465d' },
              ]}
            />
            <div className='mt-2 text-[12px] text-[var(--to-text-secondary)]'>
              {safeDrawdown.trailing_pct <
              safeDrawdown.trailing_limit_pct * 0.6 ? (
                <span className='text-[#0ecb81]'>Safe Zone</span>
              ) : safeDrawdown.trailing_pct <
                safeDrawdown.trailing_limit_pct * 0.8 ? (
                <span className='text-[#f0b90b]'>Caution Zone</span>
              ) : (
                <span className='text-[#f6465d]'>Danger Zone</span>
              )}
            </div>
          </div>

          <div className='flex flex-col items-center'>
            <CircularGauge
              value={safeConsistency.best_day_pct}
              limit={safeConsistency.limit_pct}
              label='Consistency Rule'
              sublabel={`Limit: ${safeConsistency.limit_pct}%`}
              size={150}
              colorZones={[
                { at: 0, color: '#0ecb81' },
                { at: safeConsistency.limit_pct * 0.75, color: '#f0b90b' },
                { at: safeConsistency.limit_pct * 0.9, color: '#f6465d' },
              ]}
            />
            <div className='mt-2 text-[12px] text-[var(--to-text-secondary)]'>
              {safeConsistency.best_day_pct <
              safeConsistency.limit_pct * 0.75 ? (
                <span className='text-[#0ecb81]'>Well Balanced</span>
              ) : safeConsistency.best_day_pct <
                safeConsistency.limit_pct * 0.9 ? (
                <span className='text-[#f0b90b]'>Approaching Limit</span>
              ) : (
                <span className='text-[#f6465d]'>Consistency Risk</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Performance Summary */}
      <div className='glass-panel p-6'>
        <h3 className='text-[13px] font-bold text-[var(--to-text-secondary)] uppercase tracking-widest font-mono mb-4'>
          Performance Summary
        </h3>

        <div className='grid grid-cols-2 md:grid-cols-5 gap-3'>
          <StatCard
            label='Positions'
            value={`${summary.totalPositions}`}
            variant='default'
          />

          <StatCard
            label='Closed Trades'
            value={`${summary.closedTrades}`}
            variant='default'
          />

          <StatCard
            label='Win Rate'
            value={`${summary.winRate.toFixed(1)}%`}
            variant={summary.winRate >= 50 ? 'profit' : 'loss'}
          />

          <StatCard
            label='Total PnL'
            value={`${
              summary.totalPnl >= 0 ? '+' : ''
            }$${summary.totalPnl.toFixed(2)}`}
            variant={summary.totalPnl >= 0 ? 'profit' : 'loss'}
          />

          <StatCard
            label='Best / Worst Day'
            value={`${summary.bestDay.date} / ${summary.worstDay.date}`}
            variant='warning'
          />
        </div>
      </div>

      {/* Calendar View */}
      <div className='glass-panel p-6'>
        <h3 className='text-[13px] font-bold text-[var(--to-text-secondary)] uppercase tracking-widest font-mono mb-4 flex items-center gap-2'>
          <Calendar className='h-4 w-4 text-[var(--to-warning)]' />
          Daily Performance Calendar
        </h3>

        <CalendarPnlView signals={filteredSignals.filter(isClosedSignal)} />
      </div>
    </div>
  );
}
