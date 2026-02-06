'use client';

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from 'recharts';
import type { DrawdownPoint } from '@/hooks/usePerformanceAnalytics';

interface DrawdownChartProps {
  data: DrawdownPoint[];
  maxDrawdownPct: number;
  maxDrawdownAmount: number;
  height?: number;
}

export function DrawdownChart({
  data,
  maxDrawdownPct,
  maxDrawdownAmount,
  height = 300,
}: DrawdownChartProps) {
  if (data.length < 2) {
    return (
      <div className="tv-card flex items-center justify-center" style={{ height }}>
        <span className="text-xs text-zinc-600 font-mono">
          Not enough data for drawdown chart
        </span>
      </div>
    );
  }

  return (
    <div className="tv-card p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="font-mono text-xs text-zinc-400 uppercase tracking-wider">
          Underwater Plot
        </span>
        <div className="flex items-center gap-4">
          <span className="font-mono text-[10px] text-zinc-500">
            Max DD:{' '}
            <span className="text-[#ef5350] font-semibold">
              {maxDrawdownPct.toFixed(1)}% (${maxDrawdownAmount.toFixed(2)})
            </span>
          </span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <defs>
            <linearGradient id="drawdownFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ef5350" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#ef5350" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2e39" />
          <XAxis
            dataKey="date"
            tick={{ fill: '#787b86', fontSize: 10, fontFamily: 'monospace' }}
            axisLine={{ stroke: '#2a2e39' }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: '#787b86', fontSize: 10, fontFamily: 'monospace' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `${v}%`}
          />
          <ReferenceLine y={0} stroke="#787b86" strokeDasharray="3 3" />
          <Tooltip
            contentStyle={{
              background: '#1e222d',
              border: '1px solid #2a2e39',
              borderRadius: '6px',
              fontSize: '11px',
              fontFamily: 'monospace',
              color: '#d1d4dc',
            }}
            formatter={(value: number | undefined) => [`${(value ?? 0).toFixed(2)}%`, 'Drawdown']}
          />
          <Area
            type="monotone"
            dataKey="drawdown_pct"
            stroke="#ef5350"
            strokeWidth={2}
            fill="url(#drawdownFill)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
