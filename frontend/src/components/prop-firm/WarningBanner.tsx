import { AlertTriangle } from 'lucide-react';
import { FirmInfo } from '@/hooks/usePropFirmChallenge';

export function WarningBanner({ metrics, limits }: { metrics: any; limits: FirmInfo }) {
  if (!metrics || !limits) return null;

  const threshold = 0.8; // 80%

  const dailyPct = metrics.drawdown?.daily_pct || 0;
  const maxDailyLimit = limits.max_daily_loss_pct || 5;
  const totalPct = metrics.drawdown?.trailing_pct || 0;
  const maxTotalLimit = limits.max_drawdown_pct || 10;

  const isDailyWarning = (dailyPct / maxDailyLimit) >= threshold;
  const isTotalWarning = (totalPct / maxTotalLimit) >= threshold;
  const isDrawdownBreach = metrics.status?.drawdown_breach || metrics.status?.daily_loss_breach;

  if (isDrawdownBreach) {
    return (
      <div className="flex items-center gap-2 p-2 rounded bg-red-500/10 border border-red-500/20 mb-3 text-red-500">
        <AlertTriangle className="h-4 w-4 shrink-0" />
        <span className="text-[10px] font-mono font-bold">ACCOUNT BREACH DETECTED</span>
      </div>
    );
  }

  if (isDailyWarning || isTotalWarning) {
    return (
      <div className="flex items-center gap-2 p-2 rounded bg-amber-500/10 border border-amber-500/20 mb-3 text-amber-500">
        <AlertTriangle className="h-4 w-4 shrink-0" />
        <span className="text-[10px] font-mono">
          Warning: Approaching {isDailyWarning ? 'Daily' : 'Total'} Drawdown Limit ({isDailyWarning ? dailyPct : totalPct}% / {isDailyWarning ? maxDailyLimit : maxTotalLimit}%)
        </span>
      </div>
    );
  }

  return null;
}
