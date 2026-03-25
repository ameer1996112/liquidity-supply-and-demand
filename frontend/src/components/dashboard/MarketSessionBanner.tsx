'use client';

import { useEffect, useState, useMemo } from 'react';
import { Activity, Clock, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTimezone } from '@/providers/TimezoneProvider';

type Session = {
  id: string;
  name: string;
  city: string;
  startUtcH: number;
  endUtcH: number;
  accentColor: string;
  accentBg: string;
  textColor: string;
  gradientFrom: string;
  gradientTo: string;
};

const SESSIONS: Session[] = [
  {
    id: 'sydney',
    name: 'Sydney',
    city: 'Australia',
    startUtcH: 22,
    endUtcH: 7,
    accentColor: 'border-cyan-500/30',
    accentBg: 'bg-cyan-500',
    textColor: 'text-cyan-400',
    gradientFrom: 'from-cyan-950/40',
    gradientTo: 'to-cyan-900/10',
  },
  {
    id: 'tokyo',
    name: 'Tokyo',
    city: 'Japan',
    startUtcH: 0,
    endUtcH: 9,
    accentColor: 'border-blue-500/30',
    accentBg: 'bg-blue-500',
    textColor: 'text-blue-400',
    gradientFrom: 'from-blue-950/40',
    gradientTo: 'to-blue-900/10',
  },
  {
    id: 'london',
    name: 'London',
    city: 'United Kingdom',
    startUtcH: 8,
    endUtcH: 17,
    accentColor: 'border-indigo-500/30',
    accentBg: 'bg-indigo-500',
    textColor: 'text-indigo-400',
    gradientFrom: 'from-indigo-950/40',
    gradientTo: 'to-indigo-900/10',
  },
  {
    id: 'newyork',
    name: 'New York',
    city: 'United States',
    startUtcH: 13,
    endUtcH: 22,
    accentColor: 'border-[var(--to-long)]/30',
    accentBg: 'bg-emerald-500',
    textColor: 'text-[var(--to-long)]',
    gradientFrom: 'from-emerald-950/40',
    gradientTo: 'to-emerald-900/10',
  },
];

// Check if forex markets are closed (weekend)
function isForexWeekendClosed(date: Date): boolean {
  const day = date.getUTCDay(); // 0 = Sunday, 6 = Saturday
  const hour = date.getUTCHours();

  // Saturday is always closed
  if (day === 6) return true;

  // Friday after 22:00 UTC is closed
  if (day === 5 && hour >= 22) return true;

  // Sunday before 22:00 UTC is closed
  if (day === 0 && hour < 22) return true;

  return false;
}

function isSessionActive(
  nowUtcH: number,
  startUtcH: number,
  endUtcH: number,
  isWeekendClosed: boolean
): boolean {
  if (isWeekendClosed) return false;

  // Handle sessions that cross midnight
  if (endUtcH <= startUtcH) {
    return nowUtcH >= startUtcH || nowUtcH < endUtcH;
  }
  return nowUtcH >= startUtcH && nowUtcH < endUtcH;
}

function calculateSessionProgress(
  nowUtcH: number,
  startUtcH: number,
  endUtcH: number
): number {
  // Handle sessions that cross midnight
  if (endUtcH <= startUtcH) {
    const totalHours = 24 - startUtcH + endUtcH;
    const elapsedHours =
      nowUtcH >= startUtcH ? nowUtcH - startUtcH : 24 - startUtcH + nowUtcH;
    return Math.min(100, Math.max(0, (elapsedHours / totalHours) * 100));
  }

  const totalHours = endUtcH - startUtcH;
  const elapsedHours = nowUtcH - startUtcH;
  return Math.min(100, Math.max(0, (elapsedHours / totalHours) * 100));
}

// Time formatting is now handled by useTimezone() hook

function msToWeekendOpen(now: Date): number {
  const day = now.getUTCDay();
  const nowSec =
    now.getUTCHours() * 3600 + now.getUTCMinutes() * 60 + now.getUTCSeconds();

  // If Sunday before market open, calculate time until 22:00 UTC
  if (day === 0 && now.getUTCHours() < 22) {
    return (22 * 3600 - nowSec) * 1000;
  }

  // Otherwise calculate time until next Sunday 22:00 UTC
  const weekSec = day * 86400 + nowSec;
  const nextSundayOpenSec = 7 * 86400 + 22 * 3600;
  return Math.max(0, (nextSundayOpenSec - weekSec) * 1000);
}

