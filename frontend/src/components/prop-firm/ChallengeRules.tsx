'use client';

import {
  Shield,
  AlertTriangle,
  TrendingDown,
  Calendar,
  Target,
  Scale,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface ChallengeRule {
  name: string;
  limit: string;
  icon: React.ReactNode;
  applies: boolean;
  status?: 'ok' | 'warning' | 'breach';
  currentValue?: string;
  /** 0-100 fill % for the mini progress bar */
  progressPct?: number;
  /** True for "higher is better" rules like profit target */
  isInverse?: boolean;
}

interface ChallengeRulesProps {
  dailyLimitPct: number;
  maxDrawdownPct: number;
  consistencyLimitPct?: number;
  profitTargetPct: number;
  minTradingDays?: number;
  maxTradingDays?: number;
  daysRemaining?: number;
  /** Current daily drawdown pct to determine status */
  currentDailyPct?: number;
  /** Current trailing drawdown pct to determine status */
  currentTrailingPct?: number;
  /** Current consistency pct to determine status */
  currentConsistencyPct?: number;
  /** Current profit pct to determine status */
  currentProfitPct?: number;
}

function getRuleStatus(
  current: number | undefined,
  limit: number,
  isInverse = false
): 'ok' | 'warning' | 'breach' {
  if (current == null) return 'ok';
  if (isInverse) {
    // For profit target: higher is better
    if (current >= limit) return 'ok';
    if (current >= limit * 0.5) return 'warning';
    return 'ok'; // Not a breach to be under profit target
  }
  // For drawdown: lower is better
  if (current >= limit) return 'breach';
  if (current >= limit * 0.8) return 'warning';
  return 'ok';
}

export function ChallengeRules({
  dailyLimitPct,
  maxDrawdownPct,
  consistencyLimitPct = 0,
  profitTargetPct,
  minTradingDays,
  maxTradingDays,
  daysRemaining,
  currentDailyPct,
  currentTrailingPct,
  currentConsistencyPct,
  currentProfitPct,
}: ChallengeRulesProps) {
  const rules: ChallengeRule[] = [
    {
      name: 'Daily Loss Limit',
      limit: `${dailyLimitPct}%`,
      icon: <TrendingDown className='h-3.5 w-3.5' />,
      applies: dailyLimitPct > 0,
      status: getRuleStatus(currentDailyPct, dailyLimitPct),
      currentValue:
        currentDailyPct != null ? `${currentDailyPct.toFixed(2)}%` : undefined,
      progressPct:
        currentDailyPct != null && dailyLimitPct > 0
          ? (currentDailyPct / dailyLimitPct) * 100
          : undefined,
    },
    {
      name: 'Max Drawdown',
      limit: `${maxDrawdownPct}%`,
      icon: <AlertTriangle className='h-3.5 w-3.5' />,
      applies: maxDrawdownPct > 0,
      status: getRuleStatus(currentTrailingPct, maxDrawdownPct),
      currentValue:
        currentTrailingPct != null
          ? `${currentTrailingPct.toFixed(2)}%`
          : undefined,
      progressPct:
        currentTrailingPct != null && maxDrawdownPct > 0
          ? (currentTrailingPct / maxDrawdownPct) * 100
          : undefined,
    },
    {
      name: 'Consistency Rule',
      limit: `${consistencyLimitPct}%`,
      icon: <Scale className='h-3.5 w-3.5' />,
      applies: consistencyLimitPct > 0,
      status: getRuleStatus(currentConsistencyPct, consistencyLimitPct),
      currentValue:
        currentConsistencyPct != null
          ? `${currentConsistencyPct.toFixed(2)}%`
          : undefined,
      progressPct:
        currentConsistencyPct != null && consistencyLimitPct > 0
          ? (currentConsistencyPct / consistencyLimitPct) * 100
          : undefined,
    },
    {
      name: 'Profit Target',
      limit: `${profitTargetPct}%`,
      icon: <Target className='h-3.5 w-3.5' />,
      applies: profitTargetPct > 0,
      status: getRuleStatus(currentProfitPct, profitTargetPct, true),
      currentValue:
        currentProfitPct != null
          ? `${currentProfitPct.toFixed(2)}%`
          : undefined,
      isInverse: true,
      progressPct:
        currentProfitPct != null && profitTargetPct > 0
          ? (currentProfitPct / profitTargetPct) * 100
          : undefined,
    },
    {
      name: 'Min Trading Days',
      limit: minTradingDays != null ? `${minTradingDays} days` : '',
      icon: <Calendar className='h-3.5 w-3.5' />,
      applies: minTradingDays != null && minTradingDays > 0,
    },
    {
      name: 'Time Limit',
      limit:
        maxTradingDays != null
          ? `${maxTradingDays} days`
          : daysRemaining != null
          ? `${daysRemaining} remaining`
          : '',
      icon: <Calendar className='h-3.5 w-3.5' />,
      applies:
        (maxTradingDays != null && maxTradingDays > 0) ||
        (daysRemaining != null && daysRemaining > 0),
    },
  ];

  const applicable = rules.filter((r) => r.applies);
  const notApplicable = rules.filter(
    (r) => !r.applies && ['Consistency Rule', 'Profit Target'].includes(r.name)
  );

  return (
    <div className='glow-card p-6'>
      <h3 className='text-[13px] font-bold text-[var(--to-text-dim)] uppercase tracking-widest font-mono mb-4 flex items-center gap-2'>
        <Shield className='h-4 w-4 text-blue-400' />
        Challenge Rules
      </h3>

      <div className='space-y-2'>
        {applicable.map((rule) => (
          <div
            key={rule.name}
            className={cn(
              'flex items-center justify-between px-3 py-2 rounded-lg border',
              rule.status === 'breach'
                ? 'border-[#ef5350]/30 bg-[#ef5350]/5'
                : rule.status === 'warning'
                ? 'border-amber-500/20 bg-amber-500/5'
                : 'border-[#2a2e39] bg-[#1e222d]/30'
            )}
          >
            <div className='flex items-center gap-2'>
              <span
                className={cn(
                  rule.status === 'breach'
                    ? 'text-[#ef5350]'
                    : rule.status === 'warning'
                    ? 'text-amber-400'
                    : 'text-[var(--to-text-dim)]'
                )}
              >
                {rule.icon}
              </span>
              <span className='font-mono text-xs text-[var(--to-text-secondary)]'>
                {rule.name}
              </span>
            </div>
            <div className='flex items-center gap-3'>
              {rule.progressPct != null && (
                <div className='w-20 h-1.5 rounded-full bg-[#1e222d] overflow-hidden'>
                  <div
                    className={cn(
                      'h-full rounded-full transition-all duration-500',
                      rule.status === 'breach'
                        ? 'bg-[#ef5350]'
                        : rule.status === 'warning'
                        ? 'bg-amber-400'
                        : rule.isInverse
                        ? 'bg-emerald-400'
                        : 'bg-[#26a69a]'
                    )}
                    style={{ width: `${Math.min(rule.progressPct, 100)}%` }}
                  />
                </div>
              )}
              {rule.currentValue && (
                <span
                  className={cn(
                    'font-mono text-[10px] tabular-nums',
                    rule.status === 'breach'
                      ? 'text-[#ef5350]'
                      : rule.status === 'warning'
                      ? 'text-amber-400'
                      : 'text-[var(--to-text-dim)]'
                  )}
                >
                  {rule.currentValue}
                </span>
              )}
              <span className='font-mono text-[10px] text-[var(--to-text-dim)]'>/</span>
              <span className='font-mono text-xs text-[var(--to-text-primary)] tabular-nums'>
                {rule.limit}
              </span>
              {rule.status && (
                <span className='ml-1'>
                  {rule.status === 'ok' ? (
                    <CheckCircle2 className='h-3 w-3 text-[#26a69a]' />
                  ) : rule.status === 'breach' ? (
                    <XCircle className='h-3 w-3 text-[#ef5350]' />
                  ) : (
                    <AlertTriangle className='h-3 w-3 text-amber-400' />
                  )}
                </span>
              )}
            </div>
          </div>
        ))}

        {/* Show N/A rules in muted style */}
        {notApplicable.length > 0 && (
          <div className='flex items-center gap-2 px-3 py-2 mt-1'>
            <span className='text-[9px] font-mono text-[var(--to-text-dim)] uppercase tracking-wider'>
              Not applicable:
            </span>
            {notApplicable.map((rule) => (
              <span
                key={rule.name}
                className='text-[10px] font-mono text-[var(--to-text-dim)] px-2 py-0.5 rounded bg-[#1e222d] border border-[#2a2e39]/50'
              >
                {rule.name}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
