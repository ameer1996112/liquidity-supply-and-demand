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
  account_type?: string;
  provider?: string;
  meta_api_account_id?: string;
  meta_api_token_env_key?: string;
}

async function createAccountStrategy(input: AddAccountStrategyInput): Promise<unknown> {
  if (!supabase) throw new Error('Supabase not configured');
  const db = supabase as any;

  const metaApiAccountId = (input.meta_api_account_id || '').trim() || null;
  const accountType = input.account_type ?? 'Personal';
  const provider = input.provider ?? 'Personal';

  // 1. Insert account strategy
  const payload: Record<string, unknown> = {
    account_name: (input.account_name || '').trim(),
    strategy_type: input.strategy_type ?? 'BALANCED',
    risk_percent: input.risk_percent ?? 1,
    max_positions: input.max_positions ?? 3,
    allocated_capital_usd: input.allocated_capital_usd ?? 10000,
    max_lot_size: input.max_lot_size ?? 1,
    min_rr_ratio: input.min_rr_ratio ?? 0,
    is_active: true,
    account_type: accountType,
    provider: provider,
    meta_api_account_id: metaApiAccountId,
    meta_api_token_env_key: input.meta_api_token_env_key || 'META_API_TOKEN',
    connection_status: metaApiAccountId ? 'pending' : 'not_configured',
    broker_profile_id: null,
  };

  const { data: accountData, error: accountError } = await db
    .from('account_strategies')
    .insert(payload)
    .select()
    .single();

  if (accountError) throw accountError;

  // 2. Auto-create broker profile if MetaAPI Account ID provided
  if (metaApiAccountId && accountData) {
    try {
      const tokenEnvKey = input.meta_api_token_env_key || 'META_API_TOKEN';

      // Check if profile already exists for this MetaAPI account
      const { data: existingProfile } = await db
        .from('broker_profiles')
        .select('id')
        .eq('meta_api_account_id', metaApiAccountId)
        .limit(1)
        .maybeSingle();

      let profileId: number;

      if (existingProfile) {
        profileId = existingProfile.id;
      } else {
        const { data: newProfile, error: profileError } = await db
          .from('broker_profiles')
          .insert({
            name: (input.account_name || '').trim(),
            meta_api_account_id: metaApiAccountId,
            token_env_key: tokenEnvKey,
            risk_pct: input.risk_percent ?? 1,
            max_positions: input.max_positions ?? 3,
            run_mode: 'LIVE',
            is_active: true,
            evaluation_mode: accountType === 'Eval',
            starting_balance: input.allocated_capital_usd ?? 10000,
          })
          .select()
          .single();

        if (profileError) throw profileError;
        profileId = newProfile.id;
      }

      // Link account strategy to broker profile
      await db
        .from('account_strategies')
        .update({ broker_profile_id: profileId })
        .eq('id', accountData.id);

    } catch (linkErr) {
      console.warn('Auto-link broker profile failed (account created but not linked):', linkErr);
    }
  }

  return accountData;
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
