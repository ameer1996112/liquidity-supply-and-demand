'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useCallback } from 'react';
import { supabase, fetchSignals, fetchSignalStats, isSupabaseAvailable } from '@/lib/supabase';
import { TradingSignal, TradingMode, SignalStats, RealtimePayload } from '@/types/trading';

// Query keys
export const signalKeys = {
  all: ['trading-signals'] as const,
  list: (mode?: TradingMode) => [...signalKeys.all, 'list', mode] as const,
  stats: ['trading-stats'] as const,
};

// Hook for fetching signals with real-time updates
export function useTradingSignals(mode?: TradingMode) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: signalKeys.list(mode),
    queryFn: () => fetchSignals({ mode, limit: 100 }),
    refetchInterval: isSupabaseAvailable() ? false : 30000, // Refetch every 30s if no realtime
  });

  // Real-time subscription
  useEffect(() => {
    if (!isSupabaseAvailable() || !supabase) return;

    const channel = supabase
      .channel('trading-signals-realtime')
      .on<TradingSignal>(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'trading_signals',
        },
        (payload) => {
          const { eventType, new: newRecord, old: oldRecord } = payload as unknown as RealtimePayload<TradingSignal>;

          // Update cache optimistically
          queryClient.setQueryData<TradingSignal[]>(
            signalKeys.list(mode),
            (old = []) => {
              if (eventType === 'INSERT') {
                // Filter by mode if specified
                if (mode && newRecord.mode !== mode) return old;
                return [newRecord, ...old].slice(0, 100);
              }

              if (eventType === 'UPDATE') {
                return old.map((signal) =>
                  signal.id === newRecord.id ? newRecord : signal
                );
              }

              if (eventType === 'DELETE' && oldRecord) {
                return old.filter((signal) => signal.id !== oldRecord.id);
              }

              return old;
            }
          );

          // Also invalidate stats
          queryClient.invalidateQueries({ queryKey: signalKeys.stats });
        }
      )
      .subscribe();

    return () => {
      if (supabase) {
        supabase.removeChannel(channel);
      }
    };
  }, [queryClient, mode]);

  return query;
}

// Hook for fetching signal statistics
export function useSignalStats() {
  return useQuery({
    queryKey: signalKeys.stats,
    queryFn: fetchSignalStats,
    refetchInterval: isSupabaseAvailable() ? 60000 : 30000, // Refetch every 60s with Supabase, 30s without
  });
}

// Hook to get a single signal by ID
export function useSignal(id: string | null) {
  const { data: signals = [] } = useTradingSignals();

  return signals.find((s) => s.id === id) || null;
}

// Utility hook for triggering manual refetch
export function useRefreshSignals() {
  const queryClient = useQueryClient();

  return useCallback(() => {
    queryClient.invalidateQueries({ queryKey: signalKeys.all });
    queryClient.invalidateQueries({ queryKey: signalKeys.stats });
  }, [queryClient]);
}
