'use client';

import {
  createContext,
  useContext,
  type ReactNode,
} from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api';
import { useToast } from '@/components/ui/toast';

export type TradingMode = 'LIVE' | 'PAPER' | 'DRY_RUN';

interface TradingModeContextValue {
  mode: TradingMode;
  isSaving: boolean;
  setMode: (mode: TradingMode) => void;
  error: Error | null;
}

const TradingModeContext = createContext<TradingModeContextValue>({
  mode: 'PAPER',
  isSaving: false,
  setMode: () => {},
  error: null,
});

const QUERY_KEY = ['system', 'trading-mode'] as const;

async function fetchTradingMode(): Promise<TradingMode> {
  const data = await apiFetch<{ trading_mode: string }>('/api/v1/config/trading-mode');
  return data.trading_mode as TradingMode;
}

async function saveTradingMode(mode: TradingMode): Promise<TradingMode> {
  const data = await apiFetch<{ trading_mode: string }>('/api/v1/config/trading-mode', {
    method: 'POST',
    body: JSON.stringify({ mode }),
  });
  return data.trading_mode as TradingMode;
}

export function TradingModeProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: fetchTradingMode,
    staleTime: 30_000,
    retry: 1,
  });

  const mutation = useMutation({
    mutationFn: saveTradingMode,
    onSuccess: (newMode) => {
      queryClient.setQueryData(QUERY_KEY, newMode);
    },
    onError: (err: Error) => {
      const message = err.message.includes('403')
        ? 'Access denied — check NEXT_PUBLIC_ADMIN_API_KEY is set.'
        : err.message.includes('503')
        ? 'Backend error — ADMIN_API_KEY not configured on server.'
        : `Failed to change mode: ${err.message}`;
      addToast({ title: 'Mode Change Failed', message, severity: 'critical' });
    },
  });

  return (
    <TradingModeContext.Provider
      value={{
        mode: query.data ?? 'PAPER',
        isSaving: mutation.isPending,
        setMode: mutation.mutate,
        error: (query.error ?? mutation.error) as Error | null,
      }}
    >
      {children}
    </TradingModeContext.Provider>
  );
}

export function useTradingMode() {
  return useContext(TradingModeContext);
}
