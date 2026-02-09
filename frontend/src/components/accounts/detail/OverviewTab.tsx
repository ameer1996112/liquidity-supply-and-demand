'use client';

import { Shield, Server, Clock, AlertTriangle, TrendingUp, Activity } from 'lucide-react';
import type { AccountDetailApi } from '@/lib/api';

interface OverviewTabProps {
  account: AccountDetailApi;
}

export function OverviewTab({ account }: OverviewTabProps) {
  const isPaused = account.pause_trading ?? false;

  return (
    <div className="space-y-6">
      {/* Live Status */}
      <section className="tv-card p-4">
        <h3 className="text-sm font-medium text-zinc-300 mb-4 flex items-center gap-2">
          <Server className="h-4 w-4 text-emerald-500" />
          Live Status
        </h3>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            label="Balance"
            value={`$${account.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
            valueColor="text-zinc-100"
          />
          <MetricCard
            label="Equity"
            value={`$${(account.equity || account.balance).toLocaleString(undefined, { minimumFractionDigits: 2 })}`}
            valueColor={account.equity && account.equity >= account.balance ? 'text-[#26a69a]' : account.equity && account.equity < account.balance ? 'text-[#ef5350]' : 'text-zinc-100'}
          />
          <MetricCard
            label="Free Margin"
            value={account.free_margin != null ? `$${account.free_margin.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : 'N/A'}
            valueColor="text-zinc-300"
            sublabel={account.free_margin == null ? 'Awaiting sync' : undefined}
          />
          <MetricCard
            label="Margin Level"
            value={account.margin_level_pct != null ? `${account.margin_level_pct.toFixed(1)}%` : 'N/A'}
            valueColor={
              account.margin_level_pct && account.margin_level_pct >= 200
                ? 'text-[#26a69a]'
                : account.margin_level_pct && account.margin_level_pct >= 100
                ? 'text-zinc-300'
                : account.margin_level_pct
                ? 'text-[#ef5350]'
                : 'text-zinc-400'
            }
            sublabel={account.margin_level_pct == null ? 'Awaiting sync' : undefined}
          />
        </div>

        {account.server_name && (
          <div className="mt-4 pt-4 border-t border-[#2a2e39] text-xs text-zinc-500 flex items-center gap-4">
            <span>Server: {account.server_name}</span>
            {account.platform_type && <span>Platform: {account.platform_type}</span>}
            {account.leverage && <span>Leverage: 1:{account.leverage}</span>}
            {account.last_sync_time && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                Last sync: {new Date(account.last_sync_time).toLocaleTimeString()}
              </span>
            )}
          </div>
        )}
      </section>

      {/* Risk Configuration */}
      <section className="tv-card p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-zinc-300 flex items-center gap-2">
            <Shield className="h-4 w-4 text-blue-500" />
            Risk Configuration
          </h3>
          <span className="text-xs text-zinc-500 font-mono">
            Source: {account.strategy_type || 'Pine/TradingView'}
          </span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            label="Risk per Trade"
            value={`${account.risk_percent || 0.5}%`}
            valueColor="text-amber-400"
          />
          <MetricCard
            label="Min R:R Ratio"
            value={account.min_rr_ratio != null && account.min_rr_ratio > 0 ? `${account.min_rr_ratio}:1` : 'Off (Pine)'}
            valueColor={account.min_rr_ratio != null && account.min_rr_ratio > 0 ? 'text-amber-400' : 'text-zinc-500'}
          />
          <MetricCard
            label="Max Lot Size"
            value={`${account.max_lot_size || 10.0} lots`}
            valueColor="text-amber-400"
          />
          <MetricCard
            label="Max Positions"
            value={`${account.max_positions || 3}`}
            valueColor="text-amber-400"
          />
        </div>

        <div className="mt-4 pt-4 border-t border-[#2a2e39]">
          <p className="text-xs text-zinc-500 italic">
            💡 Risk settings are controlled by Pine strategy. Dashboard displays current state (read-only).
          </p>
        </div>
      </section>

      {/* Performance Metrics */}
      <section className="tv-card p-4">
        <h3 className="text-sm font-medium text-zinc-300 mb-4 flex items-center gap-2">
          <Activity className="h-4 w-4 text-green-500" />
          Performance Summary
          <span className="ml-auto text-xs text-zinc-600 font-mono">(Last 30 days)</span>
        </h3>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <MetricCard
            label="Win Rate"
            value={`${(account.win_rate * 100).toFixed(1)}%`}
            valueColor={account.win_rate >= 0.5 ? 'text-[#26a69a]' : 'text-[#ef5350]'}
          />
          <MetricCard
            label="Profit Factor"
            value={account.profit_factor != null && account.profit_factor > 0 ? account.profit_factor.toFixed(2) : 'N/A'}
            valueColor={
              account.profit_factor && account.profit_factor >= 1.5
                ? 'text-[#26a69a]'
                : account.profit_factor && account.profit_factor >= 1
                ? 'text-zinc-400'
                : account.profit_factor
                ? 'text-[#ef5350]'
                : 'text-zinc-400'
            }
            sublabel={account.total_trades && account.total_trades < 10 ? 'Low sample' : undefined}
          />
          <MetricCard
            label="Sharpe Ratio"
            value={account.sharpe_ratio && account.sharpe_ratio !== 0 ? account.sharpe_ratio.toFixed(2) : 'N/A'}
            valueColor={
              account.sharpe_ratio && account.sharpe_ratio >= 1.5
                ? 'text-[#26a69a]'
                : account.sharpe_ratio && account.sharpe_ratio >= 1
                ? 'text-zinc-300'
                : 'text-zinc-400'
            }
          />
          <MetricCard
            label="Max Drawdown"
            value={account.max_drawdown_pct != null && account.max_drawdown_pct > 0 ? `${account.max_drawdown_pct.toFixed(1)}%` : 'N/A'}
            valueColor={
              account.max_drawdown_pct && account.max_drawdown_pct >= 10
                ? 'text-[#ef5350]'
                : account.max_drawdown_pct && account.max_drawdown_pct >= 5
                ? 'text-amber-400'
                : 'text-zinc-400'
            }
            sublabel={account.max_drawdown_pct == null || account.max_drawdown_pct === 0 ? 'Calculating' : undefined}
          />
          <MetricCard
            label="Total Trades"
            value={account.total_trades?.toString() || '0'}
            valueColor="text-zinc-300"
          />
        </div>
      </section>

      {/* Today's Activity */}
      <section className="tv-card p-4">
        <h3 className="text-sm font-medium text-zinc-300 mb-4 flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-blue-500" />
          Today's Activity
        </h3>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            label="Daily P&L"
            value={`${account.daily_pnl >= 0 ? '+' : ''}$${Math.abs(account.daily_pnl).toFixed(2)}`}
            valueColor={account.daily_pnl >= 0 ? 'text-[#26a69a]' : 'text-[#ef5350]'}
          />
          <MetricCard
            label="Daily P&L %"
            value={`${account.daily_pnl_pct >= 0 ? '+' : ''}${account.daily_pnl_pct.toFixed(2)}%`}
            valueColor={account.daily_pnl_pct >= 0 ? 'text-[#26a69a]' : 'text-[#ef5350]'}
          />
          <MetricCard
            label="Active Positions"
            value={account.active_positions?.toString() || '0'}
            valueColor={
              account.active_positions && account.max_positions && account.active_positions >= account.max_positions
                ? 'text-amber-400'
                : 'text-zinc-300'
            }
            sublabel={account.max_positions ? `Max: ${account.max_positions}` : undefined}
          />
          <MetricCard
            label="Margin Used"
            value={account.margin_used != null ? `$${account.margin_used.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : 'N/A'}
            valueColor="text-zinc-300"
            sublabel={account.margin_used == null ? 'No positions' : undefined}
          />
        </div>
      </section>

      {/* Warnings / Alerts */}
      {isPaused && (
        <section className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-500 flex-shrink-0" />
          <div>
            <div className="text-sm font-medium text-amber-600">Trading Paused</div>
            <div className="text-xs text-amber-600/80 mt-0.5">
              This account is currently paused. Resume trading from the Accounts table.
            </div>
          </div>
        </section>
      )}

      {account.account_type === 'Eval' && (
        <section className="rounded-lg border border-blue-500/30 bg-blue-500/5 px-4 py-3">
          <div className="flex items-center gap-3 mb-3">
            <TrendingUp className="h-5 w-5 text-blue-500" />
            <div className="text-sm font-medium text-blue-400">Evaluation Challenge</div>
          </div>
          <div className="text-xs text-blue-400/80">
            💡 Evaluation progress tracking coming soon. This will show profit target, drawdown limits, and trading days.
          </div>
        </section>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  valueColor,
  sublabel,
}: {
  label: string;
  value: string;
  valueColor: string;
  sublabel?: string;
}) {
  return (
    <div className="flex flex-col gap-1 p-3 rounded bg-[#1e222d]/50">
      <span className="text-[10px] text-zinc-600 font-mono">{label}</span>
      <span className={`font-mono text-sm font-semibold tabular-nums ${valueColor}`}>
        {value}
      </span>
      {sublabel && <span className="text-[9px] text-zinc-600 mt-0.5">{sublabel}</span>}
    </div>
  );
}
