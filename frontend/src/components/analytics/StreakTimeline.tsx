'use client';

import { cn } from '@/lib/utils';
import type { Streak } from '@/hooks/usePerformanceAnalytics';

interface StreakTimelineProps {
  streaks: Streak[];
  maxWinStreak: number;
  maxLossStreak: number;
  currentStreak: number;
  currentStreakType: string;
}

export function StreakTimeline({
  streaks,
  maxWinStreak,
  maxLossStreak,
  currentStreak,
  currentStreakType,
}: StreakTimelineProps) {
  const maxCount = Math.max(...streaks.map((s) => s.count), 1);

  return (
    <div className="glow-card p-4">
      <div className="flex items-center justify-between mb-4">
        <span className="font-mono text-xs text-[var(--to-text-dim)] uppercase tracking-wider">
          Win/Loss Streaks
        </span>
        <div className="flex items-center gap-4 font-mono text-[10px]">
          <span className="text-[var(--to-text-dim)]">
            Best Win:{' '}
            <span className="text-[#26a69a] font-semibold">{maxWinStreak}</span>
          </span>
          <span className="text-[var(--to-text-dim)]">
            Worst Loss:{' '}
            <span className="text-[#ef5350] font-semibold">{maxLossStreak}</span>
          </span>
          <span className="text-[var(--to-text-dim)]">
            Current:{' '}
            <span
              className={cn(
                'font-semibold',
                currentStreakType === 'win' ? 'text-[#26a69a]' : 'text-[#ef5350]',
              )}
            >
              {currentStreak} {currentStreakType}
            </span>
          </span>
        </div>
      </div>

      {streaks.length === 0 ? (
        <div className="py-8 text-center text-xs text-[var(--to-text-dim)] font-mono">
          No streak data available
        </div>
      ) : (
        <div className="space-y-1.5">
          {streaks.slice(-30).map((streak, i) => {
            const widthPct = Math.max((streak.count / maxCount) * 100, 8);
            const isWin = streak.type === 'win';

            return (
              <div key={i} className="flex items-center gap-2">
                <span className="w-8 text-right font-mono text-[10px] tabular-nums text-[var(--to-text-dim)]">
                  {streak.count}
                </span>
                <div className="flex-1">
                  <div
                    className={cn(
                      'h-5 rounded-sm flex items-center px-2 transition-all',
                      isWin ? 'bg-[#26a69a]/25' : 'bg-[#ef5350]/25',
                    )}
                    style={{ width: `${widthPct}%` }}
                  >
                    <span
                      className={cn(
                        'font-mono text-[10px] font-semibold tabular-nums whitespace-nowrap',
                        isWin ? 'text-[#26a69a]' : 'text-[#ef5350]',
                      )}
                    >
                      {streak.pnl >= 0 ? '+' : ''}${streak.pnl.toFixed(0)}
                    </span>
                  </div>
                </div>
                <span className="font-mono text-[9px] text-[var(--to-text-dim)] w-14 text-right">
                  {streak.type.toUpperCase()}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
