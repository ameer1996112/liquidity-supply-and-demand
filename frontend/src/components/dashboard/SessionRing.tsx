'use client';

import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import { FlashValue } from '@/components/ui/AnimatedNumber';

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
  return { name: 'Off', color: '#64748b' };
}

/**
 * Compact session P&L chip — fits inline in the dashboard header bar.
 * Shows: session dot · P&L value · thin progress bar toward daily target.
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

  const rawPct = dailyTarget > 0 ? pnl / dailyTarget : 0;
  const clampedPct = Math.min(Math.max(rawPct, 0), 1);

  const isPositive = pnl >= 0;
  const isTargetHit = pnl >= dailyTarget;
  const mainColor = isTargetHit
    ? '#f0b90b'
    : isPositive
    ? '#0ecb81'
    : '#f6465d';

  const pnlStr = `${pnl >= 0 ? '+' : ''}$${Math.abs(pnl).toFixed(2)}`;

  return (
    <div
      className={cn(
        'flex items-center gap-2 rounded-lg border px-2.5 py-1.5 transition-all',
        className
      )}
      style={{
        borderColor: `${mainColor}25`,
        backgroundColor: `${mainColor}08`,
        backdropFilter: 'blur(8px)',
      }}
    >
      {/* Session dot */}
      <span
        className='h-1.5 w-1.5 rounded-full flex-shrink-0'
        style={{
          backgroundColor: session.color,
          boxShadow: `0 0 4px ${session.color}`,
        }}
      />

      {/* Session name */}
      <span
        className='text-[9px] font-bold uppercase tracking-widest hidden sm:inline'
        style={{ color: session.color, fontFamily: 'var(--font-mono)' }}
      >
        {session.name}
      </span>

      {/* Divider */}
      <span className='h-3 w-px bg-white/10 hidden sm:inline-block' />

      {/* P&L value */}
      <FlashValue value={pnl}>
        <span
          className='text-[12px] font-bold tabular-nums leading-none'
          style={{ color: mainColor, fontFamily: 'var(--font-mono)' }}
        >
          {pnlStr}
        </span>
      </FlashValue>

      {/* Progress arc — thin vertical stack */}
      <div className='flex flex-col items-end gap-0.5'>
        {/* Mini arc bar */}
        <div className='w-14 h-1 rounded-full overflow-hidden bg-white/6'>
          <div
            className='h-full rounded-full transition-all duration-700'
            style={{
              width: `${clampedPct * 100}%`,
              backgroundColor: mainColor,
              boxShadow: `0 0 4px ${mainColor}80`,
            }}
          />
        </div>
        <span
          className='text-[8px] tabular-nums leading-none'
          style={{
            color: 'var(--to-text-dim)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {isTargetHit
            ? '✓ target'
            : `${(clampedPct * 100).toFixed(0)}% / $${dailyTarget}`}
        </span>
      </div>

      {/* Win/Loss counts — only if data available */}
      {(winCount != null || lossCount != null) && (
        <>
          <span className='h-3 w-px bg-white/10' />
          <span
            className='text-[9px] tabular-nums font-semibold'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            <span style={{ color: '#0ecb81' }}>{winCount ?? 0}W</span>
            <span className='text-[var(--to-text-dim)] mx-0.5'>/</span>
            <span style={{ color: '#f6465d' }}>{lossCount ?? 0}L</span>
          </span>
        </>
      )}
    </div>
  );
}
