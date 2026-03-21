'use client';

import { useMemo } from 'react';
import { TradingSignal, getPnl } from '@/types/trading';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
} from 'recharts';
import { format } from 'date-fns';
import { ShieldAlert } from 'lucide-react';

interface DrawdownChartProps {
  signals: TradingSignal[];
}

interface DataPoint {
  date: string;
  drawdown: number; // negative number (depth below peak)
  equity: number;
  drawdownPct: number;
}

interface TooltipPayload {
  payload: DataPoint;
}

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipPayload[];
}) {
  if (!active || !payload || payload.length === 0) return null;
  const d = payload[0].payload;
  return (
    <div className='rounded-lg border border-[#2a2e39] bg-[#0d1117] p-2.5 shadow-xl text-[11px] font-mono'>
      <div className='text-[var(--to-text-dim)] mb-1'>{d.date}</div>
      <div>
        Drawdown:{' '}
        <span className='text-[var(--to-short)]'>
          ${Math.abs(d.drawdown).toFixed(2)} ({Math.abs(d.drawdownPct).toFixed(1)}%)
        </span>
      </div>
      <div>
        Equity: <span className='text-[var(--to-text-secondary)]'>${d.equity.toFixed(2)}</span>
      </div>
    </div>
  );
}

export function DrawdownChart({ signals }: DrawdownChartProps) {
  const { data, maxDrawdown, maxDrawdownPct } = useMemo(() => {
    const closed = signals
      .filter((s) => {
        const st = (s.status || '').toLowerCase();
        return (st === 'closed' || st === 'executed') && getPnl(s) != null;
      })
      .sort((a, b) => {
        const aT = new Date(a.closed_at ?? a.created_at).getTime();
        const bT = new Date(b.closed_at ?? b.created_at).getTime();
        return aT - bT;
      });

    if (closed.length < 3) return { data: [], maxDrawdown: 0, maxDrawdownPct: 0 };

    let equity = 0;
    let peak = 0;
    let maxDD = 0;
    let maxDDPct = 0;

    const points: DataPoint[] = closed.map((s) => {
      const pnl = getPnl(s) ?? 0;
      equity += pnl;
      peak = Math.max(peak, equity);
      const dd = equity - peak; // ≤ 0
      const ddPct = peak > 0 ? (dd / peak) * 100 : 0;
      if (dd < maxDD) maxDD = dd;
      if (ddPct < maxDDPct) maxDDPct = ddPct;
      return {
        date: format(new Date(s.closed_at ?? s.created_at), 'MMM dd'),
        drawdown: Math.round(dd * 100) / 100,
        equity: Math.round(equity * 100) / 100,
        drawdownPct: Math.round(ddPct * 100) / 100,
      };
    });

    return { data: points, maxDrawdown: maxDD, maxDrawdownPct: maxDDPct };
  }, [signals]);

  if (data.length < 3 || maxDrawdown === 0) return null;

  return (
    <div className='rounded-xl border border-[#2a2e39] bg-[#0d1117] overflow-hidden'>
      {/* Header */}
      <div className='flex items-center justify-between px-4 py-3 border-b border-[#2a2e39]'>
        <div className='flex items-center gap-2'>
          <ShieldAlert className='w-3.5 h-3.5 text-[var(--to-short)]' />
          <span className='font-mono text-[12px] font-semibold text-[var(--to-text-primary)]'>
            Drawdown
          </span>
        </div>
        <div className='flex items-center gap-4'>
          <div className='text-right'>
            <div className='font-mono text-[10px] text-[var(--to-text-dim)]'>Max Drawdown</div>
            <div className='font-mono text-[13px] font-bold text-[var(--to-short)]'>
              ${Math.abs(maxDrawdown).toFixed(2)}
              <span className='text-[10px] ml-1'>({Math.abs(maxDrawdownPct).toFixed(1)}%)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className='px-2 py-3' style={{ height: 140 }}>
        <ResponsiveContainer width='100%' height='100%'>
          <AreaChart data={data} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id='dd-gradient' x1='0' y1='0' x2='0' y2='1'>
                <stop offset='5%' stopColor='#f6465d' stopOpacity={0.3} />
                <stop offset='95%' stopColor='#f6465d' stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray='3 3' stroke='#2a2e39' vertical={false} />
            <XAxis
              dataKey='date'
              tick={{ fill: '#848e9c', fontSize: 9, fontFamily: 'var(--font-mono)' }}
              axisLine={false}
              tickLine={false}
              interval='preserveStartEnd'
            />
            <YAxis
              tick={{ fill: '#848e9c', fontSize: 9, fontFamily: 'var(--font-mono)' }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => `$${v}`}
              width={55}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={0} stroke='#2a2e39' strokeDasharray='4 4' />
            <Area
              type='monotone'
              dataKey='drawdown'
              stroke='#f6465d'
              strokeWidth={1.5}
              fill='url(#dd-gradient)'
              dot={false}
              activeDot={{ r: 3, fill: '#f6465d', strokeWidth: 0 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
