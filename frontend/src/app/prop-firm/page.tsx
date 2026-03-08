'use client';

import { useMemo, useState } from 'react';
import {
  Trophy,
  XCircle,
  Clock,
  RefreshCw,
  ChevronRight,
  BarChart2,
  ArrowUpRight,
  ArrowDownRight,
  Filter,
  TrendingDown,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceLine,
  LineChart,
  Line,
  BarChart,
  Bar,
} from 'recharts';
import { cn } from '@/lib/utils';
import {
  usePropFirmMetrics,
  usePropFirmHistory,
  usePropFirmMtm,
  useResetPropFirmDaily,
} from '@/hooks/usePropFirm';
import { useAccountsComparison } from '@/hooks/useAccounts';
import { fetchSignals } from '@/lib/supabase';
import { useQuery } from '@tanstack/react-query';
import { format, parseISO, subDays, startOfDay } from 'date-fns';
import { getPnl, getSymbol, TradingSignal } from '@/types/trading';

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
      className='inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-bold uppercase tracking-wider font-mono'
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

  const symbolOptions = useMemo(
    () => ['ALL', ...Array.from(new Set(allSignals.map((s) => getSymbol(s))))],
    [allSignals]
  );
  const sessionOptions = useMemo(
    () => [
      'ALL',
      ...Array.from(new Set(allSignals.map((s) => getSignalSession(s)))),
    ],
    [allSignals]
  );
  const dowOptions = ['ALL', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

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
    <div className='flex-1 space-y-5 p-6'>
      <div className='flex items-start justify-between'>
        <div className='space-y-2'>
          <div className='flex items-center gap-3'>
            <div className='flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--to-warning)]/30'>
              <Trophy className='h-5 w-5 text-[var(--to-warning)]' />
            </div>
            <div>
              <h1 className='text-[18px] font-black text-[var(--to-text-primary)] tracking-tight'>
                Prop Firm Hub
              </h1>
              <div className='flex items-center gap-2 mt-0.5'>
                <span className='text-[11px] text-[var(--to-text-dim)] font-mono'>
                  {account_name}
                </span>
                <ChevronRight className='h-3 w-3 text-[var(--to-text-dim)]' />
                <PhaseBadge phase={evaluation_phase} />
              </div>
            </div>
          </div>

          <div className='flex items-center gap-1.5 flex-wrap'>
            <span className='text-[10px] text-[var(--to-text-dim)] font-mono mr-1'>
              Account:
            </span>
            {accountOptions.map((acc) => (
              <button
                key={acc}
                onClick={() => setSelectedAccount(acc)}
                className={cn(
                  'px-2.5 py-1 rounded-lg text-[10px] font-bold font-mono uppercase tracking-wide transition-all border',
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

        <div className='flex items-center gap-2'>
          {dataUpdatedAt && (
            <span className='text-[11px] text-[var(--to-text-dim)] font-mono'>
              Updated {format(new Date(dataUpdatedAt), 'HH:mm:ss')}
            </span>
          )}
          <button
            onClick={() => resetMutation.mutate()}
            disabled={resetMutation.isPending}
            className='flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--to-border)] text-[12px] text-[var(--to-text-secondary)]'
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

      <div className='rounded-2xl border border-[var(--to-border)] bg-[var(--to-surface)] p-4'>
        <div className='text-[12px] text-[var(--to-text-secondary)] font-mono'>
          Challenge Health Score:{' '}
          <span className='text-[var(--to-text-primary)] font-bold'>
            {healthScore}
          </span>
        </div>
      </div>

      <div className='rounded-2xl border border-[var(--to-border)] bg-[var(--to-surface)] p-4'>
        <div className='flex items-center gap-2 mb-3'>
          <Filter className='h-4 w-4 text-[var(--to-warning)]' />
          <span className='text-[11px] font-bold text-[var(--to-text-secondary)] uppercase tracking-widest font-mono'>
            Advanced Analytics Filters
          </span>
        </div>
        <div className='grid grid-cols-2 md:grid-cols-5 gap-2'>
          <select
            value={analyticsRange}
            onChange={(e) =>
              setAnalyticsRange(Number(e.target.value) as 7 | 14 | 30)
            }
            className='rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-2.5 py-1.5 text-[11px]'
          >
            <option value={7}>Last 7d</option>
            <option value={14}>Last 14d</option>
            <option value={30}>Last 30d</option>
          </select>
          <select
            value={symbolFilter}
            onChange={(e) => setSymbolFilter(e.target.value)}
            className='rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-2.5 py-1.5 text-[11px]'
          >
            {symbolOptions.map((s) => (
              <option key={s} value={s}>
                {s === 'ALL' ? 'All Symbols' : s}
              </option>
            ))}
          </select>
          <select
            value={sessionFilter}
            onChange={(e) => setSessionFilter(e.target.value)}
            className='rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-2.5 py-1.5 text-[11px]'
          >
            {sessionOptions.map((s) => (
              <option key={s} value={s}>
                {s === 'ALL' ? 'All Sessions' : s}
              </option>
            ))}
          </select>
          <select
            value={dowFilter}
            onChange={(e) => setDowFilter(e.target.value)}
            className='rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-2.5 py-1.5 text-[11px]'
          >
            {dowOptions.map((d) => (
              <option key={d} value={d}>
                {d === 'ALL' ? 'All Days' : d}
              </option>
            ))}
          </select>
          <button
            onClick={() => {
              setSymbolFilter('ALL');
              setSessionFilter('ALL');
              setDowFilter('ALL');
              setAnalyticsRange(14);
            }}
            className='rounded-lg border border-[var(--to-border)] px-2.5 py-1.5 text-[11px]'
          >
            Reset Filters
          </button>
        </div>
      </div>

      <div className='grid grid-cols-2 md:grid-cols-5 gap-3'>
        {[
          {
            label: 'Positions',
            value: `${summary.totalPositions}`,
            color: '#3b82f6',
          },
          {
            label: 'Closed',
            value: `${summary.closedTrades}`,
            color: '#a78bfa',
          },
          {
            label: 'Win Rate',
            value: `${summary.winRate.toFixed(1)}%`,
            color: summary.winRate >= 50 ? '#0ecb81' : '#f6465d',
          },
          {
            label: 'Total PnL',
            value: `${
              summary.totalPnl >= 0 ? '+' : ''
            }$${summary.totalPnl.toFixed(2)}`,
            color: summary.totalPnl >= 0 ? '#0ecb81' : '#f6465d',
          },
          {
            label: 'Best / Worst',
            value: `${summary.bestDay.date} / ${summary.worstDay.date}`,
            color: '#f0b90b',
          },
        ].map((kpi) => (
          <div
            key={kpi.label}
            className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface)] p-3'
          >
            <div className='text-[9px] text-[var(--to-text-dim)] uppercase tracking-wide font-mono'>
              {kpi.label}
            </div>
            <div
              className='text-[14px] font-black mt-1 font-mono'
              style={{ color: kpi.color }}
            >
              {kpi.value}
            </div>
          </div>
        ))}
      </div>

      <div className='grid grid-cols-1 xl:grid-cols-3 gap-4'>
        <div className='xl:col-span-2 rounded-2xl border border-[var(--to-border)] bg-[var(--to-surface)] p-4'>
          <div className='text-[11px] font-bold text-[var(--to-text-secondary)] uppercase tracking-widest font-mono mb-3'>
            Daily PnL
          </div>
          <ResponsiveContainer width='100%' height={220}>
            <AreaChart data={analyticsDaily}>
              <defs>
                <linearGradient id='pnlGrad' x1='0' y1='0' x2='0' y2='1'>
                  <stop offset='5%' stopColor='#3b82f6' stopOpacity={0.3} />
                  <stop offset='95%' stopColor='#3b82f6' stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray='3 3' stroke='#1e2329' />
              <XAxis dataKey='date' tick={{ fill: '#5e6673', fontSize: 10 }} />
              <YAxis tick={{ fill: '#5e6673', fontSize: 10 }} />
              <RechartsTooltip />
              <Area
                type='monotone'
                dataKey='pnl'
                stroke='#3b82f6'
                fill='url(#pnlGrad)'
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className='rounded-2xl border border-[var(--to-border)] bg-[var(--to-surface)] p-4'>
          <div className='text-[11px] font-bold text-[var(--to-text-secondary)] uppercase tracking-widest font-mono mb-3'>
            Positions / Day
          </div>
          <ResponsiveContainer width='100%' height={220}>
            <BarChart data={analyticsDaily}>
              <CartesianGrid strokeDasharray='3 3' stroke='#1e2329' />
              <XAxis dataKey='date' tick={{ fill: '#5e6673', fontSize: 10 }} />
              <YAxis tick={{ fill: '#5e6673', fontSize: 10 }} />
              <RechartsTooltip />
              <Bar dataKey='positions' fill='#a78bfa' radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className='rounded-2xl border border-[var(--to-border)] bg-[var(--to-surface)] p-4'>
        <div className='text-[11px] font-bold text-[var(--to-text-secondary)] uppercase tracking-widest font-mono mb-3'>
          Win Rate / Day
        </div>
        <ResponsiveContainer width='100%' height={220}>
          <LineChart data={analyticsDaily}>
            <CartesianGrid strokeDasharray='3 3' stroke='#1e2329' />
            <XAxis dataKey='date' tick={{ fill: '#5e6673', fontSize: 10 }} />
            <YAxis tick={{ fill: '#5e6673', fontSize: 10 }} domain={[0, 100]} />
            <RechartsTooltip formatter={(v) => [`${v}%`, 'Win Rate']} />
            <Line
              type='monotone'
              dataKey='winRate'
              stroke='#0ecb81'
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
