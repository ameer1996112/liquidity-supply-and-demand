'use client';

import { useQuery } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';
import type { AccountRow, TraceDetail, TraceSummary } from '@/types/execution';

// ── Query keys ────────────────────────────────────────────────────────────────

export const traceKeys = {
  list: (filters: TracesFilter) => ['pipeline-traces', 'list', filters] as const,
  detail: (correlationId: string) =>
    ['pipeline-traces', 'detail', correlationId] as const,
  accounts: ['trace-accounts'] as const,
};

export interface TracesFilter {
  limit?: number;
  account_id?: string | null;
  symbol?: string | null;
  run_mode?: string | null;
  has_error?: boolean | null;
}

// ── Fetch helpers ─────────────────────────────────────────────────────────────

async function fetchTraces(filter: TracesFilter): Promise<TraceSummary[]> {
  const base = getApiUrl();
  if (!base) throw new Error('API URL not configured');

  const params = new URLSearchParams();
  params.set('limit', String(filter.limit ?? 50));
  if (filter.account_id) params.set('account_id', filter.account_id);
  if (filter.symbol) params.set('symbol', filter.symbol);
  if (filter.run_mode) params.set('run_mode', filter.run_mode);
  if (filter.has_error != null) params.set('has_error', String(filter.has_error));

  const res = await fetch(`${base}/api/traces?${params}`, {
    signal: AbortSignal.timeout(8000),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchTraceDetail(correlationId: string): Promise<TraceDetail> {
  const base = getApiUrl();
  if (!base) throw new Error('API URL not configured');

  const res = await fetch(`${base}/api/traces/${encodeURIComponent(correlationId)}`, {
    signal: AbortSignal.timeout(8000),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchTraceAccounts(): Promise<AccountRow[]> {
  const base = getApiUrl();
  if (!base) throw new Error('API URL not configured');

  const res = await fetch(`${base}/api/accounts`, {
    signal: AbortSignal.timeout(5000),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Custom hooks ──────────────────────────────────────────────────────────────

export function usePipelineTraces(filter: TracesFilter = {}) {
  return useQuery({
    queryKey: traceKeys.list(filter),
    queryFn: () => fetchTraces(filter),
    refetchInterval: 15_000,
    staleTime: 8_000,
    retry: 1,
  });
}

export function useTraceDetail(correlationId: string | null) {
  return useQuery({
    queryKey: traceKeys.detail(correlationId ?? ''),
    queryFn: () => fetchTraceDetail(correlationId!),
    enabled: !!correlationId,
    staleTime: 30_000,
    retry: 1,
  });
}

export function useTraceAccounts() {
  return useQuery({
    queryKey: traceKeys.accounts,
    queryFn: fetchTraceAccounts,
    staleTime: 60_000,
    retry: 1,
  });
}
