'use client';

import { cn } from '@/lib/utils';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface PerformanceScoreCardProps {
  winRate: number;
  profitFactor: number;
  expectancy: number;
  sharpeRatio: number;
  sortinoRatio: number;
  maxDrawdownPct: number;
  totalTrades: number;
}

function computeScore(props: PerformanceScoreCardProps): {
  score: number;
  label: string;
  color: string;
  description: string;
} {
  const { winRate, profitFactor, sharpeRatio, expectancy, maxDrawdownPct } =
    props;

  // Normalize each metric to 0-100
  const wrScore = Math.min(winRate, 100); // already 0-100
  const pfScore = Math.min((profitFactor / 3) * 100, 100); // 3.0 PF = perfect
  const sharpeScore = Math.min(Math.max((sharpeRatio / 3) * 100, 0), 100); // 3.0 Sharpe = perfect
  const expScore = expectancy > 0 ? Math.min((expectancy / 50) * 100, 100) : 0; // $50 exp = perfect
  const ddPenalty = Math.min(maxDrawdownPct * 2, 40); // penalize drawdown

  const raw =
    wrScore * 0.25 +
    pfScore * 0.3 +
    sharpeScore * 0.2 +
    expScore * 0.25 -
    ddPenalty * 0.1;

  const score = Math.round(Math.max(0, Math.min(100, raw)));

  if (score >= 80)
    return {
      score,
      label: 'ELITE',
      color: '#0ecb81',
      description: 'Exceptional performance across all metrics',
    };
  if (score >= 65)
    return {
      score,
      label: 'STRONG',
      color: '#3b82f6',
      description: 'Above-average performance with solid risk control',
    };
  if (score >= 50)
    return {
      score,
      label: 'GOOD',
      color: '#f0b90b',
      description: 'Positive edge with room for improvement',
    };
  if (score >= 35)
    return {
      score,
      label: 'FAIR',
      color: '#f97316',
      description: 'Marginal edge — review risk management',
    };
  return {
    score,
    label: 'WEAK',
    color: '#f6465d',
    description: 'Below-average — strategy needs review',
  };
}

interface MiniMetricProps {
  label: string;
  value: string;
  trend?: 'up' | 'down' | 'neutral';
  color?: string;
}

