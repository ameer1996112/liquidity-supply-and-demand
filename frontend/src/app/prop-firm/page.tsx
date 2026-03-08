'use client';

import { useState, useEffect } from 'react';
import {
  Trophy,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  TrendingDown,
  Activity,
  RefreshCw,
  ChevronRight,
  Shield,
  BarChart2,
  ArrowUpRight,
  ArrowDownRight,
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
} from 'recharts';
import { cn } from '@/lib/utils';
import {
  usePropFirmMetrics,
  usePropFirmHistory,
  usePropFirmMtm,
  useResetPropFirmDaily,
} from '@/hooks/usePropFirm';
import { format, parseISO, differenceInSeconds } from 'date-fns';

// ── Helpers ───────────────────────────────────────────────────────────────────

function computeHealthScore({
  dailyPct,
  dailyLimit,
  trailingPct,
  trailingLimit,
  consistencyPct,
  consistencyLimit,
  safeToTrade,
  currentProfitPct,
}: {
  dailyPct: number;
  dailyLimit: number;
  trailingPct: number;
  trailingLimit: number;
  consistencyPct: number;
  consistencyLimit: number;
  safeToTrade: boolean;
  currentProfitPct: number;
}) {
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

function HealthScoreCard({
  score,
  safeToTrade,
}: {
  score: number;
  safeToTrade: boolean;
}) {
  const color = score >= 75 ? '#0ecb81' : score >= 50 ? '#f0b90b' : '#f6465d';
  const label = score >= 75 ? 'Excellent' : score >= 50 ? 'Caution' : 'At Risk';
  const radius = 52;
  const circ = 2 * Math.PI * radius;
  const fill = (score / 100) * circ;

  return (
    <div
      className='relative rounded-2xl border border-[var(--to-border)] overflow-hidden p-5'
      style={{ background: 'linear-gradient(135deg,#0d1117 0%,#12161c 100%)' }}
    >
      <div
        className='absolute inset-0 pointer-events-none'
        style={{
          background: `radial-gradient(ellipse at 50% 0%, ${color}12 0%, transparent 70%)`,
        }}
      />
      <div className='relative flex items-center gap-5'>
        <div className='relative shrink-0' style={{ width: 124, height: 124 }}>
          <svg width={124} height={124} viewBox='0 0 124 124'>
            <circle
              cx='62'
              cy='62'
              r={radius}
              fill='none'
              stroke='#1e2329'
              strokeWidth={10}
            />
            <circle
              cx='62'
              cy='62'
              r={radius}
              fill='none'
              stroke={color}
              strokeWidth={10}
              strokeLinecap='round'
              strokeDasharray={`${fill} ${circ - fill}`}
              strokeDashoffset={circ * 0.25}
            />
          </svg>
          <div className='absolute inset-0 flex flex-col items-center justify-center'>
            <span
              className='text-3xl font-black tabular-nums'
              style={{ color, fontFamily: 'var(--font-mono)' }}
            >
              {score}
            </span>
            <span
              className='text-[9px] font-bold uppercase tracking-widest'
              style={{ color }}
            >
              / 100
            </span>
          </div>
        </div>

        <div className='flex-1 min-w-0'>
          <span className='text-[11px] font-bold uppercase tracking-widest text-[var(--to-text-dim)] font-mono'>
            Challenge Health
          </span>
          <div
            className='text-[22px] font-black leading-tight mt-1'
            style={{ color }}
          >
            {label}
          </div>
          <div className='text-[12px] text-[var(--to-text-secondary)] mt-1'>
            {score >= 75
              ? 'All rules are healthy. Strong risk posture.'
              : score >= 50
              ? 'Some limits are getting close. Manage risk carefully.'
              : 'Critical risk levels detected. Reduce exposure now.'}
          </div>
          <div className='mt-3'>
            <span
              className='inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold font-mono'
              style={{
                color,
                backgroundColor: `${color}15`,
                border: `1px solid ${color}30`,
              }}
            >
              <span
                className='inline-block w-1.5 h-1.5 rounded-full'
                style={{ backgroundColor: color }}
              />
              {safeToTrade ? 'SAFE TO TRADE' : 'TRADING HALTED'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatusBanner({
  safeToTrade,
  drawdownBreach,
  dailyPct,
  dailyLimit,
}: {
  safeToTrade: boolean;
  drawdownBreach: boolean;
  dailyPct: number;
  dailyLimit: number;
}) {
  const danger = dailyPct > dailyLimit * 0.7;
  const warning = dailyPct > dailyLimit * 0.5;

  const cfg = !safeToTrade
    ? {
        bg: '#f6465d18',
        border: '#f6465d40',
        color: '#f6465d',
        Icon: XCircle,
        title: drawdownBreach
          ? 'Challenge Failed — Max Drawdown Breached'
          : 'Trading Halted — Daily Loss Limit Breached',
      }
    : danger
    ? {
        bg: '#f0b90b18',
        border: '#f0b90b40',
        color: '#f0b90b',
        Icon: AlertTriangle,
        title: `Danger Zone — ${dailyPct.toFixed(
          2
        )}% of ${dailyLimit}% daily limit used`,
      }
    : warning
    ? {
        bg: '#3b82f618',
        border: '#3b82f640',
        color: '#3b82f6',
        Icon: AlertTriangle,
        title: `Warning — ${dailyPct.toFixed(2)}% daily drawdown`,
      }
    : {
        bg: '#0ecb8118',
        border: '#0ecb8140',
        color: '#0ecb81',
        Icon: CheckCircle2,
        title: 'All systems green — safe to trade',
      };

  return (
    <div
      className='flex items-center gap-3 rounded-xl px-4 py-3 border'
      style={{ backgroundColor: cfg.bg, borderColor: cfg.border }}
    >
      <cfg.Icon className='h-5 w-5 shrink-0' style={{ color: cfg.color }} />
      <div className='text-sm font-semibold' style={{ color: cfg.color }}>
        {cfg.title}
      </div>
    </div>
  );
}

function useCountdown(targetDate: Date | null) {
  const [remaining, setRemaining] = useState(0);
  useEffect(() => {
    if (!targetDate) return;
    const tick = () =>
      setRemaining(Math.max(0, differenceInSeconds(targetDate, new Date())));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [targetDate]);
  return remaining;
}

function CountdownTimer({ daysRemaining }: { daysRemaining: number | null }) {
  const targetDate =
    daysRemaining != null
      ? (() => {
          const d = new Date();
          d.setDate(d.getDate() + daysRemaining);
          d.setHours(23, 59, 59, 999);
          return d;
        })()
      : null;
  const remaining = useCountdown(targetDate);
  if (daysRemaining == null) return null;

  const days = Math.floor(remaining / 86400);
  const hours = Math.floor((remaining % 86400) / 3600);
  const mins = Math.floor((remaining % 3600) / 60);
  const secs = remaining % 60;
  const urgentColor = days <= 3 ? '#f6465d' : days <= 7 ? '#f0b90b' : '#0ecb81';

  return (
    <div className='rounded-2xl border border-[var(--to-border)] bg-[var(--to-surface)] p-5'>
      <div className='flex items-center gap-2 mb-4'>
        <Clock className='h-4 w-4 text-[var(--to-warning)]' />
        <span className='text-[11px] font-bold text-[var(--to-text-secondary)] uppercase tracking-widest font-mono'>
          Challenge Deadline
        </span>
      </div>
      <div className='flex items-center gap-3 justify-center'>
        {[
          { value: days, label: 'Days' },
          { value: hours, label: 'Hours' },
          { value: mins, label: 'Mins' },
          { value: secs, label: 'Secs' },
        ].map(({ value, label }, i) => (
          <div key={label} className='flex items-center gap-3'>
            <div className='flex flex-col items-center gap-1'>
              <div
                className='flex h-14 w-14 items-center justify-center rounded-xl border-2 text-xl font-black tabular-nums'
                style={{
                  borderColor: `${urgentColor}40`,
                  backgroundColor: `${urgentColor}10`,
                  color: urgentColor,
                  fontFamily: 'var(--font-mono)',
                }}
              >
                {String(value).padStart(2, '0')}
              </div>
              <span className='text-[9px] text-[var(--to-text-dim)] uppercase tracking-wider font-mono'>
                {label}
              </span>
            </div>
            {i < 3 && (
              <span className='text-lg font-bold text-[var(--to-text-dim)] mb-4'>
                :
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function DrawdownHistoryChart({
  snapshots,
  dailyLimit,
  trailingLimit,
}: {
  snapshots: Array<{
    snapshot_time: string;
    daily_drawdown_pct: number;
    trailing_drawdown_pct: number;
  }>;
  dailyLimit: number;
  trailingLimit: number;
}) {
  if (!snapshots.length) {
    return (
      <div className='flex items-center justify-center h-40 text-[var(--to-text-dim)] text-sm'>
        No historical data yet
      </div>
    );
  }

  const data = snapshots.map((s) => ({
    time: format(parseISO(s.snapshot_time), 'MMM d HH:mm'),
    daily: parseFloat((s.daily_drawdown_pct ?? 0).toFixed(2)),
    trailing: parseFloat((s.trailing_drawdown_pct ?? 0).toFixed(2)),
  }));

  return (
    <ResponsiveContainer width='100%' height={190}>
      <AreaChart
        data={data}
        margin={{ top: 4, right: 16, left: -10, bottom: 0 }}
      >
        <defs>
          <linearGradient id='gradDaily' x1='0' y1='0' x2='0' y2='1'>
            <stop offset='5%' stopColor='#3b82f6' stopOpacity={0.3} />
            <stop offset='95%' stopColor='#3b82f6' stopOpacity={0} />
          </linearGradient>
          <linearGradient id='gradTrailing' x1='0' y1='0' x2='0' y2='1'>
            <stop offset='5%' stopColor='#f0b90b' stopOpacity={0.3} />
            <stop offset='95%' stopColor='#f0b90b' stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray='3 3' stroke='#1e2329' />
        <XAxis
          dataKey='time'
          tick={{
            fill: '#5e6673',
            fontSize: 10,
            fontFamily: 'var(--font-mono)',
          }}
          tickLine={false}
          axisLine={{ stroke: '#1e2329' }}
          interval='preserveStartEnd'
        />
        <YAxis
          tick={{
            fill: '#5e6673',
            fontSize: 10,
            fontFamily: 'var(--font-mono)',
          }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => `${v}%`}
          domain={[0, Math.max(dailyLimit, trailingLimit) * 1.1]}
        />
        <RechartsTooltip
          contentStyle={{
            backgroundColor: '#12161c',
            border: '1px solid #2b3139',
            borderRadius: 8,
            fontSize: 12,
          }}
          labelStyle={{ color: '#848e9c' }}
          formatter={(val, name) => [
            `${val}%`,
            name === 'daily' ? 'Daily DD' : 'Trailing DD',
          ]}
        />
        <ReferenceLine
          y={dailyLimit}
          stroke='#f6465d'
          strokeDasharray='4 4'
          strokeOpacity={0.6}
          label={{ value: `DD ${dailyLimit}%`, fill: '#f6465d', fontSize: 10 }}
        />
        <ReferenceLine
          y={trailingLimit}
          stroke='#f0b90b'
          strokeDasharray='4 4'
          strokeOpacity={0.6}
        />
        <Area
          type='monotone'
          dataKey='daily'
          stroke='#3b82f6'
          strokeWidth={2}
          fill='url(#gradDaily)'
          dot={false}
        />
        <Area
          type='monotone'
          dataKey='trailing'
          stroke='#f0b90b'
          strokeWidth={2}
          fill='url(#gradTrailing)'
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function PropFirmPage() {
  const [historyDays, setHistoryDays] = useState(7);
  const accountName = 'default';

  const {
    data: metricsData,
    isLoading: metricsLoading,
    error: metricsError,
    dataUpdatedAt,
  } = usePropFirmMetrics(accountName);

  const { data: historyData, isLoading: historyLoading } = usePropFirmHistory(
    accountName,
    historyDays
  );
  const { data: mtmData, isLoading: mtmLoading } = usePropFirmMtm(accountName);
  const resetMutation = useResetPropFirmDaily(accountName);
  const lastUpdated = dataUpdatedAt ? new Date(dataUpdatedAt) : null;

  if (metricsLoading) {
    return (
      <div className='flex-1 flex items-center justify-center min-h-[60vh]'>
        <div className='flex flex-col items-center gap-3'>
          <div className='h-8 w-8 rounded-full border-2 border-[var(--to-warning)] border-t-transparent animate-spin' />
          <span className='text-sm text-[var(--to-text-dim)]'>
            Loading challenge data…
          </span>
        </div>
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
  const { equity, daily_pnl, drawdown, status, consistency, days_remaining } =
    metrics;

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
    daily_remaining_usd: drawdown?.daily_remaining_usd ?? 0,
  };
  const safeConsistency = {
    best_day_pct: consistency?.best_day_pct ?? 0,
    limit_pct: consistency?.limit_pct ?? 0,
    status: consistency?.status ?? 'safe',
  };

  const currentProfitPct =
    safeEquity.current_equity > safeEquity.daily_start_balance
      ? ((safeEquity.current_equity - safeEquity.daily_start_balance) /
          Math.max(safeEquity.daily_start_balance, 1)) *
        100
      : 0;

  const accountGrowthPct =
    safeEquity.daily_start_balance > 0
      ? ((safeEquity.current_equity - safeEquity.daily_start_balance) /
          safeEquity.daily_start_balance) *
        100
      : 0;

  const healthScore = computeHealthScore({
    dailyPct: safeDrawdown.daily_pct,
    dailyLimit: safeDrawdown.daily_limit_pct,
    trailingPct: safeDrawdown.trailing_pct,
    trailingLimit: safeDrawdown.trailing_limit_pct,
    consistencyPct: safeConsistency.best_day_pct,
    consistencyLimit: safeConsistency.limit_pct,
    safeToTrade: status.safe_to_trade,
    currentProfitPct,
  });

  return (
    <div className='flex-1 space-y-5 p-6'>
      {/* Header */}
      <div className='flex items-start justify-between'>
        <div className='flex items-center gap-3'>
          <div
            className='flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--to-warning)]/30'
            style={{
              background:
                'linear-gradient(135deg,rgba(240,185,11,0.2) 0%,rgba(240,185,11,0.05) 100%)',
              boxShadow: '0 0 16px rgba(240,185,11,0.2)',
            }}
          >
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
        <div className='flex items-center gap-2'>
          {lastUpdated && (
            <span className='text-[11px] text-[var(--to-text-dim)] font-mono'>
              Updated {format(lastUpdated, 'HH:mm:ss')}
            </span>
          )}
          <button
            onClick={() => resetMutation.mutate()}
            disabled={resetMutation.isPending}
            className='flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--to-border)] text-[12px] text-[var(--to-text-secondary)] hover:bg-[var(--to-surface-raised)] hover:text-[var(--to-text-primary)] transition-colors disabled:opacity-50'
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

      <StatusBanner
        safeToTrade={status.safe_to_trade}
        drawdownBreach={status.drawdown_breach}
        dailyPct={safeDrawdown.daily_pct}
        dailyLimit={safeDrawdown.daily_limit_pct}
      />

      <div className='grid grid-cols-1 lg:grid-cols-3 gap-4'>
        <div className='lg:col-span-2'>
          <HealthScoreCard
            score={healthScore}
            safeToTrade={status.safe_to_trade}
          />
        </div>

        <div
          className='rounded-2xl border border-[var(--to-border)] p-5 space-y-3'
          style={{
            background: 'linear-gradient(160deg,#0d1117 0%,#12161c 100%)',
          }}
        >
          <div className='flex items-center gap-2'>
            <BarChart2 className='h-4 w-4 text-[var(--to-warning)]' />
            <span className='text-[11px] font-bold text-[var(--to-text-secondary)] uppercase tracking-widest font-mono'>
              Equity Today
            </span>
          </div>
          <div>
            <div className='text-[10px] text-[var(--to-text-dim)] font-mono'>
              Starting Balance
            </div>
            <div className='text-[20px] font-black font-mono'>
              $
              {safeEquity.daily_start_balance.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </div>
          </div>
          <div>
            <div className='text-[10px] text-[var(--to-text-dim)] font-mono'>
              Current Equity
            </div>
            <div className='flex items-center gap-2'>
              <div
                className='text-[20px] font-black font-mono'
                style={{
                  color:
                    safeEquity.current_equity >= safeEquity.daily_start_balance
                      ? '#0ecb81'
                      : '#f6465d',
                }}
              >
                $
                {safeEquity.current_equity.toLocaleString('en-US', {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </div>
              <span
                className='flex items-center gap-0.5 text-[11px] font-bold font-mono px-1.5 py-0.5 rounded'
                style={{
                  color: accountGrowthPct >= 0 ? '#0ecb81' : '#f6465d',
                  backgroundColor:
                    accountGrowthPct >= 0 ? '#0ecb8115' : '#f6465d15',
                }}
              >
                {accountGrowthPct >= 0 ? (
                  <ArrowUpRight className='h-3 w-3' />
                ) : (
                  <ArrowDownRight className='h-3 w-3' />
                )}
                {Math.abs(accountGrowthPct).toFixed(2)}%
              </span>
            </div>
          </div>
          <div className='grid grid-cols-3 gap-2 pt-2 border-t border-[var(--to-border)]'>
            {[
              { label: 'Closed', value: safeDailyPnl.closed },
              { label: 'Floating', value: safeDailyPnl.floating },
              { label: 'Total', value: safeDailyPnl.total },
            ].map(({ label, value }) => (
              <div key={label}>
                <div className='text-[9px] text-[var(--to-text-dim)] font-mono uppercase'>
                  {label}
                </div>
                <div
                  className='text-[13px] font-bold font-mono'
                  style={{ color: value >= 0 ? '#0ecb81' : '#f6465d' }}
                >
                  {value >= 0 ? '+' : ''}${value.toFixed(2)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className='rounded-2xl border border-[var(--to-border)] bg-[var(--to-surface)] p-5'>
        <div className='flex items-center justify-between mb-3'>
          <div className='flex items-center gap-2'>
            <TrendingDown className='h-4 w-4 text-[var(--to-warning)]' />
            <span className='text-[11px] font-bold text-[var(--to-text-secondary)] uppercase tracking-widest font-mono'>
              Drawdown History
            </span>
          </div>
          <div className='flex items-center gap-1'>
            {[3, 7, 14, 30].map((d) => (
              <button
                key={d}
                onClick={() => setHistoryDays(d)}
                className={cn(
                  'px-2.5 py-1 rounded text-[11px] font-medium transition-colors',
                  historyDays === d
                    ? 'bg-[var(--to-warning)]/15 text-[var(--to-warning)] border border-[var(--to-warning)]/30'
                    : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]'
                )}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>

        {historyLoading ? (
          <div className='h-44 flex items-center justify-center'>
            <div className='h-6 w-6 rounded-full border-2 border-[var(--to-warning)] border-t-transparent animate-spin' />
          </div>
        ) : (
          <DrawdownHistoryChart
            snapshots={historyData?.snapshots ?? []}
            dailyLimit={safeDrawdown.daily_limit_pct}
            trailingLimit={safeDrawdown.trailing_limit_pct}
          />
        )}
      </div>

      <div className='grid grid-cols-1 lg:grid-cols-2 gap-4'>
        <CountdownTimer daysRemaining={days_remaining} />
        <div className='rounded-2xl border border-[var(--to-border)] bg-[var(--to-surface)] p-5'>
          <div className='flex items-center gap-2 mb-2'>
            <Activity className='h-4 w-4 text-[var(--to-warning)]' />
            <span className='text-[11px] font-bold text-[var(--to-text-secondary)] uppercase tracking-widest font-mono'>
              Live MTM Positions
            </span>
          </div>
          {mtmLoading ? (
            <div className='space-y-2'>
              {[1, 2].map((i) => (
                <div
                  key={i}
                  className='h-12 rounded-xl bg-[var(--to-surface-raised)] animate-pulse'
                />
              ))}
            </div>
          ) : mtmData?.positions?.length ? (
            <div className='space-y-2 max-h-52 overflow-y-auto scrollbar-thin'>
              {mtmData.positions.map((p, i) => (
                <div
                  key={i}
                  className='flex items-center justify-between px-3 py-2.5 rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]'
                >
                  <div className='text-[12px] font-mono text-[var(--to-text-primary)]'>
                    {p.symbol}
                  </div>
                  <div
                    className='text-[12px] font-mono font-bold'
                    style={{
                      color: (p.floating_pnl ?? 0) >= 0 ? '#0ecb81' : '#f6465d',
                    }}
                  >
                    {(p.floating_pnl ?? 0) >= 0 ? '+' : ''}$
                    {(p.floating_pnl ?? 0).toFixed(2)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className='text-[var(--to-text-dim)] text-sm'>
              No open positions
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
