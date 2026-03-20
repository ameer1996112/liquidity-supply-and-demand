'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  CartesianGrid,
  ReferenceLine,
} from 'recharts';

interface DailyPnlChartProps {
  data: { date: string; pnl: number; wins: number; losses: number }[];
}

export function DailyPnlChart({ data }: DailyPnlChartProps) {
  if (data.length === 0) {
    return (
      <div className="glow-card p-4 flex items-center justify-center h-[220px]">
        <span className="text-xs text-[var(--to-text-dim)] font-mono">No daily PnL data</span>
      </div>
    );
  }

  return (
    <div className="glow-card p-4">
      <span className="font-mono text-xs text-[var(--to-text-dim)] uppercase tracking-wider">
        Daily PnL
      </span>
      <div className="mt-3">
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={data} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
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
              tickFormatter={(v) => `$${v}`}
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
              formatter={(value: number | undefined) => [`$${(value ?? 0).toFixed(2)}`, 'PnL']}
            />
            <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.pnl >= 0 ? '#26a69a' : '#ef5350'}
                  fillOpacity={0.8}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
