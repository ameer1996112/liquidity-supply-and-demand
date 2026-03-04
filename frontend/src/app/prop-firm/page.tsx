'use client';

import { useState } from 'react';
import {
  Trophy,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  TrendingUp,
  TrendingDown,
  Target,
  Activity,
  RefreshCw,
  ChevronRight,
  Flame,
  Shield,
  BarChart2,
} from 'lucide-react';
import {
  LineChart,
  Line,
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
import { format, parseISO } from 'date-fns';

// ── Circular SVG Gauge ────────────────────────────────────────────────────────

interface GaugeProps {
  value: number;       // current value (e.g. 2.1)
  limit: number;       // max value (e.g. 5.0)
  label: string;
  sublabel?: string;
  size?: number;
  colorZones?: { at: number; color: string }[];
  unit?: string;
}

function CircularGauge({
  value,
  limit,
  label,
  sublabel,
  size = 120,
  colorZones,
  unit = '%',
}: GaugeProps) {
  const radius = 46;
  const strokeWidth = 8;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.min(value / limit, 1);
  const fillLength = pct * circumference;

  // Determine color
  let color = '#0ecb81'; // green
  if (colorZones) {
    for (const zone of colorZones) {
      if (value >= zone.at) color = zone.color;
    }
  }

  return (
    <div className='flex flex-col items-center gap-2'>
      <div className='relative' style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox='0 0 100 100'>
          {/* Track */}
          <circle
            cx='50'
            cy='50'
            r={radius}
            fill='none'
            stroke='#1e2329'
            strokeWidth={strokeWidth}
          />
          {/* Fill — starts at top (−90°) */}
          <circle
            cx='50'
            cy='50'
            r={radius}
            fill='none'
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap='round'
            strokeDasharray={`${fillLength} ${circumference - fillLength}`}
            strokeDashoffset={circumference * 0.25}
            style={{ transition: 'stroke-dasharray 0.6s ease, stroke 0.4s ease' }}
          />
        </svg>
        {/* Center text */}
        <div className='absolute inset-0 flex flex-col items-center justify-center'>
          <span className='text-xl font-bold tabular-nums' style={{ color, fontFamily: 'var(--font-mono)' }}>
            {value.toFixed(2)}{unit}
          </span>
          <span className='text-[10px] text-[var(--to-text-dim)] mt-0.5'>
            / {limit}{unit}
          </span>
        </div>
      </div>
      <div className='text-center'>
        <div className='text-[13px] font-semibold text-[var(--to-text-primary)]'>{label}</div>
        {sublabel && (
          <div className='text-[11px] text-[var(--to-text-dim)] mt-0.5'>{sublabel}</div>
        )}
      </div>
    </div>
  );
}

// ── Phase Badge ───────────────────────────────────────────────────────────────

function PhaseBadge({ phase }: { phase: string }) {
  const labels: Record<string, { label: string; color: string }> = {
    phase1: { label: 'Phase 1', color: '#3b82f6' },
    phase2: { label: 'Phase 2', color: '#a78bfa' },
    funded: { label: 'Funded', color: '#0ecb81' },
  };
  const meta = labels[phase] ?? { label: phase.toUpperCase(), color: '#848e9c' };
  return (
    <span
      className='inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-semibold uppercase tracking-wider'
      style={{
        backgroundColor: `${meta.color}18`,
        border: `1px solid ${meta.color}40`,
        color: meta.color,
        fontFamily: 'var(--font-mono)',
      }}
    >
      <Trophy className='h-3 w-3' />
      {meta.label}
    </span>
  );
}

// ── Status Alert Banner ───────────────────────────────────────────────────────

function StatusBanner({ safeToTrade, dailyBreach, drawdownBreach, dailyPct, dailyLimit }: {
  safeToTrade: boolean;
  dailyBreach: boolean;
  drawdownBreach: boolean;
  dailyPct: number;
  dailyLimit: number;
}) {
  const danger = dailyPct > dailyLimit * 0.7;
  const warning = dailyPct > dailyLimit * 0.5;

  if (!safeToTrade) {
    return (
      <div className='flex items-center gap-3 rounded-lg px-4 py-3 border' style={{
        backgroundColor: '#f6465d18',
        borderColor: '#f6465d40',
      }}>
        <XCircle className='h-5 w-5 shrink-0' style={{ color: '#f6465d' }} />
        <div>
          <div className='text-sm font-semibold' style={{ color: '#f6465d' }}>
            {drawdownBreach ? 'Challenge Failed — Max Drawdown Breached' : 'Trading Halted — Daily Loss Limit Breached'}
          </div>
          <div className='text-[12px] text-[var(--to-text-secondary)] mt-0.5'>
            All trading has been automatically stopped. Review your risk settings before resuming.
          </div>
        </div>
      </div>
    );
  }

  if (danger) {
    return (
      <div className='flex items-center gap-3 rounded-lg px-4 py-3 border' style={{
        backgroundColor: '#f0b90b18',
        borderColor: '#f0b90b40',
      }}>
        <AlertTriangle className='h-5 w-5 shrink-0' style={{ color: '#f0b90b' }} />
        <div>
          <div className='text-sm font-semibold' style={{ color: '#f0b90b' }}>
            Danger Zone — {dailyPct.toFixed(2)}% of {dailyLimit}% daily limit used
          </div>
          <div className='text-[12px] text-[var(--to-text-secondary)] mt-0.5'>
            Consider reducing exposure. Bot will auto-pause at {dailyLimit}%.
          </div>
        </div>
      </div>
    );
  }

  if (warning) {
    return (
      <div className='flex items-center gap-3 rounded-lg px-4 py-3 border' style={{
        backgroundColor: '#3b82f618',
        borderColor: '#3b82f640',
      }}>
        <AlertTriangle className='h-5 w-5 shrink-0' style={{ color: '#3b82f6' }} />
        <div className='text-sm text-[var(--to-text-secondary)]'>
          <span style={{ color: '#3b82f6' }} className='font-semibold'>Warning:</span>{' '}
          {dailyPct.toFixed(2)}% daily drawdown — approaching limit.
        </div>
      </div>
    );
  }

  return (
    <div className='flex items-center gap-3 rounded-lg px-4 py-3 border' style={{
      backgroundColor: '#0ecb8118',
      borderColor: '#0ecb8140',
    }}>
      <CheckCircle2 className='h-5 w-5 shrink-0' style={{ color: '#0ecb81' }} />
      <div className='text-sm font-medium' style={{ color: '#0ecb81' }}>
        All systems green — safe to trade
      </div>
    </div>
  );
}

// ── Drawdown History Chart ────────────────────────────────────────────────────

function DrawdownHistoryChart({ snapshots, dailyLimit, trailingLimit }: {
  snapshots: Array<{ snapshot_time: string; daily_drawdown_pct: number; trailing_drawdown_pct: number }>;
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
    daily: parseFloat(s.daily_drawdown_pct.toFixed(2)),
    trailing: parseFloat(s.trailing_drawdown_pct.toFixed(2)),
  }));

  return (
    <ResponsiveContainer width='100%' height={180}>
      <LineChart data={data} margin={{ top: 4, right: 16, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray='3 3' stroke='#1e2329' />
        <XAxis
          dataKey='time'
          tick={{ fill: '#5e6673', fontSize: 10, fontFamily: 'var(--font-mono)' }}
          tickLine={false}
          axisLine={{ stroke: '#1e2329' }}
          interval='preserveStartEnd'
        />
        <YAxis
          tick={{ fill: '#5e6673', fontSize: 10, fontFamily: 'var(--font-mono)' }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v) => `${v}%`}
          domain={[0, Math.max(dailyLimit, trailingLimit) * 1.1]}
        />
        <RechartsTooltip
          contentStyle={{ backgroundColor: '#12161c', border: '1px solid #2b3139', borderRadius: 6, fontSize: 12 }}
          labelStyle={{ color: '#848e9c' }}
          formatter={(val, name) => [`${val ?? 0}%`, name === 'daily' ? 'Daily DD' : 'Trailing DD']}
        />
        <ReferenceLine y={dailyLimit} stroke='#f6465d' strokeDasharray='4 4' strokeOpacity={0.6} label={{ value: `DD ${dailyLimit}%`, fill: '#f6465d', fontSize: 10 }} />
        <ReferenceLine y={trailingLimit} stroke='#f0b90b' strokeDasharray='4 4' strokeOpacity={0.6} />
        <Line type='monotone' dataKey='daily' stroke='#3b82f6' strokeWidth={2} dot={false} name='daily' />
        <Line type='monotone' dataKey='trailing' stroke='#f0b90b' strokeWidth={2} dot={false} name='trailing' />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ── MTM Position Row ──────────────────────────────────────────────────────────

interface MtmPos {
  symbol: string;
  side: string;
  lots: number;
  open_price: number;
  current_price: number;
  floating_pnl: number;
  pct_to_sl?: number;
  at_risk?: boolean;
}

function MtmPositionRow({ pos }: { pos: MtmPos }) {
  const isLong = pos.side?.toLowerCase() === 'buy';
  const pnlColor = pos.floating_pnl >= 0 ? '#0ecb81' : '#f6465d';
  const atRisk = pos.at_risk || (pos.pct_to_sl !== undefined && pos.pct_to_sl > 50);

  return (
    <div className={cn(
      'flex items-center justify-between px-3 py-2 rounded',
      atRisk ? 'border border-[#f6465d]/30 bg-[#f6465d]/5' : 'border border-[var(--to-border)] bg-[var(--to-surface-raised)]'
    )}>
      <div className='flex items-center gap-2.5'>
        {atRisk && <AlertTriangle className='h-3.5 w-3.5 text-[#f6465d] shrink-0' />}
        <div>
          <div className='flex items-center gap-2'>
            <span className='text-[13px] font-semibold text-[var(--to-text-primary)]' style={{ fontFamily: 'var(--font-mono)' }}>
              {pos.symbol}
            </span>
            <span
              className='text-[10px] px-1.5 py-0.5 rounded font-medium'
              style={{
                backgroundColor: isLong ? '#0ecb8120' : '#f6465d20',
                color: isLong ? '#0ecb81' : '#f6465d',
                border: `1px solid ${isLong ? '#0ecb8140' : '#f6465d40'}`,
              }}
            >
              {isLong ? 'LONG' : 'SHORT'}
            </span>
          </div>
          <div className='text-[11px] text-[var(--to-text-dim)] mt-0.5'>
            {pos.lots} lots · Entry {pos.open_price}
          </div>
        </div>
      </div>
      <div className='text-right'>
        <div className='text-[13px] font-semibold tabular-nums' style={{ color: pnlColor, fontFamily: 'var(--font-mono)' }}>
          {pos.floating_pnl >= 0 ? '+' : ''}${pos.floating_pnl.toFixed(2)}
        </div>
        {pos.pct_to_sl !== undefined && (
          <div className='text-[10px] text-[var(--to-text-dim)]'>
            {pos.pct_to_sl.toFixed(0)}% to SL
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function PropFirmPage() {
  const [historyDays, setHistoryDays] = useState(7);
  const accountName = 'default';

  const { data: metricsData, isLoading: metricsLoading, error: metricsError, dataUpdatedAt } = usePropFirmMetrics(accountName);
  const { data: historyData, isLoading: historyLoading } = usePropFirmHistory(accountName, historyDays);
  const { data: mtmData, isLoading: mtmLoading } = usePropFirmMtm(accountName);
  const resetMutation = useResetPropFirmDaily(accountName);

  const lastUpdated = dataUpdatedAt ? new Date(dataUpdatedAt) : null;

  if (metricsLoading) {
    return (
      <div className='flex-1 flex items-center justify-center min-h-[60vh]'>
        <div className='flex flex-col items-center gap-3'>
          <div className='h-8 w-8 rounded-full border-2 border-[var(--to-warning)] border-t-transparent animate-spin' />
          <span className='text-sm text-[var(--to-text-dim)]'>Loading challenge data…</span>
        </div>
      </div>
    );
  }

  if (metricsError || !metricsData) {
    return (
      <div className='flex-1 p-6'>
        <div className='rounded-lg border border-[#f6465d]/40 bg-[#f6465d]/8 p-6 flex items-start gap-3'>
          <XCircle className='h-5 w-5 text-[#f6465d] mt-0.5 shrink-0' />
          <div>
            <div className='font-semibold text-[#f6465d]'>Failed to load prop firm metrics</div>
            <div className='text-sm text-[var(--to-text-secondary)] mt-1'>
              {metricsError instanceof Error ? metricsError.message : 'Backend may be offline or prop firm tracker not configured.'}
            </div>
          </div>
        </div>
      </div>
    );
  }

  const { metrics, evaluation_phase, account_name } = metricsData;
  const { equity, daily_pnl, drawdown, status, consistency, days_remaining } = metrics;

  const dailyColorZones = [
    { at: 0, color: '#0ecb81' },
    { at: drawdown.daily_limit_pct * 0.5, color: '#3b82f6' },
    { at: drawdown.daily_limit_pct * 0.7, color: '#f0b90b' },
    { at: drawdown.daily_limit_pct * 0.9, color: '#f6465d' },
  ];

  const trailingColorZones = [
    { at: 0, color: '#0ecb81' },
    { at: drawdown.trailing_limit_pct * 0.5, color: '#3b82f6' },
    { at: drawdown.trailing_limit_pct * 0.7, color: '#f0b90b' },
    { at: drawdown.trailing_limit_pct * 0.9, color: '#f6465d' },
  ];

  const consistencyColorZones = [
    { at: 0, color: '#0ecb81' },
    { at: consistency.limit_pct * 0.6, color: '#3b82f6' },
    { at: consistency.limit_pct * 0.8, color: '#f0b90b' },
    { at: consistency.limit_pct * 0.95, color: '#f6465d' },
  ];

  return (
    <div className='flex-1 space-y-5 p-6'>

      {/* ── Page Header ── */}
      <div className='flex items-start justify-between'>
        <div>
          <div className='flex items-center gap-3'>
            <div className='flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--to-warning)]/15 border border-[var(--to-warning)]/30'>
              <Trophy className='h-5 w-5 text-[var(--to-warning)]' />
            </div>
            <div>
              <h1 className='text-lg font-semibold text-[var(--to-text-primary)]'>Prop Firm Hub</h1>
              <div className='flex items-center gap-2 mt-0.5'>
                <span className='text-[12px] text-[var(--to-text-dim)]' style={{ fontFamily: 'var(--font-mono)' }}>
                  {account_name}
                </span>
                <ChevronRight className='h-3 w-3 text-[var(--to-text-dim)]' />
                <PhaseBadge phase={evaluation_phase} />
                {days_remaining !== null && (
                  <span className='flex items-center gap-1 text-[11px] text-[var(--to-text-secondary)]'>
                    <Clock className='h-3 w-3' />
                    {days_remaining} days left
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
        <div className='flex items-center gap-2'>
          {lastUpdated && (
            <span className='text-[11px] text-[var(--to-text-dim)]' style={{ fontFamily: 'var(--font-mono)' }}>
              Updated {format(lastUpdated, 'HH:mm:ss')}
            </span>
          )}
          <button
            onClick={() => resetMutation.mutate()}
            disabled={resetMutation.isPending}
            className='flex items-center gap-1.5 px-3 py-1.5 rounded border border-[var(--to-border)] text-[12px] text-[var(--to-text-secondary)] hover:bg-[var(--to-surface-raised)] hover:text-[var(--to-text-primary)] transition-colors disabled:opacity-50'
          >
            <RefreshCw className={cn('h-3.5 w-3.5', resetMutation.isPending && 'animate-spin')} />
            Reset Daily
          </button>
        </div>
      </div>

      {/* ── Status Banner ── */}
      <StatusBanner
        safeToTrade={status.safe_to_trade}
        dailyBreach={status.daily_loss_breach}
        drawdownBreach={status.drawdown_breach}
        dailyPct={drawdown.daily_pct}
        dailyLimit={drawdown.daily_limit_pct}
      />

      {/* ── Top Row: 3 Gauges + Equity Summary ── */}
      <div className='grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4'>

        {/* Daily Drawdown Gauge */}
        <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface)] p-5 flex flex-col items-center gap-3'>
          <CircularGauge
            value={drawdown.daily_pct}
            limit={drawdown.daily_limit_pct}
            label='Daily Drawdown'
            sublabel={`$${drawdown.daily_remaining_usd.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })} remaining`}
            colorZones={dailyColorZones}
          />
          <div className='w-full pt-2 border-t border-[var(--to-border)]'>
            <div className='flex justify-between text-[11px] text-[var(--to-text-dim)]'>
              <span>Limit</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>{drawdown.daily_limit_pct}%</span>
            </div>
          </div>
        </div>

        {/* Trailing Drawdown Gauge */}
        <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface)] p-5 flex flex-col items-center gap-3'>
          <CircularGauge
            value={drawdown.trailing_pct}
            limit={drawdown.trailing_limit_pct}
            label='Trailing Drawdown'
            sublabel='From peak equity'
            colorZones={trailingColorZones}
          />
          <div className='w-full pt-2 border-t border-[var(--to-border)]'>
            <div className='flex justify-between text-[11px] text-[var(--to-text-dim)]'>
              <span>Limit</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>{drawdown.trailing_limit_pct}%</span>
            </div>
          </div>
        </div>

        {/* Consistency Gauge */}
        <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface)] p-5 flex flex-col items-center gap-3'>
          <CircularGauge
            value={consistency.best_day_pct}
            limit={consistency.limit_pct}
            label='Consistency Rule'
            sublabel='Best day / total profit'
            colorZones={consistencyColorZones}
          />
          <div className='w-full pt-2 border-t border-[var(--to-border)]'>
            <div className='flex items-center justify-between'>
              <span className='text-[11px] text-[var(--to-text-dim)]'>FTMO 40% rule</span>
              <span className={cn(
                'text-[10px] px-1.5 py-0.5 rounded font-semibold',
                consistency.status === 'safe' ? 'bg-[#0ecb8118] text-[#0ecb81]' :
                consistency.status === 'warning' ? 'bg-[#f0b90b18] text-[#f0b90b]' :
                'bg-[#f6465d18] text-[#f6465d]',
              )}>
                {consistency.status.toUpperCase()}
              </span>
            </div>
          </div>
        </div>

        {/* Equity Summary Card */}
        <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface)] p-5 space-y-4'>
          <div className='flex items-center gap-2'>
            <BarChart2 className='h-4 w-4 text-[var(--to-warning)]' />
            <span className='text-[12px] font-semibold text-[var(--to-text-secondary)] uppercase tracking-wider'>Equity Today</span>
          </div>
          <div className='space-y-3'>
            <div>
              <div className='text-[11px] text-[var(--to-text-dim)]'>Starting Balance</div>
              <div className='text-[18px] font-bold text-[var(--to-text-primary)] tabular-nums' style={{ fontFamily: 'var(--font-mono)' }}>
                ${equity.daily_start_balance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </div>
            <div>
              <div className='text-[11px] text-[var(--to-text-dim)]'>Current Equity</div>
              <div className='text-[18px] font-bold tabular-nums' style={{ fontFamily: 'var(--font-mono)', color: equity.current_equity >= equity.daily_start_balance ? '#0ecb81' : '#f6465d' }}>
                ${equity.current_equity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </div>
            <div className='flex justify-between pt-2 border-t border-[var(--to-border)]'>
              <div>
                <div className='text-[10px] text-[var(--to-text-dim)]'>Closed</div>
                <div className='text-[13px] font-semibold tabular-nums' style={{ fontFamily: 'var(--font-mono)', color: daily_pnl.closed >= 0 ? '#0ecb81' : '#f6465d' }}>
                  {daily_pnl.closed >= 0 ? '+' : ''}${daily_pnl.closed.toFixed(2)}
                </div>
              </div>
              <div>
                <div className='text-[10px] text-[var(--to-text-dim)]'>Floating</div>
                <div className='text-[13px] font-semibold tabular-nums' style={{ fontFamily: 'var(--font-mono)', color: daily_pnl.floating >= 0 ? '#0ecb81' : '#f6465d' }}>
                  {daily_pnl.floating >= 0 ? '+' : ''}${daily_pnl.floating.toFixed(2)}
                </div>
              </div>
              <div>
                <div className='text-[10px] text-[var(--to-text-dim)]'>Total P&L</div>
                <div className='text-[13px] font-semibold tabular-nums' style={{ fontFamily: 'var(--font-mono)', color: daily_pnl.total >= 0 ? '#0ecb81' : '#f6465d' }}>
                  {daily_pnl.total >= 0 ? '+' : ''}${daily_pnl.total.toFixed(2)}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Middle Row: MTM Positions + Status Checklist ── */}
      <div className='grid grid-cols-1 lg:grid-cols-2 gap-4'>

        {/* Live MTM Positions */}
        <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface)] p-5 space-y-4'>
          <div className='flex items-center justify-between'>
            <div className='flex items-center gap-2'>
              <Activity className='h-4 w-4 text-[var(--to-warning)]' />
              <span className='text-[12px] font-semibold text-[var(--to-text-secondary)] uppercase tracking-wider'>Live MTM Positions</span>
            </div>
            {mtmData && (
              <span className='text-[11px] text-[var(--to-text-dim)]' style={{ fontFamily: 'var(--font-mono)' }}>
                Floating: <span style={{ color: mtmData.floating_pnl >= 0 ? '#0ecb81' : '#f6465d' }}>
                  {mtmData.floating_pnl >= 0 ? '+' : ''}${mtmData.floating_pnl.toFixed(2)}
                </span>
              </span>
            )}
          </div>

          {mtmLoading ? (
            <div className='space-y-2'>
              {[1, 2].map((i) => (
                <div key={i} className='h-12 rounded bg-[var(--to-surface-raised)] animate-pulse' />
              ))}
            </div>
          ) : mtmData?.positions && mtmData.positions.length > 0 ? (
            <div className='space-y-2 max-h-52 overflow-y-auto'>
              {mtmData.positions.map((pos, i) => (
                <MtmPositionRow key={i} pos={pos} />
              ))}
            </div>
          ) : (
            <div className='flex flex-col items-center justify-center py-8 text-[var(--to-text-dim)]'>
              <Shield className='h-8 w-8 mb-2 opacity-30' />
              <span className='text-sm'>No open positions</span>
            </div>
          )}
        </div>

        {/* Rules Checklist */}
        <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface)] p-5 space-y-4'>
          <div className='flex items-center gap-2'>
            <Shield className='h-4 w-4 text-[var(--to-warning)]' />
            <span className='text-[12px] font-semibold text-[var(--to-text-secondary)] uppercase tracking-wider'>Challenge Rules</span>
          </div>
          <div className='space-y-3'>
            {[
              {
                label: 'Daily Loss Limit',
                detail: `${drawdown.daily_pct.toFixed(2)}% of ${drawdown.daily_limit_pct}% used`,
                ok: !status.daily_loss_breach && drawdown.daily_pct < drawdown.daily_limit_pct * 0.7,
                warn: !status.daily_loss_breach && drawdown.daily_pct >= drawdown.daily_limit_pct * 0.7,
              },
              {
                label: 'Max Drawdown',
                detail: `${drawdown.trailing_pct.toFixed(2)}% of ${drawdown.trailing_limit_pct}% used`,
                ok: !status.drawdown_breach && drawdown.trailing_pct < drawdown.trailing_limit_pct * 0.7,
                warn: !status.drawdown_breach && drawdown.trailing_pct >= drawdown.trailing_limit_pct * 0.7,
              },
              {
                label: 'Consistency Rule (40%)',
                detail: `Best day is ${consistency.best_day_pct.toFixed(1)}% of total profit`,
                ok: status.consistency_ok && consistency.status === 'safe',
                warn: status.consistency_ok && consistency.status !== 'safe',
              },
              {
                label: 'Safe to Trade',
                detail: status.safe_to_trade ? 'No active breaches' : 'Trading paused',
                ok: status.safe_to_trade,
                warn: false,
              },
            ].map((rule) => {
              const failed = !rule.ok && !rule.warn;
              const iconColor = rule.ok ? '#0ecb81' : rule.warn ? '#f0b90b' : '#f6465d';
              const Icon = rule.ok ? CheckCircle2 : rule.warn ? AlertTriangle : XCircle;
              return (
                <div key={rule.label} className='flex items-center justify-between py-2 border-b border-[var(--to-border)] last:border-0'>
                  <div className='flex items-center gap-2.5'>
                    <Icon className='h-4 w-4 shrink-0' style={{ color: iconColor }} />
                    <div>
                      <div className='text-[13px] font-medium text-[var(--to-text-primary)]'>{rule.label}</div>
                      <div className='text-[11px] text-[var(--to-text-dim)]'>{rule.detail}</div>
                    </div>
                  </div>
                  <span
                    className='text-[10px] px-2 py-0.5 rounded font-semibold uppercase'
                    style={{
                      backgroundColor: `${iconColor}18`,
                      color: iconColor,
                      border: `1px solid ${iconColor}30`,
                    }}
                  >
                    {rule.ok ? 'OK' : rule.warn ? 'WARN' : 'BREACH'}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Drawdown History Chart ── */}
      <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface)] p-5 space-y-4'>
        <div className='flex items-center justify-between'>
          <div className='flex items-center gap-2'>
            <TrendingDown className='h-4 w-4 text-[var(--to-warning)]' />
            <span className='text-[12px] font-semibold text-[var(--to-text-secondary)] uppercase tracking-wider'>Drawdown History</span>
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
                    : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]',
                )}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>
        <div className='flex items-center gap-4 text-[11px]'>
          <span className='flex items-center gap-1.5'>
            <span className='inline-block w-4 h-0.5 rounded' style={{ backgroundColor: '#3b82f6' }} />
            <span className='text-[var(--to-text-dim)]'>Daily DD</span>
          </span>
          <span className='flex items-center gap-1.5'>
            <span className='inline-block w-4 h-0.5 rounded' style={{ backgroundColor: '#f0b90b' }} />
            <span className='text-[var(--to-text-dim)]'>Trailing DD</span>
          </span>
          <span className='flex items-center gap-1.5'>
            <span className='inline-block w-4 h-px border-t border-dashed border-[#f6465d]' />
            <span className='text-[var(--to-text-dim)]'>Daily Limit</span>
          </span>
        </div>
        {historyLoading ? (
          <div className='h-44 flex items-center justify-center'>
            <div className='h-6 w-6 rounded-full border-2 border-[var(--to-warning)] border-t-transparent animate-spin' />
          </div>
        ) : (
          <DrawdownHistoryChart
            snapshots={historyData?.snapshots ?? []}
            dailyLimit={drawdown.daily_limit_pct}
            trailingLimit={drawdown.trailing_limit_pct}
          />
        )}
      </div>

    </div>
  );
}
