'use client';

import { useQuery } from '@tanstack/react-query';
import { fetchSignals, fetchBrokerProfiles } from '@/lib/supabase';
import { TradingMode, TradingSignal } from '@/types/trading';
import { subDays } from 'date-fns';

export type JournalPeriod = '7d' | '30d' | '90d' | 'all';

export function useJournalSignals(mode?: TradingMode, period: JournalPeriod = 'all') {
  return useQuery<TradingSignal[]>({
    queryKey: ['journal', mode, period],
    queryFn: async () => {
      const [signals, profiles] = await Promise.all([
        fetchSignals({ mode, limit: 1000 }),
        fetchBrokerProfiles(),
      ]);

      const profileMap = new Map(profiles.map((p) => [p.id, p.name]));

      const enriched = signals.map((s) => {
        if (s.account_name) return s;
        const derived = s.broker_profile_id ? profileMap.get(s.broker_profile_id) : undefined;
        return derived ? { ...s, account_name: derived } : s;
      });

      if (period === 'all') return enriched;
      const days = period === '7d' ? 7 : period === '30d' ? 30 : 90;
      const cutoff = subDays(new Date(), days).getTime();
      return enriched.filter((s) => new Date(s.created_at).getTime() >= cutoff);
    },
    staleTime: 2 * 60 * 1000,
  });
}
