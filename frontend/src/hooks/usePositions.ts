'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';
import { useToast } from '@/components/ui/toast';

export interface ActivePosition {
  id: number;
  symbol: string;
  side: string;
  entry: number | null;
  sl: number | null;
  tp: number | null;
  size: number;
  broker_order_id: string | null;
  current_price: number | null;
  live_pnl: number | null;
  live_pnl_pct: number | null;
  hold_duration_seconds: number;
  created_at: string;
  zone_type: string | null;
  entry_model: string | null;
  rr_ratio: number | null;
  is_stale: boolean;
  broker_exists: boolean;
}

export interface ReconciliationInfo {
  db_position_count: number;
  broker_position_count: number;
  matched_count: number;
  stale_in_db: number;
  missing_in_db: number;
  has_mismatches: boolean;
}

export interface AccountStatus {
  balance: number;
  equity: number;
  free_margin: number;
  margin_used: number;
  margin_level_pct: number;
  active_positions_count: number;
}

export const positionKeys = {
  active: ['positions-active'] as const,
  account: ['account-status'] as const,
};

export function useActivePositions() {
  return useQuery<{
    positions: ActivePosition[];
    count: number;
    reconciliation: ReconciliationInfo;
  }>({
    queryKey: positionKeys.active,
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/positions/active`, {
        signal: AbortSignal.timeout(8000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    refetchInterval: 5_000,
    staleTime: 3_000,
    retry: 1,
  });
}

export function useAccountStatus() {
  return useQuery<AccountStatus>({
    queryKey: positionKeys.account,
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/positions/account`, {
        signal: AbortSignal.timeout(8000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    refetchInterval: 10_000,
    staleTime: 5_000,
    retry: 1,
  });
}

export function useClosePosition() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  return useMutation({
    mutationFn: async ({
      signalId,
      reason,
    }: {
      signalId: number;
      reason?: string;
    }) => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/positions/${signalId}/close`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: reason || 'Manual close from UI' }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: positionKeys.active });
      queryClient.invalidateQueries({ queryKey: positionKeys.account });
      const correlationId =
        (data as { correlation_id?: string } | undefined)?.correlation_id ?? undefined;
      addToast({
        title: 'Position close requested',
        message: `Manual close requested for signal #${variables.signalId}.`,
        severity: 'success',
        duration: 6000,
        ...(correlationId ? { correlationId } : {}),
      });
    },
    onError: (error: Error, variables) => {
      addToast({
        title: 'Failed to close position',
        message: `Signal #${variables.signalId}: ${error.message}`,
        severity: 'critical',
        duration: 8000,
      });
    },
  });
}

export function useModifySLTP() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      signalId,
      sl,
      tp,
    }: {
      signalId: number;
      sl?: number;
      tp?: number;
    }) => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/positions/${signalId}/sl-tp`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sl, tp }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: positionKeys.active });
    },
  });
}

export function usePartialClose() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  return useMutation({
    mutationFn: async ({
      signalId,
      closePercent,
    }: {
      signalId: number;
      closePercent: number;
    }) => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/positions/${signalId}/partial-close`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ close_percent: closePercent }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: positionKeys.active });
      queryClient.invalidateQueries({ queryKey: positionKeys.account });
      const correlationId =
        (data as { correlation_id?: string } | undefined)?.correlation_id ?? undefined;
      addToast({
        title: 'Partial close executed',
        message: `Closed ${variables.closePercent}% of signal #${variables.signalId}.`,
        severity: 'success',
        duration: 6000,
        ...(correlationId ? { correlationId } : {}),
      });
    },
    onError: (error: Error, variables) => {
      addToast({
        title: 'Partial close failed',
        message: `Signal #${variables.signalId}: ${error.message}`,
        severity: 'critical',
        duration: 8000,
      });
    },
  });
}

export function useCleanupStale() {
  const queryClient = useQueryClient();
  const { addToast } = useToast();
  return useMutation({
    mutationFn: async () => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/positions/cleanup-stale`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: positionKeys.active });
      queryClient.invalidateQueries({ queryKey: positionKeys.account });
      const closedCount = data?.closed_count ?? 0;
      if (closedCount > 0) {
        addToast({
          title: 'Stale positions cleaned up',
          message: `Closed ${closedCount} stale ${closedCount === 1 ? 'position' : 'positions'}.`,
          severity: 'success',
          duration: 6000,
        });
      } else {
        addToast({
          title: 'No stale positions found',
          message: 'All positions are synchronized with broker.',
          severity: 'info',
          duration: 4000,
        });
      }
    },
    onError: (error: Error) => {
      addToast({
        title: 'Cleanup failed',
        message: error.message,
        severity: 'critical',
        duration: 8000,
      });
    },
  });
}

