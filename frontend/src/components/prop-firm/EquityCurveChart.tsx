'use client';

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ReferenceArea,
  CartesianGrid,
} from 'recharts';
import { format, parseISO } from 'date-fns';
import type { PropFirmSnapshot } from '@/lib/api';
import { TrendingUp } from 'lucide-react';

interface EquityCurveChartProps {
  snapshots: PropFirmSnapshot[];
  startingBalance: number;
  dailyLimitPct: number;
  trailingLimitPct: number;
}

interface TooltipPayload {
  payload?: {
    equity: number;
    date: string;
    dailyDD: number;
    trailingDD: number;
  };
}

function CustomTooltip({ payload }: TooltipPayload) {
  if (!payload?.equity) return null;
  const { equity, date, dailyDD, trailingDD } = payload;
  return (
    <div className='bg-[#1e222d] border border-[#2a2e39] rounded-lg px-3 py-2 text-[11px] font-mono shadow-xl'>
      <div className='text-[var(--to-text-dim)] mb-1'>{date}</div>
      <div className='text-[#0ecb81]'>Equity: ${equity.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
      <div className='text-amber-400'>Daily DD: {dailyDD.toFixed(2)}%</div>
      <div className='text-[#ef5350]'>Trailing DD: {trailingDD.toFixed(2)}%</div>
    </div>
  );
}

export function EquityCurveChart({
  snapshots,
  startingBalance,
  dailyLimitPct,
  trailingLimitPct,
}: EquityCurveChartProps) {
  if (!snapshots?.length) {
    return (
      <div className='glass-panel p-6'>
        <h3 className='text-[13px] font-bold text-[var(--to-text-dim)] uppercase tracking-widest font-mono mb-4 flex items-center gap-2'>
          <TrendingUp className='h-4 w-4 text-emerald-400' />
          Equity Curve
        </h3>
        <div className='h-48 flex items-center justify-center text-[var(--to-text-dim)] text-sm font-mono'>
          No history yet — metrics snapshots will appear here after the first trading day.
        </div>
      </div>
    );
  }

  const data = snapshots
    .slice()
    .sort((a, b) => a.snapshot_time.localeCompare(b.snapshot_time))
    .map((s) => ({
      date: format(parseISO(s.snapshot_time), 'MMM dd'),
      equity: s.current_equity ?? startingBalance,
      dailyDD: s.daily_drawdown_pct ?? 0,
      trailingDD: s.trailing_drawdown_pct ?? 0,
    }));

  // Compute floor from trailing drawdown limit
  const trailingFloor = startingBalance * (1 - trailingLimitPct / 100);
  const dailyFloor = startingBalance * (1 - dailyLimitPct / 100);

  const allEquities = data.map((d) => d.equity);
  const minY = Math.min(...allEquities, trailingFloor) * 0.999;
  const maxY = Math.max(...allEquities, startingBalance) * 1.001;

  return (
    <div className='glass-panel p-6'>
      <h3 className='text-[13px] font-bold text-[var(--to-text-dim)] uppercase tracking-widest font-mono mb-4 flex items-center gap-2'>
        <TrendingUp className='h-4 w-4 text-emerald-400' />
        Equity Curve
      </h3>

      <div className='flex items-center gap-4 mb-3 text-[10px] font-mono'>
        <span className='flex items-center gap-1.5'>
          <span className='w-3 h-0.5 bg-emerald-400 inline-block' />
          <span className='text-[var(--to-text-dim)]'>Equity</span>
        </span>
        <span className='flex items-center gap-1.5'>
          <span className='w-3 h-0.5 bg-amber-400/60 inline-block border-t border-dashed border-amber-400' />
          <span className='text-[var(--to-text-dim)]'>Daily limit</span>
        </span>
        <span className='flex items-center gap-1.5'>
          <span className='w-3 h-0.5 bg-red-500/60 inline-block border-t border-dashed border-red-500' />
          <span className='text-[var(--to-text-dim)]'>Trailing limit</span>
        </span>
      </div>

      <ResponsiveContainer width='100%' height={200}>
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray='3 3' stroke='#2a2e39' vertical={false} />
          <XAxis
            dataKey='date'
            tick={{ fill: '#787b86', fontSize: 10, fontFamily: 'monospace' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={[minY, maxY]}
            tick={{ fill: '#787b86', fontSize: 10, fontFamily: 'monospace' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
            width={42}
          />
          <Tooltip
            content={({ payload }) =>
              payload?.[0] ? <CustomTooltip payload={payload[0].payload as TooltipPayload['payload']} /> : null
            }
          />

          {/* Trailing drawdown danger zone */}
          <ReferenceArea
            y1={minY}
            y2={trailingFloor}
            fill='#ef535015'
            stroke='none'
          />

          {/* Daily loss danger zone */}
          <ReferenceArea
            y1={trailingFloor}
            y2={dailyFloor}
            fill='#f0b90b08'
            stroke='none'
          />

          {/* Trailing drawdown floor line */}
          <ReferenceLine
            y={trailingFloor}
            stroke='#ef5350'
            strokeDasharray='4 3'
            strokeOpacity={0.7}
          />

          {/* Daily loss limit line */}
          <ReferenceLine
            y={dailyFloor}
            stroke='#f0b90b'
            strokeDasharray='4 3'
            strokeOpacity={0.7}
          />

          {/* Starting balance reference */}
          <ReferenceLine
            y={startingBalance}
            stroke='#2a2e39'
            strokeDasharray='2 4'
            strokeOpacity={0.5}
          />

          <Line
            type='monotone'
            dataKey='equity'
            stroke='#0ecb81'
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: '#0ecb81', stroke: '#1e222d', strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
