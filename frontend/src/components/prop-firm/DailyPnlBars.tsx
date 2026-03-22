'use client';

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
  Cell,
} from 'recharts';
import { BarChart2 } from 'lucide-react';

interface DailyBar {
  date: string;
  pnl: number;
  positions: number;
  wins: number;
  losses: number;
  winRate: number;
}

interface DailyPnlBarsProps {
  data: DailyBar[];
  /** Best-day limit in USD (null = not configured) */
  bestDayLimitUsd?: number | null;
  /** Consistency limit as pct of account (for label) */
  consistencyLimitPct?: number;
}

interface TooltipPayload {
  payload?: DailyBar;
}

function CustomTooltip({ payload }: TooltipPayload) {
  if (!payload) return null;
  const { date, pnl, positions, winRate } = payload;
  return (
    <div className='bg-[#1e222d] border border-[#2a2e39] rounded-lg px-3 py-2 text-[11px] font-mono shadow-xl'>
      <div className='text-[var(--to-text-dim)] mb-1'>{date}</div>
      <div className={pnl >= 0 ? 'text-[#0ecb81]' : 'text-[#ef5350]'}>
        PnL: {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
      </div>
      <div className='text-[var(--to-text-dim)]'>Trades: {positions}</div>
      {positions > 0 && (
        <div className='text-[var(--to-text-dim)]'>Win rate: {winRate.toFixed(0)}%</div>
      )}
    </div>
  );
}

export function DailyPnlBars({
  data,
  bestDayLimitUsd,
  consistencyLimitPct,
}: DailyPnlBarsProps) {
  if (!data?.length) {
    return (
      <div className='glass-panel p-6'>
        <h3 className='text-[13px] font-bold text-[var(--to-text-dim)] uppercase tracking-widest font-mono mb-4 flex items-center gap-2'>
          <BarChart2 className='h-4 w-4 text-blue-400' />
          Daily P&amp;L
        </h3>
        <div className='h-40 flex items-center justify-center text-[var(--to-text-dim)] text-sm font-mono'>
          No trades in this period.
        </div>
      </div>
    );
  }

  const maxAbs = Math.max(...data.map((d) => Math.abs(d.pnl)), 1);
  const domainMax = maxAbs * 1.2;

  return (
    <div className='glass-panel p-6'>
      <div className='flex items-center justify-between mb-4'>
        <h3 className='text-[13px] font-bold text-[var(--to-text-dim)] uppercase tracking-widest font-mono flex items-center gap-2'>
          <BarChart2 className='h-4 w-4 text-blue-400' />
          Daily P&amp;L
        </h3>
        {consistencyLimitPct != null && (
          <span className='text-[10px] font-mono text-amber-400/70'>
            Consistency limit: {consistencyLimitPct}% best day
          </span>
        )}
      </div>

      <ResponsiveContainer width='100%' height={180}>
        <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }} barSize={16}>
          <CartesianGrid strokeDasharray='3 3' stroke='#2a2e39' vertical={false} />
          <XAxis
            dataKey='date'
            tick={{ fill: '#787b86', fontSize: 10, fontFamily: 'monospace' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={[-domainMax, domainMax]}
            tick={{ fill: '#787b86', fontSize: 10, fontFamily: 'monospace' }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `$${v >= 0 ? '' : ''}${v.toFixed(0)}`}
            width={52}
          />
          <Tooltip
            content={({ payload }) =>
              payload?.[0] ? <CustomTooltip payload={payload[0].payload as DailyBar} /> : null
            }
          />

          {/* Zero baseline */}
          <ReferenceLine y={0} stroke='#2a2e39' strokeWidth={1} />

          {/* Best-day consistency limit */}
          {bestDayLimitUsd != null && bestDayLimitUsd > 0 && (
            <ReferenceLine
              y={bestDayLimitUsd}
              stroke='#f0b90b'
              strokeDasharray='5 3'
              strokeOpacity={0.8}
              label={{
                value: 'Best day limit',
                position: 'insideTopRight',
                fill: '#f0b90b',
                fontSize: 9,
                fontFamily: 'monospace',
              }}
            />
          )}

          <Bar dataKey='pnl' radius={[2, 2, 0, 0]}>
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.pnl >= 0 ? '#0ecb8133' : '#ef535033'}
                stroke={entry.pnl >= 0 ? '#0ecb81' : '#ef5350'}
                strokeWidth={1}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
