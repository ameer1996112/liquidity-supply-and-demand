'use client';

import { type AccountComparisonApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import {
  TrendingUp,
  TrendingDown,
  BarChart3,
  Target,
  AlertTriangle,
  DollarSign,
  Activity,
  Shield,
  Pause,
  Play,
  Calendar,
  Settings,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useState } from 'react';

interface EnhancedAccountCardProps {
  account: AccountComparisonApi;
  className?: string;
}

export function EnhancedAccountCard({ account, className }: EnhancedAccountCardProps) {
  const [showDetails, setShowDetails] = useState(false);
  const dailyPositive = account.daily_pnl >= 0;
  const winRatePct = (account.win_rate * 100).toFixed(1);
  const isPaused = account.pause_trading ?? false;

  // Calculate derived metrics
  const avgRR = account.avg_win_usd && account.avg_loss_usd && account.avg_loss_usd > 0
    ? (account.avg_win_usd / account.avg_loss_usd).toFixed(2)
    : 'N/A';

  const utilizationPct = account.max_positions && account.active_positions
    ? ((account.active_positions / account.max_positions) * 100).toFixed(0)
    : '0';

  return (
    <div
      className={cn(
        'tv-card flex flex-col overflow-hidden',
        isPaused && 'opacity-60 border-amber-500/20',
        className
      )}
    >
      {/* Header */}
      <div className="p-4 flex items-center justify-between border-b border-[#2a2e39]">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold text-zinc-200">
            {account.account_name}
          </span>
          {isPaused && (
            <Pause className="h-3.5 w-3.5 text-amber-500" />
          )}
        </div>
        <div className="flex items-center gap-2">
          {account.strategy_type && (
            <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#2a2e39] text-zinc-500">
              {account.strategy_type}
            </span>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-6 w-6 p-0 text-zinc-500 hover:text-zinc-300"
            onClick={() => setShowDetails(!showDetails)}
          >
            <Settings className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Main Metrics */}
      <div className="p-4 space-y-3">
        {/* Balance & Equity */}
        <div className="space-y-2">
          <div className="flex justify-between items-baseline">
            <span className="text-[10px] text-zinc-600 font-mono flex items-center gap-1">
              <DollarSign className="h-3 w-3" />
              Balance
            </span>
            <span className="font-mono text-base font-bold text-zinc-100 tabular-nums">
              ${account.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </span>
          </div>

          {account.allocated_capital_usd != null && account.allocated_capital_usd !== account.balance && (
            <div className="flex justify-between items-baseline">
              <span className="text-[10px] text-zinc-600 font-mono">Allocated</span>
              <span className="font-mono text-xs text-zinc-400 tabular-nums">
                ${account.allocated_capital_usd.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </span>
            </div>
          )}
        </div>

        {/* Daily P&L */}
        <div className="flex justify-between items-center p-2 rounded bg-[#1e222d]/50">
          <span className="text-[10px] text-zinc-600 font-mono">Daily P&L</span>
          <div className="flex items-center gap-1">
            {dailyPositive ? (
              <TrendingUp className="w-3 h-3 text-[#26a69a]" />
            ) : (
              <TrendingDown className="w-3 h-3 text-[#ef5350]" />
            )}
            <span
              className={cn(
                'font-mono text-sm font-semibold tabular-nums',
                dailyPositive ? 'text-[#26a69a]' : 'text-[#ef5350]'
              )}
            >
              {dailyPositive ? '+' : ''}${account.daily_pnl.toFixed(2)}
              <span className="text-[10px] ml-0.5 opacity-80">
                ({dailyPositive ? '+' : ''}{account.daily_pnl_pct.toFixed(2)}%)
              </span>
            </span>
          </div>
        </div>

        {/* Performance Metrics */}
        <div className="grid grid-cols-2 gap-2">
          <MetricItem
            label="Win Rate"
            value={`${winRatePct}%`}
            icon={<BarChart3 className="w-3 h-3" />}
            valueColor={parseFloat(winRatePct) >= 50 ? 'text-[#26a69a]' : 'text-[#ef5350]'}
          />
          <MetricItem
            label="Sharpe"
            value={account.sharpe_ratio != null ? account.sharpe_ratio.toFixed(2) : 'N/A'}
            icon={<Activity className="w-3 h-3" />}
          />

          {account.profit_factor != null && (
            <MetricItem
              label="Profit Factor"
              value={account.profit_factor.toFixed(2)}
              icon={<Target className="w-3 h-3" />}
              valueColor={account.profit_factor >= 1.5 ? 'text-[#26a69a]' : account.profit_factor >= 1 ? 'text-zinc-400' : 'text-[#ef5350]'}
            />
          )}

          {account.max_drawdown_pct != null && account.max_drawdown_pct > 0 && (
            <MetricItem
              label="Max DD"
              value={`${account.max_drawdown_pct.toFixed(1)}%`}
              icon={<AlertTriangle className="w-3 h-3" />}
              valueColor="text-[#ef5350]"
            />
          )}
        </div>

        {/* Positions */}
        <div className="pt-2 border-t border-[#2a2e39]">
          <div className="flex justify-between items-center">
            <span className="text-[10px] text-zinc-600 font-mono">Positions</span>
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs text-zinc-400 tabular-nums">
                {account.active_positions} / {account.max_positions || 3}
              </span>
              <div className="w-20 h-1.5 bg-[#1e222d] rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500/60 transition-all"
                  style={{ width: `${utilizationPct}%` }}
                />
              </div>
            </div>
          </div>
          {account.total_trades != null && (
            <div className="flex justify-between items-center mt-1">
              <span className="text-[10px] text-zinc-600 font-mono">Total Trades</span>
              <span className="font-mono text-xs text-zinc-500 tabular-nums">
                {account.total_trades}
              </span>
            </div>
          )}
        </div>

        {/* Detailed Settings (Expandable) */}
        {showDetails && (
          <div className="pt-3 mt-3 border-t border-[#2a2e39] space-y-2 animate-in fade-in slide-in-from-top-2 duration-200">
            <div className="text-[10px] text-zinc-500 font-mono mb-2 flex items-center gap-1">
              <Shield className="h-3 w-3" />
              Risk Configuration
            </div>

            <div className="grid grid-cols-2 gap-2 text-[10px]">
              <DetailItem label="Risk %" value={`${account.risk_percent ?? 0.5}%`} />
              <DetailItem label="Min RR" value={`${account.min_rr_ratio ?? 2.0}:1`} />
              <DetailItem label="Max Lots" value={account.max_lot_size?.toString() ?? '10.0'} />
              <DetailItem label="Max Pos" value={account.max_positions?.toString() ?? '3'} />
            </div>

            {(account.avg_win_usd != null || account.avg_loss_usd != null) && (
              <>
                <div className="text-[10px] text-zinc-500 font-mono mb-2 mt-3">
                  Average Trade Size
                </div>
                <div className="grid grid-cols-2 gap-2 text-[10px]">
                  {account.avg_win_usd != null && (
                    <DetailItem label="Avg Win" value={`$${account.avg_win_usd.toFixed(2)}`} valueColor="text-[#26a69a]" />
                  )}
                  {account.avg_loss_usd != null && (
                    <DetailItem label="Avg Loss" value={`$${account.avg_loss_usd.toFixed(2)}`} valueColor="text-[#ef5350]" />
                  )}
                  {typeof avgRR === 'string' && avgRR !== 'N/A' && (
                    <DetailItem label="Avg RR" value={`${avgRR}:1`} />
                  )}
                </div>
              </>
            )}

            {account.created_at && (
              <div className="pt-2 mt-2 border-t border-[#2a2e39]/50">
                <div className="flex items-center justify-between text-[10px] text-zinc-600">
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    Created
                  </span>
                  <span className="font-mono">
                    {new Date(account.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Pause Status */}
        {isPaused && (
          <div className="flex items-center gap-2 p-2 rounded bg-amber-500/10 border border-amber-500/20">
            <Pause className="h-3.5 w-3.5 text-amber-500 flex-shrink-0" />
            <span className="text-[10px] text-amber-600 font-mono">
              Trading Paused
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// Helper Components
function MetricItem({
  label,
  value,
  icon,
  valueColor = 'text-zinc-300',
}: {
  label: string;
  value: string;
  icon?: React.ReactNode;
  valueColor?: string;
}) {
  return (
    <div className="flex flex-col gap-0.5 p-2 rounded bg-[#1e222d]/30">
      <span className="text-[10px] text-zinc-600 font-mono flex items-center gap-1">
        {icon}
        {label}
      </span>
      <span className={cn('font-mono text-xs font-semibold tabular-nums', valueColor)}>
        {value}
      </span>
    </div>
  );
}

function DetailItem({
  label,
  value,
  valueColor = 'text-zinc-400',
}: {
  label: string;
  value: string;
  valueColor?: string;
}) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-zinc-600 font-mono">{label}</span>
      <span className={cn('font-mono font-medium tabular-nums', valueColor)}>
        {value}
      </span>
    </div>
  );
}
