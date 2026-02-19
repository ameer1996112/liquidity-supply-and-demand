'use client';

import { useRiskMonitor, type GuardRailStatus } from '@/hooks/useRiskMonitor';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
  Shield,
  TrendingDown,
  Target,
  Settings,
  AlertCircle,
  Info,
} from 'lucide-react';

export default function RiskMonitorPage() {
  const { data, isLoading, error } = useRiskMonitor();

  if (error) {
    return (
      <div className='space-y-4'>
        <div>
          <h1 className='page-title text-lg font-semibold'>Risk Monitor</h1>
          <p className='page-subtitle mt-0.5 text-xs'>
            Real-time risk state from Pine Script
          </p>
        </div>
        <div className='rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 text-xs text-amber-300'>
          Failed to load risk monitor data. Ensure the backend API is running.
        </div>
      </div>
    );
  }

  return (
    <div className='space-y-4'>
      {/* Header */}
      <div>
        <h1 className='page-title text-lg font-semibold'>Risk Monitor</h1>
        <p className='page-subtitle mt-0.5 text-xs'>
          Real-time risk state from Pine Script · read-only
        </p>
      </div>

      {/* Info banner */}
      <div className='flex items-start gap-2.5 rounded-lg border border-indigo-500/20 bg-indigo-500/8 px-3 py-2.5'>
        <Info className='mt-0.5 h-3.5 w-3.5 shrink-0 text-indigo-400' />
        <p
          className='text-[11px] text-indigo-300/80'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          Risk settings are configured in Pine Script (TradingView). This
          dashboard displays current state only — to adjust risk, modify
          SND_Strategy.pine inputs.
        </p>
      </div>

      {isLoading ? (
        <LoadingSkeleton />
      ) : data ? (
        <>
          <div className='grid grid-cols-1 gap-3 lg:grid-cols-2'>
            <DailyRiskCard data={data.daily_risk} />
            <PositionLimitsCard data={data.position_limits} />
          </div>
          <div className='grid grid-cols-1 gap-3 lg:grid-cols-2'>
            <DrawdownCard data={data.drawdown} />
            <ActiveSettingsCard data={data.active_settings} />
          </div>
          <GuardRailsCard data={data.guard_rails} />
          {data.symbol_overrides && data.symbol_overrides.length > 0 && (
            <SymbolOverridesCard data={data.symbol_overrides} />
          )}
          <div
            className='text-right text-[10px] text-slate-600'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            updated {new Date(data.last_updated).toLocaleTimeString()}
          </div>
        </>
      ) : null}
    </div>
  );
}

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
    <div className='tv-card'>
      <div className='tv-divider flex items-center gap-2 border-b px-3 py-2'>
        {icon}
        <span
          className='panel-label'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          {title}
        </span>
      </div>
      <div className='space-y-3 p-3'>{children}</div>
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function DailyRiskCard({ data }: { data: any }) {
  const utilizationColor =
    data.loss_pct > 80
      ? 'bg-red-500'
      : data.loss_pct > 50
      ? 'bg-amber-500'
      : 'bg-emerald-500';

  return (
    <PanelCard
      icon={<Target className='h-3.5 w-3.5 text-indigo-400' />}
      title='Daily Risk Status'
    >
      <div>
        <div className='mb-1 flex items-baseline justify-between'>
          <span
            className='text-[10px] text-slate-500'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            Daily Loss
          </span>
          <span
            className='text-xs text-slate-300 tabular-nums'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            ${data.loss_used_usd.toFixed(2)} / ${data.loss_limit_usd.toFixed(2)}
          </span>
        </div>
        <div className='h-1.5 overflow-hidden rounded-full bg-slate-800'>
          <div
            className={cn('h-full transition-all', utilizationColor)}
            style={{ width: `${Math.min(data.loss_pct, 100)}%` }}
          />
        </div>
        <div
          className='mt-1 text-[9px] text-slate-600'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {data.loss_pct.toFixed(1)}% utilization
        </div>
      </div>

      <div className='border-t border-slate-800 pt-2'>
        <div className='flex justify-between text-xs'>
          <span
            className='text-slate-500'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            Remaining
          </span>
          <span
            className='tabular-nums text-emerald-400'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            ${data.remaining_usd.toFixed(2)}
          </span>
        </div>
      </div>

      {data.profit_current_usd > 0 && (
        <div className='border-t border-slate-800 pt-2'>
          <div className='flex justify-between text-xs'>
            <span
              className='text-slate-500'
              style={{ fontFamily: 'var(--font-sans)' }}
            >
              Daily Profit
            </span>
            <span
              className='tabular-nums text-emerald-400'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              +${data.profit_current_usd.toFixed(2)}
            </span>
          </div>
          {data.is_profit_target_hit && (
            <div
              className='mt-1 text-[10px] text-emerald-500'
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

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function PositionLimitsCard({ data }: { data: any }) {
  return (
    <PanelCard
      icon={<Shield className='h-3.5 w-3.5 text-indigo-400' />}
      title='Position Limits'
    >
      <div className='flex items-center justify-between'>
        <span
          className='text-[10px] text-slate-500'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          Open Positions
        </span>
        <span
          className='text-base font-semibold tabular-nums text-slate-200'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {data.open_positions} / {data.max_positions}
        </span>
      </div>
      <div className='flex items-center justify-between'>
        <span
          className='text-[10px] text-slate-500'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          Trades Today
        </span>
        <span
          className='text-base font-semibold tabular-nums text-slate-200'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {data.trades_today} / {data.max_trades_today}
        </span>
      </div>
      {data.warning && (
        <div className='flex items-center gap-2 border-t border-slate-800 pt-2'>
          <AlertCircle className='h-3 w-3 text-amber-400' />
          <span
            className='text-[10px] text-amber-400'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            {data.warning}
          </span>
        </div>
      )}
    </PanelCard>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function DrawdownCard({ data }: { data: any }) {
  const ddColor =
    data.dd_utilization_pct > 80
      ? 'bg-red-500'
      : data.dd_utilization_pct > 50
      ? 'bg-amber-500'
      : 'bg-emerald-500';

  return (
    <PanelCard
      icon={<TrendingDown className='h-3.5 w-3.5 text-indigo-400' />}
      title='Drawdown Status'
    >
      <div>
        <div className='mb-1 flex items-baseline justify-between'>
          <span
            className='text-[10px] text-slate-500'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            Current DD
          </span>
          <span
            className='text-xs text-slate-300 tabular-nums'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {data.current_dd_pct.toFixed(2)}% /{' '}
            {data.max_dd_allowed_pct.toFixed(1)}%
          </span>
        </div>
        <div className='h-1.5 overflow-hidden rounded-full bg-slate-800'>
          <div
            className={cn('h-full transition-all', ddColor)}
            style={{ width: `${Math.min(data.dd_utilization_pct, 100)}%` }}
          />
        </div>
        <div
          className='mt-1 text-[9px] text-slate-600'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {data.dd_utilization_pct.toFixed(0)}% of max drawdown used
        </div>
      </div>

      <div className='grid grid-cols-2 gap-3 border-t border-slate-800 pt-2'>
        <div>
          <div
            className='text-[10px] text-slate-500'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            Peak Equity
          </div>
          <div
            className='text-xs tabular-nums text-slate-300'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            ${data.peak_equity_usd.toFixed(2)}
          </div>
        </div>
        <div>
          <div
            className='text-[10px] text-slate-500'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            Current
          </div>
          <div
            className='text-xs tabular-nums text-slate-300'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            ${data.current_equity_usd.toFixed(2)}
          </div>
        </div>
      </div>
    </PanelCard>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ActiveSettingsCard({ data }: { data: any }) {
  const rows = [
    { label: 'Risk/Trade', value: `${data.risk_per_trade_pct}%` },
    { label: 'Min R:R', value: data.min_rr_ratio.toFixed(1) },
    { label: 'SL Buffer', value: `${data.stop_loss_buffer_pips} pips` },
    { label: 'Trading Hours', value: `${data.trading_hours_utc} UTC` },
    { label: 'Max Trades/Day', value: String(data.max_trades_per_day) },
    {
      label: 'Dead Zone Block',
      value: data.dead_zone_block_enabled ? 'ON' : 'OFF',
    },
  ];

  return (
    <PanelCard
      icon={<Settings className='h-3.5 w-3.5 text-indigo-400' />}
      title='Active Settings'
    >
      <div className='space-y-1.5'>
        {rows.map((r) => (
          <div key={r.label} className='flex justify-between text-xs'>
            <span
              className='text-slate-500'
              style={{ fontFamily: 'var(--font-sans)' }}
            >
              {r.label}
            </span>
            <span
              className='tabular-nums text-slate-300'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {r.value}
            </span>
          </div>
        ))}
      </div>
    </PanelCard>
  );
}

function GuardRailsCard({ data }: { data: GuardRailStatus[] }) {
  return (
    <PanelCard
      icon={<Shield className='h-3.5 w-3.5 text-indigo-400' />}
      title='Guard Rails Status'
    >
      <div className='space-y-0'>
        {data.map((rail) => (
          <div
            key={rail.name}
            className='flex items-center justify-between border-b border-slate-800 py-2 last:border-0'
          >
            <span
              className='text-[11px] text-slate-400'
              style={{ fontFamily: 'var(--font-sans)' }}
            >
              {rail.name}
            </span>
            <div className='flex items-center gap-2'>
              <span
                className='text-[10px] text-slate-600'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {rail.message}
              </span>
              <StatusBadge severity={rail.severity} />
            </div>
          </div>
        ))}
      </div>
    </PanelCard>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function SymbolOverridesCard({ data }: { data: any[] }) {
  return (
    <div className='tv-card'>
      <div className='tv-divider flex items-center gap-2 border-b px-3 py-2'>
        <span
          className='panel-label'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          Symbol Overrides
        </span>
        <span
          className='text-[9px] text-slate-600'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          read-only
        </span>
      </div>
      <div className='overflow-x-auto p-3'>
        <table className='w-full text-xs'>
          <thead>
            <tr className='border-b border-slate-800'>
              {['Symbol', 'Risk%', 'Max Lots', 'SL Buffer', 'Pip Size'].map(
                (h) => (
                  <th
                    key={h}
                    className='py-1.5 text-left text-[9px] uppercase tracking-wider text-slate-600 last:text-right'
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
                className='border-b border-slate-800/50 last:border-0 data-row'
              >
                <td
                  className='py-1.5 text-slate-300'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {o.symbol}
                </td>
                <td
                  className='py-1.5 text-right tabular-nums text-slate-400'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {o.risk_pct}%
                </td>
                <td
                  className='py-1.5 text-right tabular-nums text-slate-400'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {o.max_lots}
                </td>
                <td
                  className='py-1.5 text-right tabular-nums text-slate-400'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {o.sl_buffer_pips} pips
                </td>
                <td
                  className='py-1.5 text-right tabular-nums text-slate-400'
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

function StatusBadge({ severity }: { severity: string }) {
  const styles: Record<string, string> = {
    success: 'bg-emerald-500/15 text-emerald-400',
    warning: 'bg-amber-500/15 text-amber-400',
    critical: 'bg-red-500/15 text-red-400',
    info: 'bg-indigo-500/15 text-indigo-400',
  };
  const labels: Record<string, string> = {
    success: '✓',
    warning: '⚠',
    critical: '✗',
    info: 'i',
  };

  return (
    <span
      className={cn(
        'rounded px-1.5 py-0.5 text-[9px] font-bold',
        styles[severity] ?? styles.info
      )}
      style={{ fontFamily: 'var(--font-mono)' }}
    >
      {labels[severity] ?? '?'}
    </span>
  );
}

function LoadingSkeleton() {
  return (
    <>
      <div className='grid grid-cols-1 gap-3 lg:grid-cols-2'>
        <Skeleton className='h-44 rounded-lg bg-slate-800/60' />
        <Skeleton className='h-44 rounded-lg bg-slate-800/60' />
      </div>
      <div className='grid grid-cols-1 gap-3 lg:grid-cols-2'>
        <Skeleton className='h-44 rounded-lg bg-slate-800/60' />
        <Skeleton className='h-44 rounded-lg bg-slate-800/60' />
      </div>
      <Skeleton className='h-56 rounded-lg bg-slate-800/60' />
    </>
  );
}
