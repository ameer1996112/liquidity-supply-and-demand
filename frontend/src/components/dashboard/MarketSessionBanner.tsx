'use client';

import { useEffect, useState, useMemo } from 'react';
import { Activity, Clock, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

type Session = {
  id: string;
  name: string;
  city: string;
  startUtcH: number;
  endUtcH: number;
  accentColor: string;
  accentBg: string;
};

const SESSIONS: Session[] = [
  {
    id: 'sydney',
    name: 'Sydney',
    city: 'Australia',
    startUtcH: 22,
    endUtcH: 7,
    accentColor: 'border-cyan-500/50',
    accentBg: 'bg-cyan-500',
  },
  {
    id: 'tokyo',
    name: 'Tokyo',
    city: 'Japan',
    startUtcH: 0,
    endUtcH: 9,
    accentColor: 'border-blue-500/50',
    accentBg: 'bg-blue-500',
  },
  {
    id: 'london',
    name: 'London',
    city: 'United Kingdom',
    startUtcH: 8,
    endUtcH: 17,
    accentColor: 'border-indigo-500/50',
    accentBg: 'bg-indigo-500',
  },
  {
    id: 'newyork',
    name: 'New York',
    city: 'United States',
    startUtcH: 13,
    endUtcH: 22,
    accentColor: 'border-emerald-500/50',
    accentBg: 'bg-emerald-500',
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

function formatIsraelTime(date: Date): string {
  return date.toLocaleTimeString('en-GB', {
    timeZone: 'Asia/Jerusalem',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

function formatIsraelDay(date: Date): string {
  return date.toLocaleDateString('en-GB', {
    timeZone: 'Asia/Jerusalem',
    weekday: 'short',
  });
}

function utcHourToIsraelTime(utcHour: number): string {
  const now = new Date();
  const date = new Date(
    Date.UTC(
      now.getUTCFullYear(),
      now.getUTCMonth(),
      now.getUTCDate(),
      utcHour,
      0,
      0
    )
  );

  return date.toLocaleTimeString('en-GB', {
    timeZone: 'Asia/Jerusalem',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

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

  const israelTimeString = formatIsraelTime(now);
  const israelDayString = formatIsraelDay(now);

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
      startIL: utcHourToIsraelTime(session.startUtcH),
      endIL: utcHourToIsraelTime(session.endUtcH),
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
      <div className='rounded-sm border border-white/5 bg-[#09090b] p-3'>
        {/* Header */}
        <div className='mb-3 flex items-center justify-between'>
          <div className='flex items-center gap-2 flex-wrap'>
            <span className='inline-flex items-center gap-1 rounded-sm border border-white/5 bg-[#121214] px-2 py-1'>
              <Activity
                className={cn(
                  'h-3 w-3',
                  isWeekendClosed ? 'text-amber-400' : 'text-zinc-400'
                )}
              />
              <span className='font-sans text-[10px] uppercase tracking-[0.12em] text-zinc-300'>
                {isWeekendClosed
                  ? 'Market Closed (Weekend)'
                  : 'Market Sessions'}
              </span>
            </span>

            {isHighVolumeOverlap && !isWeekendClosed && (
              <span className='inline-flex items-center gap-1 rounded-sm border border-amber-500/30 bg-[#121214] px-2 py-1 animate-pulse'>
                <Activity className='h-3 w-3 text-amber-400' />
                <span className='font-sans text-[10px] uppercase tracking-[0.12em] text-amber-300'>
                  High Volume Overlap
                </span>
              </span>
            )}

            {isWeekendClosed && (
              <span className='inline-flex items-center gap-1 rounded-sm border border-amber-500/30 bg-[#121214] px-2 py-1'>
                <AlertTriangle className='h-3 w-3 text-amber-400' />
                <span className='font-mono text-[10px] text-amber-300'>
                  Opens in {formatDuration(weekendOpenMs)}
                </span>
              </span>
            )}
          </div>

          <div className='inline-flex items-center gap-1 rounded-sm border border-white/5 bg-[#121214] px-2 py-1'>
            <Clock className='h-3 w-3 text-zinc-400' />
            <span className='font-mono text-[11px] text-zinc-300'>
              {israelDayString} {israelTimeString} IL
            </span>
          </div>
        </div>

        {/* Session Cards */}
        <div className='grid grid-cols-1 gap-2 xl:grid-cols-4'>
          {sessionStates.map((session) => (
            <div
              key={session.id}
              className={cn(
                'rounded-sm border bg-[#121214] px-3 py-2',
                'border-white/5',
                session.isActive ? session.accentColor : 'border-white/5',
                !session.isActive && 'opacity-60'
              )}
            >
              <div className='mb-1 flex items-center justify-between'>
                <div>
                  <p
                    className={cn(
                      'font-sans text-[12px] leading-none',
                      session.isActive ? 'text-white' : 'text-zinc-500'
                    )}
                  >
                    {session.name}
                  </p>
                  <p className='font-sans text-[10px] text-zinc-500'>
                    {session.city}
                  </p>
                </div>

                <span
                  className={cn(
                    'rounded-sm border px-1.5 py-0.5 font-sans text-[9px] uppercase tracking-[0.12em]',
                    session.isActive
                      ? 'border-emerald-500/30 text-emerald-300'
                      : isWeekendClosed
                      ? 'border-amber-500/25 text-amber-300'
                      : 'border-white/5 text-zinc-500'
                  )}
                >
                  {isWeekendClosed
                    ? 'Closed'
                    : session.isActive
                    ? 'Open'
                    : 'Closed'}
                </span>
              </div>

              <div className='mb-1.5 flex items-center justify-between'>
                <span className='font-mono text-[10px] text-zinc-500'>
                  {session.startIL} → {session.endIL} IL
                </span>
                {session.isActive && (
                  <span
                    className={cn(
                      'font-mono text-[10px]',
                      session.isActive ? 'text-zinc-300' : 'text-zinc-500'
                    )}
                  >
                    {Math.round(session.progress)}% elapsed
                  </span>
                )}
              </div>

              {/* Progress bar - only shown for active sessions */}
              {session.isActive ? (
                <div className='h-1 w-full overflow-hidden rounded-none border border-white/10 bg-[#09090b]'>
                  <div
                    className={session.accentBg}
                    style={{
                      width: `${Math.max(3, session.progress)}%`,
                      height: '100%',
                    }}
                  />
                </div>
              ) : (
                /* Empty progress bar placeholder for closed sessions */
                <div className='h-1 w-full border border-white/10 bg-[#09090b]' />
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
