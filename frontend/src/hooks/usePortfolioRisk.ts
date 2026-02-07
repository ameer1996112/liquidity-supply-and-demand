'use client';

import { useQuery } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';
import type {
  PortfolioRiskDashboard,
  CorrelationMatrix,
  RiskContribution,
  SectorExposure,
  PortfolioSettings,
} from '@/types/portfolio';

export const portfolioKeys = {
  riskDashboard: (lookbackDays?: number) =>
    ['portfolio-risk-dashboard', lookbackDays] as const,
  correlationMatrix: (lookbackDays?: number) =>
    ['portfolio-correlation-matrix', lookbackDays] as const,
  riskContribution: (lookbackDays?: number) =>
    ['portfolio-risk-contribution', lookbackDays] as const,
  sectorExposure: ['portfolio-sector-exposure'] as const,
  settings: ['portfolio-settings'] as const,
};

// ── Fetch Functions ───────────────────────────────────────────────

async function fetchRiskDashboard(
  lookbackDays: number = 30
): Promise<PortfolioRiskDashboard> {
  const base = getApiUrl();
  if (!base) throw new Error('API URL not configured');

  const url = `${base}/portfolio/risk-dashboard?lookback_days=${lookbackDays}`;
  const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchCorrelationMatrix(
  lookbackDays: number = 30
): Promise<CorrelationMatrix> {
  const base = getApiUrl();
  if (!base) throw new Error('API URL not configured');

  const url = `${base}/portfolio/correlation-matrix?lookback_days=${lookbackDays}`;
  const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchRiskContribution(
  lookbackDays: number = 30
): Promise<RiskContribution[]> {
  const base = getApiUrl();
  if (!base) throw new Error('API URL not configured');

  const url = `${base}/portfolio/risk-contribution?lookback_days=${lookbackDays}`;
  const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchSectorExposure(): Promise<SectorExposure[]> {
  const base = getApiUrl();
  if (!base) throw new Error('API URL not configured');

  const url = `${base}/portfolio/sector-exposure`;
  const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function fetchPortfolioSettings(): Promise<PortfolioSettings> {
  const base = getApiUrl();
  if (!base) throw new Error('API URL not configured');

  const url = `${base}/portfolio/settings`;
  const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Custom Hooks ──────────────────────────────────────────────────

export function useRiskDashboard(lookbackDays: number = 30) {
  return useQuery({
    queryKey: portfolioKeys.riskDashboard(lookbackDays),
    queryFn: () => fetchRiskDashboard(lookbackDays),
    refetchInterval: 30_000, // Refresh every 30 seconds
    staleTime: 10_000,
    retry: 1,
  });
}

export function useCorrelationMatrix(lookbackDays: number = 30) {
  return useQuery({
    queryKey: portfolioKeys.correlationMatrix(lookbackDays),
    queryFn: () => fetchCorrelationMatrix(lookbackDays),
    refetchInterval: 60_000, // Refresh every minute
    staleTime: 30_000,
    retry: 1,
  });
}

export function useRiskContribution(lookbackDays: number = 30) {
  return useQuery({
    queryKey: portfolioKeys.riskContribution(lookbackDays),
    queryFn: () => fetchRiskContribution(lookbackDays),
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: 1,
  });
}

export function useSectorExposure() {
  return useQuery({
    queryKey: portfolioKeys.sectorExposure,
    queryFn: fetchSectorExposure,
    refetchInterval: 30_000,
    staleTime: 10_000,
    retry: 1,
  });
}

export function usePortfolioSettings() {
  return useQuery({
    queryKey: portfolioKeys.settings,
    queryFn: fetchPortfolioSettings,
    staleTime: 300_000, // Settings rarely change, cache for 5 minutes
    retry: 1,
  });
}
