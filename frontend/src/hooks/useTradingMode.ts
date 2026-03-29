'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { API_BASE_URL } from '@/lib/api';

export type TradingMode = 'PAPER' | 'LIVE' | 'DRY_RUN';

const QUERY_KEY = ['system', 'trading-mode'] as const;

async function fetchTradingMode(): Promise<TradingMode> {
  const res = await fetch(`${API_BASE_URL}/api/v1/config/trading-mode`);
  if (!res.ok) throw new Error('Failed to fetch trading mode');
  const data = await res.json();
  return data.trading_mode as TradingMode;
}

async function setTradingMode(mode: TradingMode): Promise<TradingMode> {
  const res = await fetch(`${API_BASE_URL}/api/v1/config/trading-mode`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  });
  if (!res.ok) throw new Error('Failed to update trading mode');
  const data = await res.json();
  return data.trading_mode as TradingMode;
}

export function useTradingMode() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: fetchTradingMode,
    staleTime: 30_000,
  });

  const mutation = useMutation({
    mutationFn: setTradingMode,
    onSuccess: (newMode) => {
      queryClient.setQueryData(QUERY_KEY, newMode);
    },
  });

  return {
    mode: query.data ?? 'PAPER',
    isLoading: query.isLoading,
    isSaving: mutation.isPending,
    setMode: mutation.mutate,
    error: query.error ?? mutation.error,
  };
}