function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const hours = Math.floor(totalSec / 3600);
  const minutes = Math.floor((totalSec % 3600) / 60);

  if (hours > 0) {
    return `${hours}h ${minutes.toString().padStart(2, '0')}m`;
  }
  return `${minutes}m`;
}

export function MarketSessionBanner() {
  const { formatTime, formatDate, utcHourToLocal, tzAbbr } = useTimezone();
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    const tick = () => setNow(new Date());
    tick(); // Initial call
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, []);

  const isWeekendClosed = useMemo(() => {
    return now ? isForexWeekendClosed(now) : false;
  }, [now]);

  const weekendOpenMs = useMemo(() => {
    return now && isWeekendClosed ? msToWeekendOpen(now) : 0;
  }, [now, isWeekendClosed]);

  if (!now) return null;

  const utcHours = now.getUTCHours();
  const utcMinutes = now.getUTCMinutes();
  const utcSeconds = now.getUTCSeconds();
  const utcDecimalHours = utcHours + utcMinutes / 60 + utcSeconds / 3600;

  const localTimeString = formatTime(now);
  const localDayString = formatDate(now, { weekday: 'short' });

  // Calculate session states
  const sessionStates = SESSIONS.map((session) => {
    const isActive = isSessionActive(
      utcDecimalHours,
      session.startUtcH,
      session.endUtcH,
      isWeekendClosed
    );
    const progress = isActive
      ? calculateSessionProgress(
          utcDecimalHours,
          session.startUtcH,
          session.endUtcH
        )
      : 0;
    return {
      ...session,
      isActive,
      progress,
      startLocal: utcHourToLocal(session.startUtcH),
      endLocal: utcHourToLocal(session.endUtcH),
    };
  });

  // Check for London-NY overlap (high volume period)
  const londonActive =
    sessionStates.find((s) => s.id === 'london')?.isActive || false;
  const nyActive =
    sessionStates.find((s) => s.id === 'newyork')?.isActive || false;
  const isHighVolumeOverlap = londonActive && nyActive;

  return (
    <section className='shrink-0'>
      <div className='rounded-md border border-zinc-800/80 bg-[#09090b] p-3'>
        {/* Header */}
        <div className='mb-3 flex items-center justify-between'>
          <div className='flex items-center gap-2 flex-wrap'>
            <div
              className={cn(
                'flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 transition-colors',
                isWeekendClosed
                  ? 'border-amber-800/30 bg-gradient-to-r from-amber-950/40 to-amber-900/10'
                  : 'border-zinc-800 bg-gradient-to-r from-zinc-900/40 to-zinc-800/10'
              )}
            >
              <Activity
                className={cn(
                  'h-3.5 w-3.5',
                  isWeekendClosed ? 'text-amber-400' : 'text-[var(--to-text-dim)]'
                )}
              />
              <span className='font-sans text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--to-text-secondary)]'>
                {isWeekendClosed
                  ? 'Market Closed (Weekend)'
                  : 'Market Sessions'}
              </span>
            </div>

            {isHighVolumeOverlap && !isWeekendClosed && (
              <div className='flex items-center gap-1.5 rounded-md border border-amber-800/30 bg-gradient-to-r from-amber-950/40 to-amber-900/10 px-2.5 py-1.5 animate-pulse'>
                <Activity className='h-3.5 w-3.5 text-amber-400' />
                <span className='font-sans text-[10px] font-medium uppercase tracking-[0.12em] text-amber-300'>
                  High Volume Overlap
                </span>
              </div>
            )}

            {isWeekendClosed && (
              <div className='flex items-center gap-1.5 rounded-md border border-amber-800/30 bg-gradient-to-r from-amber-950/40 to-amber-900/10 px-2.5 py-1.5'>
                <AlertTriangle className='h-3.5 w-3.5 text-amber-400' />
                <span className='font-mono text-[10px] font-medium text-amber-300'>
                  Opens in {formatDuration(weekendOpenMs)}
                </span>
              </div>
            )}
          </div>

          <div className='flex items-center gap-1.5 rounded-md border border-zinc-800 bg-gradient-to-r from-zinc-900/40 to-zinc-800/10 px-2.5 py-1.5'>
            <Clock className='h-3.5 w-3.5 text-[var(--to-text-dim)]' />
            <span className='font-mono text-[11px] font-medium text-[var(--to-text-secondary)]'>
              {localDayString} {localTimeString} {tzAbbr}
            </span>
          </div>
        </div>

        {/* Session Cards */}
        <div className='grid grid-cols-1 gap-3 xl:grid-cols-4'>
          {sessionStates.map((session) => (
            <div
              key={session.id}
              className={cn(
                'group relative overflow-hidden rounded-md border transition-all duration-300',
                'bg-gradient-to-br',
                session.gradientFrom,
                session.gradientTo,
                session.isActive ? session.accentColor : 'border-zinc-800/80',
                !session.isActive && 'opacity-75'
              )}
            >
              {/* Top accent line for active sessions */}
              {session.isActive && (
                <div
                  className={cn(
                    'absolute inset-x-0 top-0 h-[2px]',
                    session.accentBg
                  )}
                />
              )}

              <div className='p-3'>
                <div className='mb-2.5 flex items-center justify-between'>
                  <div>
                    {/* Stat-card style: uppercase + tracked label */}
                    <p
                      className={cn(
                        'text-[10px] font-semibold uppercase leading-none tracking-[0.12em]',
                        session.isActive ? 'text-[var(--to-text-primary)]' : 'text-[var(--to-text-dim)]'
                      )}
                      style={{ fontFamily: 'var(--font-sans)' }}
                    >
                      {session.name}
                    </p>
                    <p
                      className='mt-1 text-[11px] uppercase tracking-[0.08em] text-[var(--to-text-dim)]'
                      style={{ fontFamily: 'var(--font-sans)' }}
                    >
                      {session.city}
                    </p>
                  </div>

                  <div
                    className={cn(
                      'flex items-center gap-1.5 rounded-md border px-2 py-1',
                      session.isActive
                        ? cn(
                            'border-zinc-700/50 bg-black/20',
                            session.textColor
                          )
                        : isWeekendClosed
                        ? 'border-amber-900/30 bg-black/20 text-amber-700'
                        : 'border-zinc-800/50 bg-black/20 text-[var(--to-text-dim)]'
                    )}
                  >
                    {session.isActive && (
                      <span
                        className={cn(
                          'h-1.5 w-1.5 rounded-full animate-pulse',
                          session.accentBg
                        )}
                      />
                    )}
                    <span
                      className='text-[11px] font-bold uppercase tracking-[0.12em]'
                      style={{ fontFamily: 'var(--font-sans)' }}
                    >
                      {isWeekendClosed
                        ? 'Closed'
                        : session.isActive
                        ? 'Live'
                        : 'Closed'}
                    </span>
                  </div>
                </div>

                {/* Time range — font-mono to prevent jitter */}
                <div className='mb-2 flex items-center justify-between'>
                  <span
                    className='text-[10px] tabular-nums text-[var(--to-text-dim)]'
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    {session.startLocal} → {session.endLocal} {tzAbbr}
                  </span>
                  {session.isActive && (
                    <span
                      className={cn(
                        'text-[10px] font-medium tabular-nums',
                        session.textColor
                      )}
                      style={{ fontFamily: 'var(--font-mono)' }}
                    >
                      {Math.round(session.progress)}%
                    </span>
                  )}
                </div>

                {/* Progress bar - only shown for active sessions */}
                {session.isActive ? (
                  <div className='h-1 w-full overflow-hidden rounded-sm bg-black/30'>
                    <div
                      className={cn('h-full', session.accentBg)}
                      style={{ width: `${Math.max(3, session.progress)}%` }}
                    />
                  </div>
                ) : (
                  /* Empty progress bar placeholder for closed sessions */
                  <div className='h-1 w-full rounded-sm bg-black/30' />
                )}
              </div>

              {/* Subtle hover effect */}
              <div className='absolute inset-0 bg-gradient-to-t from-white/[0.03] to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100' />
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
