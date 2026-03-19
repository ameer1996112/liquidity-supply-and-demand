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
import { Brain } from 'lucide-react';

interface AIConfidenceChartProps {
  data: Record<string, BucketStats>;
}

const CONFIDENCE_ORDER = [
  '0.5-0.6',
  '0.6-0.7',
  '0.7-0.8',
  '0.8-0.9',
  '0.9-1.0',
  'unknown',
];

interface ChartDataPoint {
  band: string;
  winRate: number;
  trades: number;
  pnl: number;
}

const CustomTooltip = ({
  active,
  payload,
  label,
}: {
  active?: boolean;
   
  payload?: Array<{ name: string; value: number; color: string; payload: any }>;
  label?: string;
}) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload as ChartDataPoint;
  return (
    <div
      className='rounded-lg border border-[var(--to-border)] bg-[#0d1117]/95 px-3 py-2.5 text-[11px] shadow-xl backdrop-blur-sm'
      style={{ fontFamily: 'var(--font-mono)' }}
    >
      <p className='mb-2 font-bold text-[var(--to-text-primary)]'>
        Confidence {label}
      </p>
      <div className='space-y-1'>
        <div className='flex justify-between gap-6'>
          <span className='text-[var(--to-text-dim)]'>Win Rate</span>
          <span
            style={{
              color:
                d.winRate >= 60
                  ? '#0ecb81'
                  : d.winRate >= 50
                  ? '#f0b90b'
                  : '#f6465d',
            }}
          >
            {d.winRate.toFixed(1)}%
          </span>
        </div>
        <div className='flex justify-between gap-6'>
          <span className='text-[var(--to-text-dim)]'>Trades</span>
          <span className='text-[var(--to-text-secondary)]'>{d.trades}</span>
        </div>
        <div className='flex justify-between gap-6'>
          <span className='text-[var(--to-text-dim)]'>Total PnL</span>
          <span style={{ color: d.pnl >= 0 ? '#0ecb81' : '#f6465d' }}>
            {d.pnl >= 0 ? '+' : ''}${d.pnl.toFixed(2)}
          </span>
        </div>
      </div>
    </div>
  );
};

export function AIConfidenceChart({ data }: AIConfidenceChartProps) {
  const chartData = CONFIDENCE_ORDER.filter(
    (band) => data[band]?.count > 0
  ).map((band) => {
    const b = data[band];
    return {
      band: band === 'unknown' ? 'N/A' : band,
      winRate: b.win_rate,
      trades: b.count,
      pnl: b.pnl,
    };
  });

  if (chartData.length === 0) {
    return (
      <div className='tv-card p-4'>
        <PanelEmptyState
          title='No AI confidence data'
          description='AI confidence scores will appear after more trades.'
        />
      </div>
    );
  }

  return (
    <div className='tv-card p-4'>
      {/* Header */}
      <div className='mb-4 flex items-center gap-2'>
        <div className='flex h-7 w-7 items-center justify-center rounded-lg bg-[#8b5cf6]/15 border border-[#8b5cf6]/25'>
          <Brain className='h-3.5 w-3.5 text-[#8b5cf6]' />
        </div>
        <div>
          <p className='panel-label'>AI Confidence vs Win Rate</p>
          <p
            className='mt-0.5 text-[10px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            Does higher AI confidence predict better outcomes?
          </p>
        </div>
      </div>

      <ResponsiveContainer width='100%' height={180}>
        <BarChart
          data={chartData}
          margin={{ top: 4, right: 8, left: -16, bottom: 0 }}
          barSize={28}
        >
          <CartesianGrid
            strokeDasharray='3 3'
            stroke='#1e2329'
            vertical={false}
          />
          <XAxis
            dataKey='band'
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
            tickFormatter={(v) => `${v}%`}
            domain={[0, 100]}
          />
          <Tooltip
            content={<CustomTooltip />}
            cursor={{ fill: 'rgba(255,255,255,0.03)' }}
          />
          <ReferenceLine
            y={50}
            stroke='#f0b90b'
            strokeDasharray='4 4'
            strokeOpacity={0.4}
          />
          <Bar dataKey='winRate' name='Win Rate' radius={[4, 4, 0, 0]}>
            {chartData.map((entry) => (
              <Cell
                key={entry.band}
                fill={
                  entry.winRate >= 60
                    ? '#0ecb81'
                    : entry.winRate >= 50
                    ? '#3b82f6'
                    : entry.winRate >= 40
                    ? '#f0b90b'
                    : '#f6465d'
                }
                fillOpacity={0.85}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Trade count row */}
      <div className='mt-3 flex gap-2 overflow-x-auto'>
        {chartData.map((d) => (
          <div
            key={d.band}
            className='flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-md bg-[#1e2329]/60 px-2 py-1.5'
          >
            <span
              className='text-[9px] text-[var(--to-text-dim)] truncate'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {d.band}
            </span>
            <span
              className='text-[10px] font-bold tabular-nums text-[var(--to-text-secondary)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {d.trades}t
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
