'use client';

import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';

interface WinRateDonutProps {
  wins: number;
  losses: number;
  breakeven: number;
}

const COLORS = {
  wins: '#26a69a',
  losses: '#ef5350',
  breakeven: '#787b86',
};

export function WinRateDonut({ wins, losses, breakeven }: WinRateDonutProps) {
  const total = wins + losses + breakeven;
  const winRate = total > 0 ? ((wins / total) * 100).toFixed(1) : '0.0';

  const data = [
    { name: 'Wins', value: wins },
    { name: 'Losses', value: losses },
    { name: 'Breakeven', value: breakeven },
  ].filter((d) => d.value > 0);

  if (total === 0) {
    return (
      <div className="tv-card p-4 flex items-center justify-center h-[260px]">
        <span className="text-xs text-zinc-600 font-mono">No closed trades</span>
      </div>
    );
  }

  return (
    <div className="tv-card p-4">
      <span className="font-mono text-xs text-zinc-400 uppercase tracking-wider">
        Win / Loss Distribution
      </span>
      <div className="relative mt-2">
        <ResponsiveContainer width="100%" height={200}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={55}
              outerRadius={80}
              paddingAngle={2}
              dataKey="value"
              stroke="none"
            >
              {data.map((entry) => (
                <Cell
                  key={entry.name}
                  fill={COLORS[entry.name.toLowerCase() as keyof typeof COLORS]}
                />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        {/* Center label */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="font-mono text-2xl font-bold text-zinc-100">{winRate}%</span>
          <span className="text-[10px] text-zinc-500 uppercase">Win Rate</span>
        </div>
      </div>
      {/* Legend */}
      <div className="flex items-center justify-center gap-4 mt-2">
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-sm" style={{ background: COLORS.wins }} />
          <span className="text-[10px] text-zinc-500 font-mono">{wins} Wins</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-sm" style={{ background: COLORS.losses }} />
          <span className="text-[10px] text-zinc-500 font-mono">{losses} Losses</span>
        </div>
        {breakeven > 0 && (
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-sm" style={{ background: COLORS.breakeven }} />
            <span className="text-[10px] text-zinc-500 font-mono">{breakeven} BE</span>
          </div>
        )}
      </div>
    </div>
  );
}
