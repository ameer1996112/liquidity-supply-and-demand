'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useCallback, useRef } from 'react';
import {
  supabase,
  fetchSignals,
  fetchSignalStats,
  isSupabaseAvailable,
} from '@/lib/supabase';
import {
  TradingSignal,
  TradingMode,
  SignalStatus,
  RealtimePayload,
  normalizeSignal,
} from '@/types/trading';
import { fetchAiRunsBulk, type CouncilSummary } from '@/lib/api';

// =============================================================================
// CONFIGURATION
// =============================================================================

const CONFIG = {
  /** Maximum number of signals to display */
  SIGNAL_LIMIT: 200,
  /** Polling interval when Supabase realtime is unavailable (ms) */
  FALLBACK_POLL_INTERVAL: 30_000,
  /** Stats refresh interval with Supabase (ms) */
  STATS_REFRESH_WITH_REALTIME: 60_000,
  /** Stats refresh interval without Supabase (ms) */
  STATS_REFRESH_WITHOUT_REALTIME: 30_000,
  /** Enable debug logging */
  DEBUG: process.env.NODE_ENV === 'development',
  /** Realtime event batching window (ms) */
  REALTIME_BATCH_MS: 300,
} as const;

type QueuedRealtimeEvent = {
  eventType: 'INSERT' | 'UPDATE' | 'DELETE';
  signal: TradingSignal;
};

function hasSignalMeaningfulChanges(
  prev: TradingSignal,
  next: TradingSignal
): boolean {
  return !(
    prev.updated_at === next.updated_at &&
    prev.status === next.status &&
    prev.pnl === next.pnl &&
    prev.closed_at === next.closed_at &&
    prev.exit_price === next.exit_price &&
    prev.mode === next.mode &&
    prev.run_mode === next.run_mode
  );
}

// =============================================================================
// DEBUG UTILITIES
// =============================================================================

/**
 * Debug logger for trading signals
 * Outputs raw data to console for debugging field mapping issues
 */
function debugLog(context: string, data: unknown): void {
  if (!CONFIG.DEBUG) return;

  console.group(`🔍 [useTradingSignals] ${context}`);
  console.log('Timestamp:', new Date().toISOString());
  console.log('Data:', data);
  console.groupEnd();
}

/**
 * Validate signal has required fields
 * Logs warnings for missing critical fields
 */
function validateSignal(signal: TradingSignal, source: string): void {
  if (!CONFIG.DEBUG) return;

  const warnings: string[] = [];

  // Check critical field mappings
  if (!signal.symbol && !signal.ticker) {
    warnings.push('⚠️ Missing symbol field (looked for: symbol, ticker)');
  }
  if (!signal.side && !signal.action) {
    warnings.push('⚠️ Missing side field (looked for: side, action)');
  }
  if (signal.score === undefined && signal.ai_confidence === undefined) {
    warnings.push('ℹ️ No confidence score (looked for: score, ai_confidence)');
  }

  if (warnings.length > 0) {
    console.warn(
      `[useTradingSignals] Signal validation (${source}):`,
      signal.id
    );
    warnings.forEach((w) => console.warn('  ', w));
  }
}

// =============================================================================
// QUERY KEYS
// =============================================================================

export const signalKeys = {
  all: ['trading-signals'] as const,
  list: (mode?: TradingMode) => [...signalKeys.all, 'list', mode] as const,
  stats: ['trading-stats'] as const,
};

// =============================================================================
// MAIN HOOK: useTradingSignals
// =============================================================================

/**
 * Hook for fetching trading signals with real-time updates
 *
 * ## Data Topology (DB → UI Mapping)
 * - `symbol` → UI symbol (e.g., "BTCUSD")
 * - `side` → direction ("buy" | "sell")
 * - `score` → AI confidence (0-100)
 * - `status` → signal status (active/closed/ai_rejected/filtered)
 * - `notes` OR `filter_reason` → reasoning text
 * - `pnl` → profit/loss (NULLABLE - handle safely!)
 *
 * ## Features
 * - Fetches from `trading_signals` table
 * - Orders by `created_at` descending (newest first)
 * - Limits to 50 rows
 * - Subscribes to Realtime INSERT events
 * - Debug logging for field mapping issues
 *
 * @param mode - Optional filter by trading mode (LIVE/PAPER)
 */
