'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';

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
  hold_duration_seconds: number;
  created_at: string;
  zone_type: string | null;
  entry_model: string | null;
  rr_ratio: number | null;
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
  return useQuery<{ positions: ActivePosition[]; count: number }>({
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: positionKeys.active });
      queryClient.invalidateQueries({ queryKey: positionKeys.account });
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: positionKeys.active });
      queryClient.invalidateQueries({ queryKey: positionKeys.account });
    },
  });
}
