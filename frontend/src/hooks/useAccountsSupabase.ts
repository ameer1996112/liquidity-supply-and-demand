'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { getPortfolioControlUrl } from '@/lib/api';

const ACCOUNTS_COMPARISON_KEY = [
  'portfolio-control',
  'accounts',
  'comparison',
] as const;

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

async function createAccountStrategy(
  input: AddAccountStrategyInput,
): Promise<unknown> {
  const url = getPortfolioControlUrl('/accounts');
  if (!url) throw new Error('Backend API URL not configured');

  const payload = {
    account_name: (input.account_name || '').trim(),
    account_type: input.account_type ?? 'Personal',
    provider: input.provider ?? 'Personal',
    strategy_type: input.strategy_type ?? 'BALANCED',
    risk_percent: input.risk_percent ?? 1,
    max_positions: input.max_positions ?? 3,
    allocated_capital_usd: input.allocated_capital_usd ?? 50000,
    max_lot_size: input.max_lot_size ?? 1,
    min_rr_ratio: input.min_rr_ratio ?? 0,
    meta_api_account_id: (input.meta_api_account_id || '').trim() || null,
    meta_api_token_env_key: input.meta_api_token_env_key || 'META_API_TOKEN',
  };

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(15000),
  });

  if (!res.ok) {
    let message = `Failed (${res.status})`;
    try {
      const body = await res.json();
      const detail =
        typeof body?.detail === 'string'
          ? body.detail
          : (body?.detail?.join?.(' ') ?? body?.message);
      if (detail) message = detail;
    } catch {
      // non-JSON response
    }
    throw new Error(message);
  }

  const data = await res.json();
  return data.account ?? data;
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
