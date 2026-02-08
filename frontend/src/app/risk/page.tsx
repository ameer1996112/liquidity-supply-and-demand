'use client';

import { useRiskMonitor, type GuardRailStatus } from '@/hooks/useRiskMonitor';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { Shield, TrendingDown, Target, Settings, AlertCircle, Info } from 'lucide-react';

export default function RiskMonitorPage() {
  const { data, isLoading, error } = useRiskMonitor();

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-lg font-semibold text-zinc-100">Risk Monitor</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            Real-time risk state from Pine Script
          </p>
        </div>

        <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-600">
          Failed to load risk monitor data. Ensure the backend API is running and NEXT_PUBLIC_API_URL is set.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-lg font-semibold text-zinc-100">Risk Monitor</h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          Real-time risk state from Pine Script
        </p>
      </div>

      {/* Disclaimer Banner */}
      <div className="rounded-lg border border-blue-500/30 bg-blue-500/5 px-4 py-3 flex items-start gap-3">
        <Info className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
        <div className="text-sm text-blue-400">
          <span className="font-medium">Risk settings are configured in Pine Script (TradingView).</span>
          <br />
          This dashboard displays current state only — no editing. To adjust risk: modify SND_Strategy.pine inputs.
        </div>
      </div>

      {isLoading ? (
        <LoadingSkeleton />
      ) : data ? (
        <>
          {/* Top Row: Daily Risk + Position Limits */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <DailyRiskCard data={data.daily_risk} />
            <PositionLimitsCard data={data.position_limits} />
          </div>

          {/* Middle Row: Drawdown + Active Settings */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <DrawdownCard data={data.drawdown} />
            <ActiveSettingsCard data={data.active_settings} />
          </div>

          {/* Guard Rails Status */}
          <GuardRailsCard data={data.guard_rails} />

          {/* Symbol Overrides */}
          {data.symbol_overrides && data.symbol_overrides.length > 0 && (
            <SymbolOverridesCard data={data.symbol_overrides} />
          )}

          {/* Last Updated */}
          <div className="text-xs text-zinc-600 font-mono text-right">
            Last updated: {new Date(data.last_updated).toLocaleTimeString()}
          </div>
        </>
      ) : null}
    </div>
  );
}

function DailyRiskCard({ data }: { data: any }) {
  const utilizationColor = data.loss_pct > 80 ? 'bg-red-500' : data.loss_pct > 50 ? 'bg-amber-500' : 'bg-emerald-500';

  return (
    <Card className="border-[#2a2e39] bg-[#1e222d]/50">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Target className="h-4 w-4 text-emerald-500" />
          <CardTitle className="text-sm font-medium text-zinc-100">
            Daily Risk Status
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <div className="flex items-baseline justify-between mb-1">
            <span className="text-xs text-zinc-500">Daily Loss</span>
            <span className="text-sm font-mono text-zinc-300">
              ${data.loss_used_usd.toFixed(2)} / ${data.loss_limit_usd.toFixed(2)}
            </span>
          </div>
          <div className="h-2 bg-[#131722] rounded-full overflow-hidden">
            <div
              className={cn('h-full transition-all', utilizationColor)}
              style={{ width: `${Math.min(data.loss_pct, 100)}%` }}
            />
          </div>
          <div className="text-xs text-zinc-600 mt-1 font-mono">
            {data.loss_pct.toFixed(1)}% utilization
          </div>
        </div>

        <div className="pt-2 border-t border-[#2a2e39]">
          <div className="flex justify-between text-xs">
            <span className="text-zinc-500">Remaining</span>
            <span className="font-mono text-emerald-400">${data.remaining_usd.toFixed(2)}</span>
          </div>
        </div>

        {data.profit_current_usd > 0 && (
          <div className="pt-2 border-t border-[#2a2e39]">
            <div className="flex justify-between text-xs">
              <span className="text-zinc-500">Daily Profit</span>
              <span className="font-mono text-emerald-400">+${data.profit_current_usd.toFixed(2)}</span>
            </div>
            {data.is_profit_target_hit && (
              <div className="mt-1 text-xs text-emerald-500">Target hit: ${data.profit_target_usd.toFixed(0)}</div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function PositionLimitsCard({ data }: { data: any }) {
  return (
    <Card className="border-[#2a2e39] bg-[#1e222d]/50">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-emerald-500" />
          <CardTitle className="text-sm font-medium text-zinc-100">
            Position Limits
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex justify-between items-center">
          <span className="text-xs text-zinc-500">Open Positions</span>
          <span className="text-lg font-mono text-zinc-200">
            {data.open_positions} / {data.max_positions}
          </span>
        </div>

        <div className="flex justify-between items-center">
          <span className="text-xs text-zinc-500">Trades Today</span>
          <span className="text-lg font-mono text-zinc-200">
            {data.trades_today} / {data.max_trades_today}
          </span>
        </div>

        {data.warning && (
          <div className="pt-2 border-t border-[#2a2e39] flex items-center gap-2">
            <AlertCircle className="w-3.5 h-3.5 text-amber-500" />
            <span className="text-xs text-amber-400">{data.warning}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function DrawdownCard({ data }: { data: any }) {
  const ddUtilizationColor = data.dd_utilization_pct > 80 ? 'bg-red-500' : data.dd_utilization_pct > 50 ? 'bg-amber-500' : 'bg-emerald-500';

  return (
    <Card className="border-[#2a2e39] bg-[#1e222d]/50">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <TrendingDown className="h-4 w-4 text-emerald-500" />
          <CardTitle className="text-sm font-medium text-zinc-100">
            Drawdown Status
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <div className="flex items-baseline justify-between mb-1">
            <span className="text-xs text-zinc-500">Current DD</span>
            <span className="text-sm font-mono text-zinc-300">
              {data.current_dd_pct.toFixed(2)}% / {data.max_dd_allowed_pct.toFixed(1)}%
            </span>
          </div>
          <div className="h-2 bg-[#131722] rounded-full overflow-hidden">
            <div
              className={cn('h-full transition-all', ddUtilizationColor)}
              style={{ width: `${Math.min(data.dd_utilization_pct, 100)}%` }}
            />
          </div>
          <div className="text-xs text-zinc-600 mt-1 font-mono">
            {data.dd_utilization_pct.toFixed(0)}% of max drawdown used
          </div>
        </div>

        <div className="pt-2 border-t border-[#2a2e39] grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-zinc-500">Peak Equity</div>
            <div className="text-sm font-mono text-zinc-300">${data.peak_equity_usd.toFixed(2)}</div>
          </div>
          <div>
            <div className="text-xs text-zinc-500">Current</div>
            <div className="text-sm font-mono text-zinc-300">${data.current_equity_usd.toFixed(2)}</div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ActiveSettingsCard({ data }: { data: any }) {
  return (
    <Card className="border-[#2a2e39] bg-[#1e222d]/50">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Settings className="h-4 w-4 text-emerald-500" />
          <CardTitle className="text-sm font-medium text-zinc-100">
            Active Settings
          </CardTitle>
        </div>
        <CardDescription className="text-[10px] text-zinc-500">
          Configured in Pine Script
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex justify-between text-xs">
          <span className="text-zinc-500">Risk/Trade</span>
          <span className="font-mono text-zinc-300">{data.risk_per_trade_pct}%</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-zinc-500">Min R:R</span>
          <span className="font-mono text-zinc-300">{data.min_rr_ratio.toFixed(1)}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-zinc-500">SL Buffer</span>
          <span className="font-mono text-zinc-300">{data.stop_loss_buffer_pips} pips</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-zinc-500">Trading Hours</span>
          <span className="font-mono text-zinc-300">{data.trading_hours_utc} UTC</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-zinc-500">Max Trades/Day</span>
          <span className="font-mono text-zinc-300">{data.max_trades_per_day}</span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-zinc-500">Dead Zone Block</span>
          <span className="font-mono text-zinc-300">{data.dead_zone_block_enabled ? 'ON' : 'OFF'}</span>
        </div>
      </CardContent>
    </Card>
  );
}

function GuardRailsCard({ data }: { data: GuardRailStatus[] }) {
  return (
    <Card className="border-[#2a2e39] bg-[#1e222d]/50">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-emerald-500" />
          <CardTitle className="text-sm font-medium text-zinc-100">
            Guard Rails Status
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {data.map((rail) => (
            <div key={rail.name} className="flex items-center justify-between py-2 border-b border-[#2a2e39] last:border-0">
              <span className="text-xs text-zinc-400">{rail.name}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-zinc-500">{rail.message}</span>
                <StatusBadge severity={rail.severity} />
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function SymbolOverridesCard({ data }: { data: any[] }) {
  return (
    <Card className="border-[#2a2e39] bg-[#1e222d]/50">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium text-zinc-100">
          Symbol Overrides (Read-Only)
        </CardTitle>
        <CardDescription className="text-[10px] text-zinc-500">
          Custom risk settings per symbol
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[#2a2e39] text-zinc-500">
                <th className="text-left py-2 font-mono">Symbol</th>
                <th className="text-right py-2 font-mono">Risk%</th>
                <th className="text-right py-2 font-mono">Max Lots</th>
                <th className="text-right py-2 font-mono">SL Buffer</th>
                <th className="text-right py-2 font-mono">Pip Size</th>
              </tr>
            </thead>
            <tbody>
              {data.map((override) => (
                <tr key={override.symbol} className="border-b border-[#2a2e39] last:border-0">
                  <td className="py-2 font-mono text-zinc-300">{override.symbol}</td>
                  <td className="text-right py-2 font-mono text-zinc-400">{override.risk_pct}%</td>
                  <td className="text-right py-2 font-mono text-zinc-400">{override.max_lots}</td>
                  <td className="text-right py-2 font-mono text-zinc-400">{override.sl_buffer_pips} pips</td>
                  <td className="text-right py-2 font-mono text-zinc-400">{override.pip_size}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function StatusBadge({ severity }: { severity: string }) {
  const colors = {
    success: 'bg-emerald-500/20 text-emerald-500',
    warning: 'bg-amber-500/20 text-amber-500',
    critical: 'bg-red-500/20 text-red-500',
    info: 'bg-blue-500/20 text-blue-500',
  };

  const labels = {
    success: '✓',
    warning: '⚠',
    critical: '✗',
    info: 'ℹ',
  };

  return (
    <span className={cn('px-2 py-0.5 rounded text-[10px] font-mono', colors[severity as keyof typeof colors] || colors.info)}>
      {labels[severity as keyof typeof labels] || '?'}
    </span>
  );
}

function LoadingSkeleton() {
  return (
    <>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Skeleton className="h-48 rounded-lg bg-[#1e222d]" />
        <Skeleton className="h-48 rounded-lg bg-[#1e222d]" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Skeleton className="h-48 rounded-lg bg-[#1e222d]" />
        <Skeleton className="h-48 rounded-lg bg-[#1e222d]" />
      </div>
      <Skeleton className="h-64 rounded-lg bg-[#1e222d]" />
    </>
  );
}