function MiniMetric({ label, value, trend, color }: MiniMetricProps) {
  return (
    <div className='flex flex-col gap-0.5'>
      <span
        className='text-[9px] uppercase tracking-[0.15em] text-[var(--to-text-dim)]'
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        {label}
      </span>
      <div className='flex items-center gap-1'>
        <span
          className='text-sm font-bold tabular-nums'
          style={{
            color: color ?? 'var(--to-text-primary)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {value}
        </span>
        {trend === 'up' && <TrendingUp className='h-3 w-3 text-[#0ecb81]' />}
        {trend === 'down' && (
          <TrendingDown className='h-3 w-3 text-[#f6465d]' />
        )}
        {trend === 'neutral' && (
          <Minus className='h-3 w-3 text-[var(--to-text-dim)]' />
        )}
      </div>
    </div>
  );
}

export function PerformanceScoreCard(props: PerformanceScoreCardProps) {
  const {
    winRate,
    profitFactor,
    expectancy,
    sharpeRatio,
    sortinoRatio,
    maxDrawdownPct,
    totalTrades,
  } = props;
  const { score, label, color, description } = computeScore(props);

  const circumference = 2 * Math.PI * 46;
  const dashArray = `${(score / 100) * circumference} ${circumference}`;

  const metrics: MiniMetricProps[] = [
    {
      label: 'Win Rate',
      value: `${winRate.toFixed(1)}%`,
      trend: winRate >= 55 ? 'up' : winRate >= 45 ? 'neutral' : 'down',
      color: winRate >= 55 ? '#0ecb81' : winRate >= 45 ? '#f0b90b' : '#f6465d',
    },
    {
      label: 'Profit Factor',
      value: profitFactor >= 999 ? 'Inf' : profitFactor.toFixed(2),
      trend:
        profitFactor >= 1.5 ? 'up' : profitFactor >= 1 ? 'neutral' : 'down',
      color:
        profitFactor >= 1.5
          ? '#0ecb81'
          : profitFactor >= 1
          ? '#f0b90b'
          : '#f6465d',
    },
    {
      label: 'Expectancy',
      value: `$${expectancy.toFixed(2)}`,
      trend: expectancy > 0 ? 'up' : expectancy === 0 ? 'neutral' : 'down',
      color: expectancy > 0 ? '#0ecb81' : '#f6465d',
    },
    {
      label: 'Sharpe',
      value: sharpeRatio.toFixed(2),
      trend: sharpeRatio >= 1 ? 'up' : sharpeRatio >= 0 ? 'neutral' : 'down',
      color:
        sharpeRatio >= 1 ? '#0ecb81' : sharpeRatio >= 0 ? '#f0b90b' : '#f6465d',
    },
    {
      label: 'Sortino',
      value: sortinoRatio.toFixed(2),
      trend: sortinoRatio >= 1 ? 'up' : sortinoRatio >= 0 ? 'neutral' : 'down',
      color:
        sortinoRatio >= 1
          ? '#0ecb81'
          : sortinoRatio >= 0
          ? '#f0b90b'
          : '#f6465d',
    },
    {
      label: 'Max DD',
      value: `${maxDrawdownPct.toFixed(1)}%`,
      trend:
        maxDrawdownPct < 5 ? 'up' : maxDrawdownPct < 10 ? 'neutral' : 'down',
      color:
        maxDrawdownPct < 5
          ? '#0ecb81'
          : maxDrawdownPct < 10
          ? '#f0b90b'
          : '#f6465d',
    },
  ];

  return (
    <div
      className='tv-card relative overflow-hidden p-5'
      style={{ borderColor: `${color}20` }}
    >
      {/* Background glow */}
      <div
        className='pointer-events-none absolute inset-0 opacity-5'
        style={{
          background: `radial-gradient(ellipse at 10% 50%, ${color} 0%, transparent 60%)`,
        }}
      />

      <div className='relative flex flex-col gap-5 lg:flex-row lg:items-center'>
        {/* Score ring */}
        <div className='flex shrink-0 flex-col items-center gap-2'>
          <div className='relative flex items-center justify-center'>
            <svg width={120} height={120} viewBox='0 0 120 120'>
              {/* Track */}
              <circle
                cx={60}
                cy={60}
                r={46}
                fill='none'
                stroke='#1e2329'
                strokeWidth={8}
              />
              {/* Progress */}
              <circle
                cx={60}
                cy={60}
                r={46}
                fill='none'
                stroke={color}
                strokeWidth={8}
                strokeLinecap='round'
                strokeDasharray={dashArray}
                transform='rotate(-90 60 60)'
                style={{
                  transition: 'stroke-dasharray 0.8s ease',
                  filter: `drop-shadow(0 0 6px ${color}60)`,
                }}
              />
            </svg>
            <div className='absolute flex flex-col items-center'>
              <span
                className='text-[32px] font-black tabular-nums leading-none'
                style={{ color, fontFamily: 'var(--font-mono)' }}
              >
                {score}
              </span>
              <span
                className='mt-0.5 text-[9px] font-black uppercase tracking-[0.2em]'
                style={{ color, fontFamily: 'var(--font-mono)' }}
              >
                {label}
              </span>
            </div>
          </div>
          <div className='text-center'>
            <p
              className='text-[10px] text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-sans)' }}
            >
              {description}
            </p>
            <p
              className='mt-1 text-[9px] text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {totalTrades} closed trades
            </p>
          </div>
        </div>

        {/* Divider */}
        <div className='hidden h-24 w-px bg-[var(--to-border)] lg:block' />

        {/* Metrics grid */}
        <div className='grid flex-1 grid-cols-3 gap-x-6 gap-y-4 sm:grid-cols-6'>
          {metrics.map((m) => (
            <MiniMetric key={m.label} {...m} />
          ))}
        </div>
      </div>
    </div>
  );
}
