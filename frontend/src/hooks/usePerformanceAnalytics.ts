'use client';

import { useQuery } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';

// ── Response Types ──────────────────────────────────────────

export interface BucketStats {
  count: number;
  wins: number;
  losses: number;
  pnl: number;
  win_rate: number;
}

export interface BreakdownData {
  pnl_by_hour: Record<string, BucketStats>;
  pnl_by_day_of_week: Record<string, BucketStats>;
  pnl_by_symbol: Record<string, BucketStats>;
  pnl_by_zone_type: Record<string, BucketStats>;
  pnl_by_entry_model: Record<string, BucketStats>;
  win_rate_by_ai_confidence: Record<string, BucketStats>;
}

export interface Streak {
  type: 'win' | 'loss';
  count: number;
  pnl: number;
  start_date: string;
  end_date: string;
}

export interface StreaksData {
  max_win_streak: number;
  max_loss_streak: number;
  current_streak: number;
  current_streak_type: string;
  streaks: Streak[];
}

export interface DrawdownPoint {
  date: string;
  equity: number;
  drawdown_pct: number;
  peak: number;
}

export interface DrawdownData {
  data: DrawdownPoint[];
  max_drawdown_pct: number;
  max_drawdown_amount: number;
}

export interface SummaryData {
  sharpe_ratio: number;
  sortino_ratio: number;
  avg_hold_time_hours: number;
  total_r_won: number;
  total_r_lost: number;
  expectancy: number;
  total_trades: number;
}

// ── Hooks ───────────────────────────────────────────────────

export function useBreakdown(period: string, mode: string) {
  return useQuery<BreakdownData>({
    queryKey: ['analytics-breakdown', period, mode],
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(
        `${base}/api/analytics/breakdown?period=${period}&mode=${mode}`,
        { signal: AbortSignal.timeout(10_000) }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    staleTime: 5 * 60_000,
  });
}

export function useStreaks(mode: string) {
  return useQuery<StreaksData>({
    queryKey: ['analytics-streaks', mode],
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/api/analytics/streaks?mode=${mode}`, {
        signal: AbortSignal.timeout(10_000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    staleTime: 5 * 60_000,
  });
}

export function useDrawdown(mode: string) {
  return useQuery<DrawdownData>({
    queryKey: ['analytics-drawdown', mode],
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/api/analytics/drawdown?mode=${mode}`, {
        signal: AbortSignal.timeout(10_000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    staleTime: 5 * 60_000,
  });
}

export function useSummary(mode: string) {
  return useQuery<SummaryData>({
    queryKey: ['analytics-summary', mode],
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');
      const res = await fetch(`${base}/api/analytics/summary?mode=${mode}`, {
        signal: AbortSignal.timeout(10_000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    staleTime: 5 * 60_000,
  });
}
