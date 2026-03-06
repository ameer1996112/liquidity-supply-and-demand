'use client';

import { useEffect, useMemo, useState } from 'react';
import { cn } from '@/lib/utils';
import { Clock3, Zap, MoonStar, Globe2 } from 'lucide-react';

// ── Session definitions in UTC ───────────────────────────────────────────────
const SESSIONS = [
  {
    id: 'asian',
    name: 'Asian',
    city: 'Tokyo',
    emoji: '🌏',
    startH: 0,
    endH: 9,
    color: '#8b5cf6',
  },
  {
    id: 'london',
    name: 'London',
    city: 'London',
    emoji: '🇬🇧',
    startH: 7,
    endH: 16,
    color: '#3b82f6',
  },
  {
    id: 'newyork',
    name: 'New York',
    city: 'New York',
    emoji: '🗽',
    startH: 13,
    endH: 22,
    color: '#0ecb81',
  },
] as const;

type Session = (typeof SESSIONS)[number];

// Friday close / Sunday open convention in UTC
const WEEKLY_MARKET_OPEN_UTC_DAY = 0; // Sunday
const WEEKLY_MARKET_OPEN_UTC_HOUR = 22; // 22:00 UTC (typical FX reopen)
const WEEKLY_MARKET_CLOSE_UTC_DAY = 5; // Friday
const WEEKLY_MARKET_CLOSE_UTC_HOUR = 22; // 22:00 UTC close

const SWAP_UTC_HOUR = 22;

// ── Time helpers ──────────────────────────────────────────────────────────────
function utcDecimalHours(d: Date) {
  return d.getUTCHours() + d.getUTCMinutes() / 60 + d.getUTCSeconds() / 3600;
}

function utcSecondsOfDay(d: Date) {
  return d.getUTCHours() * 3600 + d.getUTCMinutes() * 60 + d.getUTCSeconds();
}

