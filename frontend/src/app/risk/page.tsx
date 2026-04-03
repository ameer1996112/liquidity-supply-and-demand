'use client';

import { useRiskMonitor, type GuardRailStatus } from '@/hooks/useRiskMonitor';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { ClientDate } from '@/components/ui/ClientDate';
import {
  Shield,
  ShieldOff,
  ShieldCheck,
  TrendingDown,
  Target,
  Settings,
  AlertCircle,
  Info,
  Activity,
  BookOpen,
  Gauge,
} from 'lucide-react';
import { useConnectionHealth } from '@/hooks/useConnectionHealth';
import { useHtfFilter } from '@/hooks/useHtfFilter';
import { PageStatusBanner } from '@/components/shared/PageStatusBanner';
import { CircularGauge } from '@/components/ui/CircularGauge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { GuardsPanel } from '@/components/rules/GuardsPanel';
import { RiskRulesPanel } from '@/components/rules/RiskRulesPanel';
import { StrategyRulesPanel } from '@/components/rules/StrategyRulesPanel';

// ── Composite Risk Score ──────────────────────────────────────────────────────

function computeRiskScore(data: {
  daily_risk: { loss_pct: number };
  drawdown: { dd_utilization_pct: number };
  position_limits: { open_positions: number; max_positions: number };
  guard_rails: GuardRailStatus[];
}): { score: number; label: string; color: string } {
  const dailyLossScore = Math.min(data.daily_risk.loss_pct, 100);
  const ddScore = Math.min(data.drawdown.dd_utilization_pct, 100);
  const posScore =
    data.position_limits.max_positions > 0
      ? (data.position_limits.open_positions /
          data.position_limits.max_positions) *
        100
      : 0;
  const criticalRails = data.guard_rails.filter(
    (r) => r.severity === 'critical'
  ).length;
  const railScore = Math.min(criticalRails * 25, 100);

  const score = Math.round(
    dailyLossScore * 0.35 + ddScore * 0.35 + posScore * 0.15 + railScore * 0.15
  );

  if (score >= 75) return { score, label: 'Critical', color: '#f6465d' };
  if (score >= 50) return { score, label: 'Elevated', color: '#f0b90b' };
  if (score >= 25) return { score, label: 'Moderate', color: '#3b82f6' };
  return { score, label: 'Low', color: '#0ecb81' };
}

