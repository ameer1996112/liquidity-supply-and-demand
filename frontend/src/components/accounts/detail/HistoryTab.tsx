'use client';

import { useState, useEffect, useMemo } from 'react';
import { Download, Filter, Loader2, ArrowUpRight, ArrowDownRight, Database, Globe } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getPortfolioControlUrl } from '@/lib/api';

const formatCurrency = (val: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(val);

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
  source?: 'database' | 'metaapi';
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
      const params = new URLSearchParams();
      if (dateRange !== 'all') {
        const days = parseInt(dateRange);
        params.append('days', days.toString());
      }
      if (outcomeFilter !== 'all') {
        params.append('outcome', outcomeFilter);
      }

      const url = getPortfolioControlUrl(
        `/accounts/${encodeURIComponent(accountName)}/history?${params}`,
      );
      if (!url) throw new Error('Backend API URL not configured');
      const response = await fetch(url);

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

  const stats = useMemo(() => {
    if (!trades.length) return null;
    const wins = trades.filter(t => t.pnl_usd > 0);
    const losses = trades.filter(t => t.pnl_usd <= 0);
    
    const grossProfit = wins.reduce((sum, t) => sum + t.pnl_usd, 0);
    const grossLoss = Math.abs(losses.reduce((sum, t) => sum + t.pnl_usd, 0));
    const netPnl = grossProfit - grossLoss;
    
    return {
      totalTrades: trades.length,
      winRate: (wins.length / trades.length) * 100,
      netPnl,
      profitFactor: grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? 999 : 0
    };
  }, [trades]);

  const exportCSV = () => {
    const headers = [
      'Symbol', 'Side', 'Size', 'Entry', 'Exit', 'P&L USD', 'R Multiple', 'MAE', 'Exit Time', 'Source'
    ];
    const rows = trades.map((t) => [
      t.symbol,
      t.side,
      t.size.toString(),
      t.entry.toFixed(5),
      t.exit.toFixed(5),
      t.pnl_usd.toFixed(2),
      t.r_multiple?.toFixed(2) || 'N/A',
      t.mae?.toFixed(2) || 'N/A',
      t.exit_time ? new Date(t.exit_time).toLocaleString() : '-',
      t.source || 'database'
    ]);

    const csv = [headers, ...rows].map((row) => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${accountName}-history-${dateRange}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className='flex flex-col h-full space-y-4'>
      
      {/* Filters & Export Bar */}
      <div className='flex items-center justify-between bg-[#1e222d] border border-[#2a2e39] rounded-xl p-3 shadow-sm'>
        <div className='flex items-center gap-3'>
          <div className='flex items-center gap-2 pl-1 pr-3 border-r border-[#2a2e39]'>
             <Filter className='h-4 w-4 text-emerald-500/70' />
             <span className='text-xs font-medium text-[var(--to-text-secondary)] uppercase tracking-wider'>Filters</span>
          </div>

          <select 
            value={dateRange} 
            onChange={(e: any) => setDateRange(e.target.value)}
            className="h-8 px-2 bg-[#151821] border border-[#2a2e39] text-xs font-medium text-[var(--to-text-secondary)] rounded-md outline-none focus:ring-1 focus:ring-emerald-500/50"
          >
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
            <option value="90d">Last 90 Days</option>
            <option value="all">All Time</option>
          </select>

          <select 
            value={outcomeFilter} 
            onChange={(e: any) => setOutcomeFilter(e.target.value)}
            className="h-8 px-2 bg-[#151821] border border-[#2a2e39] text-xs font-medium text-[var(--to-text-secondary)] rounded-md outline-none focus:ring-1 focus:ring-emerald-500/50"
          >
            <option value="all">All Trades</option>
            <option value="win">Wins Only</option>
            <option value="loss">Losses Only</option>
          </select>
        </div>

        <Button
          variant='outline'
          size='sm'
          onClick={exportCSV}
          disabled={trades.length === 0}
          className='h-8 px-3 text-xs border-[#2a2e39] bg-[#151821] text-[var(--to-text-primary)] hover:bg-[#2a2e39] hover:text-white transition-all disabled:opacity-50'
        >
          <Download className='h-3.5 w-3.5 mr-2 text-emerald-500/70' />
          Export CSV
        </Button>
      </div>

      {/* Aggregate Stats Strip */}
      {stats && !loading && !error && (
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-[#1e222d] border border-[#2a2e39] rounded-xl p-4 flex flex-col justify-center">
            <span className="text-[10px] uppercase tracking-wider text-[var(--to-text-dim)] font-medium mb-1">Period Net P&L</span>
            <span className={`text-lg font-mono font-bold tracking-tight ${stats.netPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {stats.netPnl >= 0 ? '+' : ''}{formatCurrency(stats.netPnl)}
            </span>
          </div>
          <div className="bg-[#1e222d] border border-[#2a2e39] rounded-xl p-4 flex flex-col justify-center">
            <span className="text-[10px] uppercase tracking-wider text-[var(--to-text-dim)] font-medium mb-1">Win Rate</span>
            <span className="text-lg font-mono font-bold tracking-tight text-[var(--to-text-primary)]">
              {stats.winRate.toFixed(1)}<span className="text-sm text-[var(--to-text-dim)]">%</span>
            </span>
          </div>
          <div className="bg-[#1e222d] border border-[#2a2e39] rounded-xl p-4 flex flex-col justify-center">
            <span className="text-[10px] uppercase tracking-wider text-[var(--to-text-dim)] font-medium mb-1">Profit Factor</span>
            <span className={`text-lg font-mono font-bold tracking-tight ${stats.profitFactor >= 1.5 ? 'text-emerald-400' : stats.profitFactor < 1 ? 'text-rose-400' : 'text-[var(--to-text-primary)]'}`}>
              {stats.profitFactor.toFixed(2)}x
            </span>
          </div>
          <div className="bg-[#1e222d] border border-[#2a2e39] rounded-xl p-4 flex flex-col justify-center">
            <span className="text-[10px] uppercase tracking-wider text-[var(--to-text-dim)] font-medium mb-1">Total Trades</span>
            <span className="text-lg font-mono font-bold tracking-tight text-[var(--to-text-primary)]">
              {stats.totalTrades}
            </span>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className='flex-1 rounded-xl border border-[#2a2e39] bg-[#151821] overflow-hidden flex flex-col min-h-[400px]'>
        
        {loading && (
          <div className='flex-1 flex flex-col items-center justify-center py-20'>
            <div className='relative flex items-center justify-center h-12 w-12 rounded-full bg-[#1e222d] border border-[#2a2e39] shadow-lg'>
              <div className="absolute inset-0 rounded-full border border-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.1)]"></div>
              <Loader2 className='h-5 w-5 animate-spin text-emerald-500' />
            </div>
            <p className="mt-4 text-sm text-[var(--to-text-dim)] font-medium">Syncing history ledger...</p>
          </div>
        )}

        {error && !loading && (
          <div className='flex-1 flex flex-col items-center justify-center p-8'>
            <div className="p-4 rounded-full bg-rose-500/10 mb-4 border border-rose-500/20">
              <ArrowDownRight className="h-6 w-6 text-rose-500" />
            </div>
            <h3 className="text-[var(--to-text-primary)] font-medium mb-1">Reconciliation Failed</h3>
            <p className="text-sm text-[var(--to-text-dim)] text-center max-w-sm">{error}</p>
          </div>
        )}

        {!loading && !error && trades.length === 0 && (
          <div className='flex-1 flex flex-col items-center justify-center p-12'>
            <div className="w-16 h-16 rounded-full bg-[#1e222d] border border-[#2a2e39] flex items-center justify-center mb-5 shadow-inner">
              <Database className="h-6 w-6 text-[#2a2e39]" />
            </div>
            <h3 className="text-[var(--to-text-secondary)] font-medium text-lg mb-2">No Historical Data</h3>
            <p className="text-sm text-[var(--to-text-dim)] text-center max-w-md">
              No closed executions found for <span className="text-[var(--to-text-primary)]">{accountName}</span> within the selected parameters.
            </p>
          </div>
        )}

        {!loading && !error && trades.length > 0 && (
          <div className='overflow-auto flex-1'>
            <table className='w-full text-sm whitespace-nowrap'>
              <thead className='sticky top-0 z-10 bg-[#151821] shadow-[0_1px_0_#2a2e39]'>
                <tr>
                  <th className='px-5 py-3.5 text-left text-[10px] font-bold text-[var(--to-text-dim)] uppercase tracking-wider'>Symbol</th>
                  <th className='px-5 py-3.5 text-left text-[10px] font-bold text-[var(--to-text-dim)] uppercase tracking-wider'>Type</th>
                  <th className='px-5 py-3.5 text-right text-[10px] font-bold text-[var(--to-text-dim)] uppercase tracking-wider'>Size</th>
                  <th className='px-5 py-3.5 text-right text-[10px] font-bold text-[var(--to-text-dim)] uppercase tracking-wider'>Entry Price</th>
                  <th className='px-5 py-3.5 text-right text-[10px] font-bold text-[var(--to-text-dim)] uppercase tracking-wider'>Exit Price</th>
                  <th className='px-5 py-3.5 text-right text-[10px] font-bold text-[var(--to-text-dim)] uppercase tracking-wider'>Net P&L</th>
                  <th className='px-5 py-3.5 text-right text-[10px] font-bold text-[var(--to-text-dim)] uppercase tracking-wider'>R:R</th>
                  <th className='px-5 py-3.5 text-left text-[10px] font-bold text-[var(--to-text-dim)] uppercase tracking-wider'>Exit Time</th>
                  <th className='px-5 py-3.5 text-center text-[10px] font-bold text-[var(--to-text-dim)] uppercase tracking-wider'>Source</th>
                </tr>
              </thead>
              <tbody className='divide-y divide-[#1e222d] bg-[#181b26]'>
                {trades.map((trade) => {
                  const isWin = trade.pnl_usd > 0;
                  const isLoss = trade.pnl_usd < 0;
                  
                  return (
                    <tr key={trade.id} className='group hover:bg-[#1e222d]/60 transition-colors'>
                      <td className='px-5 py-3'>
                        <div className="flex items-center gap-2">
                           <div className={`w-1 h-3 rounded-full ${isWin ? 'bg-emerald-500' : isLoss ? 'bg-rose-500' : 'bg-gray-500'}`} />
                           <span className="font-mono font-medium text-[var(--to-text-primary)]">{trade.symbol}</span>
                        </div>
                      </td>
                      <td className='px-5 py-3'>
                        <div className={`inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider px-2 py-0.5 rounded border ${
                            trade.side === 'buy'
                              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                              : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                            }`}
                        >
                          {trade.side === 'buy' ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                          {trade.side}
                        </div>
                      </td>
                      <td className='px-5 py-3 text-right font-mono text-xs text-[var(--to-text-secondary)]'>
                        {trade.size.toFixed(2)}
                      </td>
                      <td className='px-5 py-3 text-right font-mono text-xs text-[var(--to-text-secondary)]'>
                        {trade.entry.toFixed(5)}
                      </td>
                      <td className='px-5 py-3 text-right font-mono text-xs text-[var(--to-text-secondary)]'>
                        {trade.exit.toFixed(5)}
                      </td>
                      <td className='px-5 py-3 text-right font-mono text-sm font-semibold'>
                        <span className={isWin ? 'text-emerald-400' : isLoss ? 'text-rose-400' : 'text-gray-400'}>
                          {isWin ? '+' : ''}{formatCurrency(trade.pnl_usd)}
                        </span>
                      </td>
                      <td className='px-5 py-3 text-right font-mono text-xs text-[var(--to-text-dim)]'>
                        {trade.r_multiple != null ? (
                           <span className={trade.r_multiple >= 1 ? 'text-emerald-400/80' : 'text-rose-400/80'}>{trade.r_multiple.toFixed(2)}R</span>
                        ) : (
                           '-'
                        )}
                      </td>
                      <td className='px-5 py-3 text-left font-mono text-xs text-[var(--to-text-dim)] group-hover:text-[var(--to-text-secondary)] transition-colors'>
                        {trade.exit_time ? new Date(trade.exit_time).toLocaleString(undefined, {
                          month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit'
                        }) : '-'}
                      </td>
                      <td className='px-5 py-3 text-center'>
                        {trade.source === 'metaapi' ? (
                          <div className="inline-flex items-center justify-center p-1 rounded-md bg-[#2a2e39]/50 text-blue-400 tooltip-trigger" title="Synced from Broker">
                            <Globe className="w-3.5 h-3.5 shadow-sm" />
                          </div>
                        ) : (
                          <div className="inline-flex items-center justify-center p-1 rounded-md bg-[#2a2e39]/50 text-amber-500/80 tooltip-trigger" title="Database Executed">
                            <Database className="w-3.5 h-3.5 shadow-sm" />
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

    </div>
  );
}
