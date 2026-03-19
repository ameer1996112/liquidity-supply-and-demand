'use client';

import { CheckCircle, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { computeHealthScore } from './propFirmUtils';

interface HealthScoreGaugeProps {
  dailyPct: number;
  dailyLimitPct: number;
  trailingPct: number;
  trailingLimitPct: number;
  consistencyPct: number;
  consistencyLimitPct: number;
  safeToTrade: boolean;
  currentProfitPct: number;
}

export function HealthScoreGauge({
  dailyPct,
  dailyLimitPct,
  trailingPct,
  trailingLimitPct,
  consistencyPct,
  consistencyLimitPct,
  safeToTrade,
  currentProfitPct,
}: HealthScoreGaugeProps) {
  const healthScore = computeHealthScore(
    dailyPct,
    dailyLimitPct,
    trailingPct,
    trailingLimitPct,
    consistencyPct,
    consistencyLimitPct,
    safeToTrade,
    currentProfitPct
  );

  const color =
    healthScore > 80
      ? '#0ecb81'
      : healthScore > 50
      ? '#f0b90b'
      : '#f6465d';

  const label =
    healthScore > 80
      ? 'Excellent'
      : healthScore > 50
      ? 'Caution'
      : 'At Risk';

  return (
    <div className='tv-card p-6'>
      <div className='flex flex-col items-center'>
        <h3 className='text-[13px] font-bold text-[var(--to-text-dim)] uppercase tracking-widest font-mono mb-4'>
          Challenge Health
        </h3>

        <div className='relative'>
          <div className='absolute inset-0 flex items-center justify-center'>
            <div className='text-center'>
              <div
                className='text-[32px] font-bold font-mono'
                style={{ color }}
              >
                {healthScore}
              </div>
              <div className='text-[11px] text-[var(--to-text-dim)] mt-1'>{label}</div>
            </div>
          </div>
          <svg width='180' height='180' viewBox='0 0 100 100'>
            <circle
              cx='50'
              cy='50'
              r='45'
              fill='none'
              stroke='#1e2329'
              strokeWidth='8'
            />
            <circle
              cx='50'
              cy='50'
              r='45'
              fill='none'
              stroke={color}
              strokeWidth='8'
              strokeLinecap='round'
              strokeDasharray={`${healthScore * 2.83} ${
                283 - healthScore * 2.83
              }`}
              strokeDashoffset='70'
              style={{
                transition: 'stroke-dasharray 0.6s ease, stroke 0.4s ease',
                filter: `drop-shadow(0 0 4px ${color}60)`,
              }}
            />
          </svg>
        </div>

        <div className='mt-4 text-center'>
          <div className='text-[13px]'>
            {safeToTrade ? (
              <div className='flex items-center justify-center gap-1.5 text-[#0ecb81]'>
                <CheckCircle className='h-4 w-4' />
                <span>Safe to Trade</span>
              </div>
            ) : (
              <div className='flex items-center justify-center gap-1.5 text-[#f6465d]'>
                <AlertTriangle className='h-4 w-4' />
                <span>Trading Restricted</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
