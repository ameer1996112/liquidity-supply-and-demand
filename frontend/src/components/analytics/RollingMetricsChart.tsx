'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from 'recharts';
import { format, parseISO } from 'date-fns';
import { PanelEmptyState } from '@/components/shared/PanelEmptyState';

interface RollingPoint {
  date: string;
  equity: number;
  drawdown_pct: number;
  peak: number;
}

interface RollingMetricsChartProps {
  drawdownData: RollingPoint[];
  /** Rolling window size in trades */
  windowSize?: number;
}

interface RollingDataPoint {
  date: string;
  winRate: number | null;
  profitFactor: number | null;
  avgRR: number | null;
}

function computeRolling(
  data: RollingPoint[],
  window: number
): RollingDataPoint[] {
  if (data.length < 2) return [];

  // Derive win/loss from equity changes
  const trades = data.map((d, i) => {
    if (i === 0) return { date: d.date, pnl: 0 };
    return { date: d.date, pnl: d.equity - data[i - 1].equity };
  });

  return trades.slice(1).map((_, i) => {
    const start = Math.max(0, i - window + 1);
    const slice = trades.slice(start, i + 2);
    const wins = slice.filter((t) => t.pnl > 0);
    const losses = slice.filter((t) => t.pnl < 0);
    const winRate =
      slice.length > 0 ? (wins.length / slice.length) * 100 : null;
    const grossWin = wins.reduce((s, t) => s + t.pnl, 0);
    const grossLoss = Math.abs(losses.reduce((s, t) => s + t.pnl, 0));
    const profitFactor =
      grossLoss > 0 ? Math.min(grossWin / grossLoss, 10) : null;
    const avgWin = wins.length > 0 ? grossWin / wins.length : 0;
    const avgLoss = losses.length > 0 ? grossLoss / losses.length : 0;
    const avgRR = avgLoss > 0 ? Math.min(avgWin / avgLoss, 10) : null;

    return {
      date: slice[slice.length - 1].date,
      winRate,
      profitFactor,
      avgRR,
    };
  });
}

const CustomTooltip = ({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) => {
  if (!active || !payload?.length) return null;
  return (
    <div
      className='rounded-lg border border-[var(--to-border)] bg-[#0d1117]/95 px-3 py-2 text-[11px] shadow-xl backdrop-blur-sm'
      style={{ fontFamily: 'var(--font-mono)' }}
    >
      <p className='mb-1.5 text-[var(--to-text-dim)]'>
        {label
          ? (() => {
              try {
                return format(parseISO(label), 'MMM d, yyyy');
              } catch {
                return label;
              }
            })()
          : ''}
      </p>
      {payload.map((p) => (
        <div key={p.name} className='flex items-center justify-between gap-4'>
          <span style={{ color: p.color }}>{p.name}</span>
          <span className='font-semibold' style={{ color: p.color }}>
            {p.name === 'Win Rate'
              ? `${p.value.toFixed(1)}%`
              : p.value.toFixed(2)}
          </span>
        </div>
      ))}
    </div>
  );
};

export function RollingMetricsChart({
  drawdownData,
  windowSize = 10,
}: RollingMetricsChartProps) {
  const rollingData = computeRolling(drawdownData, windowSize);

  if (rollingData.length < 3) {
    return (
      <div className='tv-card p-4'>
        <PanelEmptyState
          title='Not enough data'
          description='Execute more trades to see rolling metrics.'
        />
      </div>
    );
  }

  const tickFormatter = (val: string) => {
    try {
      return format(parseISO(val), 'MMM d');
    } catch {
      return val;
    }
  };

  return (
    <div className='space-y-4'>
      {/* Win Rate Rolling */}
      <div className='tv-card p-4'>
        <div className='mb-3 flex items-center justify-between'>
          <span className='panel-label'>
            Rolling Win Rate ({windowSize}-trade window)
          </span>
          <span
            className='text-[10px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {rollingData.length} data points
          </span>
        </div>
        <ResponsiveContainer width='100%' height={180}>
          <LineChart
            data={rollingData}
            margin={{ top: 4, right: 16, left: -10, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray='3 3' stroke='#1e2329' />
            <XAxis
              dataKey='date'
              tickFormatter={tickFormatter}
              tick={{
                fill: '#5e6673',
                fontSize: 10,
                fontFamily: 'var(--font-mono)',
              }}
              tickLine={false}
              axisLine={{ stroke: '#1e2329' }}
              interval='preserveStartEnd'
            />
            <YAxis
              tick={{
                fill: '#5e6673',
                fontSize: 10,
                fontFamily: 'var(--font-mono)',
              }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${v.toFixed(0)}%`}
              domain={[0, 100]}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine
              y={50}
              stroke='#f0b90b'
              strokeDasharray='4 4'
              strokeOpacity={0.5}
            />
            <Line
              type='monotone'
              dataKey='winRate'
              name='Win Rate'
              stroke='#0ecb81'
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Profit Factor + Avg R:R Rolling */}
      <div className='tv-card p-4'>
        <div className='mb-3'>
          <span className='panel-label'>
            Rolling Profit Factor & Avg R:R ({windowSize}-trade window)
          </span>
        </div>
        <ResponsiveContainer width='100%' height={180}>
          <LineChart
            data={rollingData}
            margin={{ top: 4, right: 16, left: -10, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray='3 3' stroke='#1e2329' />
            <XAxis
              dataKey='date'
              tickFormatter={tickFormatter}
              tick={{
                fill: '#5e6673',
                fontSize: 10,
                fontFamily: 'var(--font-mono)',
              }}
              tickLine={false}
              axisLine={{ stroke: '#1e2329' }}
              interval='preserveStartEnd'
            />
            <YAxis
              tick={{
                fill: '#5e6673',
                fontSize: 10,
                fontFamily: 'var(--font-mono)',
              }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => v.toFixed(1)}
              domain={[0, 'auto']}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine
              y={1}
              stroke='#f0b90b'
              strokeDasharray='4 4'
              strokeOpacity={0.5}
            />
            <Legend
              wrapperStyle={{
                fontSize: 10,
                fontFamily: 'var(--font-mono)',
                color: '#5e6673',
              }}
            />
            <Line
              type='monotone'
              dataKey='profitFactor'
              name='Profit Factor'
              stroke='#3b82f6'
              strokeWidth={2}
              dot={false}
              connectNulls
            />
            <Line
              type='monotone'
              dataKey='avgRR'
              name='Avg R:R'
              stroke='#8b5cf6'
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
