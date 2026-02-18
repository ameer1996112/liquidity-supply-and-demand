'use client';

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  CartesianGrid,
} from 'recharts';
import { WaitingPlaceholder } from '@/components/shared';

interface EquityCurveChartProps {
  data: { date: string; cumPnl: number }[];
}

export function EquityCurveChart({ data }: EquityCurveChartProps) {
  if (data.length < 2) {
    return (
      <div className='tv-card min-h-[400px] h-full flex items-center justify-center'>
        <WaitingPlaceholder />
      </div>
    );
  }

  const lastValue = data[data.length - 1].cumPnl;
  const isPositive = lastValue >= 0;

  return (
    <div className='tv-card p-4 min-h-[400px] h-full flex flex-col'>
      <div className='flex items-center justify-between mb-3'>
        <span className='font-mono text-xs text-zinc-400 uppercase tracking-wider'>
          Equity Curve
        </span>
        <span
          className={`font-mono text-sm font-bold tabular-nums ${isPositive ? 'text-[#26a69a]' : 'text-[#ef5350]'}`}
        >
          {isPositive ? '+' : ''}${lastValue.toFixed(2)}
        </span>
      </div>
      <div className='flex-1 min-h-0'>
        <ResponsiveContainer width='100%' height='100%'>
          <AreaChart
            data={data}
            margin={{ top: 5, right: 5, left: 5, bottom: 5 }}
          >
            <defs>
              <linearGradient id='equityUp' x1='0' y1='0' x2='0' y2='1'>
                <stop offset='5%' stopColor='#26a69a' stopOpacity={0.25} />
                <stop offset='95%' stopColor='#26a69a' stopOpacity={0} />
              </linearGradient>
              <linearGradient id='equityDown' x1='0' y1='0' x2='0' y2='1'>
                <stop offset='5%' stopColor='#ef5350' stopOpacity={0.25} />
                <stop offset='95%' stopColor='#ef5350' stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray='3 3' stroke='#2a2e39' />
            <XAxis
              dataKey='date'
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
            <ReferenceLine y={0} stroke='#787b86' strokeDasharray='3 3' />
            <Tooltip
              contentStyle={{
                background: '#1e222d',
                border: '1px solid #2a2e39',
                borderRadius: '6px',
                fontSize: '11px',
                fontFamily: 'monospace',
                color: '#d1d4dc',
              }}
              formatter={(value: number | undefined) => [
                `$${(value ?? 0).toFixed(2)}`,
                'PnL',
              ]}
            />
            <Area
              type='monotone'
              dataKey='cumPnl'
              stroke={isPositive ? '#26a69a' : '#ef5350'}
              strokeWidth={2}
              fill={isPositive ? 'url(#equityUp)' : 'url(#equityDown)'}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
