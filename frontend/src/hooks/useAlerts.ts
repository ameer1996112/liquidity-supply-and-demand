'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useMemo } from 'react';
import {
  getAlertsActiveUrl,
  getAlertAcknowledgeUrl,
  getAlertAcknowledgeAllUrl,
} from '@/lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type AlertSeverity = 'info' | 'warning' | 'error' | 'critical';

export interface Alert {
  id: number;
  alert_type: string;
  severity: AlertSeverity | string;
  title: string;
  message: string;
  metadata: Record<string, unknown>;
  signal_id?: number | null;
  acknowledged_at?: string | null;
  created_at: string;
}

interface AlertsListResponse {
  alerts: Alert[];
  count: number;
}

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

export const alertKeys = {
  all: ['alerts'] as const,
  active: ['alerts', 'active'] as const,
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAlerts() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: alertKeys.active,
    queryFn: async (): Promise<Alert[]> => {
      const url = getAlertsActiveUrl();
      if (!url) {
        // Backend URL not configured – behave as no alerts.
        return [];
      }

      const res = await fetch(url, {
        signal: AbortSignal.timeout(5_000),
      });
      if (!res.ok) {
        // Log and degrade gracefully.
         
        console.warn('Failed to fetch alerts', res.status, res.statusText);
        return [];
      }
      const json = (await res.json()) as AlertsListResponse;
      return json.alerts ?? [];
    },
    // Poll every 15s for active alerts.
    refetchInterval: 15_000,
    staleTime: 10_000,
  });

  const markAsRead = useCallback(
    async (id: number) => {
      const url = getAlertAcknowledgeUrl(id);
      if (!url) return;
      try {
        await fetch(url, {
          method: 'POST',
          signal: AbortSignal.timeout(5_000),
        });
        // Optimistically remove from cache.
        queryClient.setQueryData<Alert[]>(alertKeys.active, (old) =>
          (old ?? []).filter((a) => a.id !== id),
        );
      } catch (err) {
         
        console.error('Failed to acknowledge alert', err);
      }
    },
    [queryClient],
  );

  const clearAll = useCallback(async () => {
    const url = getAlertAcknowledgeAllUrl();
    if (!url) {
      queryClient.setQueryData<Alert[]>(alertKeys.active, []);
      return;
    }
    try {
      await fetch(url, {
        method: 'POST',
        signal: AbortSignal.timeout(5_000),
      });
      queryClient.setQueryData<Alert[]>(alertKeys.active, []);
    } catch (err) {
       
      console.error('Failed to acknowledge all alerts', err);
    }
  }, [queryClient]);

  const unreadCount = useMemo(
    () => (query.data ?? []).length,
    [query.data],
  );

  return {
    alerts: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    unreadCount,
    refetch: query.refetch,
    markAsRead,
    clearAll,
  };
}