export function useTradingSignals(mode?: TradingMode) {
  const queryClient = useQueryClient();
   
  const subscriptionRef = useRef<any>(null);
  const eventQueueRef = useRef<QueuedRealtimeEvent[]>([]);
  const batchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flushRealtimeBatch = useCallback(() => {
    const queued = eventQueueRef.current;
    eventQueueRef.current = [];
    batchTimerRef.current = null;

    if (queued.length === 0) return;

    debugLog('Flushing realtime batch', { size: queued.length, mode });

    // Keep only latest event per signal id to minimize cache writes.
    const latestById = new Map<string, QueuedRealtimeEvent>();
    for (const evt of queued) {
      latestById.set(evt.signal.id, evt);
    }
    const batchedEvents = Array.from(latestById.values());

    let didMutateList = false;

    queryClient.setQueryData<TradingSignal[]>(
      signalKeys.list(mode),
      (old = []) => {
        let next = old;

        for (const evt of batchedEvents) {
          if (evt.eventType === 'DELETE') {
            const hadSignal = next.some(
              (signal) => signal.id === evt.signal.id
            );
            next = next.filter((signal) => signal.id !== evt.signal.id);
            didMutateList = didMutateList || hadSignal;
            continue;
          }

          // Filter by mode if requested.
          const signalMode = (evt.signal.mode ?? '').toUpperCase();
          const filterMode = (mode ?? '').toUpperCase();
          if (mode && signalMode !== filterMode) {
            continue;
          }

          const idx = next.findIndex((signal) => signal.id === evt.signal.id);
          if (idx >= 0) {
            if (hasSignalMeaningfulChanges(next[idx], evt.signal)) {
              const copy = [...next];
              copy[idx] = evt.signal;
              next = copy;
              didMutateList = true;
            }
          } else {
            next = [evt.signal, ...next].slice(0, CONFIG.SIGNAL_LIMIT);
            didMutateList = true;
          }
        }

        return next;
      }
    );

    if (didMutateList) {
      // Invalidate derived stats once per effective batch change.
      queryClient.invalidateQueries({ queryKey: signalKeys.stats });
    }
  }, [mode, queryClient]);

  const enqueueRealtimeEvent = useCallback(
    (event: QueuedRealtimeEvent) => {
      eventQueueRef.current.push(event);
      if (!batchTimerRef.current) {
        batchTimerRef.current = setTimeout(
          flushRealtimeBatch,
          CONFIG.REALTIME_BATCH_MS
        );
      }
    },
    [flushRealtimeBatch]
  );

  // Main query
  const query = useQuery({
    queryKey: signalKeys.list(mode),
    queryFn: async () => {
      debugLog('Fetching signals', { mode, limit: CONFIG.SIGNAL_LIMIT });

      const rawSignals = await fetchSignals({
        mode,
        limit: CONFIG.SIGNAL_LIMIT,
      });

      // Normalize run_mode (uppercase) and status (lowercase) for case-insensitive filtering
      const signals: TradingSignal[] = rawSignals.map((s) => ({
        ...s,
        mode: s.mode ? (String(s.mode).toUpperCase() as TradingMode) : s.mode,
        status: (s.status
          ? String(s.status).toLowerCase()
          : 'pending') as SignalStatus,
      }));

      // Debug: Log raw data for field mapping verification
      debugLog('Received signals', {
        count: signals.length,
        firstSignal: signals[0],
        fieldSample: signals[0]
          ? {
              symbol: signals[0].symbol,
              side: signals[0].side,
              score: signals[0].score,
              status: signals[0].status,
              run_mode: signals[0].mode,
              notes: signals[0].notes,
              pnl: signals[0].pnl,
            }
          : null,
      });

      // Validate each signal for field mapping issues
      signals.forEach((s) => validateSignal(s, 'initial-fetch'));

      return signals;
    },
    refetchInterval: isSupabaseAvailable()
      ? false
      : CONFIG.FALLBACK_POLL_INTERVAL,
    staleTime: 1000 * 60, // 1 minute
  });

  // Real-time subscription for INSERT events
  useEffect(() => {
    if (!isSupabaseAvailable() || !supabase) {
      debugLog('Realtime disabled', 'Supabase not available');
      return;
    }

    // Clean up previous subscription
    if (subscriptionRef.current) {
      supabase.removeChannel(subscriptionRef.current);
    }

    debugLog('Setting up realtime subscription', { mode });

    const channel = supabase
      .channel(`trading-signals-realtime-${mode || 'all'}`)
      .on<TradingSignal>(
        'postgres_changes',
        {
          event: '*', // Listen to INSERT, UPDATE, DELETE
          schema: 'public',
          table: 'trading_signals',
        },
        (payload) => {
          const {
            eventType,
            new: newRecord,
            old: oldRecord,
          } = payload as unknown as RealtimePayload<TradingSignal>;

          debugLog(`Realtime event: ${eventType}`, {
            eventType,
            newRecord: eventType !== 'DELETE' ? newRecord : undefined,
            oldRecord: eventType === 'DELETE' ? oldRecord : undefined,
          });

          // Normalize the incoming signal
          const normalizedNew =
            eventType !== 'DELETE'
              ? normalizeSignal(newRecord as Partial<TradingSignal>)
              : null;

          if (normalizedNew) {
            validateSignal(normalizedNew, `realtime-${eventType}`);
          }

          if (
            (eventType === 'INSERT' || eventType === 'UPDATE') &&
            normalizedNew
          ) {
            enqueueRealtimeEvent({ eventType, signal: normalizedNew });
          }

          if (eventType === 'DELETE' && oldRecord) {
            enqueueRealtimeEvent({
              eventType: 'DELETE',
              signal: normalizeSignal(oldRecord as Partial<TradingSignal>),
            });
          }
        }
      )
      .subscribe((status) => {
        debugLog('Realtime subscription status', status);
      });

    subscriptionRef.current = channel;

    return () => {
      debugLog('Cleaning up realtime subscription', null);
      if (batchTimerRef.current) {
        clearTimeout(batchTimerRef.current);
        batchTimerRef.current = null;
      }
      flushRealtimeBatch();
      if (supabase && subscriptionRef.current) {
        supabase.removeChannel(subscriptionRef.current);
        subscriptionRef.current = null;
      }
    };
  }, [queryClient, mode, enqueueRealtimeEvent, flushRealtimeBatch]);

  return query;
}

