'use client';

import { useQuery } from '@tanstack/react-query';
import { fetchSignals } from '@/lib/supabase';
import { TradingMode, TradingSignal } from '@/types/trading';
import { subDays } from 'date-fns';

export type JournalPeriod = '7d' | '30d' | '90d' | 'all';

export function useJournalSignals(mode?: TradingMode, period: JournalPeriod = 'all') {
  return useQuery<TradingSignal[]>({
    queryKey: ['journal', mode, period],
    queryFn: async () => {
      const signals = await fetchSignals({ mode, limit: 1000 });
      if (period === 'all') return signals;
      const days = period === '7d' ? 7 : period === '30d' ? 30 : 90;
      const cutoff = subDays(new Date(), days).getTime();
      return signals.filter((s) => new Date(s.created_at).getTime() >= cutoff);
    },
    staleTime: 2 * 60 * 1000,
  });
}
