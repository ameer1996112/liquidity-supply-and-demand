"use client";

import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  TrendingUp,
  Target,
  BarChart3,
  Calendar,
} from "lucide-react";
import type { Trade } from "./BacktestChart";

export interface BacktestStats {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  profit_factor: number;
  avg_win: number;
  avg_loss: number;
  largest_win: number;
  largest_loss: number;
  avg_trade_duration?: string;
  exposure_time?: number;
}

export interface BacktestPerformanceTabProps {
  trades: Trade[];
  stats: BacktestStats;
  initialCash: number;
  finalEquity: number;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (mins < 60) return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
  const hours = Math.floor(mins / 60);
  const remainMins = mins % 60;
  if (hours < 24) return `${hours}h ${remainMins}m`;
  const days = Math.floor(hours / 24);
  const remainHours = hours % 24;
  return `${days}d ${remainHours}h`;
}

function computeSortinoRatio(trades: Trade[]): number {
  if (trades.length === 0) return 0;
  const returns = trades.map((t) => t.return_pct / 100);
  const meanReturn = returns.reduce((a, b) => a + b, 0) / returns.length;
  const negativeReturns = returns.filter((r) => r < 0);
  if (negativeReturns.length === 0) return meanReturn > 0 ? 999 : 0;
  const downsideVariance =
    negativeReturns.reduce((a, b) => a + b * b, 0) / negativeReturns.length;
  const downsideDev = Math.sqrt(downsideVariance);
  return downsideDev === 0 ? 0 : meanReturn / downsideDev;
}

function computeConsecutiveStreaks(trades: Trade[]): {
  maxWinStreak: number;
  maxLossStreak: number;
} {
  let maxWin = 0;
  let maxLoss = 0;
  let currentWin = 0;
  let currentLoss = 0;

  for (const t of trades) {
    if (t.pnl > 0) {
      currentWin++;
      currentLoss = 0;
      maxWin = Math.max(maxWin, currentWin);
    } else if (t.pnl < 0) {
      currentLoss++;
      currentWin = 0;
      maxLoss = Math.max(maxLoss, currentLoss);
    } else {
      currentWin = 0;
      currentLoss = 0;
    }
  }

  return { maxWinStreak: maxWin, maxLossStreak: maxLoss };
}

function computeAvgDuration(trades: Trade[]): string {
  if (trades.length === 0) return "0m";
  const totalSeconds = trades.reduce(
    (sum, t) => sum + (t.exit_time - t.entry_time),
    0
  );
  return formatDuration(totalSeconds / trades.length);
}

function computeBestWorstMonths(
  trades: Trade[]
): { best: { month: string; pnl: number }; worst: { month: string; pnl: number } } {
  const byMonth: Record<string, number> = {};

  for (const t of trades) {
    const date = new Date(t.entry_time * 1000);
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
    byMonth[key] = (byMonth[key] || 0) + t.pnl;
  }

  const entries = Object.entries(byMonth);
  if (entries.length === 0) {
    return { best: { month: "—", pnl: 0 }, worst: { month: "—", pnl: 0 } };
  }

  const [bestKey, bestPnl] = entries.reduce((a, b) =>
    a[1] >= b[1] ? a : b
  );
  const [worstKey, worstPnl] = entries.reduce((a, b) =>
    a[1] <= b[1] ? a : b
  );

  const formatMonth = (k: string) => {
    const [y, m] = k.split("-");
    const date = new Date(parseInt(y), parseInt(m) - 1);
    return date.toLocaleString("default", { month: "short", year: "2-digit" });
  };

  return {
    best: { month: formatMonth(bestKey), pnl: bestPnl },
    worst: { month: formatMonth(worstKey), pnl: worstPnl },
  };
}

function StatRow({
  label,
  value,
  variant = "neutral",
}: {
  label: string;
  value: string | number;
  variant?: "positive" | "negative" | "neutral";
}) {
  const colorClass =
    variant === "positive" ? "text-green-500" : variant === "negative" ? "text-red-500" : "";

  return (
    <div className="flex justify-between items-center py-2 border-b border-gray-800 last:border-0">
      <span className="text-gray-400 text-sm">{label}</span>
      <span className={`font-medium text-sm ${colorClass}`}>{value}</span>
    </div>
  );
}

