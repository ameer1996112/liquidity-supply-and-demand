'use client';

import { useMemo } from 'react';
import { TradingSignal, getPnl } from '@/types/trading';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
} from 'recharts';
import { format } from 'date-fns';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface JournalEquityCurveProps {
  signals: TradingSignal[];
}

interface DataPoint {
  date: string;
  rawDate: number;
  cumPnl: number;
  tradePnl: number;
  symbol: string;
  tradeNum: number;
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
  const isWin = d.tradePnl >= 0;
  return (
    <div className='rounded-lg border border-[#2a2e39] bg-[#0d1117] p-2.5 shadow-xl text-[11px] font-mono'>
      <div className='text-[var(--to-text-dim)] mb-1'>{d.date} · Trade #{d.tradeNum}</div>
      <div className='text-[var(--to-text-secondary)]'>
        Symbol: <span className='text-[var(--to-text-primary)]'>{d.symbol}</span>
      </div>
      <div>
        Trade:{' '}
        <span className={isWin ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]'}>
          {isWin ? '+' : ''}${d.tradePnl.toFixed(2)}
        </span>
      </div>
      <div>
        Cumulative:{' '}
        <span className={d.cumPnl >= 0 ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]'}>
          {d.cumPnl >= 0 ? '+' : ''}${d.cumPnl.toFixed(2)}
        </span>
      </div>
    </div>
  );
}

export function JournalEquityCurve({ signals }: JournalEquityCurveProps) {
  const { data, finalPnl, isPositive } = useMemo(() => {
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

    if (closed.length < 3) return { data: [], finalPnl: 0, isPositive: true };

    let cum = 0;
    const points: DataPoint[] = closed.map((s, i) => {
      const pnl = getPnl(s) ?? 0;
      cum += pnl;
      const dateObj = new Date(s.closed_at ?? s.created_at);
      return {
        date: format(dateObj, 'MMM dd'),
        rawDate: dateObj.getTime(),
        cumPnl: Math.round(cum * 100) / 100,
        tradePnl: Math.round(pnl * 100) / 100,
        symbol: s.symbol || 'UNKNOWN',
        tradeNum: i + 1,
      };
    });

    return {
      data: points,
      finalPnl: cum,
      isPositive: cum >= 0,
    };
  }, [signals]);

  if (data.length < 3) return null;

  const lineColor = isPositive ? '#0ecb81' : '#f6465d';
  const gradientId = `equity-gradient-${isPositive ? 'pos' : 'neg'}`;

  return (
    <div className='rounded-xl border border-[#2a2e39] bg-[#0d1117] overflow-hidden'>
      {/* Header */}
      <div className='flex items-center justify-between px-4 py-3 border-b border-[#2a2e39]'>
        <div className='flex items-center gap-2'>
          {isPositive
            ? <TrendingUp className='w-3.5 h-3.5 text-[var(--to-long)]' />
            : <TrendingDown className='w-3.5 h-3.5 text-[var(--to-short)]' />
          }
          <span className='font-mono text-[12px] font-semibold text-[var(--to-text-primary)]'>
            Equity Curve
          </span>
          <span className='font-mono text-[10px] text-[var(--to-text-dim)]'>
            {data.length} closed trades
          </span>
        </div>
        <span
          className={`font-mono text-[13px] font-bold ${isPositive ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]'}`}
        >
          {isPositive ? '+' : ''}${finalPnl.toFixed(2)}
        </span>
      </div>

      {/* Chart */}
      <div className='px-2 py-3' style={{ height: 180 }}>
        <ResponsiveContainer width='100%' height='100%'>
          <LineChart data={data} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={gradientId} x1='0' y1='0' x2='0' y2='1'>
                <stop offset='5%' stopColor={lineColor} stopOpacity={0.15} />
                <stop offset='95%' stopColor={lineColor} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray='3 3'
              stroke='#2a2e39'
              vertical={false}
            />
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
            <Line
              type='monotone'
              dataKey='cumPnl'
              stroke={lineColor}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: lineColor, strokeWidth: 0 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
