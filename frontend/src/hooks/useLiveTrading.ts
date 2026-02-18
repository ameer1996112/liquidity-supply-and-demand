/**
 * useLiveTrading Hook
 *
 * Comprehensive hook for fetching real-time trading data with auto-refresh.
 * Provides system health, positions, and calculated statistics.
 *
 * Features:
 * - Auto-refresh every 1 second (live terminal feel)
 * - Offline state detection
 * - Error handling with graceful degradation
 * - TypeScript interfaces for type safety
 */

'use client';

import { useQuery } from '@tanstack/react-query';
import { getApiUrl } from '@/lib/api';
import { useActivePositions, useAccountStatus } from './usePositions';
import { useTradingSignals } from './useTradingSignals';
import { useTradingMode } from '@/providers/TradingModeProvider';

// ══════════════════════════════════════════════════════════
// Type Definitions
// ══════════════════════════════════════════════════════════

export interface HealthCheckResponse {
  status: 'healthy' | 'degraded' | 'offline';
  redis: boolean;
  supabase: boolean;
  timestamp: string;
}

export interface LiveTradingData {
  // System Status
  isOnline: boolean;
  health: HealthCheckResponse | null;

  // Positions & Account
  positions: {
    active: unknown[];
    count: number;
    isLoading: boolean;
    error: Error | null;
  };

  account: {
    balance: number;
    equity: number;
    freeMargin: number;
    marginUsed: number;
    marginLevel: number;
    isLoading: boolean;
    error: Error | null;
  };

  // Trading Statistics (from signals)
  stats: {
    winRate: number;
    netPnL: number;
    totalTrades: number;
    activeTrades: number;
    todayPnL: number;
    isLoading: boolean;
    error: Error | null;
  };

  // Refresh control
  lastUpdate: Date | null;
}

// ══════════════════════════════════════════════════════════
// Health Check Query
// ══════════════════════════════════════════════════════════

const healthKeys = {
  status: ['health'] as const,
};

function useHealthCheck() {
  return useQuery<HealthCheckResponse>({
    queryKey: healthKeys.status,
    queryFn: async () => {
      const base = getApiUrl();
      if (!base) throw new Error('API URL not configured');

      const res = await fetch(`${base}/health`, {
        signal: AbortSignal.timeout(3000), // 3s timeout
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    refetchInterval: 1000, // 1 second for live feel
    staleTime: 500,
    retry: 1, // Only retry once for health checks
    retryDelay: 500,
  });
}

// ══════════════════════════════════════════════════════════
// Main Hook
// ══════════════════════════════════════════════════════════

export function useLiveTrading(): LiveTradingData {
  const { mode } = useTradingMode();

  // Fetch health status
  const { data: health, isError: healthError } = useHealthCheck();

  // Fetch positions
  const {
    data: positionsData,
    isError: positionsError,
    isLoading: positionsLoading,
    error: positionsErrorObj,
  } = useActivePositions();

  // Fetch account status
  const {
    data: accountData,
    isError: accountError,
    isLoading: accountLoading,
    error: accountErrorObj,
  } = useAccountStatus();

  // Fetch trading signals for statistics
  const signalsQuery = useTradingSignals(mode);
  const signals = signalsQuery.data || [];
  const signalsLoading = signalsQuery.isLoading;
  const signalsError = signalsQuery.error;

  // ──────────────────────────────────────────────────────
  // Calculate Statistics from Signals
  // ──────────────────────────────────────────────────────

  const calculateStats = () => {
    if (!signals || signals.length === 0) {
      return {
        winRate: 0,
        netPnL: 0,
        totalTrades: 0,
        activeTrades: positionsData?.count || 0,
        todayPnL: 0,
      };
    }

    // Filter closed trades (those with exit_price)
    const closedTrades = signals.filter((s) => s.exit_price != null);

    // Calculate wins and losses
    const wins = closedTrades.filter((s) => (s.pnl_usd || 0) > 0);

    // Win rate
    const winRate =
      closedTrades.length > 0 ? (wins.length / closedTrades.length) * 100 : 0;

    // Net P&L
    const netPnL = closedTrades.reduce((sum, s) => sum + (s.pnl_usd || 0), 0);

    // Today's P&L (signals from today)
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const todaySignals = closedTrades.filter((s) => {
      const exitDate = new Date(s.closed_at || s.created_at);
      return exitDate >= today;
    });
    const todayPnL = todaySignals.reduce((sum, s) => sum + (s.pnl_usd || 0), 0);

    return {
      winRate: Math.round(winRate * 10) / 10, // Round to 1 decimal
      netPnL: Math.round(netPnL * 100) / 100, // Round to 2 decimals
      totalTrades: closedTrades.length,
      activeTrades: positionsData?.count || 0,
      todayPnL: Math.round(todayPnL * 100) / 100,
    };
  };

  // ──────────────────────────────────────────────────────
  // Determine Online Status
  // ──────────────────────────────────────────────────────

  const isOnline = !healthError && health?.status !== 'offline';

  // ──────────────────────────────────────────────────────
  // Return Aggregated Data
  // ──────────────────────────────────────────────────────

  return {
    // System Status
    isOnline,
    health: health || null,

    // Positions
    positions: {
      active: positionsData?.positions || [],
      count: positionsData?.count || 0,
      isLoading: positionsLoading,
      error: positionsError ? (positionsErrorObj as Error) : null,
    },

    // Account
    account: {
      balance: accountData?.balance ?? 50000,
      equity: accountData?.equity || 0,
      freeMargin: accountData?.free_margin || 0,
      marginUsed: accountData?.margin_used || 0,
      marginLevel: accountData?.margin_level_pct || 0,
      isLoading: accountLoading,
      error: accountError ? (accountErrorObj as Error) : null,
    },

    // Statistics
    stats: {
      ...calculateStats(),
      isLoading: signalsLoading,
      error: signalsError,
    },

    // Metadata
    lastUpdate: new Date(),
  };
}
