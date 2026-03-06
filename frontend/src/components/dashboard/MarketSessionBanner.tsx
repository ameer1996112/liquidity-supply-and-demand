'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { Zap, Clock } from 'lucide-react';

// ── Session definitions (UTC hours) ──────────────────────────────────────────
const SESSIONS = [
  {
    id: 'asian',
    name: 'Asian',
    city: 'Tokyo',
    emoji: '🌏',
    startH: 0,
    endH: 9,
    color: '#8b5cf6',
    border: 'rgba(139,92,246,0.45)',
    bg: 'rgba(139,92,246,0.07)',
    glow: '0 0 18px rgba(139,92,246,0.45), 0 0 36px rgba(139,92,246,0.15)',
    barGradient: 'linear-gradient(90deg, #7c3aed, #8b5cf6, #a78bfa)',
    textColor: '#a78bfa',
    dimTextColor: 'rgba(167,139,250,0.45)',
    timelineBg: 'rgba(139,92,246,0.35)',
  },
  {
    id: 'london',
    name: 'London',
    city: 'London',
    emoji: '🇬🇧',
    startH: 7,
    endH: 16,
    color: '#3b82f6',
    border: 'rgba(59,130,246,0.45)',
    bg: 'rgba(59,130,246,0.07)',
    glow: '0 0 18px rgba(59,130,246,0.45), 0 0 36px rgba(59,130,246,0.15)',
    barGradient: 'linear-gradient(90deg, #1d4ed8, #3b82f6, #60a5fa)',
    textColor: '#60a5fa',
    dimTextColor: 'rgba(96,165,250,0.45)',
    timelineBg: 'rgba(59,130,246,0.35)',
  },
  {
    id: 'newyork',
    name: 'New York',
    city: 'New York',
    emoji: '🗽',
    startH: 13,
    endH: 22,
    color: '#0ecb81',
    border: 'rgba(14,203,129,0.45)',
    bg: 'rgba(14,203,129,0.07)',
    glow: '0 0 18px rgba(14,203,129,0.45), 0 0 36px rgba(14,203,129,0.15)',
    barGradient: 'linear-gradient(90deg, #059669, #0ecb81, #34d399)',
    textColor: '#34d399',
    dimTextColor: 'rgba(52,211,153,0.45)',
    timelineBg: 'rgba(14,203,129,0.35)',
  },
] as const;

type Session = (typeof SESSIONS)[number];

// Swap/rollover: 22:00 UTC (≈ 5 PM New York EST)
const SWAP_UTC_HOUR = 22;

// ── Helpers ───────────────────────────────────────────────────────────────────
function utcDecimalHours(d: Date) {
  return d.getUTCHours() + d.getUTCMinutes() / 60 + d.getUTCSeconds() / 3600;
}

