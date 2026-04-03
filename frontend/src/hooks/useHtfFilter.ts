'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { API_BASE_URL } from '@/lib/api';

export interface HtfFilterSettings {
  htf_candle_filter_enabled: boolean;
  htf_candle_block_minutes: number;
  htf_candle_period: number; // HTF cycle length in minutes (15, 30, 60)
  block_before_hourly_close: boolean;
  block_one_candle_liq: boolean;
  one_candle_liq_min_departure: number;
}

const QUERY_KEY = ['config', 'pine-filters'] as const;

async function fetchHtfFilter(): Promise<HtfFilterSettings> {
  const res = await fetch(`${API_BASE_URL}/api/v1/config/pine-filters`);
  if (!res.ok) throw new Error('Failed to fetch HTF filter settings');
  return res.json();
}

async function patchHtfFilter(patch: Partial<HtfFilterSettings>): Promise<HtfFilterSettings> {
  const res = await fetch(`${API_BASE_URL}/api/v1/config/pine-filters`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error('Failed to update HTF filter settings');
  return res.json();
}

export function useHtfFilter() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: QUERY_KEY,
    queryFn: fetchHtfFilter,
    staleTime: 30_000,
  });

  const mutation = useMutation({
    mutationFn: patchHtfFilter,
    onSuccess: (updated) => {
      queryClient.setQueryData(QUERY_KEY, updated);
    },
  });

  return {
    settings: query.data ?? { htf_candle_filter_enabled: true, htf_candle_block_minutes: 5, htf_candle_period: 30, block_before_hourly_close: true, block_one_candle_liq: true, one_candle_liq_min_departure: 60 },
    isLoading: query.isLoading,
    isSaving: mutation.isPending,
    update: mutation.mutate,
    error: query.error ?? mutation.error,
  };
}
