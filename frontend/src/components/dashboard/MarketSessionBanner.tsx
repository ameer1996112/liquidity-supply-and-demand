'use client';

import { useEffect, useState } from 'react';
import { Activity, Clock, Globe } from 'lucide-react';
import { cn } from '@/lib/utils';

type Session = {
  id: string;
  name: string;
  city: string;
  startUtcH: number;
  endUtcH: number;
  accentColor: string;
};

const SESSIONS: Session[] = [
  {
    id: 'sydney',
    name: 'Sydney',
    city: 'Australia',
    startUtcH: 22,
    endUtcH: 7,
    accentColor: 'border-cyan-500/50',
  },
  {
    id: 'tokyo',
    name: 'Tokyo',
    city: 'Japan',
    startUtcH: 0,
    endUtcH: 9,
    accentColor: 'border-blue-500/50',
  },
  {
    id: 'london',
    name: 'London',
    city: 'United Kingdom',
    startUtcH: 8,
    endUtcH: 17,
    accentColor: 'border-indigo-500/50',
  },
  {
    id: 'newyork',
    name: 'New York',
    city: 'United States',
    startUtcH: 13,
    endUtcH: 22,
    accentColor: 'border-emerald-500/50',
  },
];

function isSessionActive(
  nowUtcH: number,
  startUtcH: number,
  endUtcH: number
): boolean {
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

function formatUtcTime(
  hours: number,
  minutes: number,
  seconds: number
): string {
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(
    2,
    '0'
  )}:${String(seconds).padStart(2, '0')}`;
}

export function MarketSessionBanner() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    const tick = () => setNow(new Date());
    tick(); // Initial call
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, []);

  if (!now) return null;

  const utcHours = now.getUTCHours();
  const utcMinutes = now.getUTCMinutes();
  const utcSeconds = now.getUTCSeconds();
  const utcDecimalHours = utcHours + utcMinutes / 60 + utcSeconds / 3600;

  const utcTimeString = formatUtcTime(utcHours, utcMinutes, utcSeconds);

  // Calculate session states
  const sessionStates = SESSIONS.map((session) => {
    const isActive = isSessionActive(
      utcDecimalHours,
      session.startUtcH,
      session.endUtcH
    );
    const progress = isActive
      ? calculateSessionProgress(
          utcDecimalHours,
          session.startUtcH,
          session.endUtcH
        )
      : 0;
    return { ...session, isActive, progress };
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
          <div className='flex items-center gap-2'>
            <span className='inline-flex items-center gap-1 rounded-sm border border-white/5 bg-[#121214] px-2 py-1'>
              <Activity className='h-3 w-3 text-zinc-400' />
              <span className='font-sans text-[10px] uppercase tracking-[0.12em] text-zinc-300'>
                Market Sessions
              </span>
            </span>

            {isHighVolumeOverlap && (
              <span className='inline-flex items-center gap-1 rounded-sm border border-amber-500/30 bg-[#121214] px-2 py-1 animate-pulse'>
                <Activity className='h-3 w-3 text-amber-400' />
                <span className='font-sans text-[10px] uppercase tracking-[0.12em] text-amber-300'>
                  High Volume Overlap
                </span>
              </span>
            )}
          </div>

          <div className='inline-flex items-center gap-1 rounded-sm border border-white/5 bg-[#121214] px-2 py-1'>
            <Clock className='h-3 w-3 text-zinc-400' />
            <span className='font-mono text-[11px] text-zinc-300'>
              {utcTimeString} UTC
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
                      : 'border-white/5 text-zinc-500'
                  )}
                >
                  {session.isActive ? 'Open' : 'Closed'}
                </span>
              </div>

              <div className='mb-1.5 flex items-center justify-between'>
                <span className='font-mono text-[10px] text-zinc-500'>
                  {String(session.startUtcH).padStart(2, '0')}:00 →{' '}
                  {String(session.endUtcH).padStart(2, '0')}:00 UTC
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
              {session.isActive && (
                <div className='h-1 w-full overflow-hidden rounded-none border border-white/10 bg-[#09090b]'>
                  <div
                    className={cn(
                      'h-full bg-emerald-500',
                      session.id === 'sydney' && 'bg-cyan-500',
                      session.id === 'tokyo' && 'bg-blue-500',
                      session.id === 'london' && 'bg-indigo-500',
                      session.id === 'newyork' && 'bg-emerald-500'
                    )}
                    style={{ width: `${Math.max(3, session.progress)}%` }}
                  />
                </div>
              )}

              {/* Empty progress bar placeholder for closed sessions */}
              {!session.isActive && (
                <div className='h-1 w-full border border-white/10 bg-[#09090b]' />
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
