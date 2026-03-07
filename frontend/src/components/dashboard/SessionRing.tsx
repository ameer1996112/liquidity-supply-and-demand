'use client';

import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { AnimatedNumber, FlashValue } from '@/components/ui/AnimatedNumber';
import { CheckCircle2, TrendingUp, TrendingDown, Target } from 'lucide-react';

interface SessionRingProps {
  todayPnl: number | null | undefined;
  dailyTarget?: number;
  winCount?: number;
  lossCount?: number;
  className?: string;
}

/** Detect current trading session from UTC hour */
function getCurrentSession(): { name: string; color: string } {
  const hour = new Date().getUTCHours();
  if (hour >= 0 && hour < 7) return { name: 'Tokyo', color: '#3b82f6' };
  if (hour >= 7 && hour < 12) return { name: 'London', color: '#0ecb81' };
  if (hour >= 12 && hour < 17) return { name: 'NY', color: '#f0b90b' };
  if (hour >= 17 && hour < 21) return { name: 'NY Close', color: '#a78bfa' };
  return { name: 'Off-Hours', color: '#64748b' };
}

/**
 * Premium session performance widget.
 * Shows today's P&L progress toward a daily target with an arc gauge,
 * animated numbers, win/loss counts, and session indicator.
 */
export function SessionRing({
  todayPnl,
  dailyTarget = 200,
  winCount,
  lossCount,
  className,
}: SessionRingProps) {
  const pnl = todayPnl ?? 0;
  const session = useMemo(() => getCurrentSession(), []);

  // Arc geometry — 240° sweep (like a speedometer)
  const SIZE = 96;
  const cx = SIZE / 2;
  const cy = SIZE / 2;
  const R = 38;
  const SWEEP_DEG = 240;
  const START_DEG = 150; // starts bottom-left
  const toRad = (d: number) => (d * Math.PI) / 180;

  const arcPath = (startDeg: number, sweepDeg: number, r: number) => {
    const s = toRad(startDeg);
    const e = toRad(startDeg + sweepDeg);
    const x1 = cx + r * Math.cos(s);
    const y1 = cy + r * Math.sin(s);
    const x2 = cx + r * Math.cos(e);
    const y2 = cy + r * Math.sin(e);
    const large = sweepDeg > 180 ? 1 : 0;
    return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
  };

  const rawPct = dailyTarget > 0 ? pnl / dailyTarget : 0;
  const clampedPct = Math.min(Math.max(rawPct, 0), 1);
  const fillSweep = clampedPct * SWEEP_DEG;

  const isPositive = pnl >= 0;
  const isTargetHit = pnl >= dailyTarget;
  const isLoss = pnl < 0;

  const mainColor = isTargetHit
    ? '#f0b90b'
    : isPositive
    ? '#0ecb81'
    : '#f6465d';

  const remaining = dailyTarget - pnl;
  const pctDisplay = Math.abs(rawPct * 100);

  // Circumference of the arc for stroke-dasharray
  const arcLength = (SWEEP_DEG / 360) * 2 * Math.PI * R;
  const fillLength = clampedPct * arcLength;

  return (
    <div
      className={cn(
        'relative flex items-center gap-3 rounded-2xl border px-4 py-3 overflow-hidden',
        isTargetHit
          ? 'border-[#f0b90b]/30 bg-[#f0b90b]/6'
          : isPositive
          ? 'border-[#0ecb81]/20 bg-[#0ecb81]/5'
          : 'border-[#f6465d]/20 bg-[#f6465d]/5',
        className
      )}
      style={{
        backdropFilter: 'blur(12px)',
        boxShadow: isTargetHit
          ? '0 0 24px rgba(240,185,11,0.12), inset 0 1px 0 rgba(255,255,255,0.04)'
          : isPositive
          ? '0 0 20px rgba(14,203,129,0.08), inset 0 1px 0 rgba(255,255,255,0.04)'
          : '0 0 20px rgba(246,70,93,0.08), inset 0 1px 0 rgba(255,255,255,0.04)',
      }}
    >
      {/* Subtle background gradient */}
      <div
        className='pointer-events-none absolute inset-0 opacity-30'
        style={{
          background: `radial-gradient(ellipse at 20% 50%, ${mainColor}18 0%, transparent 70%)`,
        }}
      />

      {/* Arc gauge */}
      <div className='relative shrink-0' style={{ width: SIZE, height: SIZE }}>
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
          {/* Track arc */}
          <path
            d={arcPath(START_DEG, SWEEP_DEG, R)}
            fill='none'
            stroke='rgba(255,255,255,0.06)'
            strokeWidth={6}
            strokeLinecap='round'
          />

          {/* Fill arc — uses stroke-dasharray trick */}
          <path
            d={arcPath(START_DEG, SWEEP_DEG, R)}
            fill='none'
            stroke={mainColor}
            strokeWidth={6}
            strokeLinecap='round'
            strokeDasharray={`${fillLength} ${arcLength}`}
            style={{
              transition: 'stroke-dasharray 1s cubic-bezier(0.4,0,0.2,1)',
              filter: `drop-shadow(0 0 5px ${mainColor}90)`,
            }}
          />

          {/* Tick marks at 25%, 50%, 75% */}
          {[0.25, 0.5, 0.75].map((t) => {
            const angle = toRad(START_DEG + t * SWEEP_DEG);
            const inner = R - 5;
            const outer = R + 1;
            return (
              <line
                key={t}
                x1={cx + inner * Math.cos(angle)}
                y1={cy + inner * Math.sin(angle)}
                x2={cx + outer * Math.cos(angle)}
                y2={cy + outer * Math.sin(angle)}
                stroke='rgba(255,255,255,0.15)'
                strokeWidth={1.5}
                strokeLinecap='round'
              />
            );
          })}
        </svg>

        {/* Center content */}
        <div className='absolute inset-0 flex flex-col items-center justify-center gap-0.5'>
          {isTargetHit ? (
            <CheckCircle2 className='h-4 w-4' style={{ color: mainColor }} />
          ) : isPositive ? (
            <TrendingUp className='h-3.5 w-3.5' style={{ color: mainColor }} />
          ) : (
            <TrendingDown
              className='h-3.5 w-3.5'
              style={{ color: mainColor }}
            />
          )}
          <span
            className='text-[9px] font-bold uppercase tracking-widest'
            style={{ color: mainColor, fontFamily: 'var(--font-mono)' }}
          >
            {isTargetHit ? 'HIT!' : `${pctDisplay.toFixed(0)}%`}
          </span>
        </div>
      </div>

      {/* Right side: labels */}
      <div className='flex flex-col gap-1 min-w-0 relative z-10'>
        {/* Session badge */}
        <div className='flex items-center gap-1.5'>
          <span
            className='h-1.5 w-1.5 rounded-full flex-shrink-0'
            style={{
              backgroundColor: session.color,
              boxShadow: `0 0 5px ${session.color}`,
            }}
          />
          <span
            className='text-[9px] font-bold uppercase tracking-[0.18em]'
            style={{ color: session.color, fontFamily: 'var(--font-mono)' }}
          >
            {session.name}
          </span>
        </div>

        {/* P&L value */}
        <FlashValue value={pnl}>
          <span
            className='text-[22px] font-bold tabular-nums leading-none'
            style={{ color: mainColor, fontFamily: 'var(--font-mono)' }}
          >
            {pnl >= 0 ? '+' : ''}
            <AnimatedNumber
              value={pnl}
              format={(v) =>
                v.toLocaleString('en-US', {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })
              }
              duration={600}
            />
          </span>
        </FlashValue>

        {/* Target progress */}
        <div className='flex flex-col gap-1'>
          <div className='flex items-center justify-between gap-3'>
            <span
              className='text-[9px] text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {isTargetHit
                ? `+$${(pnl - dailyTarget).toFixed(0)} over target`
                : `$${remaining.toFixed(0)} to $${dailyTarget}`}
            </span>
            <Target className='h-2.5 w-2.5 text-[var(--to-text-dim)] flex-shrink-0' />
          </div>

          {/* Progress bar */}
          <div className='h-1 w-full rounded-full bg-white/5 overflow-hidden'>
            <div
              className='h-full rounded-full transition-all duration-700'
              style={{
                width: `${Math.min(clampedPct * 100, 100)}%`,
                backgroundColor: mainColor,
                boxShadow: `0 0 6px ${mainColor}80`,
              }}
            />
          </div>
        </div>

        {/* Win / Loss counts */}
        {(winCount != null || lossCount != null) && (
          <div className='flex items-center gap-2 mt-0.5'>
            {winCount != null && (
              <span
                className='text-[9px] font-semibold tabular-nums'
                style={{ color: '#0ecb81', fontFamily: 'var(--font-mono)' }}
              >
                {winCount}W
              </span>
            )}
            {lossCount != null && (
              <span
                className='text-[9px] font-semibold tabular-nums'
                style={{ color: '#f6465d', fontFamily: 'var(--font-mono)' }}
              >
                {lossCount}L
              </span>
            )}
            {winCount != null &&
              lossCount != null &&
              winCount + lossCount > 0 && (
                <span
                  className='text-[9px] text-[var(--to-text-dim)]'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {((winCount / (winCount + lossCount)) * 100).toFixed(0)}% WR
                </span>
              )}
          </div>
        )}
      </div>
    </div>
  );
}
