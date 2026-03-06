'use client';

import { useEffect, useMemo, useState } from 'react';
import { Activity, Clock3, Zap } from 'lucide-react';
import { cn } from '@/lib/utils';

type SessionId = 'sydney' | 'tokyo' | 'london' | 'newyork';

type SessionDef = {
  id: SessionId;
  name: string;
  city: string;
  startUtcH: number;
  endUtcH: number;
  accent: string;
  accentSoft: string;
  accentText: string;
  progressFrom: string;
  progressTo: string;
};

const SESSIONS: SessionDef[] = [
  {
    id: 'sydney',
    name: 'Sydney',
    city: 'Sydney',
    startUtcH: 22,
    endUtcH: 7,
    accent: 'rgba(34,211,238,0.45)',
    accentSoft: 'rgba(34,211,238,0.12)',
    accentText: '#67e8f9',
    progressFrom: '#0891b2',
    progressTo: '#22d3ee',
  },
  {
    id: 'tokyo',
    name: 'Tokyo',
    city: 'Tokyo',
    startUtcH: 0,
    endUtcH: 9,
    accent: 'rgba(59,130,246,0.45)',
    accentSoft: 'rgba(59,130,246,0.12)',
    accentText: '#93c5fd',
    progressFrom: '#2563eb',
    progressTo: '#60a5fa',
  },
  {
    id: 'london',
    name: 'London',
    city: 'London',
    startUtcH: 8,
    endUtcH: 17,
    accent: 'rgba(99,102,241,0.45)',
    accentSoft: 'rgba(99,102,241,0.12)',
    accentText: '#a5b4fc',
    progressFrom: '#4f46e5',
    progressTo: '#818cf8',
  },
  {
    id: 'newyork',
    name: 'New York',
    city: 'New York',
    startUtcH: 13,
    endUtcH: 22,
    accent: 'rgba(16,185,129,0.45)',
    accentSoft: 'rgba(16,185,129,0.12)',
    accentText: '#6ee7b7',
    progressFrom: '#059669',
    progressTo: '#34d399',
  },
];

type SessionState = SessionDef & {
  active: boolean;
  progressPct: number;
  remainingMs: number;
  startIL: string;
  endIL: string;
};

function utcSeconds(d: Date): number {
  return d.getUTCHours() * 3600 + d.getUTCMinutes() * 60 + d.getUTCSeconds();
}

function isWeekendClosedForex(now: Date): boolean {
  const day = now.getUTCDay(); // 0 Sun ... 6 Sat
  const hour = now.getUTCHours();

  if (day === 6) return true; // Saturday
  if (day === 5 && hour >= 22) return true; // Friday after 22:00 UTC
  if (day === 0 && hour < 22) return true; // Sunday before 22:00 UTC

  return false;
}

function isActiveSession(
  nowSec: number,
  startH: number,
  endH: number
): boolean {
  const start = startH * 3600;
  const end = endH * 3600;

  if (end <= start) {
    return nowSec >= start || nowSec < end;
  }
  return nowSec >= start && nowSec < end;
}

function getProgress(
  nowSec: number,
  startH: number,
  endH: number
): { progressPct: number; remainingMs: number } {
  const start = startH * 3600;
  const end = endH * 3600;

  if (end <= start) {
    const total = 24 * 3600 - start + end;
    const elapsed =
      nowSec >= start ? nowSec - start : 24 * 3600 - start + nowSec;
    const rem = Math.max(0, total - elapsed);
    return {
      progressPct: Math.max(0, Math.min(100, (elapsed / total) * 100)),
      remainingMs: rem * 1000,
    };
  }

  const total = end - start;
  const elapsed = Math.max(0, Math.min(total, nowSec - start));
  const rem = Math.max(0, total - elapsed);
  return {
    progressPct: Math.max(0, Math.min(100, (elapsed / total) * 100)),
    remainingMs: rem * 1000,
  };
}

function hms(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(
    sec
  ).padStart(2, '0')}`;
}

function hm(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m`;
  return `${m}m`;
}

