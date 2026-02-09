'use client';

import { useState, useEffect } from 'react';
import { Download, Filter, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface HistoryTabProps {
  accountName: string;
}

interface Trade {
  id: number;
  symbol: string;
  side: string;
  size: number;
  entry: number;
  exit: number;
  sl?: number;
  tp?: number;
  pnl_usd: number;
  pnl_percent?: number;
  r_multiple?: number;
  mae?: number;
  mfe?: number;
  entry_time: string;
  exit_time: string;
  exit_reason?: string;
  outcome: 'win' | 'loss';
  trade_key?: string;
}

export function HistoryTab({ accountName }: HistoryTabProps) {
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d' | 'all'>('30d');
  const [outcomeFilter, setOutcomeFilter] = useState<'all' | 'win' | 'loss'>('all');
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTradeHistory();
  }, [accountName, dateRange, outcomeFilter]);

  const fetchTradeHistory = async () => {
    setLoading(true);
    setError(null);

    try {
      // Build query params
      const params = new URLSearchParams();
      if (dateRange !== 'all') {
        const days = parseInt(dateRange);
        params.append('days', days.toString());
      }
      if (outcomeFilter !== 'all') {
        params.append('outcome', outcomeFilter);
      }

      const response = await fetch(
        `/api/portfolio-control/accounts/${encodeURIComponent(accountName)}/history?${params}`
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch trade history: ${response.statusText}`);
      }

      const data = await response.json();
      setTrades(data.trades || []);
    } catch (err) {
      console.error('Error fetching trade history:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch trade history');
    } finally {
      setLoading(false);
    }
  };

  const exportCSV = () => {
    const headers = ['Symbol', 'Side', 'Entry', 'Exit', 'P&L USD', 'R Multiple', 'MAE', 'Exit Time'];
    const rows = trades.map(t => [
      t.symbol,
      t.side,
      t.entry.toFixed(5),
      t.exit.toFixed(5),
      t.pnl_usd.toFixed(2),
      t.r_multiple?.toFixed(2) || 'N/A',
      t.mae?.toFixed(2) || 'N/A',
      new Date(t.exit_time).toLocaleString(),
    ]);

    const csv = [headers, ...rows].map(row => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${accountName}-history-${dateRange}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Filter className="h-4 w-4 text-zinc-500" />
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value as any)}
            className="px-3 py-1.5 text-sm rounded border border-[#2a2e39] bg-[#1e222d] text-zinc-300 focus:outline-none focus:border-emerald-500"
          >
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
            <option value="all">All time</option>
          </select>

          <select
            value={outcomeFilter}
            onChange={(e) => setOutcomeFilter(e.target.value as any)}
            className="px-3 py-1.5 text-sm rounded border border-[#2a2e39] bg-[#1e222d] text-zinc-300 focus:outline-none focus:border-emerald-500"
          >
            <option value="all">All outcomes</option>
            <option value="win">Wins only</option>
            <option value="loss">Losses only</option>
          </select>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={exportCSV}
          disabled={trades.length === 0}
          className="border-[#2a2e39] text-zinc-400 hover:bg-[#2a2e39] hover:text-zinc-200"
        >
          <Download className="h-3.5 w-3.5 mr-1.5" />
          Export CSV
        </Button>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center rounded-lg border border-[#2a2e39] bg-[#1e222d]/50 py-16">
          <Loader2 className="h-8 w-8 animate-spin text-emerald-500" />
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="rounded-lg border border-red-900/50 bg-red-950/30 p-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && trades.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-[#2a2e39] bg-[#1e222d]/50 py-16 text-zinc-500">
          <div className="text-4xl mb-4">📊</div>
          <p className="text-sm font-mono">No Closed Trades</p>
          <p className="text-xs text-zinc-600 mt-1 max-w-md text-center">
            No closed trades found for the selected period. Closed trades will appear here once positions are exited.
          </p>
        </div>
      )}

      {/* Trade History Table */}
      {!loading && !error && trades.length > 0 && (
        <div className="rounded-lg border border-[#2a2e39] overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#1e222d] border-b border-[#2a2e39]">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Symbol</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Side</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase tracking-wider">Entry</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase tracking-wider">Exit</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase tracking-wider">P&L</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase tracking-wider">R Multiple</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase tracking-wider">MAE</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Exit Time</th>
              </tr>
            </thead>
            <tbody className="bg-[#1a1e2e] divide-y divide-[#2a2e39]">
              {trades.map((trade) => (
                <tr key={trade.id} className="hover:bg-[#1e222d] transition-colors">
                  <td className="px-4 py-3 font-mono text-zinc-200">{trade.symbol}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 text-xs rounded ${
                      trade.side === 'buy' ? 'bg-emerald-900/30 text-emerald-400' : 'bg-rose-900/30 text-rose-400'
                    }`}>
                      {trade.side.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-zinc-300">{trade.entry.toFixed(5)}</td>
                  <td className="px-4 py-3 text-right font-mono text-zinc-300">{trade.exit.toFixed(5)}</td>
                  <td className={`px-4 py-3 text-right font-mono font-semibold ${
                    trade.pnl_usd >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  }`}>
                    ${trade.pnl_usd.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-zinc-300">
                    {trade.r_multiple ? `${trade.r_multiple.toFixed(2)}R` : 'N/A'}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-zinc-400">
                    {trade.mae ? `$${trade.mae.toFixed(2)}` : 'N/A'}
                  </td>
                  <td className="px-4 py-3 text-zinc-400 text-xs">
                    {new Date(trade.exit_time).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="bg-[#1e222d] px-4 py-3 border-t border-[#2a2e39] text-xs text-zinc-500">
            Showing {trades.length} closed {trades.length === 1 ? 'trade' : 'trades'}
          </div>
        </div>
      )}
    </div>
  );
}
