'use client';

import { useQuery } from '@tanstack/react-query';
import { fetchSignals } from '@/lib/supabase';
import { TradingMode, TradingSignal } from '@/types/trading';

export function useJournalSignals(mode?: TradingMode) {
  return useQuery<TradingSignal[]>({
    queryKey: ['journal', mode],
    queryFn: () => fetchSignals({ mode, limit: 200 }),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}
