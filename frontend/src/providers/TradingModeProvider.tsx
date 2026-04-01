'use client';

import {
  createContext,
  useContext,
  type ReactNode,
} from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useToast } from '@/components/ui/toast';
import type { TradingMode } from '@/types/trading';

export type { TradingMode };

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
  // Use the server-side proxy so ADMIN_API_KEY is read at runtime, not baked into the bundle.
  const res = await fetch('/api/config/trading-mode', { cache: 'no-store' });
  if (!res.ok) throw new Error(`API Error (${res.status})`);
  const data: { trading_mode: string } = await res.json();
  return data.trading_mode as TradingMode;
}

async function saveTradingMode(mode: TradingMode): Promise<TradingMode> {
  // Use the server-side proxy so ADMIN_API_KEY is read at runtime, not baked into the bundle.
  const res = await fetch('/api/config/trading-mode', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  });
  if (!res.ok) throw new Error(`API Error (${res.status}): ${await res.text()}`);
  const data: { trading_mode: string } = await res.json();
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
        ? 'Access denied — check ADMIN_API_KEY matches on frontend and backend servers.'
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
