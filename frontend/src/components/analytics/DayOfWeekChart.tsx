'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from 'recharts';
import type { BucketStats } from '@/hooks/usePerformanceAnalytics';
import { PanelEmptyState } from '@/components/shared/PanelEmptyState';
import { CalendarDays } from 'lucide-react';

interface DayOfWeekChartProps {
  data: Record<string, BucketStats>;
}

const DAY_ORDER = [
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
  'Sunday',
];
const DAY_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

interface ChartDataPoint {
  day: string;
  dayShort: string;
  pnl: number;
  winRate: number;
  trades: number;
}

const CustomTooltip = ({
  active,
  payload,
  label,
}: {
  active?: boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: Array<{ value: number; payload: any }>;
  label?: string;
}) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload as ChartDataPoint;
  return (
    <div
      className='rounded-lg border border-[var(--to-border)] bg-[#0d1117]/95 px-3 py-2.5 text-[11px] shadow-xl backdrop-blur-sm'
      style={{ fontFamily: 'var(--font-mono)' }}
    >
      <p className='mb-2 font-bold text-[var(--to-text-primary)]'>{label}</p>
      <div className='space-y-1'>
        <div className='flex justify-between gap-6'>
          <span className='text-[var(--to-text-dim)]'>PnL</span>
          <span style={{ color: d.pnl >= 0 ? '#0ecb81' : '#f6465d' }}>
            {d.pnl >= 0 ? '+' : ''}${d.pnl.toFixed(2)}
          </span>
        </div>
        <div className='flex justify-between gap-6'>
          <span className='text-[var(--to-text-dim)]'>Win Rate</span>
          <span style={{ color: d.winRate >= 50 ? '#0ecb81' : '#f6465d' }}>
            {d.winRate.toFixed(1)}%
          </span>
        </div>
        <div className='flex justify-between gap-6'>
          <span className='text-[var(--to-text-dim)]'>Trades</span>
          <span className='text-[var(--to-text-secondary)]'>{d.trades}</span>
        </div>
      </div>
    </div>
  );
};

export function DayOfWeekChart({ data }: DayOfWeekChartProps) {
  const chartData: ChartDataPoint[] = DAY_ORDER.map((day, i) => {
    const b = data[day];
    return {
      day,
      dayShort: DAY_SHORT[i],
      pnl: b?.pnl ?? 0,
      winRate: b?.win_rate ?? 0,
      trades: b?.count ?? 0,
    };
  }).filter((d) => d.trades > 0);

  if (chartData.length === 0) {
    return (
      <div className='tv-card p-4'>
        <PanelEmptyState
          title='No day-of-week data'
          description='More trades needed to show day-of-week patterns.'
        />
      </div>
    );
  }

  return (
    <div className='tv-card p-4'>
      {/* Header */}
      <div className='mb-4 flex items-center gap-2'>
        <div className='flex h-7 w-7 items-center justify-center rounded-lg bg-[#f0b90b]/15 border border-[#f0b90b]/25'>
          <CalendarDays className='h-3.5 w-3.5 text-[#f0b90b]' />
        </div>
        <div>
          <p className='panel-label'>Day-of-Week PnL</p>
          <p
            className='mt-0.5 text-[10px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            Which days generate the most profit?
          </p>
        </div>
      </div>

      <ResponsiveContainer width='100%' height={160}>
        <BarChart
          data={chartData}
          margin={{ top: 4, right: 8, left: -16, bottom: 0 }}
          barSize={24}
        >
          <CartesianGrid
            strokeDasharray='3 3'
            stroke='#1e2329'
            vertical={false}
          />
          <XAxis
            dataKey='dayShort'
            tick={{
              fill: '#5e6673',
              fontSize: 10,
              fontFamily: 'var(--font-mono)',
            }}
            tickLine={false}
            axisLine={{ stroke: '#1e2329' }}
          />
          <YAxis
            tick={{
              fill: '#5e6673',
              fontSize: 10,
              fontFamily: 'var(--font-mono)',
            }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `$${v}`}
          />
          <Tooltip
            content={<CustomTooltip />}
            cursor={{ fill: 'rgba(255,255,255,0.03)' }}
          />
          <ReferenceLine y={0} stroke='#21262d' strokeWidth={1} />
          <Bar dataKey='pnl' radius={[4, 4, 0, 0]}>
            {chartData.map((entry) => (
              <Cell
                key={entry.day}
                fill={entry.pnl >= 0 ? '#0ecb81' : '#f6465d'}
                fillOpacity={0.8}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Win rate row */}
      <div className='mt-3 flex gap-1.5 overflow-x-auto'>
        {chartData.map((d) => (
          <div
            key={d.day}
            className='flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-md bg-[#1e2329]/60 px-2 py-1.5'
          >
            <span
              className='text-[9px] text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {d.dayShort}
            </span>
            <span
              className='text-[10px] font-bold tabular-nums'
              style={{
                color:
                  d.winRate >= 60
                    ? '#0ecb81'
                    : d.winRate >= 50
                    ? '#f0b90b'
                    : '#f6465d',
                fontFamily: 'var(--font-mono)',
              }}
            >
              {d.winRate.toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
