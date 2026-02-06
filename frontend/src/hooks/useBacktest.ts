'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';

export interface BacktestRun {
  id: number;
  run_id: string;
  name: string;
  config: Record<string, unknown>;
  status: 'pending' | 'running' | 'completed' | 'failed';
  signal_count: number;
  result_summary: Record<string, unknown> | string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export const backtestKeys = {
  runs: ['backtest-runs'] as const,
  run: (id: string) => ['backtest-run', id] as const,
};

export function useBacktestRuns() {
  return useQuery<{ runs: BacktestRun[] }>({
    queryKey: backtestKeys.runs,
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/backtest/runs`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    refetchInterval: 10_000,
  });
}

export function useBacktestRun(runId: string | null) {
  return useQuery<BacktestRun>({
    queryKey: backtestKeys.run(runId || ''),
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/backtest/runs/${runId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    enabled: !!runId,
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.status === 'running' ? 3000 : false;
    },
  });
}

export function useStartBacktest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (params: {
      name: string;
      config_overrides: Record<string, unknown>;
      signal_source: 'date_range' | 'payload_list';
      date_from?: string;
      date_to?: string;
    }) => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/backtest/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<{ run_id: string; status: string }>;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: backtestKeys.runs });
    },
  });
}
