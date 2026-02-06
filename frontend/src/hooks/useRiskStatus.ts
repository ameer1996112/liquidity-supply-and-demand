'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';

export interface RiskStatus {
  kill_switch_active: boolean;
  kill_switch_reason: string | null;
  daily_pnl: number;
  daily_pnl_pct: number;
  /** LIVE-only daily PnL (closed today). Use in RiskBar when showing LIVE risk. */
  live_daily_pnl?: number | null;
  /** PAPER-only daily PnL (closed today). */
  paper_daily_pnl?: number | null;
  max_daily_loss_pct: number;
  drawdown_pct: number;
  max_drawdown_pct: number;
  active_positions: number;
  max_positions: number;
  current_equity: number;
  starting_equity: number;
  correlation_exposure: Record<string, unknown>;
  risk_mode: string;
  risk_multiplier: number;
  risk_label: string;
}

export const riskKeys = {
  status: ['risk-status'] as const,
};

async function fetchRiskStatus(): Promise<RiskStatus> {
  const base = getApiUrl();
  const url = base ? `${base}/risk/status` : '';
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function toggleKillSwitch(
  enabled: boolean,
  reason: string,
): Promise<void> {
  const base = getApiUrl();
  const url = base ? `${base}/risk/kill-switch` : '';
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled, reason }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export function useRiskStatus() {
  return useQuery({
    queryKey: riskKeys.status,
    queryFn: fetchRiskStatus,
    refetchInterval: 10_000,
    staleTime: 5_000,
    retry: 1,
  });
}

export function useKillSwitchMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      enabled,
      reason,
    }: {
      enabled: boolean;
      reason: string;
    }) => toggleKillSwitch(enabled, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: riskKeys.status });
    },
  });
}
