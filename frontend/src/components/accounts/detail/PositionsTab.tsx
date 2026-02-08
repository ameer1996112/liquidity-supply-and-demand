'use client';

import { useQuery } from '@tanstack/react-query';
import { AlertCircle, CheckCircle, XCircle } from 'lucide-react';
import { fetchAccountPositions } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';

interface PositionsTabProps {
  accountName: string;
}

export function PositionsTab({ accountName }: PositionsTabProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['account-positions', accountName],
    queryFn: () => fetchAccountPositions(accountName),
    staleTime: 10_000, // 10s cache
  });

  const brokerPositions = data?.broker || [];
  const dbPositions = data?.db || [];

  const matchedCount = brokerPositions.filter(p => p.reconciliation_status === 'matched').length;
  const orphanedCount = brokerPositions.filter(p => p.reconciliation_status === 'orphaned').length;
  const pendingCount = brokerPositions.filter(p => p.reconciliation_status === 'pending').length;

  return (
    <div className="space-y-6">
      {/* Reconciliation Status */}
      {!isLoading && brokerPositions.length > 0 && (
        <div className={`rounded-lg border px-4 py-3 flex items-center gap-3 ${
          orphanedCount > 0 || pendingCount > 0
            ? 'border-amber-500/30 bg-amber-500/5'
            : 'border-emerald-500/30 bg-emerald-500/5'
        }`}>
          {orphanedCount > 0 || pendingCount > 0 ? (
            <AlertCircle className="h-5 w-5 text-amber-500 flex-shrink-0" />
          ) : (
            <CheckCircle className="h-5 w-5 text-emerald-500 flex-shrink-0" />
          )}
          <div>
            <div className={`text-sm font-medium ${orphanedCount > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
              {orphanedCount > 0 || pendingCount > 0 ? (
                <>
                  {orphanedCount > 0 && `${orphanedCount} unreconciled position${orphanedCount > 1 ? 's' : ''}`}
                  {orphanedCount > 0 && pendingCount > 0 && ', '}
                  {pendingCount > 0 && `${pendingCount} pending reconciliation`}
                </>
              ) : (
                `All positions matched (${matchedCount} broker = ${dbPositions.length} DB)`
              )}
            </div>
            {(orphanedCount > 0 || pendingCount > 0) && (
              <div className="text-xs text-amber-600/80 mt-0.5">
                Position sync will attempt reconciliation on next refresh.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Broker Positions */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-zinc-300">
            Broker Positions
            {!isLoading && <span className="ml-2 text-zinc-500">({brokerPositions.length})</span>}
          </h3>
        </div>

        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map(i => (
              <Skeleton key={i} className="h-16 bg-[#1e222d]" />
            ))}
          </div>
        ) : error ? (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-600">
            Failed to fetch positions. This endpoint may not be implemented yet.
          </div>
        ) : brokerPositions.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-lg border border-[#2a2e39] bg-[#1e222d]/50 py-12 text-zinc-500">
            <XCircle className="h-10 w-10 mb-3 opacity-50" />
            <p className="text-sm font-mono">No open positions</p>
            <p className="text-xs text-zinc-600 mt-1">
              Positions from MetaAPI will appear here.
            </p>
          </div>
        ) : (
          <div className="tv-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#2a2e39] bg-[#1e222d]/50">
                    <th className="text-left px-4 py-2 text-xs font-mono text-zinc-500">Symbol</th>
                    <th className="text-left px-4 py-2 text-xs font-mono text-zinc-500">Side</th>
                    <th className="text-right px-4 py-2 text-xs font-mono text-zinc-500">Lots</th>
                    <th className="text-right px-4 py-2 text-xs font-mono text-zinc-500">Entry</th>
                    <th className="text-right px-4 py-2 text-xs font-mono text-zinc-500">Current</th>
                    <th className="text-right px-4 py-2 text-xs font-mono text-zinc-500">SL</th>
                    <th className="text-right px-4 py-2 text-xs font-mono text-zinc-500">TP</th>
                    <th className="text-right px-4 py-2 text-xs font-mono text-zinc-500">P&L</th>
                    <th className="text-left px-4 py-2 text-xs font-mono text-zinc-500">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {brokerPositions.map((pos, idx) => {
                    const isProfit = pos.profit >= 0;
                    const statusColor = {
                      matched: 'text-emerald-500',
                      orphaned: 'text-amber-500',
                      pending: 'text-zinc-500',
                    }[pos.reconciliation_status];

                    return (
                      <tr key={pos.id || idx} className="border-b border-[#2a2e39] hover:bg-[#1e222d]/30">
                        <td className="px-4 py-3 font-mono text-xs text-zinc-200">{pos.symbol}</td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-mono ${pos.side === 'buy' ? 'text-[#26a69a]' : 'text-[#ef5350]'}`}>
                            {pos.side.toUpperCase()}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-xs text-zinc-300">{pos.volume.toFixed(2)}</td>
                        <td className="px-4 py-3 text-right font-mono text-xs text-zinc-300">{pos.open_price.toFixed(5)}</td>
                        <td className="px-4 py-3 text-right font-mono text-xs text-zinc-300">
                          {pos.current_price ? pos.current_price.toFixed(5) : '-'}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-xs text-zinc-400">
                          {pos.sl ? pos.sl.toFixed(5) : '-'}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-xs text-zinc-400">
                          {pos.tp ? pos.tp.toFixed(5) : '-'}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <span className={`font-mono text-xs font-semibold ${isProfit ? 'text-[#26a69a]' : 'text-[#ef5350]'}`}>
                            {isProfit ? '+' : ''}${pos.profit.toFixed(2)}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`text-xs font-mono ${statusColor}`}>
                            {pos.reconciliation_status}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>

      {/* DB Positions */}
      <section className="space-y-3">
        <h3 className="text-sm font-medium text-zinc-300">
          Database Positions
          {!isLoading && <span className="ml-2 text-zinc-500">({dbPositions.length})</span>}
        </h3>

        {dbPositions.length === 0 ? (
          <div className="rounded-lg border border-[#2a2e39] bg-[#1e222d]/50 px-4 py-8 text-center text-xs text-zinc-500">
            No active positions in database.
          </div>
        ) : (
          <div className="tv-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#2a2e39] bg-[#1e222d]/50">
                    <th className="text-left px-4 py-2 text-xs font-mono text-zinc-500">Symbol</th>
                    <th className="text-left px-4 py-2 text-xs font-mono text-zinc-500">Side</th>
                    <th className="text-right px-4 py-2 text-xs font-mono text-zinc-500">Size</th>
                    <th className="text-right px-4 py-2 text-xs font-mono text-zinc-500">Entry</th>
                    <th className="text-right px-4 py-2 text-xs font-mono text-zinc-500">SL</th>
                    <th className="text-right px-4 py-2 text-xs font-mono text-zinc-500">TP</th>
                    <th className="text-left px-4 py-2 text-xs font-mono text-zinc-500">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {dbPositions.map((pos: any, idx: number) => (
                    <tr key={pos.id || idx} className="border-b border-[#2a2e39] hover:bg-[#1e222d]/30">
                      <td className="px-4 py-3 font-mono text-xs text-zinc-200">{pos.symbol}</td>
                      <td className="px-4 py-3">
                        <span className={`text-xs font-mono ${pos.side === 'buy' ? 'text-[#26a69a]' : 'text-[#ef5350]'}`}>
                          {pos.side?.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-xs text-zinc-300">{pos.size?.toFixed(2)}</td>
                      <td className="px-4 py-3 text-right font-mono text-xs text-zinc-300">{pos.entry?.toFixed(5)}</td>
                      <td className="px-4 py-3 text-right font-mono text-xs text-zinc-400">{pos.sl?.toFixed(5)}</td>
                      <td className="px-4 py-3 text-right font-mono text-xs text-zinc-400">{pos.tp?.toFixed(5)}</td>
                      <td className="px-4 py-3 font-mono text-xs text-zinc-500">{pos.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
