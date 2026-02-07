'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchAccountsComparison,
  fetchAllocationSuggest,
  executeAllocation,
  fetchTradeCopyRules,
  createTradeCopyRule,
  toggleTradeCopyRule,
  fetchTradeCopyLog,
} from '@/lib/api';

const ACCOUNTS_COMPARISON_KEY = ['portfolio-control', 'accounts', 'comparison'] as const;
const TRADE_COPY_RULES_KEY = ['portfolio-control', 'accounts', 'trade-copy-rules'] as const;
const TRADE_COPY_LOG_KEY = ['portfolio-control', 'accounts', 'trade-copy-log'] as const;

export function useAccountsComparison() {
  return useQuery({
    queryKey: ACCOUNTS_COMPARISON_KEY,
    queryFn: fetchAccountsComparison,
    staleTime: 30_000,
  });
}

export function useAllocationSuggest(totalCapital: number, goal = 'maximize_sharpe') {
  return useQuery({
    queryKey: ['portfolio-control', 'accounts', 'allocation-suggest', totalCapital, goal],
    queryFn: () => fetchAllocationSuggest(totalCapital, goal),
    staleTime: 60_000,
    enabled: totalCapital > 0,
  });
}

export function useExecuteAllocation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ accountName, allocationUsd }: { accountName: string; allocationUsd: number }) =>
      executeAllocation(accountName, allocationUsd),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ACCOUNTS_COMPARISON_KEY });
    },
  });
}

export function useTradeCopyRules() {
  return useQuery({
    queryKey: TRADE_COPY_RULES_KEY,
    queryFn: fetchTradeCopyRules,
    staleTime: 30_000,
  });
}

export function useCreateTradeCopyRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (rule: Parameters<typeof createTradeCopyRule>[0]) => createTradeCopyRule(rule),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TRADE_COPY_RULES_KEY });
      queryClient.invalidateQueries({ queryKey: TRADE_COPY_LOG_KEY });
    },
  });
}

export function useToggleTradeCopyRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ruleId, enabled }: { ruleId: number; enabled: boolean }) =>
      toggleTradeCopyRule(ruleId, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TRADE_COPY_RULES_KEY });
    },
  });
}

export function useTradeCopyLog(limit = 50) {
  return useQuery({
    queryKey: [...TRADE_COPY_LOG_KEY, limit],
    queryFn: () => fetchTradeCopyLog(limit),
    staleTime: 15_000,
  });
}
