'use client';

import { useEffect, useMemo, useState } from 'react';
import { Activity, Clock, Timer } from 'lucide-react';

type SessionDef = {
  id: 'sydney' | 'tokyo' | 'london' | 'newyork';
  label: string;
  city: string;
  startHourUtc: number;
  endHourUtc: number;
  accent: string;
};

const SESSIONS: SessionDef[] = [
  {
    id: 'sydney',
    label: 'Sydney',
    city: 'Sydney',
    startHourUtc: 22,
    endHourUtc: 7,
    accent: 'border-l-cyan-500',
  },
  {
    id: 'tokyo',
    label: 'Tokyo',
    city: 'Tokyo',
    startHourUtc: 0,
    endHourUtc: 9,
    accent: 'border-l-sky-500',
  },
  {
    id: 'london',
    label: 'London',
    city: 'London',
    startHourUtc: 8,
    endHourUtc: 17,
    accent: 'border-l-indigo-500',
  },
  {
    id: 'newyork',
    label: 'New York',
    city: 'New York',
    startHourUtc: 13,
    endHourUtc: 22,
    accent: 'border-l-emerald-500',
  },
];

type SessionState = SessionDef & {
  active: boolean;
  progressPct: number;
  remainingMs: number;
  startDisplayUtc: string;
  endDisplayUtc: string;
};

function utcSeconds(now: Date): number {
  return (
    now.getUTCHours() * 3600 + now.getUTCMinutes() * 60 + now.getUTCSeconds()
  );
}

function toUtcLabel(hour: number): string {
  return `${String(hour).padStart(2, '0')}:00`;
}

function isSessionActive(
  nowSec: number,
  startHourUtc: number,
  endHourUtc: number
): boolean {
  const start = startHourUtc * 3600;
  const end = endHourUtc * 3600;

  // overnight session
  if (end <= start) {
    return nowSec >= start || nowSec < end;
  }

  return nowSec >= start && nowSec < end;
}

function computeSessionProgress(
  nowSec: number,
  startHourUtc: number,
  endHourUtc: number
): { progressPct: number; remainingMs: number } {
  const start = startHourUtc * 3600;
  const end = endHourUtc * 3600;

  if (end <= start) {
    const total = 24 * 3600 - start + end;
    const elapsed =
      nowSec >= start ? nowSec - start : 24 * 3600 - start + nowSec;
    const remaining = Math.max(0, total - elapsed);
    return {
      progressPct: Math.max(0, Math.min(100, (elapsed / total) * 100)),
      remainingMs: remaining * 1000,
    };
  }

  const total = end - start;
  const elapsed = Math.max(0, Math.min(total, nowSec - start));
  const remaining = Math.max(0, total - elapsed);

  return {
    progressPct: Math.max(0, Math.min(100, (elapsed / total) * 100)),
    remainingMs: remaining * 1000,
  };
}

function formatDurationHMS(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(
    s
  ).padStart(2, '0')}`;
}

function formatDurationHM(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m`;
  return `${m}m`;
}

