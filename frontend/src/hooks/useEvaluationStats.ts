'use client';

import { useQuery } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';

export interface EvaluationStats {
  evaluation_mode: boolean;
  phase: 'phase1' | 'phase2' | 'funded';
  current_day: number;
  total_days: number;
  profit_target: number;
  current_profit: number;
  profit_progress_pct: number;
  max_daily_loss: number;
  today_pnl: number;
  daily_loss_buffer: number;
  max_drawdown_pct: number;
  current_drawdown_pct: number;
  peak_balance: number;
  min_trading_days: number;
  actual_trading_days: number;
  consistency_pct: number;
  consistency_target_pct: number;
  rules_passed: {
    profit_target: boolean;
    min_trading_days: boolean;
    max_daily_loss: boolean;
    max_drawdown: boolean;
    consistency: boolean;
  };
  violations: Array<{
    rule: string;
    message: string;
    severity: 'critical' | 'warning';
  }>;
  can_upgrade: boolean;
}

export const evaluationKeys = {
  stats: ['evaluation-stats'] as const,
};

async function fetchEvaluationStats(): Promise<EvaluationStats> {
  const base = getApiUrl();
  const url = base ? `${base}/evaluation/stats` : '';
  if (!url) throw new Error('API URL not configured');
  const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export function useEvaluationStats() {
  return useQuery({
    queryKey: evaluationKeys.stats,
    queryFn: fetchEvaluationStats,
    refetchInterval: 10_000, // Poll every 10 seconds
    staleTime: 5_000,
    retry: 1,
  });
}
