'use client';

import { useEffect, useMemo, useState } from 'react';
import { Activity, Clock3, Zap } from 'lucide-react';

type SessionId = 'sydney' | 'tokyo' | 'london' | 'newyork';

type SessionDef = {
  id: SessionId;
  name: string;
  city: string;
  flag: string;
  startUtcH: number;
  endUtcH: number;
  colorPrimary: string;
  colorSecondary: string;
  colorGlow: string;
  colorBg: string;
  colorBorder: string;
  colorText: string;
  colorDim: string;
};

const SESSIONS: SessionDef[] = [
  {
    id: 'sydney',
    name: 'Sydney',
    city: 'Australia',
    flag: '🦘',
    startUtcH: 22,
    endUtcH: 7,
    colorPrimary: '#06b6d4',
    colorSecondary: '#22d3ee',
    colorGlow: 'rgba(6,182,212,0.35)',
    colorBg: 'rgba(6,182,212,0.08)',
    colorBorder: 'rgba(6,182,212,0.4)',
    colorText: '#67e8f9',
    colorDim: 'rgba(6,182,212,0.25)',
  },
  {
    id: 'tokyo',
    name: 'Tokyo',
    city: 'Japan',
    flag: '🗾',
    startUtcH: 0,
    endUtcH: 9,
    colorPrimary: '#3b82f6',
    colorSecondary: '#60a5fa',
    colorGlow: 'rgba(59,130,246,0.35)',
    colorBg: 'rgba(59,130,246,0.08)',
    colorBorder: 'rgba(59,130,246,0.4)',
    colorText: '#93c5fd',
    colorDim: 'rgba(59,130,246,0.25)',
  },
  {
    id: 'london',
    name: 'London',
    city: 'United Kingdom',
    flag: '🇬🇧',
    startUtcH: 8,
    endUtcH: 17,
    colorPrimary: '#8b5cf6',
    colorSecondary: '#a78bfa',
    colorGlow: 'rgba(139,92,246,0.35)',
    colorBg: 'rgba(139,92,246,0.08)',
    colorBorder: 'rgba(139,92,246,0.4)',
    colorText: '#c4b5fd',
    colorDim: 'rgba(139,92,246,0.25)',
  },
  {
    id: 'newyork',
    name: 'New York',
    city: 'United States',
    flag: '🗽',
    startUtcH: 13,
    endUtcH: 22,
    colorPrimary: '#10b981',
    colorSecondary: '#34d399',
    colorGlow: 'rgba(16,185,129,0.35)',
    colorBg: 'rgba(16,185,129,0.08)',
    colorBorder: 'rgba(16,185,129,0.4)',
    colorText: '#6ee7b7',
    colorDim: 'rgba(16,185,129,0.25)',
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

function isWeekendClosed(now: Date): boolean {
  const day = now.getUTCDay();
  const hour = now.getUTCHours();
  if (day === 6) return true;
  if (day === 5 && hour >= 22) return true;
  if (day === 0 && hour < 22) return true;
  return false;
}

function isActiveSession(
  nowSec: number,
  startH: number,
  endH: number
): boolean {
  const start = startH * 3600;
  const end = endH * 3600;
  if (end <= start) return nowSec >= start || nowSec < end;
  return nowSec >= start && nowSec < end;
}

function getProgress(nowSec: number, startH: number, endH: number) {
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
  if (day === 0 && now.getUTCHours() < 22) return (22 * 3600 - nowSec) * 1000;
  const weekSec = day * 86400 + nowSec;
  const nextSundayOpen = 7 * 86400 + 22 * 3600;
  return Math.max(0, (nextSundayOpen - weekSec) * 1000);
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
    () => (now ? isWeekendClosed(now) : false),
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

  const utcH =
    now.getUTCHours() + now.getUTCMinutes() / 60 + now.getUTCSeconds() / 3600;
  const markerPct = (utcH / 24) * 100;

  return (
    <section className='shrink-0'>
      <div
        style={{
          borderRadius: '12px',
          border: '1px solid rgba(255,255,255,0.07)',
          background: 'linear-gradient(135deg, #0d0f14 0%, #111318 100%)',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        {/* Top rainbow accent line */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '2px',
            background:
              'linear-gradient(90deg, #06b6d4 0%, #3b82f6 30%, #8b5cf6 60%, #10b981 100%)',
          }}
        />

        <div style={{ padding: '10px 12px 12px' }}>
          {/* Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '10px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '5px',
                  borderRadius: '20px',
                  border: `1px solid ${
                    marketClosed
                      ? 'rgba(251,191,36,0.35)'
                      : 'rgba(16,185,129,0.35)'
                  }`,
                  background: marketClosed
                    ? 'rgba(251,191,36,0.08)'
                    : 'rgba(16,185,129,0.08)',
                  padding: '3px 10px',
                }}
              >
                <Activity
                  style={{
                    width: 11,
                    height: 11,
                    color: marketClosed ? '#fbbf24' : '#34d399',
                  }}
                />
                <span
                  style={{
                    fontFamily: 'var(--font-sans)',
                    fontSize: '9px',
                    fontWeight: 700,
                    letterSpacing: '0.14em',
                    textTransform: 'uppercase',
                    color: marketClosed ? '#fcd34d' : '#6ee7b7',
                  }}
                >
                  {marketClosed
                    ? 'Market Closed · Weekend'
                    : 'Market Sessions · Live'}
                </span>
              </div>

              {overlap && !marketClosed && (
                <div
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    borderRadius: '20px',
                    border: '1px solid rgba(251,191,36,0.4)',
                    background: 'rgba(251,191,36,0.1)',
                    padding: '3px 10px',
                  }}
                >
                  <Zap style={{ width: 10, height: 10, color: '#fbbf24' }} />
                  <span
                    style={{
                      fontFamily: 'var(--font-sans)',
                      fontSize: '9px',
                      fontWeight: 700,
                      letterSpacing: '0.14em',
                      textTransform: 'uppercase',
                      color: '#fde68a',
                    }}
                  >
                    High Volume Overlap
                  </span>
                </div>
              )}

              {marketClosed && (
                <div
                  style={{
                    borderRadius: '20px',
                    border: '1px solid rgba(251,191,36,0.25)',
                    background: 'rgba(251,191,36,0.06)',
                    padding: '3px 10px',
                  }}
                >
                  <span
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '10px',
                      color: '#fcd34d',
                    }}
                  >
                    Opens in {hm(weeklyOpenMs)}
                  </span>
                </div>
              )}
            </div>

            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                borderRadius: '8px',
                border: '1px solid rgba(255,255,255,0.08)',
                background: 'rgba(0,0,0,0.25)',
                padding: '4px 10px',
              }}
            >
              <Clock3 style={{ width: 11, height: 11, color: '#71717a' }} />
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  color: '#d4d4d8',
                  letterSpacing: '0.04em',
                }}
              >
                {ilDay(now)} {ilClock(now)} IL
              </span>
            </div>
          </div>

          {/* Timeline */}
          <div style={{ position: 'relative', marginBottom: '10px' }}>
            <div
              style={{
                height: '6px',
                borderRadius: '3px',
                background: '#0a0c10',
                border: '1px solid rgba(255,255,255,0.06)',
                overflow: 'hidden',
                position: 'relative',
              }}
            >
              {SESSIONS.map((s) => {
                const span =
                  s.endUtcH > s.startUtcH
                    ? s.endUtcH - s.startUtcH
                    : 24 - s.startUtcH + s.endUtcH;
                return (
                  <div
                    key={s.id}
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: `${(s.startUtcH / 24) * 100}%`,
                      width: `${(span / 24) * 100}%`,
                      height: '100%',
                      background: `linear-gradient(90deg, ${s.colorPrimary}, ${s.colorSecondary})`,
                      opacity: 0.55,
                    }}
                  />
                );
              })}
            </div>
            {/* Current time marker */}
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: `${markerPct}%`,
                transform: 'translate(-50%, -50%)',
                width: '3px',
                height: '14px',
                borderRadius: '2px',
                background: '#ffffff',
                boxShadow:
                  '0 0 8px rgba(255,255,255,0.9), 0 0 16px rgba(255,255,255,0.4)',
                zIndex: 10,
              }}
            />
            {/* Timeline labels */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                marginTop: '4px',
              }}
            >
              {[0, 6, 12, 18, 24].map((h) => (
                <span
                  key={h}
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '8px',
                    color: '#52525b',
                  }}
                >
                  {utcHourToIL(h % 24)} IL
                </span>
              ))}
            </div>
          </div>

          {/* Session Cards */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: '8px',
            }}
          >
            {sessions.map((s) => (
              <div
                key={s.id}
                style={{
                  borderRadius: '10px',
                  border: `1px solid ${
                    s.active ? s.colorBorder : 'rgba(255,255,255,0.06)'
                  }`,
                  background: s.active
                    ? `linear-gradient(160deg, ${s.colorBg} 0%, rgba(0,0,0,0.2) 100%)`
                    : 'rgba(255,255,255,0.02)',
                  padding: '10px 12px',
                  position: 'relative',
                  overflow: 'hidden',
                  transition: 'all 0.5s ease',
                  boxShadow: s.active
                    ? `0 0 20px ${s.colorGlow}, inset 0 1px 0 ${s.colorDim}`
                    : 'none',
                }}
              >
                {/* Top accent line on active */}
                {s.active && (
                  <div
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      right: 0,
                      height: '2px',
                      background: `linear-gradient(90deg, ${s.colorPrimary}, ${s.colorSecondary})`,
                    }}
                  />
                )}

                {/* Header row */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'space-between',
                    marginBottom: '8px',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                    }}
                  >
                    <span style={{ fontSize: '16px', lineHeight: 1 }}>
                      {s.flag}
                    </span>
                    <div>
                      <p
                        style={{
                          fontFamily: 'var(--font-sans)',
                          fontSize: '12px',
                          fontWeight: 700,
                          lineHeight: 1,
                          color: s.active ? '#ffffff' : '#52525b',
                          marginBottom: '2px',
                        }}
                      >
                        {s.name}
                      </p>
                      <p
                        style={{
                          fontFamily: 'var(--font-sans)',
                          fontSize: '9px',
                          color: '#3f3f46',
                          lineHeight: 1,
                        }}
                      >
                        {s.city}
                      </p>
                    </div>
                  </div>

                  <div
                    style={{
                      borderRadius: '6px',
                      border: `1px solid ${
                        s.active ? s.colorBorder : 'rgba(255,255,255,0.08)'
                      }`,
                      background: s.active
                        ? s.colorBg
                        : 'rgba(255,255,255,0.03)',
                      padding: '2px 7px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    {s.active && (
                      <span
                        style={{
                          width: '5px',
                          height: '5px',
                          borderRadius: '50%',
                          background: s.colorSecondary,
                          display: 'inline-block',
                          boxShadow: `0 0 6px ${s.colorPrimary}`,
                          animation: 'pulse 2s infinite',
                        }}
                      />
                    )}
                    <span
                      style={{
                        fontFamily: 'var(--font-sans)',
                        fontSize: '8px',
                        fontWeight: 700,
                        letterSpacing: '0.12em',
                        textTransform: 'uppercase',
                        color: s.active
                          ? s.colorText
                          : marketClosed
                          ? '#a16207'
                          : '#3f3f46',
                      }}
                    >
                      {marketClosed ? 'Closed' : s.active ? 'Live' : 'Closed'}
                    </span>
                  </div>
                </div>

                {/* Time range */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '8px',
                  }}
                >
                  <span
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '9px',
                      color: s.active ? '#71717a' : '#3f3f46',
                    }}
                  >
                    {s.startIL} – {s.endIL} IL
                  </span>
                  {s.active && (
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '9px',
                        color: s.colorText,
                        fontWeight: 600,
                      }}
                    >
                      {hm(s.remainingMs)} left
                    </span>
                  )}
                </div>

                {/* Progress bar */}
                <div
                  style={{
                    height: '3px',
                    borderRadius: '2px',
                    background: 'rgba(255,255,255,0.06)',
                    overflow: 'hidden',
                    marginBottom: s.active ? '6px' : '0',
                  }}
                >
                  {s.active && (
                    <div
                      style={{
                        height: '100%',
                        width: `${Math.max(3, s.progressPct)}%`,
                        background: `linear-gradient(90deg, ${s.colorPrimary}, ${s.colorSecondary})`,
                        borderRadius: '2px',
                        boxShadow: `0 0 6px ${s.colorPrimary}`,
                        transition: 'width 1s linear',
                      }}
                    />
                  )}
                </div>

                {/* Countdown + percent */}
                {s.active && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '9px',
                        color: s.colorText,
                      }}
                    >
                      {Math.round(s.progressPct)}%
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '10px',
                        color: '#d4d4d8',
                        letterSpacing: '0.04em',
                      }}
                    >
                      {hms(s.remainingMs)}
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