/** Returns current Israel (Asia/Jerusalem) time as decimal hours 0–24 */
function getILDecimalHours(date: Date): number {
  const ilStr = date.toLocaleString('en-US', {
    timeZone: 'Asia/Jerusalem',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
  // format: "HH:MM:SS"
  const [hStr, mStr, sStr] = ilStr.split(':');
  const h = parseInt(hStr, 10);
  const m = parseInt(mStr, 10);
  const s = parseInt(sStr, 10);
  return h + m / 60 + s / 3600;
}

/** Returns Israel UTC offset in whole hours (+2 or +3 for DST) */
function getILOffset(date: Date): number {
  const utcH = utcDecimalHours(date);
  const ilH = getILDecimalHours(date);
  let offset = ilH - utcH;
  if (offset > 12) offset -= 24;
  if (offset < -12) offset += 24;
  return Math.round(offset);
}

/** Convert a UTC hour (0–23) to Israel hour, wrapping at 24 */
function utcHToIL(utcH: number, ilOffset: number): number {
  return (utcH + ilOffset + 24) % 24;
}

/** Format Israel time string from a Date */
function formatILTime(date: Date): string {
  return date.toLocaleTimeString('en-GB', {
    timeZone: 'Asia/Jerusalem',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

function isSessionActive(s: Session, utcH: number) {
  return utcH >= s.startH && utcH < s.endH;
}

function getSessionProgress(s: Session, utcH: number) {
  if (!isSessionActive(s, utcH)) return 0;
  return ((utcH - s.startH) / (s.endH - s.startH)) * 100;
}

function getRemainingMs(endH: number, now: Date) {
  const endSec = endH * 3600;
  const nowSec =
    now.getUTCHours() * 3600 + now.getUTCMinutes() * 60 + now.getUTCSeconds();
  return Math.max(0, (endSec - nowSec) * 1000);
}

function getOpensInMs(startH: number, endH: number, now: Date) {
  const nowSec =
    now.getUTCHours() * 3600 + now.getUTCMinutes() * 60 + now.getUTCSeconds();
  const startSec = startH * 3600;
  const endSec = endH * 3600;
  if (nowSec >= startSec && nowSec < endSec) return 0;
  let diff = startSec - nowSec;
  if (diff <= 0) diff += 86400;
  return diff * 1000;
}

function getSwapMs(now: Date) {
  const nowSec =
    now.getUTCHours() * 3600 + now.getUTCMinutes() * 60 + now.getUTCSeconds();
  const swapSec = SWAP_UTC_HOUR * 3600;
  let diff = swapSec - nowSec;
  if (diff <= 0) diff += 86400;
  return diff * 1000;
}

function msToHMS(ms: number) {
  const totalSec = Math.floor(ms / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  return { h, m, s };
}

function pad2(n: number) {
  return String(n).padStart(2, '0');
}

function formatHM(ms: number) {
  const { h, m } = msToHMS(ms);
  if (h > 0) return `${h}h ${pad2(m)}m`;
  return `${m}m`;
}

// ── 24h Timeline Bar ──────────────────────────────────────────────────────────
interface TimelineBarProps {
  utcH: number;
  ilOffset: number;
  ilTimeStr: string;
}

function TimelineBar({ utcH, ilOffset, ilTimeStr }: TimelineBarProps) {
  const markerPct = (utcH / 24) * 100;

  // IL hour labels: show IL time at UTC 0, 6, 12, 18, 24
  const ilLabels = [0, 6, 12, 18, 24].map((h) => ({
    utcH: h,
    ilH: utcHToIL(h, ilOffset),
  }));

  return (
    <div className='relative mb-4'>
      {/* Track */}
      <div className='relative h-[5px] rounded-full bg-[var(--to-surface-raised)] overflow-hidden'>
        {/* Session bands */}
        {SESSIONS.map((s) => (
          <div
            key={s.id}
            className='absolute top-0 h-full opacity-50'
            style={{
              left: `${(s.startH / 24) * 100}%`,
              width: `${((s.endH - s.startH) / 24) * 100}%`,
              background: s.barGradient,
            }}
          />
        ))}
        {/* Overlap highlight: London + NY (13-16 UTC) */}
        <div
          className='absolute top-0 h-full opacity-70'
          style={{
            left: `${(13 / 24) * 100}%`,
            width: `${(3 / 24) * 100}%`,
            background:
              'linear-gradient(90deg, rgba(240,185,11,0.6), rgba(240,185,11,0.8))',
          }}
        />
      </div>

      {/* Current time marker — sits above the track */}
      <div
        className='absolute top-1/2 -translate-y-1/2 z-10'
        style={{ left: `${markerPct}%` }}
      >
        <div className='relative -translate-x-1/2'>
          <div className='w-[3px] h-[14px] rounded-full bg-white shadow-[0_0_8px_rgba(255,255,255,0.9),0_0_16px_rgba(255,255,255,0.4)]' />
          {/* Tooltip — shows Israel time */}
          <div
            className='absolute -top-6 left-1/2 -translate-x-1/2 text-[8px] font-bold text-white/80 whitespace-nowrap bg-[var(--to-surface-raised)] border border-white/10 px-1.5 py-0.5 rounded'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {ilTimeStr} IL
          </div>
        </div>
      </div>

      {/* Hour labels — Israel time */}
      <div className='flex justify-between mt-1.5 px-0'>
        {ilLabels.map(({ utcH: h, ilH }) => (
          <span
            key={h}
            className='text-[8px] text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {pad2(ilH)}:00
          </span>
        ))}
      </div>

      {/* Session labels on timeline */}
      <div className='relative h-3 mt-0.5'>
        {SESSIONS.map((s) => {
          const midPct = ((s.startH + s.endH) / 2 / 24) * 100;
          return (
            <span
              key={s.id}
              className='absolute text-[7px] font-bold uppercase tracking-widest -translate-x-1/2'
              style={{
                left: `${midPct}%`,
                color: s.dimTextColor,
                fontFamily: 'var(--font-mono)',
              }}
            >
              {s.name}
            </span>
          );
        })}
        {/* Overlap label */}
        <span
          className='absolute text-[7px] font-bold uppercase tracking-widest -translate-x-1/2'
          style={{
            left: `${((13 + 1.5) / 24) * 100}%`,
            color: 'rgba(240,185,11,0.6)',
            fontFamily: 'var(--font-mono)',
          }}
        >
          overlap
        </span>
      </div>
    </div>
  );
}

// ── Session Card ──────────────────────────────────────────────────────────────
function ProgressRing({
  progress,
  color,
  label,
}: {
  progress: number;
  color: string;
  label: string;
}) {
  const size = 44;
  const stroke = 4;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, progress));
  const dashOffset = circumference * (1 - clamped / 100);

  return (
    <div className='relative shrink-0'>
      <svg width={size} height={size} className='-rotate-90'>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill='transparent'
          stroke='rgba(255,255,255,0.08)'
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill='transparent'
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap='round'
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          style={{
            transition: 'stroke-dashoffset 700ms ease-out',
            filter: `drop-shadow(0 0 4px ${color}88)`,
          }}
        />
      </svg>
      <div
        className='absolute inset-0 flex items-center justify-center text-[9px] font-bold tabular-nums'
        style={{ color, fontFamily: 'var(--font-mono)' }}
      >
        {label}
      </div>
    </div>
  );
}

interface SessionCardProps {
  session: Session;
  utcH: number;
  now: Date;
  ilOffset: number;
}

function SessionCard({ session: s, utcH, now, ilOffset }: SessionCardProps) {
  const active = isSessionActive(s, utcH);
  const progress = getSessionProgress(s, utcH);
  const remainingMs = active ? getRemainingMs(s.endH, now) : 0;
  const opensInMs = !active ? getOpensInMs(s.startH, s.endH, now) : 0;

  // Convert session UTC hours to Israel time for display
  const ilStartH = utcHToIL(s.startH, ilOffset);
  const ilEndH = utcHToIL(s.endH, ilOffset);

  const ringLabel = `${Math.round(progress)}%`;

  return (
    <div
      className={cn(
        'relative flex-1 min-w-0 rounded-xl border p-3 transition-all duration-700 overflow-hidden',
        'flex flex-col gap-2'
      )}
      style={
        active
          ? {
              borderColor: s.border,
              background: s.bg,
              boxShadow: s.glow,
            }
          : {
              borderColor: 'var(--to-border)',
              background: 'var(--to-surface)',
            }
      }
    >
      {/* Shimmer sweep on active */}
      {active && (
        <div className='pointer-events-none absolute inset-0 overflow-hidden rounded-xl'>
          <div
            className='absolute inset-y-0 w-1/3 opacity-20'
            style={{
              background: `linear-gradient(90deg, transparent, ${s.color}, transparent)`,
              animation: 'shimmer-scan 3s ease-in-out infinite',
            }}
          />
        </div>
      )}

      {/* Header row */}
      <div className='flex items-center justify-between'>
        <div className='flex items-center gap-1.5'>
          <span className='text-base leading-none'>{s.emoji}</span>
          <div>
            <p
              className='text-[10px] font-bold uppercase tracking-[0.12em] leading-none'
              style={{
                color: active ? s.textColor : 'var(--to-text-dim)',
                fontFamily: 'var(--font-sans)',
              }}
            >
              {s.name}
            </p>
            <p
              className='text-[8px] mt-0.5 leading-none'
              style={{
                color: active ? s.dimTextColor : 'var(--to-text-dim)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              {s.city}
            </p>
          </div>
        </div>

        {/* Status badge */}
        <div
          className={cn(
            'flex items-center gap-1 rounded-full px-2 py-0.5 text-[8px] font-bold uppercase tracking-widest border'
          )}
          style={
            active
              ? {
                  background: `${s.color}18`,
                  borderColor: `${s.color}40`,
                  color: s.textColor,
                }
              : {
                  background: 'rgba(255,255,255,0.03)',
                  borderColor: 'var(--to-border)',
                  color: 'var(--to-text-dim)',
                }
          }
        >
          {active && (
            <span
              className='w-1.5 h-1.5 rounded-full animate-pulse'
              style={{ background: s.color }}
            />
          )}
          {active ? 'LIVE' : 'CLOSED'}
        </div>
      </div>

      {/* Ring progress (active) or opens-in (inactive) */}
      {active ? (
        <div className='flex items-center gap-2'>
          <ProgressRing progress={progress} color={s.color} label={ringLabel} />
          <div className='min-w-0 flex-1 space-y-0.5'>
            <p
              className='text-[8px]'
              style={{
                color: s.dimTextColor,
                fontFamily: 'var(--font-mono)',
              }}
            >
              {pad2(ilStartH)}:00 → {pad2(ilEndH)}:00 IL
            </p>
            <p
              className='text-[10px] font-bold tabular-nums'
              style={{
                color: s.textColor,
                fontFamily: 'var(--font-mono)',
              }}
            >
              {formatHM(remainingMs)} left
            </p>
          </div>
        </div>
      ) : (
        <div className='flex items-center justify-between'>
          <span
            className='text-[8px]'
            style={{
              color: 'var(--to-text-dim)',
              fontFamily: 'var(--font-mono)',
            }}
          >
            {pad2(ilStartH)}:00 – {pad2(ilEndH)}:00 IL
          </span>
          <span
            className='text-[9px] tabular-nums'
            style={{
              color: 'var(--to-text-dim)',
              fontFamily: 'var(--font-mono)',
            }}
          >
            Opens in {formatHM(opensInMs)}
          </span>
        </div>
      )}
    </div>
  );
}

// ── Overlap Badge ─────────────────────────────────────────────────────────────
function OverlapBadge() {
  return (
    <div
      className='shrink-0 flex flex-col items-center justify-center rounded-xl border px-3 py-2 gap-1'
      style={{
        borderColor: 'rgba(240,185,11,0.4)',
        background: 'rgba(240,185,11,0.06)',
        boxShadow:
          '0 0 16px rgba(240,185,11,0.3), 0 0 32px rgba(240,185,11,0.1)',
      }}
    >
      <Zap className='h-4 w-4 text-amber-400 animate-pulse' />
      <span
        className='text-[8px] font-bold uppercase tracking-widest text-amber-400 text-center leading-tight'
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        HIGH
        <br />
        VOL
      </span>
    </div>
  );
}

// ── Swap Countdown ────────────────────────────────────────────────────────────
interface SwapCountdownProps {
  swapMs: number;
  ilSwapHour: number;
}

function SwapCountdown({ swapMs, ilSwapHour }: SwapCountdownProps) {
  const { h, m, s } = msToHMS(swapMs);

  // Urgency levels
  const isUrgent = swapMs < 30 * 60 * 1000; // < 30 min
  const isWarning = swapMs < 2 * 60 * 60 * 1000; // < 2 hours

  const color = isUrgent ? '#f6465d' : isWarning ? '#f0b90b' : '#0ecb81';

  const glow = isUrgent
    ? '0 0 16px rgba(246,70,93,0.5), 0 0 32px rgba(246,70,93,0.2)'
    : isWarning
    ? '0 0 16px rgba(240,185,11,0.4), 0 0 32px rgba(240,185,11,0.15)'
    : '0 0 12px rgba(14,203,129,0.3)';

  const border = isUrgent
    ? 'rgba(246,70,93,0.4)'
    : isWarning
    ? 'rgba(240,185,11,0.35)'
    : 'rgba(14,203,129,0.25)';

  const bg = isUrgent
    ? 'rgba(246,70,93,0.07)'
    : isWarning
    ? 'rgba(240,185,11,0.06)'
    : 'rgba(14,203,129,0.05)';

  return (
    <div
      className='shrink-0 flex flex-col items-center justify-center rounded-xl border px-4 py-3 gap-1 min-w-[110px] transition-all duration-700'
      style={{
        borderColor: border,
        background: bg,
        boxShadow: glow,
      }}
    >
      <div className='flex items-center gap-1.5 mb-0.5'>
        <Clock className='h-3 w-3' style={{ color, opacity: 0.8 }} />
        <span
          className='text-[8px] font-bold uppercase tracking-widest'
          style={{ color, opacity: 0.8, fontFamily: 'var(--font-mono)' }}
        >
          Swap In
        </span>
      </div>

      {/* Countdown */}
      <div
        className={cn(
          'text-[1.1rem] font-bold tabular-nums leading-none tracking-tight',
          isUrgent && 'animate-pulse'
        )}
        style={{
          color,
          fontFamily: 'var(--font-mono)',
          textShadow: `0 0 12px ${color}80`,
        }}
      >
        {pad2(h)}:{pad2(m)}:{pad2(s)}
      </div>

      <span
        className='text-[7px] mt-0.5'
        style={{
          color: 'var(--to-text-dim)',
          fontFamily: 'var(--font-mono)',
        }}
      >
        {pad2(ilSwapHour)}:00 IL daily
      </span>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
export function MarketSessionBanner() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    const tick = () => setNow(new Date());
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  if (!now) return null;

  const utcH = utcDecimalHours(now);
  const ilOffset = getILOffset(now);
  const ilTimeStr = formatILTime(now);
  const ilSwapHour = utcHToIL(SWAP_UTC_HOUR, ilOffset);

  const activeSessions = SESSIONS.filter((s) => isSessionActive(s, utcH));
  const isOverlap = activeSessions.length > 1;
  const swapMs = getSwapMs(now);

  return (
    <section
      className='shrink-0 animate-fade-in-up'
      style={{ animationDelay: '20ms' }}
    >
      {/* Card wrapper */}
      <div
        className='relative rounded-xl border overflow-hidden'
        style={{
          borderColor: 'var(--to-border)',
          background:
            'linear-gradient(135deg, var(--to-surface) 0%, var(--to-surface-raised) 100%)',
        }}
      >
        {/* Top accent line */}
        <div
          className='absolute inset-x-0 top-0 h-[1px]'
          style={{
            background:
              'linear-gradient(90deg, rgba(139,92,246,0.4) 0%, rgba(59,130,246,0.5) 33%, rgba(240,185,11,0.6) 55%, rgba(14,203,129,0.5) 100%)',
          }}
        />

        <div className='p-3 pt-4'>
          {/* Header row */}
          <div className='flex items-center justify-between mb-3'>
            <div className='flex items-center gap-2'>
              <span
                className='text-[9px] font-bold uppercase tracking-[0.18em] text-[var(--to-text-dim)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                Market Sessions
              </span>
              {isOverlap && (
                <span
                  className='inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[7px] font-bold uppercase tracking-widest border animate-pulse'
                  style={{
                    borderColor: 'rgba(240,185,11,0.4)',
                    background: 'rgba(240,185,11,0.08)',
                    color: '#f0b90b',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  <Zap className='h-2.5 w-2.5' />
                  {activeSessions.length} sessions overlap · peak volatility
                </span>
              )}
            </div>
            <span
              className='text-[8px] text-[var(--to-text-dim)]'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              IL {ilTimeStr}
            </span>
          </div>

          {/* Timeline */}
          <TimelineBar utcH={utcH} ilOffset={ilOffset} ilTimeStr={ilTimeStr} />

          {/* Session cards + swap */}
          <div className='flex gap-2 items-stretch'>
            {SESSIONS.map((s) => (
              <SessionCard
                key={s.id}
                session={s}
                utcH={utcH}
                now={now}
                ilOffset={ilOffset}
              />
            ))}

            {isOverlap && <OverlapBadge />}

            <SwapCountdown swapMs={swapMs} ilSwapHour={ilSwapHour} />
          </div>
        </div>
      </div>
    </section>
  );
}
