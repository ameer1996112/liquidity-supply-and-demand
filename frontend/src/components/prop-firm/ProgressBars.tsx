import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import { FirmInfo } from '@/hooks/usePropFirmChallenge';

export function ProgressBars({ metrics, limits }: { metrics: any; limits: FirmInfo }) {
  if (!metrics || !limits) return null;

  const dailyPct = metrics.drawdown?.daily_pct || 0;
  const maxDailyLimit = limits.max_daily_loss_pct || 5;
  const totalPct = metrics.drawdown?.trailing_pct || 0;
  const maxTotalLimit = limits.max_drawdown_pct || 10;
  const profitTarget = limits.profit_target_pct || null;
  const pnlPct = metrics.daily_pnl?.total ? ((metrics.daily_pnl.total / metrics.equity?.daily_start_balance) * 100) : 0;

  // Calculate percentages safely relative to their caps for the progress bar width (max 100%)
  const dailyProgress = Math.min((dailyPct / maxDailyLimit) * 100, 100);
  const totalProgress = Math.min((totalPct / maxTotalLimit) * 100, 100);

  // Profit progress: PnL / ProfitTarget * 100 (if profit target exists)
  // If no profit target (e.g. funded phase), we might not show it or show infinite.
  const profitProgress = profitTarget ? Math.min(Math.max((pnlPct / profitTarget) * 100, 0), 100) : 0;

  const getColorClass = (val: number, limit: number) => {
    const ratio = val / limit;
    if (ratio >= 1.0) return 'bg-red-500';
    if (ratio >= 0.8) return 'bg-amber-500';
    return 'bg-emerald-500';
  };

  return (
    <div className="space-y-3 pb-2">
      {/* Daily Drawdown */}
      <div className="space-y-1">
        <div className="flex justify-between items-end">
          <span className="text-[10px] font-mono text-[var(--to-text-dim)]">Daily Loss</span>
          <span className="text-[10px] font-mono font-medium text-[var(--to-text-secondary)]">
            {dailyPct.toFixed(2)}% <span className="text-[var(--to-text-dim)]">/ {maxDailyLimit}%</span>
          </span>
        </div>
        <div className="h-1.5 w-full bg-[#2a2e39] rounded-full overflow-hidden">
          <div 
            className={cn("h-full transition-all duration-500", getColorClass(dailyPct, maxDailyLimit))}
            style={{ width: `${dailyProgress}%` }}
          />
        </div>
      </div>

      {/* Total Drawdown */}
      <div className="space-y-1">
        <div className="flex justify-between items-end">
          <span className="text-[10px] font-mono text-[var(--to-text-dim)]">Max DD</span>
          <span className="text-[10px] font-mono font-medium text-[var(--to-text-secondary)]">
             {totalPct.toFixed(2)}% <span className="text-[var(--to-text-dim)]">/ {maxTotalLimit}%</span>
          </span>
        </div>
        <div className="h-1.5 w-full bg-[#2a2e39] rounded-full overflow-hidden">
          <div 
            className={cn("h-full transition-all duration-500", getColorClass(totalPct, maxTotalLimit))}
            style={{ width: `${totalProgress}%` }}
          />
        </div>
      </div>

      {/* Profit Target (Only for Eval Phases) */}
      {profitTarget && profitTarget > 0 && (
        <div className="space-y-1 mt-3">
          <div className="flex justify-between items-end">
            <span className="text-[10px] font-mono text-[var(--to-text-dim)]">Target</span>
            <span className="text-[10px] font-mono font-medium text-[var(--to-long)]">
              {pnlPct > 0 ? pnlPct.toFixed(2) : 0}% <span className="text-[var(--to-text-dim)]">/ {profitTarget}%</span>
            </span>
          </div>
          <div className="h-1.5 w-full bg-[#2a2e39] rounded-full overflow-hidden">
            <div 
              className="h-full transition-all duration-500 bg-emerald-400"
              style={{ width: `${profitProgress}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
