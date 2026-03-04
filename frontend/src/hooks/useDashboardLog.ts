import { useState, useRef, useEffect } from 'react';
import type { LogEntry } from '@/components/dashboard/LiveLog';
import type { TradingSignal, TradingMode } from '@/types/trading';

const MAX_LOG_ENTRIES = 200;

interface UseDashboardLogOptions {
  signals: TradingSignal[];
  activeMode: TradingMode;
  isConnected: boolean;
  strategyName: string;
  timeframe: string;
  mounted: boolean;
}

interface UseDashboardLogResult {
  entries: LogEntry[];
  clear: () => void;
}

/**
 * Manages the live-log feed for the dashboard.
 * Extracted from page.tsx to keep the page component as a pure layout layer.
 *
 * Rules:
 * - Seeds three context entries on first mount
 * - Appends one entry per new incoming signal
 * - Caps total entries at MAX_LOG_ENTRIES to prevent unbounded growth
 */
export function useDashboardLog({
  signals,
  activeMode,
  isConnected,
  strategyName,
  timeframe,
  mounted,
}: UseDashboardLogOptions): UseDashboardLogResult {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const idRef = useRef(0);
  const prevCountRef = useRef(signals.length);

  const nextId = () => String(++idRef.current);

  const append = (newEntries: LogEntry[]) => {
    setEntries((prev) => {
      const combined = [...prev, ...newEntries];
      return combined.length > MAX_LOG_ENTRIES
        ? combined.slice(combined.length - MAX_LOG_ENTRIES)
        : combined;
    });
  };

  useEffect(() => {
    if (!mounted) return;
    const now = new Date().toISOString();
    setEntries([
      {
        id: nextId(),
        timestamp: now,
        level: 'info',
        message: `Dashboard initialized — mode: ${activeMode}`,
        source: 'SYSTEM',
      },
      {
        id: nextId(),
        timestamp: now,
        level: isConnected ? 'success' : 'error',
        message: isConnected
          ? 'API connection established'
          : 'API unreachable — signals via Supabase only',
        source: 'HEALTH',
      },
      {
        id: nextId(),
        timestamp: now,
        level: 'info',
        message: `Strategy: ${strategyName} | Timeframe: ${timeframe}`,
        source: 'CONFIG',
      },
    ]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted]);

  // Update HEALTH entry when connection status changes (health check may complete after initial seed)
  useEffect(() => {
    if (!mounted) return;
    setEntries((prev) => {
      const healthIdx = prev.findIndex((e) => e.source === 'HEALTH');
      if (healthIdx === -1) return prev;
      const updated = [...prev];
      updated[healthIdx] = {
        ...updated[healthIdx],
        id: nextId(),
        timestamp: new Date().toISOString(),
        level: isConnected ? 'success' : 'error',
        message: isConnected
          ? 'API connection established'
          : 'API unreachable — signals via Supabase only',
      };
      return updated;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mounted, isConnected]);

  useEffect(() => {
    if (!mounted) return;
    const newCount = signals.length - prevCountRef.current;
    if (newCount > 0) {
      const incoming = signals.slice(0, newCount);
      append(
        incoming.map((s): LogEntry => ({
          id: nextId(),
          timestamp: s.created_at,
          level:
            s.status === 'active' || s.status === 'executed'
              ? 'success'
              : s.status === 'filtered' || s.status === 'ai_rejected'
                ? 'warn'
                : 'info',
          message: `${s.symbol} ${s.side.toUpperCase()} @ ${s.entry ?? s.price ?? '?'} — ${s.status}`,
          source: 'SIGNAL',
        })),
      );
    }
    prevCountRef.current = signals.length;
  }, [signals, mounted]);

  return { entries, clear: () => setEntries([]) };
}