export function MarketSessionBanner() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    const tick = () => setNow(new Date());
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const sessionStates = useMemo<SessionState[]>(() => {
    if (!now) return [];

    const sec = utcSeconds(now);

    return SESSIONS.map((s) => {
      const active = isSessionActive(sec, s.startHourUtc, s.endHourUtc);
      const { progressPct, remainingMs } = active
        ? computeSessionProgress(sec, s.startHourUtc, s.endHourUtc)
        : { progressPct: 0, remainingMs: 0 };

      return {
        ...s,
        active,
        progressPct,
        remainingMs,
        startDisplayUtc: toUtcLabel(s.startHourUtc),
        endDisplayUtc: toUtcLabel(s.endHourUtc),
      };
    });
  }, [now]);

  const isLondonActive =
    sessionStates.find((s) => s.id === 'london')?.active ?? false;
  const isNyActive =
    sessionStates.find((s) => s.id === 'newyork')?.active ?? false;
  const isOverlap = isLondonActive && isNyActive;

  const nowUtcLabel = now
    ? now.toLocaleTimeString('en-GB', {
        timeZone: 'UTC',
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
    : '--:--:--';

  return (
    <section className='shrink-0 animate-fade-in-up'>
      <div className='rounded-sm border border-white/5 bg-[#09090b] p-3'>
        <div className='mb-2 flex items-center justify-between'>
          <div className='flex items-center gap-2'>
            <span className='inline-flex items-center gap-1 rounded-sm border border-white/5 bg-[#121214] px-2 py-1'>
              <Activity className='h-3 w-3 text-zinc-300' />
              <span className='font-sans text-[10px] uppercase tracking-[0.12em] text-zinc-300'>
                Market Sessions
              </span>
            </span>

            {isOverlap && (
              <span className='inline-flex items-center gap-1 rounded-sm border border-amber-500/40 bg-[#121214] px-2 py-1'>
                <Activity className='h-3 w-3 text-amber-400' />
                <span className='font-sans text-[10px] uppercase tracking-[0.12em] text-amber-300'>
                  High Volume / Overlap
                </span>
              </span>
            )}
          </div>

          <div className='inline-flex items-center gap-1 rounded-sm border border-white/5 bg-[#121214] px-2 py-1'>
            <Clock className='h-3 w-3 text-zinc-400' />
            <span className='font-mono text-[11px] text-zinc-300'>
              {nowUtcLabel} UTC
            </span>
          </div>
        </div>

        <div className='grid grid-cols-1 gap-2 xl:grid-cols-4'>
          {sessionStates.map((s) => (
            <div
              key={s.id}
              className={[
                'rounded-sm border bg-[#121214] px-3 py-2',
                'border-white/5',
                'border-l-2',
                s.active ? s.accent : 'border-l-white/5',
              ].join(' ')}
            >
              <div className='mb-1 flex items-center justify-between'>
                <div>
                  <p
                    className={[
                      'font-sans text-[12px] leading-none',
                      s.active ? 'text-white' : 'text-zinc-500',
                    ].join(' ')}
                  >
                    {s.label}
                  </p>
                  <p className='font-sans text-[10px] text-zinc-500'>
                    {s.city}
                  </p>
                </div>

                <span
                  className={[
                    'rounded-sm border px-1.5 py-0.5 font-sans text-[9px] uppercase tracking-[0.12em]',
                    s.active
                      ? 'border-emerald-500/30 text-emerald-300'
                      : 'border-white/5 text-zinc-500',
                  ].join(' ')}
                >
                  {s.active ? 'Active' : 'Closed'}
                </span>
              </div>

              <div className='mb-1.5 flex items-center justify-between'>
                <span className='font-mono text-[10px] text-zinc-500'>
                  {s.startDisplayUtc} → {s.endDisplayUtc} UTC
                </span>
                {s.active ? (
                  <span className='font-mono text-[10px] text-zinc-200'>
                    {formatDurationHM(s.remainingMs)} left
                  </span>
                ) : (
                  <span className='font-mono text-[10px] text-zinc-500'>
                    --
                  </span>
                )}
              </div>

              {s.active ? (
                <div>
                  <div className='h-1 w-full overflow-hidden rounded-none border border-white/10 bg-[#09090b]'>
                    <div
                      className='h-full bg-white'
                      style={{
                        width: `${Math.max(3, s.progressPct)}%`,
                      }}
                    />
                  </div>
                  <div className='mt-1 flex items-center justify-between'>
                    <span className='font-mono text-[10px] text-zinc-400'>
                      {Math.round(s.progressPct)}%
                    </span>
                    <span className='inline-flex items-center gap-1 font-mono text-[10px] text-zinc-300'>
                      <Timer className='h-3 w-3 text-zinc-400' />
                      {formatDurationHMS(s.remainingMs)}
                    </span>
                  </div>
                </div>
              ) : (
                <div className='h-1 w-full border border-white/10 bg-[#09090b]' />
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