export default function RiskMonitorPage() {
  const { status } = useConnectionHealth();

  const tabClass =
    'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[11px] font-medium data-[state=active]:bg-indigo-600/20 data-[state=active]:text-indigo-300 data-[state=inactive]:text-[var(--to-text-dim)]';

  return (
    <div className='space-y-4 animate-fade-in-up'>
      {/* Header */}
      <div className='flex items-center gap-3'>
        <div className='flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/10 border border-indigo-500/20'>
          <Shield className='h-4 w-4 text-indigo-400' />
        </div>
        <div>
          <h1 className='page-title text-lg font-semibold'>Risk & Rules</h1>
          <p className='page-subtitle mt-0.5 text-[11px]'>
            Live risk monitoring, trade guards, and strategy rules
          </p>
        </div>
      </div>

      <PageStatusBanner status={status} surfaceLabel='Risk decisions' />

      <Tabs defaultValue='monitor'>
        <TabsList className='surface-soft rounded-lg border border-[var(--to-border)] p-0.5'>
          <TabsTrigger value='monitor' className={tabClass} style={{ fontFamily: 'var(--font-sans)' }}>
            <Gauge className='h-3.5 w-3.5' />
            Monitor
          </TabsTrigger>
          <TabsTrigger value='guards' className={tabClass} style={{ fontFamily: 'var(--font-sans)' }}>
            <Shield className='h-3.5 w-3.5' />
            Guards
          </TabsTrigger>
          <TabsTrigger value='risk-rules' className={tabClass} style={{ fontFamily: 'var(--font-sans)' }}>
            <ShieldCheck className='h-3.5 w-3.5' />
            Risk Rules
          </TabsTrigger>
          <TabsTrigger value='strategy' className={tabClass} style={{ fontFamily: 'var(--font-sans)' }}>
            <BookOpen className='h-3.5 w-3.5' />
            Strategy
          </TabsTrigger>
        </TabsList>

        <TabsContent value='monitor' className='mt-4'>
          <RiskMonitorTab />
        </TabsContent>

        <TabsContent value='guards' className='mt-4'>
          <GuardsPanel />
        </TabsContent>

        <TabsContent value='risk-rules' className='mt-4'>
          <RiskRulesPanel />
        </TabsContent>

        <TabsContent value='strategy' className='mt-4'>
          <StrategyRulesPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function RiskMonitorTab() {
  const { data, isLoading, error } = useRiskMonitor();

  if (isLoading || error) return <LoadingSkeleton />;
  if (!data) return null;

  return (
    <div className='space-y-3'>
      {/* ── Composite Risk Score — Hero Row ─────────────── */}
      <CompositeRiskScore data={data} />

      {/* ── Circular Gauges ──────────────────────────────── */}
      <div className='grid grid-cols-1 gap-3 sm:grid-cols-2'>
        <div className='glow-card flex flex-col items-center justify-center p-5'>
          <CircularGauge
            value={data.daily_risk.loss_pct}
            limit={100}
            label='Daily Loss'
            sublabel={`$${data.daily_risk.loss_used_usd.toFixed(0)} / $${data.daily_risk.loss_limit_usd.toFixed(0)}`}
            size={120}
            colorZones={[{ at: 50, color: '#f0b90b' }, { at: 80, color: '#f6465d' }]}
            unit='%'
          />
        </div>
        <div className='glow-card flex flex-col items-center justify-center p-5'>
          <CircularGauge
            value={data.drawdown.dd_utilization_pct}
            limit={100}
            label='Drawdown Used'
            sublabel={`${data.drawdown.current_dd_pct.toFixed(2)}% / ${data.drawdown.max_dd_allowed_pct.toFixed(1)}% max`}
            size={120}
            colorZones={[{ at: 50, color: '#f0b90b' }, { at: 80, color: '#f6465d' }]}
            unit='%'
          />
        </div>
      </div>

      {/* ── Detail cards ── */}
      <div className='grid grid-cols-1 gap-3 lg:grid-cols-2'>
        <DailyRiskCard data={data.daily_risk} />
        <PositionLimitsCard data={data.position_limits} />
      </div>
      <div className='grid grid-cols-1 gap-3 lg:grid-cols-2'>
        <DrawdownCard data={data.drawdown} />
        <ActiveSettingsCard data={data.active_settings} />
      </div>
      <div className='grid grid-cols-1 gap-3 lg:grid-cols-2'>
        <HtfFilterCard />
        <OneCandleLiqCard />
      </div>
      {data.symbol_overrides && data.symbol_overrides.length > 0 && (
        <SymbolOverridesCard data={data.symbol_overrides} />
      )}
      <div
        className='text-right text-[10px] text-[var(--to-text-dim)]'
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        updated{' '}
        <ClientDate render={() => new Date(data.last_updated).toLocaleTimeString()} />
      </div>
    </div>
  );
}

// ── Composite Risk Score Card ─────────────────────────────────────────────────

 
function CompositeRiskScore({ data }: { data: any }) {
  const { score, label, color } = computeRiskScore(data);

  const severityBg =
    score >= 75
      ? 'bg-[var(--to-short)]/5 border-l-4 border-l-[var(--to-short)]'
      : score >= 50
      ? 'bg-[var(--to-warning)]/5 border-l-4 border-l-[var(--to-warning)]'
      : score >= 25
      ? 'bg-blue-500/5 border-l-4 border-l-blue-500/60'
      : 'bg-[var(--to-long)]/5 border-l-4 border-l-[var(--to-long)]';

  return (
    <div className={cn('glow-card flex items-center gap-6 p-5', severityBg)}>
      {/* Score ring */}
      <div className='relative flex shrink-0 items-center justify-center'>
        <svg width={96} height={96} viewBox='0 0 120 120'>
          <circle
            cx={60} cy={60} r={46} fill='none'
            stroke='#1e2329' strokeWidth={10}
          />
          <circle
            cx={60} cy={60} r={46} fill='none'
            stroke={color} strokeWidth={10} strokeLinecap='round'
            strokeDasharray={`${(score / 100) * 289} 289`}
            transform='rotate(-90 60 60)'
            style={{ transition: 'stroke-dasharray 0.6s ease' }}
          />
        </svg>
        <div className='absolute flex flex-col items-center'>
          <span
            className='text-[22px] font-bold tabular-nums leading-none'
            style={{ color, fontFamily: 'var(--font-mono)' }}
          >
            {score}
          </span>
          <span
            className='text-[8px] font-bold uppercase tracking-widest mt-0.5'
            style={{ color, fontFamily: 'var(--font-mono)' }}
          >
            {label}
          </span>
        </div>
      </div>

      {/* Label + breakdown bars */}
      <div className='flex flex-1 flex-col gap-1'>
        <div className='flex items-center gap-2 mb-2'>
          <Activity className='h-3.5 w-3.5' style={{ color }} />
          <span
            className='text-[10px] font-bold uppercase tracking-[0.18em]'
            style={{ color, fontFamily: 'var(--font-mono)' }}
          >
            Composite Risk Score
          </span>
        </div>
        {[
          { label: 'Daily Loss', value: data.daily_risk.loss_pct },
          { label: 'Drawdown', value: data.drawdown.dd_utilization_pct },
          {
            label: 'Positions',
            value:
              data.position_limits.max_positions > 0
                ? (data.position_limits.open_positions /
                    data.position_limits.max_positions) *
                  100
                : 0,
          },
        ].map((item) => (
          <div key={item.label} className='flex items-center gap-2'>
            <span
              className='w-20 text-[9px] text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {item.label}
            </span>
            <div className='flex-1 h-1 rounded-full bg-[#1e2329] overflow-hidden'>
              <div
                className='h-full rounded-full transition-all'
                style={{
                  width: `${Math.min(item.value, 100)}%`,
                  backgroundColor:
                    item.value > 80
                      ? '#f6465d'
                      : item.value > 50
                      ? '#f0b90b'
                      : '#0ecb81',
                }}
              />
            </div>
            <span
              className='w-8 text-right text-[9px] tabular-nums text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {item.value.toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Panel Card wrapper ────────────────────────────────────────────────────────

function PanelCard({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className='glow-card'>
      <div className='to-panel-header'>
        <div className='flex items-center gap-2'>
          {icon}
          <span
            className='panel-label'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            {title}
          </span>
        </div>
      </div>
      <div className='space-y-3 p-3'>{children}</div>
    </div>
  );
}

 
function DailyRiskCard({ data }: { data: any }) {
  const utilizationColor =
    data.loss_pct > 80
      ? 'bg-[var(--to-short)]'
      : data.loss_pct > 50
      ? 'bg-[var(--to-warning)]'
      : 'bg-[var(--to-long)]';

  return (
    <PanelCard
      icon={<Target className='h-3.5 w-3.5 text-[var(--to-accent-blue)]' />}
      title='Daily Risk Status'
    >
      <div>
        <div className='mb-1 flex items-baseline justify-between'>
          <span
            className='text-[10px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            Daily Loss
          </span>
          <span
            className='text-xs text-[var(--to-text-primary)] tabular-nums'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            ${data.loss_used_usd.toFixed(2)} / ${data.loss_limit_usd.toFixed(2)}
          </span>
        </div>
        <div className='h-1.5 overflow-hidden rounded-full bg-[var(--to-border)]'>
          <div
            className={cn('h-full transition-all', utilizationColor)}
            style={{ width: `${Math.min(data.loss_pct, 100)}%` }}
          />
        </div>
        <div
          className='mt-1 text-[9px] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {data.loss_pct.toFixed(1)}% utilization
        </div>
      </div>
      <div className='border-t border-[var(--to-border)] pt-2'>
        <div className='flex justify-between text-xs'>
          <span
            className='text-[var(--to-text-secondary)]'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            Remaining
          </span>
          <span
            className='tabular-nums text-[var(--to-long)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            ${data.remaining_usd.toFixed(2)}
          </span>
        </div>
      </div>
      {data.profit_current_usd > 0 && (
        <div className='border-t border-[var(--to-border)] pt-2'>
          <div className='flex justify-between text-xs'>
            <span
              className='text-[var(--to-text-secondary)]'
              style={{ fontFamily: 'var(--font-sans)' }}
            >
              Daily Profit
            </span>
            <span
              className='tabular-nums text-[var(--to-long)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              +${data.profit_current_usd.toFixed(2)}
            </span>
          </div>
          {data.is_profit_target_hit && (
            <div
              className='mt-1 text-[10px] text-[var(--to-long)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              target hit: ${data.profit_target_usd.toFixed(0)}
            </div>
          )}
        </div>
      )}
    </PanelCard>
  );
}

 
function PositionLimitsCard({ data }: { data: any }) {
  return (
    <PanelCard
      icon={<Shield className='h-3.5 w-3.5 text-[var(--to-accent-blue)]' />}
      title='Position Limits'
    >
      <div className='flex items-center justify-between'>
        <span
          className='text-[10px] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          Open Positions
        </span>
        <span
          className='text-base font-semibold tabular-nums text-[var(--to-text-primary)]'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {data.open_positions} / {data.max_positions}
        </span>
      </div>
      <div className='flex items-center justify-between'>
        <span
          className='text-[10px] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          Trades Today
        </span>
        <span
          className='text-base font-semibold tabular-nums text-[var(--to-text-primary)]'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {data.trades_today} / {data.max_trades_today}
        </span>
      </div>
      {data.warning && (
        <div className='flex items-center gap-2 border-t border-[var(--to-border)] pt-2'>
          <AlertCircle className='h-3 w-3 text-[var(--to-warning)]' />
          <span
            className='text-[10px] text-[var(--to-warning)]'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            {data.warning}
          </span>
        </div>
      )}
    </PanelCard>
  );
}

 
function DrawdownCard({ data }: { data: any }) {
  const ddColor =
    data.dd_utilization_pct > 80
      ? 'bg-[var(--to-short)]'
      : data.dd_utilization_pct > 50
      ? 'bg-[var(--to-warning)]'
      : 'bg-[var(--to-long)]';

  return (
    <PanelCard
      icon={<TrendingDown className='h-3.5 w-3.5 text-[var(--to-accent-blue)]' />}
      title='Drawdown Status'
    >
      <div>
        <div className='mb-1 flex items-baseline justify-between'>
          <span
            className='text-[10px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            Current DD
          </span>
          <span
            className='text-xs text-[var(--to-text-primary)] tabular-nums'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {data.current_dd_pct.toFixed(2)}% /{' '}
            {data.max_dd_allowed_pct.toFixed(1)}%
          </span>
        </div>
        <div className='h-1.5 overflow-hidden rounded-full bg-[var(--to-border)]'>
          <div
            className={cn('h-full transition-all', ddColor)}
            style={{ width: `${Math.min(data.dd_utilization_pct, 100)}%` }}
          />
        </div>
        <div
          className='mt-1 text-[9px] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {data.dd_utilization_pct.toFixed(0)}% of max drawdown used
        </div>
      </div>
      <div className='grid grid-cols-2 gap-3 border-t border-[var(--to-border)] pt-2'>
        <div>
          <div
            className='text-[10px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            Peak Equity
          </div>
          <div
            className='text-xs tabular-nums text-[var(--to-text-secondary)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            ${data.peak_equity_usd.toFixed(2)}
          </div>
        </div>
        <div>
          <div
            className='text-[10px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            Current
          </div>
          <div
            className='text-xs tabular-nums text-[var(--to-text-secondary)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            ${data.current_equity_usd.toFixed(2)}
          </div>
        </div>
      </div>
    </PanelCard>
  );
}

 
const HOUR_PRESETS_START = [5, 6, 7, 8, 9] as const;
const HOUR_PRESETS_END = [20, 21, 22, 23] as const;

function ActiveSettingsCard({ data }: { data: any }) {
  const { settings, isSaving, update } = useHtfFilter();
  const startHour = settings.trading_start_hour;
  const endHour = settings.trading_end_hour;

  const rows = [
    { label: 'Risk/Trade', value: `${data.risk_per_trade_pct}%` },
    { label: 'Min R:R', value: data.min_rr_ratio.toFixed(1) },
    { label: 'SL Buffer', value: `${data.stop_loss_buffer_pips} pips` },
    { label: 'Max Trades/Day', value: String(data.max_trades_per_day) },
    {
      label: 'Hourly Close Block',
      value: data.hourly_close_block_enabled ? 'ON' : 'OFF',
    },
    {
      label: 'Return Strength',
      value: data.pine_min_return_strength > 0 ? `≥ ${data.pine_min_return_strength}` : 'OFF',
    },
  ];

  return (
    <PanelCard
      icon={<Settings className='h-3.5 w-3.5 text-[var(--to-accent-blue)]' />}
      title='Active Settings'
    >
      <div className='space-y-1.5'>
        {rows.map((r) => (
          <div key={r.label} className='flex justify-between text-xs'>
            <span
              className='text-[var(--to-text-secondary)]'
              style={{ fontFamily: 'var(--font-sans)' }}
            >
              {r.label}
            </span>
            <span
              className='tabular-nums text-[var(--to-text-primary)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {r.value}
            </span>
          </div>
        ))}
      </div>

      {/* Trading Hours — editable */}
      <div className='mt-3 pt-3 border-t border-[var(--to-border)]'>
        <div
          className='mb-1.5 text-[9px] uppercase tracking-[0.15em] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          Trading hours (Israel)
        </div>
        <div className='space-y-1.5'>
          <div className='flex items-center gap-2'>
            <span className='text-[10px] text-[var(--to-text-dim)] w-10' style={{ fontFamily: 'var(--font-mono)' }}>Start</span>
            <div className='flex gap-1 flex-1'>
              {HOUR_PRESETS_START.map((h) => {
                const isActive = startHour === h;
                return (
                  <button
                    key={h}
                    disabled={isSaving}
                    onClick={() => update({ trading_start_hour: h })}
                    className={cn(
                      'flex flex-1 items-center justify-center rounded-md py-1 text-[10px] font-medium transition-all duration-150',
                      isActive ? 'opacity-100' : 'opacity-40 hover:opacity-70'
                    )}
                    style={isActive ? {
                      background: 'var(--to-accent-blue)18',
                      border: '1px solid var(--to-accent-blue)40',
                      color: 'var(--to-accent-blue)',
                    } : {
                      background: 'transparent',
                      border: '1px solid transparent',
                      color: 'var(--to-text-dim)',
                    }}
                  >
                    {h}:00
                  </button>
                );
              })}
            </div>
          </div>
          <div className='flex items-center gap-2'>
            <span className='text-[10px] text-[var(--to-text-dim)] w-10' style={{ fontFamily: 'var(--font-mono)' }}>End</span>
            <div className='flex gap-1 flex-1'>
              {HOUR_PRESETS_END.map((h) => {
                const isActive = endHour === h;
                return (
                  <button
                    key={h}
                    disabled={isSaving}
                    onClick={() => update({ trading_end_hour: h })}
                    className={cn(
                      'flex flex-1 items-center justify-center rounded-md py-1 text-[10px] font-medium transition-all duration-150',
                      isActive ? 'opacity-100' : 'opacity-40 hover:opacity-70'
                    )}
                    style={isActive ? {
                      background: 'var(--to-accent-blue)18',
                      border: '1px solid var(--to-accent-blue)40',
                      color: 'var(--to-accent-blue)',
                    } : {
                      background: 'transparent',
                      border: '1px solid transparent',
                      color: 'var(--to-text-dim)',
                    }}
                  >
                    {h}:00
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </PanelCard>
  );
}


const HTF_MINUTE_PRESETS = [3, 5, 7, 10, 12] as const;
const HTF_PERIOD_OPTIONS = [30, 60] as const;

function HtfFilterCard() {
  const { settings, isLoading, isSaving, update } = useHtfFilter();
  const enabled = settings.htf_candle_filter_enabled;
  const blockMins = settings.htf_candle_block_minutes;
  const htfPeriod = settings.htf_candle_period || 15;

  return (
    <PanelCard
      icon={<Activity className='h-3.5 w-3.5 text-[var(--to-accent-blue)]' />}
      title='HTF Pre-Candle Block'
    >
      {isLoading ? (
        <div className='space-y-2'>
          <Skeleton className='h-8 w-full rounded-lg bg-[var(--to-surface-raised)]/60' />
          <Skeleton className='h-6 w-full rounded bg-[var(--to-surface-raised)]/60' />
          <Skeleton className='h-10 w-full rounded bg-[var(--to-surface-raised)]/60' />
        </div>
      ) : (
        <div className='space-y-3'>

          {/* ON / OFF toggle */}
          <div className='mx-0 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)]/50 p-0.5'>
            <div
              className='mb-1 px-1.5 pt-0.5 text-[9px] uppercase tracking-[0.2em] text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              Filter
            </div>
            <div className='flex gap-1'>
              {([true, false] as const).map((val) => {
                const isActive = enabled === val;
                const color = val ? 'var(--to-long)' : 'var(--to-short)';
                const Icon = val ? Shield : ShieldOff;
                return (
                  <button
                    key={String(val)}
                    disabled={isSaving}
                    onClick={() => update({ htf_candle_filter_enabled: val })}
                    className={cn(
                      'flex flex-1 items-center justify-center gap-1 rounded-md py-1 text-[10px] font-medium transition-all duration-150',
                      isActive ? 'opacity-100' : 'opacity-40 hover:opacity-70'
                    )}
                    style={isActive ? {
                      background: `${color}18`,
                      border: `1px solid ${color}40`,
                      color,
                    } : {
                      background: 'transparent',
                      border: '1px solid transparent',
                      color: 'var(--to-text-dim)',
                    }}
                  >
                    <Icon className='h-3 w-3 shrink-0' />
                    {val ? 'Enabled' : 'Disabled'}
                  </button>
                );
              })}
            </div>
          </div>

          {/* HTF Period selector */}
          <div className={cn('transition-opacity duration-200', !enabled && 'pointer-events-none opacity-30')}>
            <div className='mx-0 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)]/50 p-0.5'>
              <div
                className='mb-1 px-1.5 pt-0.5 text-[9px] uppercase tracking-[0.2em] text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                HTF Period
              </div>
              <div className='flex gap-1'>
                {HTF_PERIOD_OPTIONS.map((p) => {
                  const isActive = htfPeriod === p;
                  const label = p === 60 ? '1h' : `${p}m`;
                  return (
                    <button
                      key={p}
                      disabled={isSaving}
                      onClick={() => update({ htf_candle_period: p })}
                      className={cn(
                        'flex flex-1 items-center justify-center rounded-md py-1 text-[10px] font-medium transition-all duration-150',
                        isActive ? 'opacity-100' : 'opacity-40 hover:opacity-70'
                      )}
                      style={isActive ? {
                        background: 'var(--to-accent-blue)18',
                        border: '1px solid var(--to-accent-blue)40',
                        color: 'var(--to-accent-blue)',
                      } : {
                        background: 'transparent',
                        border: '1px solid transparent',
                        color: 'var(--to-text-dim)',
                      }}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Block window presets */}
          <div className={cn('transition-opacity duration-200', !enabled && 'pointer-events-none opacity-30')}>
            <div className='mx-0 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)]/50 p-0.5'>
              <div
                className='mb-1 px-1.5 pt-0.5 text-[9px] uppercase tracking-[0.2em] text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                Block window
              </div>
              <div className='flex gap-1'>
                {HTF_MINUTE_PRESETS.map((min) => {
                  const isActive = blockMins === min;
                  return (
                    <button
                      key={min}
                      disabled={isSaving}
                      onClick={() => update({ htf_candle_block_minutes: min })}
                      className={cn(
                        'flex flex-1 items-center justify-center rounded-md py-1 text-[10px] font-medium transition-all duration-150',
                        isActive ? 'opacity-100' : 'opacity-40 hover:opacity-70'
                      )}
                      style={isActive ? {
                        background: 'var(--to-accent-blue)18',
                        border: '1px solid var(--to-accent-blue)40',
                        color: 'var(--to-accent-blue)',
                      } : {
                        background: 'transparent',
                        border: '1px solid transparent',
                        color: 'var(--to-text-dim)',
                      }}
                    >
                      {min}m
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Timeline: safe zone vs blocked zone within HTF cycle */}
          <div className={cn('space-y-2 transition-opacity duration-200', !enabled && 'opacity-30')}>
            <div
              className='text-[9px] uppercase tracking-[0.15em] text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {htfPeriod === 60 ? '1h' : `${htfPeriod}m`} HTF cycle
            </div>

            <div className='relative'>
              <div className='relative h-5 w-full overflow-hidden rounded-md bg-[var(--to-surface-raised)]'>
                {/* Safe zone */}
                <div
                  className='absolute left-0 top-0 h-full transition-all duration-300'
                  style={{
                    width: `${((htfPeriod - blockMins) / htfPeriod) * 100}%`,
                    background: 'var(--to-long)',
                    opacity: 0.4,
                  }}
                />
                {/* Blocked zone */}
                <div
                  className='absolute right-0 top-0 h-full transition-all duration-300'
                  style={{
                    width: `${(blockMins / htfPeriod) * 100}%`,
                    background: 'var(--to-short)',
                    opacity: 0.5,
                  }}
                />
                {/* Tick dividers — every 5m */}
                {Array.from({ length: Math.floor(htfPeriod / 5) - 1 }, (_, i) => (i + 1) * 5).map((tick) => (
                  <div
                    key={tick}
                    className='absolute top-0 h-full w-px bg-[var(--to-border)]/60'
                    style={{ left: `${(tick / htfPeriod) * 100}%` }}
                  />
                ))}
                {/* Split marker */}
                <div
                  className='absolute top-0 h-full w-0.5 bg-[var(--to-text-primary)] opacity-60 transition-all duration-300'
                  style={{ left: `${((htfPeriod - blockMins) / htfPeriod) * 100}%` }}
                />
              </div>

              {/* Time axis */}
              <div className='relative mt-1 h-3.5'>
                {[0, Math.floor(htfPeriod / 3), Math.floor(htfPeriod * 2 / 3), htfPeriod].map((tick) => (
                  <span
                    key={tick}
                    className='absolute text-[8px] tabular-nums text-[var(--to-text-dim)]'
                    style={{
                      fontFamily: 'var(--font-mono)',
                      left: `${(tick / htfPeriod) * 100}%`,
                      transform: tick === 0 ? 'none' : tick === htfPeriod ? 'translateX(-100%)' : 'translateX(-50%)',
                    }}
                  >
                    {tick}m
                  </span>
                ))}
              </div>
            </div>

            {/* Summary */}
            <div
              className='flex items-center justify-between rounded-md px-2 py-1 text-[8px]'
              style={{ background: 'var(--to-surface-raised)', fontFamily: 'var(--font-mono)' }}
            >
              <span style={{ color: 'var(--to-long)', opacity: 0.9 }}>
                ✓ enter 0–{htfPeriod - blockMins}m
              </span>
              <span className='text-[var(--to-text-dim)]'>·</span>
              <span style={{ color: 'var(--to-short)', opacity: 0.9 }}>
                ✗ last {blockMins}m blocked
              </span>
            </div>
          </div>

        </div>
      )}
    </PanelCard>
  );
}

const DEP_PRESETS = [40, 50, 60, 70, 80];

function OneCandleLiqCard() {
  const { settings, isLoading, isSaving, update } = useHtfFilter();
  const enabled = settings.block_one_candle_liq;
  const minDep = settings.one_candle_liq_min_departure;

  return (
    <PanelCard
      icon={<Activity className='h-3.5 w-3.5 text-[var(--to-accent-blue)]' />}
      title='1-Candle Liquidity Filter'
    >
      {isLoading ? (
        <div className='space-y-2'>
          <Skeleton className='h-8 w-full rounded-lg bg-[var(--to-surface-raised)]/60' />
          <Skeleton className='h-6 w-full rounded bg-[var(--to-surface-raised)]/60' />
        </div>
      ) : (
        <div className='space-y-3'>

          {/* Description */}
          <p className='text-[11px] text-[var(--to-text-dim)]' style={{ fontFamily: 'var(--font-sans)' }}>
            Block trades where the liquidity was formed by a single candle, unless all
            high-confidence conditions are met (trend, sweep, departure strength).
          </p>

          {/* ON / OFF toggle */}
          <div className='mx-0 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)]/50 p-0.5'>
            <div
              className='mb-1 px-1.5 pt-0.5 text-[9px] uppercase tracking-[0.2em] text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              Filter
            </div>
            <div className='flex gap-1'>
              {([true, false] as const).map((val) => {
                const isActive = enabled === val;
                const color = val ? 'var(--to-long)' : 'var(--to-short)';
                const Icon = val ? Shield : ShieldOff;
                return (
                  <button
                    key={String(val)}
                    disabled={isSaving}
                    onClick={() => update({ block_one_candle_liq: val })}
                    className={cn(
                      'flex flex-1 items-center justify-center gap-1 rounded-md py-1 text-[10px] font-medium transition-all duration-150',
                      isActive ? 'opacity-100' : 'opacity-40 hover:opacity-70'
                    )}
                    style={isActive ? {
                      background: `${color}18`,
                      border: `1px solid ${color}40`,
                      color,
                    } : {
                      background: 'transparent',
                      border: '1px solid transparent',
                      color: 'var(--to-text-dim)',
                    }}
                  >
                    <Icon className='h-3 w-3 shrink-0' />
                    {val ? 'Enabled' : 'Disabled'}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Min departure strength presets */}
          <div className={cn('transition-opacity duration-200', !enabled && 'pointer-events-none opacity-30')}>
            <div className='mx-0 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface-raised)]/50 p-0.5'>
              <div
                className='mb-1 px-1.5 pt-0.5 text-[9px] uppercase tracking-[0.2em] text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                Min departure strength (base)
              </div>
              <div className='flex gap-1'>
                {DEP_PRESETS.map((val) => {
                  const isActive = minDep === val;
                  return (
                    <button
                      key={val}
                      disabled={isSaving}
                      onClick={() => update({ one_candle_liq_min_departure: val })}
                      className={cn(
                        'flex flex-1 items-center justify-center rounded-md py-1 text-[10px] font-medium transition-all duration-150',
                        isActive ? 'opacity-100' : 'opacity-40 hover:opacity-70'
                      )}
                      style={isActive ? {
                        background: 'var(--to-accent-blue)18',
                        border: '1px solid var(--to-accent-blue)40',
                        color: 'var(--to-accent-blue)',
                      } : {
                        background: 'transparent',
                        border: '1px solid transparent',
                        color: 'var(--to-text-dim)',
                      }}
                    >
                      {val}
                    </button>
                  );
                })}
              </div>
              {/* Dynamic range annotation */}
              {(() => {
                // Market adjustments: RVOL ±5, session ±5, ADX ±5 = max ±15, scaled x0.8 = ±12
                const maxAdj = 15 * 0.8;
                const dynMin = Math.max(30, Math.round(minDep - maxAdj));
                const dynMax = Math.min(90, Math.round(minDep + maxAdj));
                return (
                  <div className='mt-1.5 px-1.5 pb-0.5 flex items-center gap-1.5'>
                    <span className='text-[9px] text-[var(--to-text-dim)]' style={{ fontFamily: 'var(--font-mono)' }}>
                      Effective range:
                    </span>
                    <span className='text-[9px] font-medium' style={{ fontFamily: 'var(--font-mono)', color: 'var(--to-accent-blue)' }}>
                      {dynMin}–{dynMax}
                    </span>
                    <span className='text-[8px] text-[var(--to-text-dim)]' style={{ fontFamily: 'var(--font-sans)' }}>
                      (adjusted by RVOL / session / ADX)
                    </span>
                  </div>
                );
              })()}
            </div>
          </div>

          {/* Conditions summary */}
          <div className={cn('transition-opacity duration-200', !enabled && 'opacity-30')}>
            <div
              className='text-[9px] uppercase tracking-[0.15em] text-[var(--to-text-dim)] mb-1.5'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              Override conditions (all required)
            </div>
            <div className='space-y-1'>
              {[
                'Not a middle zone (only trade-ready zones count)',
                'Trend aligned (above 200 EMA)',
                'Liquidity swept + caused sweep',
                `Departure strength ≥ ${minDep} (dynamic: ${Math.max(30, Math.round(minDep - 12))}–${Math.min(90, Math.round(minDep + 12))})`,
              ].map((cond) => (
                <div key={cond} className='flex items-center gap-1.5'>
                  <span className='text-[10px]' style={{ color: 'var(--to-long)' }}>✓</span>
                  <span className='text-[11px] text-[var(--to-text-secondary)]' style={{ fontFamily: 'var(--font-sans)' }}>
                    {cond}
                  </span>
                </div>
              ))}
            </div>
          </div>

        </div>
      )}
    </PanelCard>
  );
}


 
function SymbolOverridesCard({ data }: { data: any[] }) {
  return (
    <div className='glow-card'>
      <div className='to-panel-header'>
        <div className='flex items-center gap-2'>
          <span
            className='panel-label'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            Symbol Overrides
          </span>
          <span
            className='text-[9px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            read-only
          </span>
        </div>
      </div>
      <div className='overflow-x-auto p-3'>
        <table className='w-full text-xs'>
          <thead>
            <tr className='border-b border-[var(--to-border)]'>
              {['Symbol', 'Risk%', 'Max Lots', 'SL Buffer', 'Pip Size'].map(
                (h) => (
                  <th
                    key={h}
                    className='py-1.5 text-left text-[9px] uppercase tracking-wider text-[var(--to-text-dim)] last:text-right'
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    {h}
                  </th>
                )
              )}
            </tr>
          </thead>
          <tbody>
            {data.map((o) => (
              <tr
                key={o.symbol}
                className='border-b border-[var(--to-border)]/50 last:border-0 data-row'
              >
                <td
                  className='py-1.5 text-[var(--to-text-secondary)]'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {o.symbol}
                </td>
                <td
                  className='py-1.5 text-right tabular-nums text-[var(--to-text-dim)]'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {o.risk_pct}%
                </td>
                <td
                  className='py-1.5 text-right tabular-nums text-[var(--to-text-dim)]'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {o.max_lots}
                </td>
                <td
                  className='py-1.5 text-right tabular-nums text-[var(--to-text-dim)]'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {o.sl_buffer_pips} pips
                </td>
                <td
                  className='py-1.5 text-right tabular-nums text-[var(--to-text-dim)]'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {o.pip_size}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div aria-label='Loading risk metrics' className='space-y-3'>
      <div className='grid grid-cols-1 gap-3 lg:grid-cols-3'>
        <Skeleton className='h-32 w-32 rounded-full bg-[var(--to-surface-raised)]/60 mx-auto' />
        <Skeleton className='h-32 w-32 rounded-full bg-[var(--to-surface-raised)]/60 mx-auto' />
        <Skeleton className='h-32 w-32 rounded-full bg-[var(--to-surface-raised)]/60 mx-auto' />
      </div>
      <div className='space-y-2'>
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className='h-10 w-full rounded-xl bg-[var(--to-surface-raised)]/60' />
        ))}
      </div>
      <div className='grid grid-cols-1 gap-3 lg:grid-cols-2'>
        <Skeleton className='h-44 rounded-xl bg-[var(--to-surface-raised)]/60' />
        <Skeleton className='h-44 rounded-xl bg-[var(--to-surface-raised)]/60' />
      </div>
    </div>
  );
}
