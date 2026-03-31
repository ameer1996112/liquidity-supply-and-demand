'use client';

import { CheckCircle2, XCircle, AlertTriangle, Trophy } from 'lucide-react';
import { cn } from '@/lib/utils';

type CheckStatus = 'pass' | 'warn' | 'fail' | 'na';

interface ReadinessItem {
  label: string;
  detail: string;
  status: CheckStatus;
}

interface PayoutReadinessProps {
  profitTargetPct: number;
  currentProfitPct: number;
  minTradingDays: number | undefined;
  tradingDaysCompleted: number;
  dailyBreach: boolean;
  drawdownBreach: boolean;
  consistencyOk: boolean;
  consistencyPct: number;
  consistencyLimitPct?: number;
}

function StatusIcon({ status }: { status: CheckStatus }) {
  if (status === 'pass') return <CheckCircle2 className='h-4 w-4 text-emerald-400 shrink-0' />;
  if (status === 'warn') return <AlertTriangle className='h-4 w-4 text-amber-400 shrink-0' />;
  if (status === 'fail') return <XCircle className='h-4 w-4 text-red-500 shrink-0' />;
  return <span className='h-4 w-4 shrink-0 inline-flex items-center justify-center text-[var(--to-text-dim)] text-xs'>—</span>;
}

export function PayoutReadiness({
  profitTargetPct,
  currentProfitPct,
  minTradingDays,
  tradingDaysCompleted,
  dailyBreach,
  drawdownBreach,
  consistencyOk,
  consistencyPct,
  consistencyLimitPct = 0,
}: PayoutReadinessProps) {
  const profitReached = profitTargetPct > 0 && currentProfitPct >= profitTargetPct;
  const profitClose = profitTargetPct > 0 && currentProfitPct >= profitTargetPct * 0.7;

  const daysMetStatus: CheckStatus =
    minTradingDays == null
      ? 'na'
      : tradingDaysCompleted >= minTradingDays
      ? 'pass'
      : tradingDaysCompleted >= minTradingDays * 0.5
      ? 'warn'
      : 'fail';

  const profitStatus: CheckStatus =
    profitTargetPct <= 0
      ? 'na'
      : profitReached
      ? 'pass'
      : profitClose
      ? 'warn'
      : 'fail';

  const items: ReadinessItem[] = [
    {
      label: 'Profit Target',
      detail:
        profitTargetPct > 0
          ? `${currentProfitPct.toFixed(2)}% / ${profitTargetPct}%`
          : 'N/A',
      status: profitStatus,
    },
    {
      label: 'Min Trading Days',
      detail:
        minTradingDays != null
          ? `${tradingDaysCompleted} / ${minTradingDays} days`
          : 'N/A',
      status: daysMetStatus,
    },
    {
      label: 'No Daily Loss Breach',
      detail: dailyBreach ? 'Breach detected — challenge may be void' : 'Clean',
      status: dailyBreach ? 'fail' : 'pass',
    },
    {
      label: 'No Max Drawdown Breach',
      detail: drawdownBreach ? 'Breach detected — challenge may be void' : 'Clean',
      status: drawdownBreach ? 'fail' : 'pass',
    },
    {
      label: 'Consistency Rule',
      detail:
        consistencyLimitPct > 0
          ? `Best day ${consistencyPct.toFixed(1)}% / limit ${consistencyLimitPct}%`
          : 'N/A',
      status:
        consistencyLimitPct <= 0
          ? 'na'
          : consistencyOk
          ? 'pass'
          : consistencyPct >= consistencyLimitPct * 0.85
          ? 'warn'
          : 'fail',
    },
  ];

  const passCount = items.filter((i) => i.status === 'pass').length;
  const failCount = items.filter((i) => i.status === 'fail').length;
  const activeItems = items.filter((i) => i.status !== 'na');

  const overallReady = failCount === 0 && passCount === activeItems.length;
  const overallClose = failCount === 0 && passCount >= activeItems.length - 1;

  return (
    <div className='glass-panel p-6'>
      <div className='flex items-center justify-between mb-4'>
        <h3 className='text-[13px] font-bold text-[var(--to-text-dim)] uppercase tracking-widest font-mono flex items-center gap-2'>
          <Trophy className='h-4 w-4 text-amber-400' />
          Payout Readiness
        </h3>
        <span
          className={cn(
            'text-[11px] font-bold font-mono px-2.5 py-1 rounded-md border',
            overallReady
              ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10'
              : overallClose
              ? 'text-amber-400 border-amber-500/30 bg-amber-500/10'
              : 'text-red-400 border-red-500/30 bg-red-500/10'
          )}
        >
          {overallReady ? 'READY' : overallClose ? 'ALMOST' : 'NOT YET'}
        </span>
      </div>

      <div className='space-y-2'>
        {items.map((item) => (
          <div
            key={item.label}
            className={cn(
              'flex items-center gap-3 px-3 py-2.5 rounded-lg border',
              item.status === 'fail'
                ? 'border-red-500/25 bg-red-500/5'
                : item.status === 'warn'
                ? 'border-amber-500/20 bg-amber-500/5'
                : item.status === 'pass'
                ? 'border-emerald-500/15 bg-emerald-500/5'
                : 'border-[#2a2e39] bg-[#1e222d]/20 opacity-50'
            )}
          >
            <StatusIcon status={item.status} />
            <div className='flex-1 min-w-0'>
              <div className='text-xs font-mono text-[var(--to-text-secondary)]'>{item.label}</div>
              <div
                className={cn(
                  'text-[10px] font-mono mt-0.5',
                  item.status === 'fail'
                    ? 'text-red-400'
                    : item.status === 'warn'
                    ? 'text-amber-400'
                    : item.status === 'pass'
                    ? 'text-emerald-400/80'
                    : 'text-[var(--to-text-dim)]'
                )}
              >
                {item.detail}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
