'use client';

import {
  useQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import {
  fetchRiskSettings,
  updateRiskSetting,
  fetchSymbolRiskRules,
  createSymbolRiskRule,
  updateSymbolRiskRule,
  deleteSymbolRiskRule,
  type SymbolRiskRuleApi,
} from '@/lib/api';

const RISK_SETTINGS_QUERY_KEY = ['portfolio-control', 'risk', 'settings'] as const;
const SYMBOL_RULES_QUERY_KEY = ['rules', 'symbols'] as const;

export function useRiskSettings() {
  return useQuery({
    queryKey: RISK_SETTINGS_QUERY_KEY,
    queryFn: fetchRiskSettings,
    staleTime: 30_000,
  });
}

export function useUpdateRiskSetting() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      settingKey,
      value,
      changeReason,
    }: {
      settingKey: string;
      value: number | boolean | string | Record<string, unknown>;
      changeReason?: string;
    }) => updateRiskSetting(settingKey, value, changeReason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: RISK_SETTINGS_QUERY_KEY });
    },
  });
}

export function useSymbolRiskRules() {
  return useQuery({
    queryKey: SYMBOL_RULES_QUERY_KEY,
    queryFn: fetchSymbolRiskRules,
    staleTime: 30_000,
  });
}

export function useCreateSymbolRiskRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (rule: Omit<SymbolRiskRuleApi, 'id' | 'created_at' | 'updated_at'>) =>
      createSymbolRiskRule(rule),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: SYMBOL_RULES_QUERY_KEY });
    },
  });
}

export function useUpdateSymbolRiskRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ symbol, updates }: { symbol: string; updates: Partial<SymbolRiskRuleApi> }) =>
      updateSymbolRiskRule(symbol, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: SYMBOL_RULES_QUERY_KEY });
    },
  });
}

export function useDeleteSymbolRiskRule() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (symbol: string) => deleteSymbolRiskRule(symbol),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: SYMBOL_RULES_QUERY_KEY });
    },
  });
}
