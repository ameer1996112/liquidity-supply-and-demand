'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/lib/supabase';

const ACCOUNTS_COMPARISON_KEY = ['portfolio-control', 'accounts', 'comparison'] as const;

export interface AddAccountStrategyInput {
  account_name: string;
  strategy_type?: string;
  risk_percent?: number;
  max_positions?: number;
  allocated_capital_usd?: number;
  max_lot_size?: number;
  min_rr_ratio?: number;
}

async function createAccountStrategy(input: AddAccountStrategyInput): Promise<unknown> {
  if (!supabase) throw new Error('Supabase not configured');
  const db = supabase as any;

  const payload = {
    account_name: (input.account_name || '').trim(),
    strategy_type: input.strategy_type ?? 'BALANCED',
    risk_percent: input.risk_percent ?? 1,
    max_positions: input.max_positions ?? 3,
    allocated_capital_usd: input.allocated_capital_usd ?? 10000,
    max_lot_size: input.max_lot_size ?? 1,
    min_rr_ratio: input.min_rr_ratio ?? 2,
    is_active: true,
    broker_profile_id: null,
  };

  const { data, error } = await db
    .from('account_strategies')
    .insert(payload)
    .select()
    .single();

  if (error) throw error;
  return data;
}

export function useCreateAccountStrategy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createAccountStrategy,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ACCOUNTS_COMPARISON_KEY });
    },
  });
}
