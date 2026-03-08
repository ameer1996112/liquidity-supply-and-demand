'use client';

import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from 'react';

// ── Available timezones ───────────────────────────────────────────────────────

export interface TzOption {
  value: string; // IANA tz identifier
  label: string; // Display name
  abbr: string; // Short abbreviation shown in UI
}

export const TZ_OPTIONS: TzOption[] = [
  { value: 'Asia/Jerusalem', label: 'Israel (IL)', abbr: 'IL' },
  { value: 'UTC', label: 'UTC', abbr: 'UTC' },
  { value: 'America/New_York', label: 'New York (ET)', abbr: 'ET' },
  { value: 'Europe/London', label: 'London (GMT/BST)', abbr: 'LON' },
  { value: 'Asia/Tokyo', label: 'Tokyo (JST)', abbr: 'JST' },
  { value: 'Asia/Dubai', label: 'Dubai (GST)', abbr: 'GST' },
  { value: 'Europe/Berlin', label: 'Frankfurt (CET/CEST)', abbr: 'FRA' },
  { value: 'Asia/Singapore', label: 'Singapore (SGT)', abbr: 'SGT' },
];

export const DEFAULT_TZ = 'Asia/Jerusalem';
const STORAGE_KEY = 'tradeops_timezone';

// ── Context ───────────────────────────────────────────────────────────────────

interface TimezoneContextValue {
  /** Current IANA timezone string, e.g. "Asia/Jerusalem" */
  timezone: string;
  /** Abbreviation for the current timezone, e.g. "IL" */
  tzAbbr: string;
  /** Change the active timezone */
  setTimezone: (tz: string) => void;
  /** Format a Date object as a time string in the active timezone */
  formatTime: (date: Date, opts?: Intl.DateTimeFormatOptions) => string;
  /** Format a Date object as a date string in the active timezone */
  formatDate: (date: Date, opts?: Intl.DateTimeFormatOptions) => string;
  /** Convert a UTC hour (0-23) to a time string in the active timezone */
  utcHourToLocal: (utcHour: number) => string;
}

const TimezoneContext = createContext<TimezoneContextValue | null>(null);

// ── Provider ──────────────────────────────────────────────────────────────────

export function TimezoneProvider({ children }: { children: ReactNode }) {
  // Lazy initializer reads localStorage once on first render (client only)
  const [timezone, setTimezoneState] = useState<string>(() => {
    if (typeof window === 'undefined') return DEFAULT_TZ;
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored && TZ_OPTIONS.some((o) => o.value === stored)) return stored;
    } catch {
      // localStorage unavailable
    }
    return DEFAULT_TZ;
  });

  const setTimezone = useCallback((tz: string) => {
    setTimezoneState(tz);
    try {
      localStorage.setItem(STORAGE_KEY, tz);
    } catch {
      // ignore
    }
  }, []);

  const tzAbbr = TZ_OPTIONS.find((o) => o.value === timezone)?.abbr ?? 'IL';

  const formatTime = useCallback(
    (date: Date, opts?: Intl.DateTimeFormatOptions) =>
      date.toLocaleTimeString('en-GB', {
        timeZone: timezone,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
        ...opts,
      }),
    [timezone]
  );

  const formatDate = useCallback(
    (date: Date, opts?: Intl.DateTimeFormatOptions) =>
      date.toLocaleDateString('en-GB', {
        timeZone: timezone,
        ...opts,
      }),
    [timezone]
  );

  /** Convert a UTC hour (0-23) to a HH:MM string in the active timezone */
  const utcHourToLocal = useCallback(
    (utcHour: number) => {
      const now = new Date();
      const d = new Date(
        Date.UTC(
          now.getUTCFullYear(),
          now.getUTCMonth(),
          now.getUTCDate(),
          utcHour,
          0,
          0
        )
      );
      return d.toLocaleTimeString('en-GB', {
        timeZone: timezone,
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });
    },
    [timezone]
  );

  return (
    <TimezoneContext.Provider
      value={{
        timezone,
        tzAbbr,
        setTimezone,
        formatTime,
        formatDate,
        utcHourToLocal,
      }}
    >
      {children}
    </TimezoneContext.Provider>
  );
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useTimezone(): TimezoneContextValue {
  const ctx = useContext(TimezoneContext);
  if (!ctx)
    throw new Error('useTimezone must be used inside <TimezoneProvider>');
  return ctx;
}
