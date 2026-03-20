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
  Calendar,
  Settings,
  Trash2,
  Wifi,
  WifiOff,
  Clock,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useState } from 'react';
import { toPercentFromRatioOrPercent } from '@/domain/metrics/tradingMetrics';
import { PropFirmSection } from './PropFirmSection';

interface EnhancedAccountCardProps {
  account: AccountComparisonApi;
  className?: string;
  onDelete?: (accountName: string) => void;
}

export function EnhancedAccountCard({
  account,
  className,
  onDelete,
}: EnhancedAccountCardProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const dailyPositive = (account.daily_pnl ?? 0) >= 0;
  const winRatePct = toPercentFromRatioOrPercent(account.win_rate).toFixed(1);
  const isPaused = account.pause_trading ?? false;
  const equity = account.equity || account.balance;
  const equityDiffPct =
    account.balance > 0
      ? (((equity - account.balance) / account.balance) * 100).toFixed(2)
      : '0.00';
  const equityDiffPositive = equity >= account.balance;

  const avgRR =
    account.avg_win_usd && account.avg_loss_usd && account.avg_loss_usd > 0
      ? (account.avg_win_usd / account.avg_loss_usd).toFixed(1)
      : null;

  const handleDelete = () => {
    if (onDelete) onDelete(account.account_name);
    setShowDeleteConfirm(false);
  };

  return (
    <div
      className={cn(
        'glow-card flex flex-col overflow-hidden',
        isPaused && 'opacity-60 border-amber-500/20',
        className
      )}
    >
      {/* ── Section 1: Header ──────────────────────────────────── */}
      <div className='px-4 py-3 flex items-center justify-between border-b border-[#2a2e39]'>
        <div className='flex items-center gap-2'>
          <span className='font-mono text-sm font-bold text-[var(--to-text-primary)] tracking-wide'>
            {account.account_name}
          </span>
          {account.account_type && (
            <span
              className={cn(
                'px-2 py-0.5 text-[9px] font-mono font-bold rounded uppercase tracking-wider border',
                account.account_type === 'Eval' &&
                  'bg-amber-500/10 text-amber-400 border-amber-500/20',
                account.account_type === 'Funded' &&
                  'bg-[var(--to-long)]/10 text-[var(--to-long)] border-[var(--to-long)]/20',
                account.account_type === 'Personal' &&
                  'bg-[var(--to-surface-raised)]/30 text-[var(--to-text-dim)] border-[var(--to-border)]/20'
              )}
            >
              {account.account_type}
            </span>
          )}
          {account.provider && account.provider !== 'Personal' && (
            <span className='px-1.5 py-0.5 text-[9px] font-mono rounded bg-blue-500/10 text-blue-400 border border-blue-500/20'>
              {account.provider}
            </span>
          )}
          {isPaused && <Pause className='h-3 w-3 text-amber-500' />}
        </div>
        <div className='flex items-center gap-1.5'>
          {/* Connection dot */}
          <span className='flex items-center gap-1 text-[9px] font-mono text-[var(--to-text-dim)]'>
            <span className='relative flex h-1.5 w-1.5'>
              <span className='relative inline-flex rounded-full h-1.5 w-1.5 bg-[var(--to-surface-raised)]'></span>
            </span>
          </span>
          <Button
            variant='ghost'
            size='sm'
            className='h-6 w-6 p-0 text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]'
            onClick={() => setShowDeleteConfirm(true)}
          >
            <Trash2 className='h-3 w-3' />
          </Button>
        </div>
      </div>

      {/* ── Section 2: Balance & Equity ────────────────────────── */}
      <div className='px-4 py-3 border-b border-[#2a2e39]'>
        <div className='flex items-baseline justify-between'>
          <div className='flex items-center gap-1.5'>
            <DollarSign className='h-3 w-3 text-[var(--to-text-dim)]' />
            <span className='text-[10px] text-[var(--to-text-dim)] font-mono'>Balance</span>
          </div>
          <span className='font-mono text-lg font-bold text-zinc-50 tabular-nums tracking-tight'>
            ${account.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </span>
        </div>

        <div className='flex items-baseline justify-between mt-1.5'>
          <span className='text-[10px] text-[var(--to-text-dim)] font-mono ml-[18px]'>Equity</span>
          <div className='flex items-baseline gap-2'>
            <span className='font-mono text-xs text-[var(--to-text-dim)] tabular-nums'>
              ${equity.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </span>
            <span
              className={cn(
                'text-[10px] font-mono font-semibold tabular-nums px-1.5 py-0.5 rounded',
                equityDiffPositive
                  ? 'text-[#26a69a] bg-[#26a69a]/10'
                  : 'text-[#ef5350] bg-[#ef5350]/10'
              )}
            >
              {equityDiffPositive ? '+' : ''}{equityDiffPct}%
            </span>
          </div>
        </div>

        {account.allocated_capital_usd != null &&
          account.allocated_capital_usd !== account.balance && (
            <div className='flex items-baseline justify-between mt-1'>
              <span className='text-[10px] text-[var(--to-text-dim)] font-mono ml-[18px]'>Allocated</span>
              <span className='font-mono text-xs text-[var(--to-text-dim)] tabular-nums'>
                ${account.allocated_capital_usd.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </span>
            </div>
          )}
      </div>

      {/* ── Section 3: P&L ─────────────────────────────────────── */}
      <div className='px-4 py-3 border-b border-[#2a2e39]'>
        {/* Daily P&L row */}
        <div className='flex items-center justify-between'>
          <span className='text-[10px] text-[var(--to-text-dim)] font-mono flex items-center gap-1'>
            <Activity className='h-3 w-3' />
            Daily P&L
          </span>
          <div className='flex items-center gap-1.5'>
            {dailyPositive ? (
              <TrendingUp className='w-3 h-3 text-[#26a69a]' />
            ) : (
              <TrendingDown className='w-3 h-3 text-[#ef5350]' />
            )}
            <span
              className={cn(
                'font-mono text-sm font-bold tabular-nums',
                dailyPositive ? 'text-[#26a69a]' : 'text-[#ef5350]'
              )}
            >
              {dailyPositive ? '+' : ''}${(account.daily_pnl ?? 0).toFixed(2)}
            </span>
            <span
              className={cn(
                'text-[10px] font-mono tabular-nums opacity-80',
                dailyPositive ? 'text-[#26a69a]' : 'text-[#ef5350]'
              )}
            >
              ({dailyPositive ? '+' : ''}
              {(account.daily_pnl_pct ?? 0).toFixed(2)}%)
            </span>
          </div>
        </div>

        {/* Floating P&L */}
        {account.floating_pnl != null && account.floating_pnl !== 0 && (
          <div className='flex items-center justify-between mt-1.5'>
            <span className='text-[10px] text-[var(--to-text-dim)] font-mono ml-[16px]'>Floating</span>
            <span
              className={cn(
                'font-mono text-xs tabular-nums',
                account.floating_pnl >= 0 ? 'text-[#26a69a]' : 'text-[#ef5350]'
              )}
            >
              {account.floating_pnl >= 0 ? '+' : ''}${account.floating_pnl.toFixed(2)}
            </span>
          </div>
        )}

        {/* Realized Today */}
        {account.realized_pnl_today != null && account.realized_pnl_today !== 0 && (
          <div className='flex items-center justify-between mt-1'>
            <span className='text-[10px] text-[var(--to-text-dim)] font-mono ml-[16px]'>Realized</span>
            <span
              className={cn(
                'font-mono text-xs tabular-nums',
                account.realized_pnl_today >= 0 ? 'text-[#26a69a]' : 'text-[#ef5350]'
              )}
            >
              {account.realized_pnl_today >= 0 ? '+' : ''}${account.realized_pnl_today.toFixed(2)}
            </span>
          </div>
        )}
      </div>

      {/* ── Section 4: Performance Metrics ─────────────────────── */}
      <div className='px-4 py-3 border-b border-[#2a2e39]'>
        <div className='grid grid-cols-2 gap-2'>
          <MetricBox
            label='Win Rate'
            value={`${winRatePct}%`}
            icon={<BarChart3 className='w-3 h-3' />}
            color={parseFloat(winRatePct) >= 50 ? 'green' : 'red'}
          />
          <MetricBox
            label='Profit Factor'
            value={account.profit_factor != null ? account.profit_factor.toFixed(2) : 'N/A'}
            icon={<Target className='w-3 h-3' />}
            color={
              account.profit_factor != null
                ? account.profit_factor >= 1.5
                  ? 'green'
                  : account.profit_factor >= 1
                  ? 'neutral'
                  : 'red'
                : 'neutral'
            }
          />
          <MetricBox
            label='Sharpe'
            value={account.sharpe_ratio != null ? account.sharpe_ratio.toFixed(2) : 'N/A'}
            icon={<Activity className='w-3 h-3' />}
            color='neutral'
          />
          <MetricBox
            label='Max DD'
            value={
              account.max_drawdown_pct != null && account.max_drawdown_pct > 0
                ? `${account.max_drawdown_pct.toFixed(1)}%`
                : '0.0%'
            }
            icon={<AlertTriangle className='w-3 h-3' />}
            color={
              account.max_drawdown_pct != null && account.max_drawdown_pct > 5
                ? 'red'
                : account.max_drawdown_pct != null && account.max_drawdown_pct > 2
                ? 'amber'
                : 'neutral'
            }
          />
        </div>
      </div>

      {/* ── Section 5: Trading Stats ───────────────────────────── */}
      <div className='px-4 py-3 border-b border-[#2a2e39]'>
        <div className='flex items-center justify-between'>
          <div className='flex items-center gap-4'>
            <div className='flex flex-col'>
              <span className='text-[9px] text-[var(--to-text-dim)] font-mono'>Positions</span>
              <span className='font-mono text-xs text-[var(--to-text-secondary)] tabular-nums'>
                {account.active_positions ?? 0} / {account.max_positions || 3}
              </span>
            </div>
            <div className='flex flex-col'>
              <span className='text-[9px] text-[var(--to-text-dim)] font-mono'>Total Trades</span>
              <span className='font-mono text-xs text-[var(--to-text-secondary)] tabular-nums'>
                {account.total_trades ?? 0}
              </span>
            </div>
            {account.winning_trades != null && (
              <div className='flex flex-col'>
                <span className='text-[9px] text-[var(--to-text-dim)] font-mono'>W / L</span>
                <span className='font-mono text-xs tabular-nums'>
                  <span className='text-[#26a69a]'>{account.winning_trades}</span>
                  <span className='text-[var(--to-text-dim)]'> / </span>
                  <span className='text-[#ef5350]'>{account.losing_trades ?? 0}</span>
                </span>
              </div>
            )}
            {avgRR && (
              <div className='flex flex-col'>
                <span className='text-[9px] text-[var(--to-text-dim)] font-mono'>Avg RR</span>
                <span className='font-mono text-xs text-[var(--to-text-secondary)] tabular-nums'>
                  {avgRR}:1
                </span>
              </div>
            )}
          </div>
          {/* Position utilization bar */}
          <div className='w-16 h-1.5 bg-[#1e222d] rounded-full overflow-hidden'>
            <div
              className='h-full bg-emerald-500/60 transition-all'
              style={{
                width: `${
                  account.max_positions && account.active_positions
                    ? Math.min(
                        (account.active_positions / account.max_positions) * 100,
                        100
                      )
                    : 0
                }%`,
              }}
            />
          </div>
        </div>

        {/* Avg Win/Loss */}
        {(account.avg_win_usd != null || account.avg_loss_usd != null) && (
          <div className='flex items-center gap-4 mt-2 pt-2 border-t border-[#2a2e39]/50'>
            {account.avg_win_usd != null && (
              <div className='flex items-center gap-1'>
                <span className='text-[9px] text-[var(--to-text-dim)] font-mono'>Avg Win</span>
                <span className='font-mono text-[10px] text-[#26a69a] tabular-nums'>
                  ${account.avg_win_usd.toFixed(0)}
                </span>
              </div>
            )}
            {account.avg_loss_usd != null && (
              <div className='flex items-center gap-1'>
                <span className='text-[9px] text-[var(--to-text-dim)] font-mono'>Avg Loss</span>
                <span className='font-mono text-[10px] text-[#ef5350] tabular-nums'>
                  ${account.avg_loss_usd.toFixed(0)}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Section 6: Risk Config ─────────────────────────────── */}
      <div className='px-4 py-2.5 border-b border-[#2a2e39]'>
        <div className='flex items-center gap-3'>
          <Shield className='h-3 w-3 text-[var(--to-text-dim)]' />
          <div className='flex items-center gap-3 text-[9px] font-mono text-[var(--to-text-dim)]'>
            <span>Risk: <span className='text-[var(--to-text-dim)]'>{account.risk_percent ?? 0.5}%</span></span>
            <span>Min RR: <span className='text-[var(--to-text-dim)]'>{account.min_rr_ratio ?? 2.0}:1</span></span>
            <span>Max Lots: <span className='text-[var(--to-text-dim)]'>{account.max_lot_size ?? 10.0}</span></span>
          </div>
        </div>
      </div>

      {/* ── Section 7: Prop Firm (Conditional) ──────────────────── */}
      <PropFirmSection accountName={account.account_name} serverName={account.server_name} />

      {/* ── Section 8: Footer (Last Sync + Strategy) ────────────── */}
      <div className='px-4 py-2 flex items-center justify-between'>
        {account.strategy_type && (
          <span className='font-mono text-[9px] px-2 py-0.5 rounded bg-[#2a2e39] text-[var(--to-text-dim)]'>
            {account.strategy_type}
          </span>
        )}
        {account.last_sync_time && (
          <span suppressHydrationWarning className='flex items-center gap-1 text-[9px] text-[var(--to-text-dim)] font-mono'>
            <Clock className='h-2.5 w-2.5' />
            {new Date(account.last_sync_time).toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Pause Banner */}
      {isPaused && (
        <div className='mx-4 mb-3 flex items-center gap-2 p-2 rounded bg-amber-500/10 border border-amber-500/20'>
          <Pause className='h-3.5 w-3.5 text-amber-500 flex-shrink-0' />
          <span className='text-[10px] text-amber-600 font-mono'>Trading Paused</span>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      {showDeleteConfirm && (
        <div className='fixed inset-0 bg-black/50 flex items-center justify-center z-50'>
          <div className='glow-card p-6 max-w-md w-full mx-4'>
            <div className='flex items-center gap-3 mb-4'>
              <AlertTriangle className='h-5 w-5 text-[var(--to-short)]' />
              <h3 className='text-base font-semibold text-[var(--to-text-primary)]'>
                Delete Account
              </h3>
            </div>
            <p className='text-sm text-[var(--to-text-dim)] mb-6'>
              Are you sure you want to delete{' '}
              <span className='font-mono text-[var(--to-text-primary)]'>
                {account.account_name}
              </span>
              ? This action cannot be undone.
            </p>
            <div className='flex gap-3 justify-end'>
              <Button
                variant='outline'
                size='sm'
                className='border-[#2a2e39] text-[var(--to-text-dim)] hover:bg-[#2a2e39] hover:text-[var(--to-text-primary)]'
                onClick={() => setShowDeleteConfirm(false)}
              >
                Cancel
              </Button>
              <Button
                size='sm'
                className='bg-red-500 text-white hover:bg-red-600'
                onClick={handleDelete}
              >
                <Trash2 className='h-3.5 w-3.5 mr-1.5' />
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Metric Box Component ──────────────────────────────────────────
function MetricBox({
  label,
  value,
  icon,
  color = 'neutral',
}: {
  label: string;
  value: string;
  icon?: React.ReactNode;
  color?: 'green' | 'red' | 'amber' | 'neutral';
}) {
  const colorClasses = {
    green: 'text-[#26a69a] border-[#26a69a]/15 bg-[#26a69a]/5',
    red: 'text-[#ef5350] border-[#ef5350]/15 bg-[#ef5350]/5',
    amber: 'text-amber-400 border-amber-500/15 bg-amber-500/5',
    neutral: 'text-[var(--to-text-secondary)] border-[#2a2e39] bg-[#1e222d]/30',
  };

  return (
    <div
      className={cn(
        'flex flex-col gap-0.5 p-2 rounded-lg border',
        colorClasses[color]
      )}
    >
      <span className='text-[9px] text-[var(--to-text-dim)] font-mono flex items-center gap-1'>
        {icon}
        {label}
      </span>
      <span className='font-mono text-xs font-bold tabular-nums'>
        {value}
      </span>
    </div>
  );
}
