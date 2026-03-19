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
} from 'recharts';

interface PnlBySymbolChartProps {
  data: { symbol: string; pnl: number; count: number; winRate: number }[];
}

export function PnlBySymbolChart({ data }: PnlBySymbolChartProps) {
  if (data.length === 0) {
    return (
      <div className="tv-card p-4 flex items-center justify-center h-[260px]">
        <span className="text-xs text-[var(--to-text-dim)] font-mono">No symbol data</span>
      </div>
    );
  }

  return (
    <div className="tv-card p-4">
      <span className="font-mono text-xs text-[var(--to-text-dim)] uppercase tracking-wider">
        PnL by Symbol
      </span>
      <div className="mt-3">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} layout="vertical" margin={{ top: 5, right: 20, left: 50, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2e39" horizontal={false} />
            <XAxis
              type="number"
              tick={{ fill: '#787b86', fontSize: 10, fontFamily: 'monospace' }}
              axisLine={{ stroke: '#2a2e39' }}
              tickLine={false}
              tickFormatter={(v) => `$${v}`}
            />
            <YAxis
              type="category"
              dataKey="symbol"
              tick={{ fill: '#d1d4dc', fontSize: 11, fontFamily: 'monospace', fontWeight: 600 }}
              axisLine={false}
              tickLine={false}
              width={50}
            />
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
            <Bar dataKey="pnl" radius={[0, 4, 4, 0]}>
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
