'use client';

import { cn } from '@/lib/utils';
import { Radio, Wifi, WifiOff, TrendingUp, TrendingDown, Shield } from 'lucide-react';
import type { DashboardSummary } from '@/types/trading';
import { formatCurrency, formatPercent } from '@/lib/formatters';
import { useRiskStatus } from '@/hooks/useRiskStatus';

interface AggregateBarProps {
  summary: DashboardSummary | undefined;
  isLoading: boolean;
  isConnected: boolean;
}

export function AggregateBar({ summary, isLoading, isConnected }: AggregateBarProps) {
  const { data: risk } = useRiskStatus();
  const totalPnl = summary?.total_pnl_all_time ?? 0;
  const pnlPositive = totalPnl >= 0;
  const connectedCount = summary?.accounts.filter(a => a.connection_status === 'connected').length ?? 0;
  const totalAccounts = summary?.accounts.length ?? 0;
  const hasDisconnected = connectedCount < totalAccounts;

  return (
    <div
      className={cn(
        'flex shrink-0 items-center justify-between gap-4 px-4 py-2.5',
        'border-b border-[var(--to-border)] bg-[var(--to-surface)] sticky top-0 z-10',
        'text-xs font-mono'
      )}
    >
      {/* Left: Bot status */}
      <div className='flex items-center gap-3'>
        <span className='flex items-center gap-1.5'>
          {isConnected ? (
            <Wifi className='h-3 w-3 text-[var(--to-long)]' />
          ) : (
            <WifiOff className='h-3 w-3 text-[var(--to-short)]' />
          )}
          <span
            className={cn(
              'font-bold uppercase tracking-widest text-[10px]',
              isConnected ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]'
            )}
          >
            {isConnected ? 'LIVE' : 'OFFLINE'}
          </span>
        </span>

        <span className='text-[var(--to-border)]'>|</span>

        {/* Total PnL today */}
        <span className='flex items-center gap-1'>
          {pnlPositive ? (
            <TrendingUp className='h-3 w-3 text-[var(--to-long)]' />
          ) : (
            <TrendingDown className='h-3 w-3 text-[var(--to-short)]' />
          )}
          <span className='text-[var(--to-text-dim)]'>Total PnL</span>
          <span
            className={cn(
              'font-bold tabular-nums',
              isLoading ? 'text-[var(--to-text-dim)]' : pnlPositive ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]'
            )}
          >
            {isLoading ? '...' : formatCurrency(totalPnl, { signed: true })}
          </span>
        </span>
      </div>

      {/* Center: Key metrics */}
      <div className='flex items-center gap-4'>
        <AggMetric
          label='Open'
          value={isLoading ? '...' : String(summary?.total_active_positions ?? 0)}
        />
        <AggMetric
          label='Win Rate'
          value={isLoading ? '...' : formatPercent(summary?.total_win_rate ?? 0)}
        />
        <AggMetric
          label='Max DD'
          value={isLoading ? '...' : formatPercent(summary?.max_drawdown_pct ?? 0)}
          danger={(summary?.max_drawdown_pct ?? 0) > 5}
        />

        <span className='text-[var(--to-border)]'>|</span>

        <RiskModeChip risk={risk} />
      </div>

      {/* Right: Accounts health */}
      <div className='flex items-center gap-1.5'>
        <Radio className='h-3 w-3 text-[var(--to-text-dim)]' />
        <span className='text-[var(--to-text-dim)]'>Accounts</span>
        <span
          className={cn(
            'font-bold',
            hasDisconnected ? 'text-amber-400' : 'text-[var(--to-long)]'
          )}
        >
          {connectedCount}/{totalAccounts}
        </span>
        <span
          className={cn(
            'h-1.5 w-1.5 rounded-full',
            hasDisconnected ? 'bg-amber-400' : 'bg-[var(--to-long)]'
          )}
        />
      </div>
    </div>
  );
}

function AggMetric({
  label,
  value,
  danger = false,
}: {
  label: string;
  value: string;
  danger?: boolean;
}) {
  return (
    <span className='flex items-center gap-1'>
      <span className='text-[var(--to-text-dim)]'>{label}</span>
      <span
        className={cn(
          'tabular-nums font-semibold',
          danger ? 'text-[var(--to-short)]' : 'text-[var(--to-text-secondary)]'
        )}
      >
        {value}
      </span>
    </span>
  );
}

function getRiskModeStyle(label: string) {
  const l = label.toLowerCase();
  if (l.includes('kill') || l.includes('severe'))
    return { color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30' };
  if (l.includes('survival') || l.includes('moderate'))
    return { color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/30' };
  if (l.includes('building') || l.includes('buffer'))
    return { color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/30' };
  if (l.includes('aggressive') || l.includes('kill zone'))
    return { color: 'text-purple-400', bg: 'bg-purple-500/10', border: 'border-purple-500/30' };
  return { color: 'text-[var(--to-long)]', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' };
}

function RiskModeChip({ risk }: { risk: ReturnType<typeof import('@/hooks/useRiskStatus').useRiskStatus>['data'] }) {
  if (!risk) return null;

  const style = getRiskModeStyle(risk.risk_label);
  const shortLabel = risk.risk_label
    .replace('Drawdown Scale (severe): ', '')
    .replace('Drawdown Scale (moderate): ', '')
    .replace(' (Evaluation: no scale-up)', '')
    .split(':')[0];

  return (
    <span className='flex items-center gap-1.5'>
      <Shield className={cn('h-3 w-3', style.color)} />
      <span className='text-[var(--to-text-dim)]'>Risk</span>
      <span className={cn('tabular-nums font-bold', style.color)}>
        {risk.effective_risk_pct}%
      </span>
      <span
        className={cn(
          'rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider border',
          style.bg, style.border, style.color
        )}
      >
        {shortLabel}
      </span>
    </span>
  );
}
