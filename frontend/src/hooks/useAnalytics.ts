'use client';

import { useQuery } from '@tanstack/react-query';
import { fetchSignals } from '@/lib/supabase';
import { TradingMode, TradingSignal, getPnl, getSymbol } from '@/types/trading';
import { format } from 'date-fns';

export interface AnalyticsData {
  equityCurve: { date: string; cumPnl: number }[];
  winRate: number;
  totalTrades: number;
  closedTrades: number;
  profitFactor: number;
  avgRR: number;
  avgWin: number;
  avgLoss: number;
  bestTrade: TradingSignal | null;
  worstTrade: TradingSignal | null;
  pnlBySymbol: { symbol: string; pnl: number; count: number; winRate: number }[];
  pnlByDay: { date: string; pnl: number; wins: number; losses: number }[];
  outcomeDistribution: { wins: number; losses: number; breakeven: number };
}

export function useAnalytics(mode?: TradingMode) {
  return useQuery<AnalyticsData>({
    queryKey: ['analytics', mode],
    queryFn: async () => {
      const signals = await fetchSignals({ mode, limit: 500 });
      return computeAnalytics(signals);
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

function computeAnalytics(signals: TradingSignal[]): AnalyticsData {
  // Filter to closed/executed trades with PnL
  const closed = signals.filter((s) => {
    const st = s.status?.toLowerCase();
    return (st === 'closed' || st === 'executed') && getPnl(s) != null;
  });

  const sorted = [...closed].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );

  // Outcome distribution
  let wins = 0;
  let losses = 0;
  let breakeven = 0;
  let totalWinPnl = 0;
  let totalLossPnl = 0;
  let totalRR = 0;
  let rrCount = 0;
  let bestTrade: TradingSignal | null = null;
  let worstTrade: TradingSignal | null = null;
  let bestPnl = -Infinity;
  let worstPnl = Infinity;

  for (const s of closed) {
    const pnl = getPnl(s) ?? 0;
    if (pnl > 0) {
      wins++;
      totalWinPnl += pnl;
    } else if (pnl < 0) {
      losses++;
      totalLossPnl += Math.abs(pnl);
    } else {
      breakeven++;
    }

    if (pnl > bestPnl) {
      bestPnl = pnl;
      bestTrade = s;
    }
    if (pnl < worstPnl) {
      worstPnl = pnl;
      worstTrade = s;
    }

    if (s.rr_ratio != null) {
      totalRR += s.rr_ratio;
      rrCount++;
    }
  }

  const winRate = closed.length > 0 ? (wins / closed.length) * 100 : 0;
  const profitFactor = totalLossPnl > 0 ? totalWinPnl / totalLossPnl : totalWinPnl > 0 ? Infinity : 0;
  const avgRR = rrCount > 0 ? totalRR / rrCount : 0;
  const avgWin = wins > 0 ? totalWinPnl / wins : 0;
  const avgLoss = losses > 0 ? totalLossPnl / losses : 0;

  // Equity curve
  let cumPnl = 0;
  const equityCurve = sorted.map((s) => {
    cumPnl += getPnl(s) ?? 0;
    return {
      date: format(new Date(s.created_at), 'MMM dd'),
      cumPnl: Number(cumPnl.toFixed(2)),
    };
  });

  // PnL by symbol
  const symbolMap = new Map<string, { pnl: number; count: number; wins: number }>();
  for (const s of closed) {
    const sym = getSymbol(s);
    const pnl = getPnl(s) ?? 0;
    const existing = symbolMap.get(sym) || { pnl: 0, count: 0, wins: 0 };
    existing.pnl += pnl;
    existing.count++;
    if (pnl > 0) existing.wins++;
    symbolMap.set(sym, existing);
  }
  const pnlBySymbol = Array.from(symbolMap.entries())
    .map(([symbol, data]) => ({
      symbol,
      pnl: Number(data.pnl.toFixed(2)),
      count: data.count,
      winRate: data.count > 0 ? (data.wins / data.count) * 100 : 0,
    }))
    .sort((a, b) => b.pnl - a.pnl);

  // PnL by day
  const dayMap = new Map<string, { pnl: number; wins: number; losses: number }>();
  for (const s of closed) {
    const day = format(new Date(s.created_at), 'MMM dd');
    const pnl = getPnl(s) ?? 0;
    const existing = dayMap.get(day) || { pnl: 0, wins: 0, losses: 0 };
    existing.pnl += pnl;
    if (pnl > 0) existing.wins++;
    if (pnl < 0) existing.losses++;
    dayMap.set(day, existing);
  }
  const pnlByDay = Array.from(dayMap.entries()).map(([date, data]) => ({
    date,
    pnl: Number(data.pnl.toFixed(2)),
    wins: data.wins,
    losses: data.losses,
  }));

  return {
    equityCurve,
    winRate,
    totalTrades: signals.length,
    closedTrades: closed.length,
    profitFactor: Number(profitFactor === Infinity ? 999 : profitFactor.toFixed(2)),
    avgRR: Number(avgRR.toFixed(2)),
    avgWin: Number(avgWin.toFixed(2)),
    avgLoss: Number(avgLoss.toFixed(2)),
    bestTrade,
    worstTrade,
    pnlBySymbol,
    pnlByDay,
    outcomeDistribution: { wins, losses, breakeven },
  };
}
