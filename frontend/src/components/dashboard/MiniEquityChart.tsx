'use client';

import { useMemo } from 'react';
import { useTradingSignals } from '@/hooks/useTradingSignals';
import { TradingMode, getPnl } from '@/types/trading';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  EMPTY_VALUE,
  formatCurrency,
  normalizeNegativeZero,
} from '@/lib/formatters';

interface MiniEquityChartProps {
  mode?: TradingMode;
}

export function MiniEquityChart({ mode }: MiniEquityChartProps) {
  const { data: signals = [] } = useTradingSignals(mode);

  const { chartData, totalPnl } = useMemo(() => {
    // Filter to closed trades with PnL, sort by time ascending
    const closed = signals
      .filter((s) => {
        const st = s.status?.toLowerCase();
        const pnl = getPnl(s);
        return (st === 'closed' || st === 'executed') && pnl != null;
      })
      .sort(
        (a, b) =>
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      );

    if (closed.length === 0) {
      return { chartData: [], totalPnl: 0 };
    }

    // Build cumulative PnL series
    let cumPnl = 0;
    const data = closed.map((s) => {
      const pnl = normalizeNegativeZero(getPnl(s) ?? 0) ?? 0;
      cumPnl += pnl;
      return {
        time: new Date(s.created_at).toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
        }),
        cumPnl: Number(cumPnl.toFixed(2)),
      };
    });

    return { chartData: data, totalPnl: normalizeNegativeZero(cumPnl) ?? 0 };
  }, [signals]);

  const isPositive = totalPnl >= 0;

  if (chartData.length < 2) {
    return (
      <div className='glow-card min-h-[140px] flex items-center justify-center'>
        <div className='empty-state py-12'>
          <span className='empty-state-text'>[ NO ACTIVE DATA ]</span>
          <span
            className='mt-1 text-[10px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            awaiting 5m zone entry
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className='glow-card p-3'>
      {/* Header */}
      <div className='flex items-center justify-between mb-2'>
        <span className='font-mono text-[10px] text-[var(--to-text-dim)] uppercase tracking-wider'>
          Equity Curve
        </span>
        <div className='flex items-center gap-1'>
          {isPositive ? (
            <TrendingUp className='w-3 h-3 text-[#26a69a]' />
          ) : (
            <TrendingDown className='w-3 h-3 text-[#ef5350]' />
          )}
          <span
            className={cn(
              'font-mono text-xs font-bold tabular-nums',
              isPositive ? 'text-[#26a69a]' : 'text-[#ef5350]'
            )}
          >
            {formatCurrency(totalPnl, { signed: true })}
          </span>
        </div>
      </div>

      {/* Chart */}
      <ResponsiveContainer width='100%' height={100}>
        <AreaChart
          data={chartData}
          margin={{ top: 2, right: 2, left: 2, bottom: 0 }}
        >
          <defs>
            <linearGradient id='equityGradientUp' x1='0' y1='0' x2='0' y2='1'>
              <stop offset='5%' stopColor='#26a69a' stopOpacity={0.3} />
              <stop offset='95%' stopColor='#26a69a' stopOpacity={0} />
            </linearGradient>
            <linearGradient id='equityGradientDown' x1='0' y1='0' x2='0' y2='1'>
              <stop offset='5%' stopColor='#ef5350' stopOpacity={0.3} />
              <stop offset='95%' stopColor='#ef5350' stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey='time' hide />
          <YAxis hide domain={['auto', 'auto']} />
          <ReferenceLine y={0} stroke='#2a2e39' strokeDasharray='3 3' />
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
              formatCurrency(value ?? null) || EMPTY_VALUE,
              'PnL',
            ]}
          />
          <Area
            type='monotone'
            dataKey='cumPnl'
            stroke={isPositive ? '#26a69a' : '#ef5350'}
            strokeWidth={1.5}
            fill={
              isPositive ? 'url(#equityGradientUp)' : 'url(#equityGradientDown)'
            }
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