// =============================================================================
// HOOK: useSignalStats
// =============================================================================

/**
 * Hook for fetching signal statistics (24h metrics)
 */
export function useSignalStats() {
  return useQuery({
    queryKey: signalKeys.stats,
    queryFn: async () => {
      debugLog('Fetching stats', null);
      const stats = await fetchSignalStats();
      debugLog('Received stats', stats);
      return stats;
    },
    refetchInterval: isSupabaseAvailable()
      ? CONFIG.STATS_REFRESH_WITH_REALTIME
      : CONFIG.STATS_REFRESH_WITHOUT_REALTIME,
  });
}

// =============================================================================
// HOOK: useSignal (single signal by ID)
// =============================================================================

/**
 * Hook to get a single signal by ID from the cache
 */
export function useSignal(id: string | null) {
  const { data: signals = [] } = useTradingSignals();

  return signals.find((s) => s.id === id) || null;
}

// =============================================================================
// HOOK: useRefreshSignals
// =============================================================================

/**
 * Utility hook for triggering manual refetch of all signal data
 */
export function useRefreshSignals() {
  const queryClient = useQueryClient();

  return useCallback(() => {
    debugLog('Manual refresh triggered', null);
    queryClient.invalidateQueries({ queryKey: signalKeys.all });
    queryClient.invalidateQueries({ queryKey: signalKeys.stats });
  }, [queryClient]);
}

// =============================================================================
// HOOK: useCouncilSummaries
// =============================================================================

/**
 * Fetches Trading Council summaries (recommendation, confidence, votes) for
 * a list of signal IDs. Returns a stable map keyed by signal ID string.
 * Refreshes every 60 s so newly processed signals pick up council data.
 */
export function useCouncilSummaries(
  signalIds: string[],
): Record<string, CouncilSummary> {
  const { data = {} } = useQuery({
    queryKey: ['council-summaries', signalIds.slice().sort().join(',')],
    queryFn: () => fetchAiRunsBulk(signalIds),
    enabled: signalIds.length > 0,
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
  return data;
}

// =============================================================================
// HOOK: useSignalSubscription (standalone realtime)
// =============================================================================

/**
 * Standalone hook for subscribing to realtime signal events
 * Useful for components that need custom handling of realtime events
 */
export function useSignalSubscription(
  onInsert?: (signal: TradingSignal) => void,
  onUpdate?: (signal: TradingSignal) => void,
  onDelete?: (signalId: string) => void
) {
  useEffect(() => {
    if (!isSupabaseAvailable() || !supabase) return;

    const channel = supabase
      .channel('trading-signals-custom')
      .on<TradingSignal>(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'trading_signals',
        },
        (payload) => {
          const {
            eventType,
            new: newRecord,
            old: oldRecord,
          } = payload as unknown as RealtimePayload<TradingSignal>;

          if (eventType === 'INSERT' && newRecord) {
            const normalized = normalizeSignal(
              newRecord as Partial<TradingSignal>
            );
            onInsert?.(normalized);
          }

          if (eventType === 'UPDATE' && newRecord) {
            const normalized = normalizeSignal(
              newRecord as Partial<TradingSignal>
            );
            onUpdate?.(normalized);
          }

          if (eventType === 'DELETE' && oldRecord) {
            onDelete?.(oldRecord.id);
          }
        }
      )
      .subscribe();

    return () => {
      if (supabase) {
        supabase.removeChannel(channel);
      }
    };
  }, [onInsert, onUpdate, onDelete]);
}
