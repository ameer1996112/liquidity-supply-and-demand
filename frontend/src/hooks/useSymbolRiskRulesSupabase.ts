'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/lib/supabase';
import type { SymbolRiskRule } from '@/types/rules';

const SYMBOL_RULES_QUERY_KEY = ['symbol-risk-rules'] as const;

async function fetchSymbolRiskRules(): Promise<SymbolRiskRule[]> {
  if (!supabase) throw new Error('Supabase not configured');
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const db = supabase as any;
  const { data, error } = await db
    .from('symbol_risk_rules')
    .select('*')
    .order('symbol', { ascending: true });
  if (error) throw error;
  return (data || []) as SymbolRiskRule[];
}

async function createSymbolRiskRule(rule: Omit<SymbolRiskRule, 'id' | 'created_at' | 'updated_at'>): Promise<SymbolRiskRule> {
  if (!supabase) throw new Error('Supabase not configured');
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const db = supabase as any;
  const payload = {
    symbol: (rule.symbol || '').trim().toUpperCase(),
    max_lot_size: rule.max_lot_size ?? 1,
    risk_percent: rule.risk_percent ?? 1,
    pip_size: rule.pip_size ?? 0.0001,
    pip_value_per_lot: rule.pip_value_per_lot ?? 10,
    max_positions: rule.max_positions ?? 3,
    enabled: rule.enabled ?? true,
  };
  const { data, error } = await db.from('symbol_risk_rules').insert(payload).select().single();
  if (error) throw error;
  return data as SymbolRiskRule;
}

async function updateSymbolRiskRule(symbol: string, updates: Partial<SymbolRiskRule>): Promise<SymbolRiskRule> {
  if (!supabase) throw new Error('Supabase not configured');
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const db = supabase as any;
  const payload: Record<string, unknown> = {
    updated_at: new Date().toISOString(),
  };
  if (updates.risk_percent != null) payload.risk_percent = updates.risk_percent;
  if (updates.max_lot_size != null) payload.max_lot_size = updates.max_lot_size;
  if (updates.pip_size != null) payload.pip_size = updates.pip_size;
  if (updates.pip_value_per_lot != null) payload.pip_value_per_lot = updates.pip_value_per_lot;
  if (updates.max_positions != null) payload.max_positions = updates.max_positions;
  if (updates.enabled != null) payload.enabled = updates.enabled;

  const { data, error } = await db.from('symbol_risk_rules').update(payload).eq('symbol', symbol.trim().toUpperCase()).select().single();
  if (error) throw error;
  return data as SymbolRiskRule;
}

async function deleteSymbolRiskRule(symbol: string): Promise<void> {
  if (!supabase) throw new Error('Supabase not configured');
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const db = supabase as any;
  const { error } = await db.from('symbol_risk_rules').delete().eq('symbol', symbol.trim().toUpperCase());
  if (error) throw error;
}

export function useSymbolRiskRulesSupabase() {
  return useQuery({
    queryKey: SYMBOL_RULES_QUERY_KEY,
    queryFn: fetchSymbolRiskRules,
    staleTime: 30_000,
    enabled: !!supabase,
  });
}

export function useCreateSymbolRiskRuleSupabase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createSymbolRiskRule,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: SYMBOL_RULES_QUERY_KEY }),
  });
}

export function useUpdateSymbolRiskRuleSupabase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ symbol, updates }: { symbol: string; updates: Partial<SymbolRiskRule> }) =>
      updateSymbolRiskRule(symbol, updates),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: SYMBOL_RULES_QUERY_KEY }),
  });
}

export function useDeleteSymbolRiskRuleSupabase() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteSymbolRiskRule,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: SYMBOL_RULES_QUERY_KEY }),
  });
}
