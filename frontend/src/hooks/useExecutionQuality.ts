'use client';

import { useQuery } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';
import type {
  TCAMetrics,
  SlippageBySymbol,
  SlippageByHour,
  LatencyBreakdown,
  TCAAlert,
  TCASettings,
} from '@/types/execution';

export const executionKeys = {
  tcaSummary: (days: number, runMode?: string) =>
    ['tca-summary', days, runMode] as const,
  slippageBySymbol: (days: number, runMode?: string) =>
    ['slippage-by-symbol', days, runMode] as const,
  slippageByHour: (days: number) => ['slippage-by-hour', days] as const,
  latencyBreakdown: (days: number) => ['latency-breakdown', days] as const,
  tcaAlerts: (days: number) => ['tca-alerts', days] as const,
  tcaSettings: ['tca-settings'] as const,
};

// ── Fetch Functions ───────────────────────────────────────────────

async function fetchTCASummary(
  days: number,
  runMode?: string,
): Promise<TCAMetrics> {
  const base = getApiUrl();
  if (!base) throw new Error('API URL not configured');

  const params = new URLSearchParams({ days: days.toString() });
  if (runMode) params.append('run_mode', runMode);

  const url = `${base}/execution/tca-summary?${params}`;
  const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchSlippageBySymbol(
  days: number,
  runMode?: string,
): Promise<SlippageBySymbol[]> {
  const base = getApiUrl();
  if (!base) throw new Error('API URL not configured');

  const params = new URLSearchParams({ days: days.toString() });
  if (runMode) params.append('run_mode', runMode);

  const url = `${base}/execution/slippage-by-symbol?${params}`;
  const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchSlippageByHour(days: number): Promise<SlippageByHour[]> {
  const base = getApiUrl();
  if (!base) throw new Error('API URL not configured');

  const url = `${base}/execution/slippage-by-hour?days=${days}`;
  const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchLatencyBreakdown(days: number): Promise<LatencyBreakdown> {
  const base = getApiUrl();
  if (!base) throw new Error('API URL not configured');

  const url = `${base}/execution/latency-breakdown?days=${days}`;
  const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchTCAAlerts(days: number): Promise<TCAAlert[]> {
  const base = getApiUrl();
  if (!base) throw new Error('API URL not configured');

  const url = `${base}/execution/alerts?days=${days}&limit=50`;
  const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchTCASettings(): Promise<TCASettings> {
  const base = getApiUrl();
  if (!base) throw new Error('API URL not configured');

  const url = `${base}/execution/settings`;
  const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Custom Hooks ──────────────────────────────────────────────────

export function useTCASummary(days: number = 1, runMode?: string) {
  return useQuery({
    queryKey: executionKeys.tcaSummary(days, runMode),
    queryFn: () => fetchTCASummary(days, runMode),
    refetchInterval: 30_000, // Refresh every 30 seconds
    staleTime: 10_000,
    retry: 1,
  });
}

export function useSlippageBySymbol(days: number = 30, runMode?: string) {
  return useQuery({
    queryKey: executionKeys.slippageBySymbol(days, runMode),
    queryFn: () => fetchSlippageBySymbol(days, runMode),
    refetchInterval: 60_000, // Refresh every minute
    staleTime: 30_000,
    retry: 1,
  });
}

export function useSlippageByHour(days: number = 7) {
  return useQuery({
    queryKey: executionKeys.slippageByHour(days),
    queryFn: () => fetchSlippageByHour(days),
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: 1,
  });
}

export function useLatencyBreakdown(days: number = 7) {
  return useQuery({
    queryKey: executionKeys.latencyBreakdown(days),
    queryFn: () => fetchLatencyBreakdown(days),
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: 1,
  });
}

export function useTCAAlerts(days: number = 7) {
  return useQuery({
    queryKey: executionKeys.tcaAlerts(days),
    queryFn: () => fetchTCAAlerts(days),
    refetchInterval: 30_000,
    staleTime: 10_000,
    retry: 1,
  });
}

export function useTCASettings() {
  return useQuery({
    queryKey: executionKeys.tcaSettings,
    queryFn: fetchTCASettings,
    staleTime: 300_000, // Settings rarely change, cache for 5 minutes
    retry: 1,
  });
}
