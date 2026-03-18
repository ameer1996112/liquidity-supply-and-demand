'use client';

import { useEffect } from 'react';
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
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
    staleTime: 30_000,
    placeholderData: keepPreviousData,
    retry: 1,
  });
}

export function usePropFirmHistory(accountName = 'default', days = 7) {
  return useQuery({
    queryKey: propFirmKeys.history(accountName, days),
    queryFn: () => fetchPropFirmHistory(accountName, days),
    refetchInterval: 60_000,
    staleTime: 30_000,
    placeholderData: keepPreviousData,
    retry: 1,
  });
}

export function usePropFirmConsistency(accountName = 'default') {
  return useQuery({
    queryKey: propFirmKeys.consistency(accountName),
    queryFn: () => fetchPropFirmConsistency(accountName),
    refetchInterval: 30_000,
    staleTime: 15_000,
    placeholderData: keepPreviousData,
    retry: 1,
  });
}

export function usePropFirmMtm(accountName = 'default') {
  return useQuery({
    queryKey: propFirmKeys.mtm(accountName),
    queryFn: () => fetchPropFirmMtm(accountName),
    refetchInterval: 10_000,
    staleTime: 30_000,
    placeholderData: keepPreviousData,
    retry: 1,
  });
}

/**
 * Prefetch prop firm metrics for ALL accounts so switching is instant.
 * Call once at the page level with the list of account names.
 */
export function usePrefetchPropFirmAccounts(accountNames: string[]) {
  const queryClient = useQueryClient();

  useEffect(() => {
    for (const name of accountNames) {
      // Prefetch metrics (most critical for perceived speed)
      queryClient.prefetchQuery({
        queryKey: propFirmKeys.metrics(name),
        queryFn: () => fetchPropFirmMetrics(name),
        staleTime: 30_000,
      });
    }
  }, [accountNames, queryClient]);
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