function getILDecimalHours(date: Date): number {
  const ilStr = date.toLocaleString('en-US', {
    timeZone: 'Asia/Jerusalem',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
  const [hStr, mStr, sStr] = ilStr.split(':');
  const h = parseInt(hStr, 10);
  const m = parseInt(mStr, 10);
  const s = parseInt(sStr, 10);
  return h + m / 60 + s / 3600;
}

function getILOffset(date: Date): number {
  const utcH = utcDecimalHours(date);
  const ilH = getILDecimalHours(date);
  let offset = ilH - utcH;
  if (offset > 12) offset -= 24;
  if (offset < -12) offset += 24;
  return Math.round(offset);
}

function utcHToIL(utcH: number, ilOffset: number): number {
  return (utcH + ilOffset + 24) % 24;
}

function formatILTime(date: Date): string {
  return date.toLocaleTimeString('en-GB', {
    timeZone: 'Asia/Jerusalem',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

function formatILDay(date: Date): string {
  return date.toLocaleDateString('en-GB', {
    timeZone: 'Asia/Jerusalem',
    weekday: 'short',
  });
}

function pad2(n: number) {
  return String(n).padStart(2, '0');
}

function msToHMS(ms: number) {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  return { h, m, s };
}

function formatHMShort(ms: number) {
  const { h, m } = msToHMS(ms);
  if (h > 0) return `${h}h ${pad2(m)}m`;
  return `${m}m`;
}

// ── Market state helpers ─────────────────────────────────────────────────────
function isMarketClosedWeekend(now: Date): boolean {
  const day = now.getUTCDay(); // 0=Sun ... 5=Fri ... 6=Sat
  const sec = utcSecondsOfDay(now);
  const closeSec = WEEKLY_MARKET_CLOSE_UTC_HOUR * 3600;
  const openSec = WEEKLY_MARKET_OPEN_UTC_HOUR * 3600;

  // Sat all day closed
  if (day === 6) return true;
  // Fri after close closed
  if (day === WEEKLY_MARKET_CLOSE_UTC_DAY && sec >= closeSec) return true;
  // Sun before open closed
  if (day === WEEKLY_MARKET_OPEN_UTC_DAY && sec < openSec) return true;

  return false;
}

function msToWeeklyOpen(now: Date): number {
  const current = new Date(now);
  let target = new Date(now);

  // start from this week's Sunday 22:00 UTC
  const day = current.getUTCDay();
  const diffToSunday = (7 - day) % 7;
  target.setUTCDate(current.getUTCDate() + diffToSunday);
  target.setUTCHours(WEEKLY_MARKET_OPEN_UTC_HOUR, 0, 0, 0);

  // if already past target, go next week
  if (target.getTime() <= current.getTime()) {
    target.setUTCDate(target.getUTCDate() + 7);
  }

  return Math.max(0, target.getTime() - current.getTime());
}

function isSessionActive(session: Session, utcH: number) {
  return utcH >= session.startH && utcH < session.endH;
}

function getActiveSessions(utcH: number) {
  return SESSIONS.filter((s) => isSessionActive(s, utcH));
}

function getSessionProgressPct(session: Session, utcH: number) {
  if (!isSessionActive(session, utcH)) return 0;
  return ((utcH - session.startH) / (session.endH - session.startH)) * 100;
}

function getSessionRemainingMs(session: Session, now: Date) {
  const endSec = session.endH * 3600;
  const nowSec = utcSecondsOfDay(now);
  return Math.max(0, (endSec - nowSec) * 1000);
}

function getNextSessionOpenMs(now: Date): number {
  const nowSec = utcSecondsOfDay(now);
  const nowH = utcDecimalHours(now);
  const sorted = [...SESSIONS].sort((a, b) => a.startH - b.startH);

  for (const s of sorted) {
    if (nowH < s.startH) {
      return (s.startH * 3600 - nowSec) * 1000;
    }
  }

  // next day first session
  return (24 * 3600 - nowSec + sorted[0].startH * 3600) * 1000;
}

function getSwapMs(now: Date) {
  const nowSec = utcSecondsOfDay(now);
  const swapSec = SWAP_UTC_HOUR * 3600;
  let diff = swapSec - nowSec;
  if (diff <= 0) diff += 86400;
  return diff * 1000;
}

// ── Compact visual pieces ─────────────────────────────────────────────────────
function MiniTimeline({ utcH, ilOffset }: { utcH: number; ilOffset: number }) {
  const markerPct = (utcH / 24) * 100;

  return (
    <div className='relative'>
      <div className='relative h-[4px] rounded-full bg-[var(--to-surface-raised)] overflow-hidden'>
        {SESSIONS.map((s) => (
          <div
            key={s.id}
            className='absolute top-0 h-full opacity-70'
            style={{
              left: `${(s.startH / 24) * 100}%`,
              width: `${((s.endH - s.startH) / 24) * 100}%`,
              background: s.color,
            }}
          />
        ))}
        <div
          className='absolute top-1/2 -translate-y-1/2 h-[12px] w-[2px] rounded-full bg-white'
          style={{
            left: `${markerPct}%`,
            boxShadow: '0 0 10px rgba(255,255,255,0.8)',
          }}
        />
      </div>

      <div className='mt-1.5 flex justify-between text-[8px] text-[var(--to-text-dim)]'>
        {[0, 12, 24].map((h) => (
          <span key={h} style={{ fontFamily: 'var(--font-mono)' }}>
            {pad2(utcHToIL(h % 24, ilOffset))}:00 IL
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export function MarketSessionBanner() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    const tick = () => setNow(new Date());
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const model = useMemo(() => {
    if (!now) return null;

    const utcH = utcDecimalHours(now);
    const ilOffset = getILOffset(now);
    const ilTimeStr = formatILTime(now);
    const ilDay = formatILDay(now);
    const ilSwapHour = utcHToIL(SWAP_UTC_HOUR, ilOffset);

    const weekendClosed = isMarketClosedWeekend(now);
    const activeSessions = weekendClosed ? [] : getActiveSessions(utcH);
    const primary = activeSessions[0] ?? null;
    const overlap = activeSessions.length > 1;

    const swapMs = weekendClosed ? null : getSwapMs(now);
    const nextOpenMs = weekendClosed
      ? msToWeeklyOpen(now)
      : getNextSessionOpenMs(now);

    let statusTone: 'open' | 'warn' | 'closed' = 'open';
    if (weekendClosed) statusTone = 'closed';
    else if (activeSessions.length === 0) statusTone = 'warn';

    return {
      now,
      utcH,
      ilOffset,
      ilTimeStr,
      ilDay,
      ilSwapHour,
      weekendClosed,
      activeSessions,
      primary,
      overlap,
      statusTone,
      swapMs,
      nextOpenMs,
    };
  }, [now]);

  if (!model) return null;

  const toneClasses = {
    open: {
      border: 'rgba(14,203,129,0.25)',
      bg: 'linear-gradient(135deg, rgba(14,203,129,0.08), rgba(14,203,129,0.03))',
      dot: 'bg-[#0ecb81]',
      text: 'text-[#0ecb81]',
    },
    warn: {
      border: 'rgba(240,185,11,0.28)',
      bg: 'linear-gradient(135deg, rgba(240,185,11,0.08), rgba(240,185,11,0.03))',
      dot: 'bg-[#f0b90b]',
      text: 'text-[#f0b90b]',
    },
    closed: {
      border: 'rgba(139,149,165,0.3)',
      bg: 'linear-gradient(135deg, rgba(139,149,165,0.08), rgba(139,149,165,0.03))',
      dot: 'bg-[#8b95a5]',
      text: 'text-[#8b95a5]',
    },
  }[model.statusTone];

  const primarySessionProgress =
    model.primary != null
      ? getSessionProgressPct(model.primary, model.utcH)
      : 0;
  const primaryRemaining =
    model.primary != null
      ? getSessionRemainingMs(model.primary, model.now)
      : null;

  return (
    <section
      className='shrink-0 animate-fade-in-up'
      style={{ animationDelay: '10ms' }}
    >
      <div
        className='relative rounded-xl border px-3 py-2 overflow-hidden'
        style={{
          borderColor: 'var(--to-border)',
          background:
            'linear-gradient(135deg, rgba(13,17,23,0.96) 0%, rgba(22,27,34,0.92) 100%)',
        }}
      >
        <div className='absolute inset-x-0 top-0 h-[1px] bg-gradient-to-r from-[#8b5cf6]/40 via-[#3b82f6]/40 to-[#0ecb81]/40' />

        <div className='grid grid-cols-1 gap-2 xl:grid-cols-[1.8fr_auto] xl:items-center'>
          {/* left: compact pulse */}
          <div className='space-y-2'>
            <div className='flex items-center justify-between'>
              <div className='flex items-center gap-2 min-w-0'>
                <div
                  className='inline-flex items-center gap-1 rounded-md border px-2 py-0.5'
                  style={{
                    borderColor: toneClasses.border,
                    background: toneClasses.bg,
                  }}
                >
                  <span
                    className={cn('h-1.5 w-1.5 rounded-full', toneClasses.dot)}
                  />
                  <span
                    className={cn(
                      'text-[9px] font-bold uppercase tracking-[0.12em]',
                      toneClasses.text
                    )}
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    Market Pulse
                  </span>
                </div>

                {model.overlap && (
                  <span
                    className='inline-flex items-center gap-1 rounded-md border border-amber-400/30 bg-amber-400/10 px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-widest text-amber-300'
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    <Zap className='h-2.5 w-2.5' />
                    Overlap
                  </span>
                )}
              </div>

              <div
                className='text-[9px] text-[var(--to-text-dim)] tabular-nums'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {model.ilDay} {model.ilTimeStr} IL
              </div>
            </div>

            <div className='flex items-center gap-2 flex-wrap'>
              {model.weekendClosed ? (
                <>
                  <MoonStar className='h-3.5 w-3.5 text-[var(--to-text-secondary)]' />
                  <span className='text-[11px] font-semibold text-[var(--to-text-primary)]'>
                    Market Closed (Weekend)
                  </span>
                  <span
                    className='text-[10px] text-[var(--to-text-secondary)] tabular-nums'
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    Opens in {formatHMShort(model.nextOpenMs)}
                  </span>
                </>
              ) : model.primary ? (
                <>
                  <Globe2
                    className='h-3.5 w-3.5'
                    style={{ color: model.primary.color }}
                  />
                  <span
                    className='text-[11px] font-semibold'
                    style={{ color: model.primary.color }}
                  >
                    {model.primary.name} Session Live
                  </span>
                  <span
                    className='text-[10px] tabular-nums'
                    style={{
                      color: model.primary.color,
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {Math.round(primarySessionProgress)}% ·{' '}
                    {primaryRemaining ? formatHMShort(primaryRemaining) : '—'}{' '}
                    left
                  </span>
                </>
              ) : (
                <>
                  <Clock3 className='h-3.5 w-3.5 text-amber-300' />
                  <span className='text-[11px] font-semibold text-amber-300'>
                    Market open, waiting next session
                  </span>
                  <span
                    className='text-[10px] text-amber-200/90 tabular-nums'
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    Starts in {formatHMShort(model.nextOpenMs)}
                  </span>
                </>
              )}
            </div>

            <MiniTimeline utcH={model.utcH} ilOffset={model.ilOffset} />
          </div>

          {/* right: compact swap pod */}
          <div
            className='rounded-lg border px-2.5 py-2 min-w-[128px]'
            style={{
              borderColor: model.weekendClosed
                ? 'rgba(139,149,165,0.25)'
                : 'rgba(14,203,129,0.28)',
              background: model.weekendClosed
                ? 'rgba(139,149,165,0.04)'
                : 'rgba(14,203,129,0.05)',
            }}
          >
            <div className='flex items-center justify-between gap-2'>
              <span
                className='text-[8px] uppercase tracking-[0.12em] text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                Swap
              </span>
              <span
                className='text-[8px] text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {pad2(model.ilSwapHour)}:00 IL
              </span>
            </div>

            {model.weekendClosed ? (
              <p
                className='mt-1 text-[10px] text-[var(--to-text-secondary)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                Paused on weekend
              </p>
            ) : (
              <p
                className='mt-1 text-[14px] font-extrabold tabular-nums text-[#0ecb81]'
                style={{
                  fontFamily: 'var(--font-mono)',
                  textShadow: '0 0 10px rgba(14,203,129,0.45)',
                }}
              >
                {(() => {
                  const s = msToHMS(model.swapMs ?? 0);
                  return `${pad2(s.h)}:${pad2(s.m)}:${pad2(s.s)}`;
                })()}
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
