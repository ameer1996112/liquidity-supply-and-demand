'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';

export type TradingMode = 'PAPER' | 'LIVE' | 'DRY_RUN';

const QUERY_KEY = ['system', 'trading-mode'] as const;

async function fetchTradingMode(): Promise<TradingMode> {
  const data = await apiFetch<any>('/api/v1/config/trading-mode');
  return data.trading_mode as TradingMode;
}

async function setTradingMode(mode: TradingMode): Promise<TradingMode> {
  const data = await apiFetch<any>('/api/v1/config/trading-mode', {
    method: 'POST',
    body: JSON.stringify({ mode }),
  });
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
