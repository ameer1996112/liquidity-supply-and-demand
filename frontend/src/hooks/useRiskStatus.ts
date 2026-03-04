'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';
import { useToast } from '@/components/ui/toast';

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

interface KillSwitchResponse {
  status: string;
  kill_switch_active: boolean;
  action: 'engage' | 'reset';
  reason: string;
  // Optional correlation identifier for linking to traces / audit.
  correlation_id?: string;
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
): Promise<KillSwitchResponse> {
  const base = getApiUrl();
  const url = base ? `${base}/risk/kill-switch` : '';
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled, reason }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
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
  const { addToast } = useToast();
  return useMutation({
    mutationFn: ({
      enabled,
      reason,
    }: {
      enabled: boolean;
      reason: string;
    }) => toggleKillSwitch(enabled, reason),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: riskKeys.status });
      const resp = data as KillSwitchResponse;
      const engaging = resp.action === 'engage';
      const correlationId = resp.correlation_id ?? undefined;
      addToast({
        title: engaging ? 'Global kill switch engaged' : 'Global kill switch reset',
        message: engaging
          ? 'All accounts halted. New trade execution is blocked.'
          : 'Kill switch reset. New execution may resume subject to guard rails.',
        severity: engaging ? 'critical' : 'success',
        duration: 8000,
        ...(correlationId ? { correlationId } : {}),
      });
    },
    onError: (error: Error) => {
      addToast({
        title: 'Kill switch toggle failed',
        message: error.message,
        severity: 'critical',
        duration: 8000,
      });
    },
  });
}
