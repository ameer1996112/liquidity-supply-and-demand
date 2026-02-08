'use client';

import { useState } from 'react';
import { Download, Filter } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface HistoryTabProps {
  accountName: string;
}

export function HistoryTab({ accountName }: HistoryTabProps) {
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d' | 'all'>('30d');
  const [outcomeFilter, setOutcomeFilter] = useState<'all' | 'win' | 'loss'>('all');

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
          className="border-[#2a2e39] text-zinc-400 hover:bg-[#2a2e39] hover:text-zinc-200"
        >
          <Download className="h-3.5 w-3.5 mr-1.5" />
          Export CSV
        </Button>
      </div>

      {/* Empty State */}
      <div className="flex flex-col items-center justify-center rounded-lg border border-[#2a2e39] bg-[#1e222d]/50 py-16 text-zinc-500">
        <div className="text-4xl mb-4">📊</div>
        <p className="text-sm font-mono">Trade History</p>
        <p className="text-xs text-zinc-600 mt-1 max-w-md text-center">
          Trade history from trading_signals table will appear here.
          This will show closed trades with P&L, R multiple, MAE, and exit details.
        </p>
        <div className="mt-4 text-xs text-zinc-600">
          <strong>Coming soon:</strong> Filterable table, export CSV, inline notes
        </div>
      </div>
    </div>
  );
}
