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

// =============================================================================
// CONFIGURATION
// =============================================================================

const CONFIG = {
  /** Maximum number of signals to display */
  SIGNAL_LIMIT: 50,
  /** Polling interval when Supabase realtime is unavailable (ms) */
  FALLBACK_POLL_INTERVAL: 30_000,
  /** Stats refresh interval with Supabase (ms) */
  STATS_REFRESH_WITH_REALTIME: 60_000,
  /** Stats refresh interval without Supabase (ms) */
  STATS_REFRESH_WITHOUT_REALTIME: 30_000,
  /** Enable debug logging */
  DEBUG: process.env.NODE_ENV === 'development',
} as const;

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
      signal.id,
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
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const subscriptionRef = useRef<any>(null);

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
      console.log('First Signal Raw:', rawSignals[0]);
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

          // Update cache optimistically
          queryClient.setQueryData<TradingSignal[]>(
            signalKeys.list(mode),
            (old = []) => {
              if (eventType === 'INSERT' && normalizedNew) {
                // Filter by mode if specified (case-insensitive: LIVE/live, PAPER/paper)
                const signalMode = (normalizedNew.mode ?? '').toUpperCase();
                const filterMode = (mode ?? '').toUpperCase();
                if (mode && signalMode !== filterMode) {
                  debugLog('INSERT filtered by mode', {
                    signalMode,
                    filterMode,
                  });
                  return old;
                }

                debugLog('Prepending new signal', {
                  id: normalizedNew.id,
                  symbol: normalizedNew.symbol,
                });

                // Prepend new signal and limit to CONFIG.SIGNAL_LIMIT
                return [normalizedNew, ...old].slice(0, CONFIG.SIGNAL_LIMIT);
              }

              if (eventType === 'UPDATE' && normalizedNew) {
                debugLog('Updating signal', { id: normalizedNew.id });
                return old.map((signal) =>
                  signal.id === normalizedNew.id ? normalizedNew : signal,
                );
              }

              if (eventType === 'DELETE' && oldRecord) {
                debugLog('Removing signal', { id: oldRecord.id });
                return old.filter((signal) => signal.id !== oldRecord.id);
              }

              return old;
            },
          );

          // Invalidate stats cache on any change
          queryClient.invalidateQueries({ queryKey: signalKeys.stats });
        },
      )
      .subscribe((status) => {
        debugLog('Realtime subscription status', status);
      });

    subscriptionRef.current = channel;

    return () => {
      debugLog('Cleaning up realtime subscription', null);
      if (supabase && subscriptionRef.current) {
        supabase.removeChannel(subscriptionRef.current);
        subscriptionRef.current = null;
      }
    };
  }, [queryClient, mode]);

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
// HOOK: useSignalSubscription (standalone realtime)
// =============================================================================

/**
 * Standalone hook for subscribing to realtime signal events
 * Useful for components that need custom handling of realtime events
 */
export function useSignalSubscription(
  onInsert?: (signal: TradingSignal) => void,
  onUpdate?: (signal: TradingSignal) => void,
  onDelete?: (signalId: string) => void,
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
              newRecord as Partial<TradingSignal>,
            );
            onInsert?.(normalized);
          }

          if (eventType === 'UPDATE' && newRecord) {
            const normalized = normalizeSignal(
              newRecord as Partial<TradingSignal>,
            );
            onUpdate?.(normalized);
          }

          if (eventType === 'DELETE' && oldRecord) {
            onDelete?.(oldRecord.id);
          }
        },
      )
      .subscribe();

    return () => {
      if (supabase) {
        supabase.removeChannel(channel);
      }
    };
  }, [onInsert, onUpdate, onDelete]);
}