export function BacktestPerformanceTab({
  trades,
  stats,
  initialCash,
  finalEquity,
}: BacktestPerformanceTabProps) {
  const netProfit = finalEquity - initialCash;
  const sortinoRatio = useMemo(() => computeSortinoRatio(trades), [trades]);
  const { maxWinStreak, maxLossStreak } = useMemo(
    () => computeConsecutiveStreaks(trades),
    [trades]
  );
  const avgDuration = useMemo(() => computeAvgDuration(trades), [trades]);
  const { best, worst } = useMemo(
    () => computeBestWorstMonths(trades),
    [trades]
  );

  return (
    <div className="space-y-6">
      {/* Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <BarChart3 className="h-5 w-5 text-blue-500" />
            Overview
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="space-y-1">
              <p className="text-xs text-gray-500">Net Profit</p>
              <p
                className={`text-xl font-bold ${
                  netProfit >= 0 ? "text-green-500" : "text-red-500"
                }`}
              >
                {netProfit >= 0 ? "+" : ""}${netProfit.toFixed(2)}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-gray-500">Total Trades</p>
              <p className="text-xl font-bold">{stats.total_trades}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-gray-500">Win Rate</p>
              <p className="text-xl font-bold text-green-500">
                {stats.win_rate.toFixed(1)}%
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-gray-500">Profit Factor</p>
              <p className="text-xl font-bold">
                {stats.profit_factor >= 999 || !isFinite(stats.profit_factor)
                  ? "∞"
                  : stats.profit_factor.toFixed(2)}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Performance */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <TrendingUp className="h-5 w-5 text-emerald-500" />
            Performance
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-0">
            <StatRow
              label="Sharpe Ratio"
              value={stats.sharpe_ratio.toFixed(2)}
              variant={stats.sharpe_ratio > 0 ? "positive" : "neutral"}
            />
            <StatRow
              label="Sortino Ratio"
              value={sortinoRatio.toFixed(2)}
              variant={sortinoRatio > 0 ? "positive" : "neutral"}
            />
            <StatRow
              label="Max Drawdown"
              value={`${stats.max_drawdown.toFixed(2)}%`}
              variant="negative"
            />
            <StatRow
              label="Total Return"
              value={`${stats.total_return >= 0 ? "+" : ""}${stats.total_return.toFixed(2)}%`}
              variant={stats.total_return >= 0 ? "positive" : "negative"}
            />
            {stats.exposure_time != null && (
              <StatRow
                label="Exposure Time"
                value={`${stats.exposure_time.toFixed(1)}%`}
              />
            )}
          </div>
        </CardContent>
      </Card>

      {/* Trade Stats */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Target className="h-5 w-5 text-amber-500" />
            Trade Stats
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-0">
            <StatRow
              label="Avg Win"
              value={`$${stats.avg_win.toFixed(2)}`}
              variant={stats.avg_win > 0 ? "positive" : "neutral"}
            />
            <StatRow
              label="Avg Loss"
              value={`$${stats.avg_loss.toFixed(2)}`}
              variant={stats.avg_loss < 0 ? "negative" : "neutral"}
            />
            <StatRow
              label="Largest Win"
              value={`$${stats.largest_win.toFixed(2)}`}
              variant={stats.largest_win > 0 ? "positive" : "neutral"}
            />
            <StatRow
              label="Largest Loss"
              value={`$${stats.largest_loss.toFixed(2)}`}
              variant={stats.largest_loss < 0 ? "negative" : "neutral"}
            />
            <StatRow label="Consecutive Wins" value={maxWinStreak} />
            <StatRow label="Consecutive Losses" value={maxLossStreak} />
          </div>
        </CardContent>
      </Card>

      {/* Time Analysis */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Calendar className="h-5 w-5 text-violet-500" />
            Time Analysis
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-0">
            <StatRow
              label="Avg Trade Duration"
              value={stats.avg_trade_duration || avgDuration}
            />
            <StatRow
              label="Best Month"
              value={`${best.month} ($${best.pnl.toFixed(2)})`}
              variant={best.pnl > 0 ? "positive" : "neutral"}
            />
            <StatRow
              label="Worst Month"
              value={`${worst.month} ($${worst.pnl.toFixed(2)})`}
              variant={worst.pnl < 0 ? "negative" : "neutral"}
            />
          </div>
        </CardContent>
      </Card>

      {/* Summary Footer */}
      <div className="flex items-center justify-between text-sm text-gray-500">
        <span>
          {stats.winning_trades}W / {stats.losing_trades}L
        </span>
        <span>
          Initial: ${initialCash.toLocaleString()} → Final: $
          {finalEquity.toLocaleString()}
        </span>
      </div>
    </div>
  );
}
