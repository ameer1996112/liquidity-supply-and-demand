'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchPropFirmMetrics,
  fetchPropFirmHistory,
  fetchPropFirmConsistency,
  fetchPropFirmMtm,
  resetPropFirmDaily,
} from '@/lib/api';

export const propFirmKeys = {
  metrics: (account: string) => ['prop-firm-metrics', account] as const,
  history: (account: string, days: number) => ['prop-firm-history', account, days] as const,
  consistency: (account: string) => ['prop-firm-consistency', account] as const,
  mtm: (account: string) => ['prop-firm-mtm', account] as const,
};

export function usePropFirmMetrics(accountName = 'default') {
  return useQuery({
    queryKey: propFirmKeys.metrics(accountName),
    queryFn: () => fetchPropFirmMetrics(accountName),
    refetchInterval: 10_000,
    staleTime: 5_000,
    retry: 1,
  });
}

export function usePropFirmHistory(accountName = 'default', days = 7) {
  return useQuery({
    queryKey: propFirmKeys.history(accountName, days),
    queryFn: () => fetchPropFirmHistory(accountName, days),
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: 1,
  });
}

export function usePropFirmConsistency(accountName = 'default') {
  return useQuery({
    queryKey: propFirmKeys.consistency(accountName),
    queryFn: () => fetchPropFirmConsistency(accountName),
    refetchInterval: 30_000,
    staleTime: 15_000,
    retry: 1,
  });
}

export function usePropFirmMtm(accountName = 'default') {
  return useQuery({
    queryKey: propFirmKeys.mtm(accountName),
    queryFn: () => fetchPropFirmMtm(accountName),
    refetchInterval: 10_000,
    staleTime: 5_000,
    retry: 1,
  });
}

export function useResetPropFirmDaily(accountName = 'default') {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => resetPropFirmDaily(accountName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: propFirmKeys.metrics(accountName) });
      queryClient.invalidateQueries({ queryKey: propFirmKeys.history(accountName, 7) });
    },
  });
}