function utcHourToIL(utcHour: number): string {
  const now = new Date();
  const utc = new Date(
    Date.UTC(
      now.getUTCFullYear(),
      now.getUTCMonth(),
      now.getUTCDate(),
      utcHour,
      0,
      0
    )
  );
  return utc.toLocaleTimeString('en-GB', {
    timeZone: 'Asia/Jerusalem',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

function ilClock(now: Date): string {
  return now.toLocaleTimeString('en-GB', {
    timeZone: 'Asia/Jerusalem',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

function ilDay(now: Date): string {
  return now.toLocaleDateString('en-GB', {
    timeZone: 'Asia/Jerusalem',
    weekday: 'short',
  });
}

function msToWeeklyOpen(now: Date): number {
  const day = now.getUTCDay();
  const nowSec = utcSeconds(now);
  const weekSec = day * 86400 + nowSec;
  const sundayOpenSec = 22 * 3600; // Sunday 22:00 UTC

  if (day === 0 && now.getUTCHours() < 22) {
    return (22 * 3600 - nowSec) * 1000;
  }

  const nextSundayOpen = 7 * 86400 + sundayOpenSec;
  return Math.max(0, (nextSundayOpen - weekSec) * 1000);
}

function MiniTimeline({ now }: { now: Date }) {
  const utcH =
    now.getUTCHours() + now.getUTCMinutes() / 60 + now.getUTCSeconds() / 3600;
  const markerPct = (utcH / 24) * 100;

  return (
    <div className='relative mt-2'>
      <div className='relative h-1.5 rounded-full bg-[#0b0d10] border border-white/5 overflow-hidden'>
        {SESSIONS.map((s) => (
          <div
            key={s.id}
            className='absolute top-0 h-full opacity-65'
            style={{
              left: `${(s.startUtcH / 24) * 100}%`,
              width: `${
                ((s.endUtcH > s.startUtcH
                  ? s.endUtcH - s.startUtcH
                  : 24 - s.startUtcH + s.endUtcH) /
                  24) *
                100
              }%`,
              background: `linear-gradient(90deg, ${s.progressFrom}, ${s.progressTo})`,
            }}
          />
        ))}
      </div>
      <div
        className='absolute top-1/2 -translate-y-1/2 w-[2px] h-3 bg-white rounded-full'
        style={{
          left: `${markerPct}%`,
          boxShadow: '0 0 8px rgba(255,255,255,0.8)',
        }}
      />
      <div className='mt-1 flex items-center justify-between text-[8px] text-zinc-500 font-mono'>
        <span>{utcHourToIL(0)} IL</span>
        <span>{utcHourToIL(8)} IL</span>
        <span>{utcHourToIL(16)} IL</span>
        <span>{utcHourToIL(22)} IL</span>
      </div>
    </div>
  );
}

export function MarketSessionBanner() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    const tick = () => setNow(new Date());
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const marketClosed = useMemo(
    () => (now ? isWeekendClosedForex(now) : false),
    [now]
  );

  const sessions = useMemo<SessionState[]>(() => {
    if (!now) return [];
    const sec = utcSeconds(now);

    return SESSIONS.map((s) => {
      const activeNow =
        !marketClosed && isActiveSession(sec, s.startUtcH, s.endUtcH);
      const p = activeNow
        ? getProgress(sec, s.startUtcH, s.endUtcH)
        : { progressPct: 0, remainingMs: 0 };
      return {
        ...s,
        active: activeNow,
        progressPct: p.progressPct,
        remainingMs: p.remainingMs,
        startIL: utcHourToIL(s.startUtcH),
        endIL: utcHourToIL(s.endUtcH),
      };
    });
  }, [now, marketClosed]);

  const london = sessions.find((s) => s.id === 'london')?.active ?? false;
  const ny = sessions.find((s) => s.id === 'newyork')?.active ?? false;
  const overlap = london && ny;
  const weeklyOpenMs = now && marketClosed ? msToWeeklyOpen(now) : 0;

  if (!now) return null;

  return (
    <section className='shrink-0 animate-fade-in-up'>
      <div className='relative overflow-hidden rounded-xl border border-[var(--to-border)] bg-[linear-gradient(135deg,var(--to-surface)_0%,var(--to-surface-raised)_100%)]'>
        <div
          className='absolute inset-x-0 top-0 h-[1px]'
          style={{
            background:
              'linear-gradient(90deg, rgba(34,211,238,0.4) 0%, rgba(99,102,241,0.5) 45%, rgba(16,185,129,0.45) 100%)',
          }}
        />

        <div className='p-3 pt-3.5'>
          <div className='flex items-center justify-between'>
            <div className='flex items-center gap-2'>
              <span className='inline-flex items-center gap-1 rounded-full border border-white/10 bg-black/20 px-2 py-0.5'>
                <Activity
                  className={cn(
                    'h-3 w-3',
                    marketClosed ? 'text-amber-400' : 'text-emerald-400'
                  )}
                />
                <span className='font-sans text-[9px] font-bold uppercase tracking-[0.16em] text-zinc-300'>
                  {marketClosed ? 'Market Closed (Weekend)' : 'Market Sessions'}
                </span>
              </span>

              {overlap && !marketClosed && (
                <span className='inline-flex items-center gap-1 rounded-full border border-amber-400/40 bg-amber-500/10 px-2 py-0.5'>
                  <Zap className='h-3 w-3 text-amber-300' />
                  <span className='font-sans text-[9px] font-bold uppercase tracking-[0.16em] text-amber-200'>
                    High Volume Overlap
                  </span>
                </span>
              )}

              {marketClosed && (
                <span className='rounded-full border border-amber-400/30 bg-amber-500/10 px-2 py-0.5 text-[9px] font-mono text-amber-200'>
                  Opens in {hm(weeklyOpenMs)}
                </span>
              )}
            </div>

            <div className='inline-flex items-center gap-1 rounded-lg border border-white/10 bg-black/20 px-2 py-1'>
              <Clock3 className='h-3 w-3 text-zinc-400' />
              <span className='font-mono text-[10px] text-zinc-300'>
                {ilDay(now)} {ilClock(now)} IL
              </span>
            </div>
          </div>

          <MiniTimeline now={now} />

          <div className='mt-2 grid grid-cols-1 gap-2 xl:grid-cols-4'>
            {sessions.map((s) => (
              <div
                key={s.id}
                className='relative overflow-hidden rounded-lg border border-white/8 bg-black/20 p-2.5 transition-all'
                style={
                  s.active
                    ? {
                        borderColor: s.accent,
                        background: `linear-gradient(180deg, ${s.accentSoft} 0%, rgba(0,0,0,0.18) 100%)`,
                      }
                    : undefined
                }
              >
                {s.active && (
                  <div
                    className='absolute inset-x-0 top-0 h-[1px]'
                    style={{
                      background: `linear-gradient(90deg, ${s.progressFrom}, ${s.progressTo})`,
                    }}
                  />
                )}

                <div className='flex items-center justify-between'>
                  <div>
                    <p
                      className={cn(
                        'font-sans text-[11px] font-semibold',
                        s.active ? 'text-white' : 'text-zinc-500'
                      )}
                    >
                      {s.name}
                    </p>
                    <p className='font-sans text-[9px] text-zinc-500'>
                      {s.city}
                    </p>
                  </div>
                  <span
                    className={cn(
                      'rounded-md border px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-widest',
                      s.active
                        ? 'border-emerald-400/30 text-emerald-300'
                        : marketClosed
                        ? 'border-amber-400/20 text-amber-300'
                        : 'border-white/10 text-zinc-500'
                    )}
                  >
                    {marketClosed ? 'Closed' : s.active ? 'Active' : 'Closed'}
                  </span>
                </div>

                <div className='mt-1 flex items-center justify-between'>
                  <span className='font-mono text-[9px] text-zinc-500'>
                    {s.startIL} → {s.endIL} IL
                  </span>
                  <span className='font-mono text-[9px] text-zinc-400'>
                    {s.active ? `${hm(s.remainingMs)} left` : '--'}
                  </span>
                </div>

                {s.active ? (
                  <div className='mt-1.5'>
                    <div className='h-1 rounded-full bg-[#0a0c10] border border-white/10 overflow-hidden'>
                      <div
                        className='h-full rounded-full'
                        style={{
                          width: `${Math.max(3, s.progressPct)}%`,
                          background: `linear-gradient(90deg, ${s.progressFrom}, ${s.progressTo})`,
                        }}
                      />
                    </div>
                    <div className='mt-1 flex items-center justify-between'>
                      <span
                        className='font-mono text-[9px]'
                        style={{ color: s.accentText }}
                      >
                        {Math.round(s.progressPct)}%
                      </span>
                      <span className='font-mono text-[9px] text-zinc-300'>
                        {hms(s.remainingMs)}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className='mt-1.5 h-1 rounded-full bg-[#0a0c10] border border-white/10' />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
