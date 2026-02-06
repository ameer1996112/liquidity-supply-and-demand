'use client';

import { cn } from '@/lib/utils';
import { Search, Download } from 'lucide-react';
import { TradingMode, SignalStatus } from '@/types/trading';

type StatusFilter = 'ALL' | SignalStatus;
type ModeFilter = 'ALL' | TradingMode;

interface JournalFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  statusFilter: StatusFilter;
  onStatusChange: (value: StatusFilter) => void;
  modeFilter: ModeFilter;
  onModeChange: (value: ModeFilter) => void;
  onExport: () => void;
  resultCount: number;
}

const STATUS_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: 'ALL', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'closed', label: 'Closed' },
  { value: 'executed', label: 'Executed' },
  { value: 'ai_rejected', label: 'Rejected' },
  { value: 'filtered', label: 'Filtered' },
];

const MODE_OPTIONS: { value: ModeFilter; label: string }[] = [
  { value: 'ALL', label: 'All' },
  { value: 'LIVE', label: 'Live' },
  { value: 'PAPER', label: 'Paper' },
];

export function JournalFilters({
  search,
  onSearchChange,
  statusFilter,
  onStatusChange,
  modeFilter,
  onModeChange,
  onExport,
  resultCount,
}: JournalFiltersProps) {
  return (
    <div className="space-y-3">
      {/* Top row: Search + Export */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-500" />
          <input
            type="text"
            placeholder="Search by symbol, status, notes..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full pl-9 pr-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded-md text-sm text-zinc-200 placeholder:text-zinc-600 font-mono focus:outline-none focus:border-zinc-600 transition-colors"
          />
        </div>
        <button
          onClick={onExport}
          className="flex items-center gap-2 px-3 py-2 bg-[#1e222d] border border-[#2a2e39] rounded-md text-xs text-zinc-400 hover:text-zinc-200 hover:border-zinc-600 transition-colors font-mono"
        >
          <Download className="w-3.5 h-3.5" />
          CSV
        </button>
      </div>

      {/* Bottom row: Status + Mode filters + Count */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          {/* Status Filter */}
          <div className="flex items-center gap-1 bg-[#1e222d] border border-[#2a2e39] rounded-md p-0.5">
            {STATUS_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => onStatusChange(opt.value)}
                className={cn(
                  'font-mono text-[10px] px-2 py-1 rounded transition-colors',
                  statusFilter === opt.value
                    ? 'bg-[#2a2e39] text-zinc-200'
                    : 'text-zinc-500 hover:text-zinc-300'
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Mode Filter */}
          <div className="flex items-center gap-1 bg-[#1e222d] border border-[#2a2e39] rounded-md p-0.5">
            {MODE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => onModeChange(opt.value)}
                className={cn(
                  'font-mono text-[10px] px-2 py-1 rounded transition-colors',
                  modeFilter === opt.value
                    ? 'bg-[#2a2e39] text-zinc-200'
                    : 'text-zinc-500 hover:text-zinc-300'
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <span className="font-mono text-[10px] text-zinc-600">
          {resultCount} trade{resultCount !== 1 ? 's' : ''}
        </span>
      </div>
    </div>
  );
}
