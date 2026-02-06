'use client';

import { useState, useMemo } from 'react';
import { useJournalSignals } from '@/hooks/useJournalSignals';
import { TradingSignal, TradingMode, SignalStatus, getSymbol, getSide, getNotes } from '@/types/trading';
import { JournalFilters } from '@/components/journal/JournalFilters';
import { TradeTable } from '@/components/journal/TradeTable';
import { SignalInspector } from '@/components/SignalInspector';
import { exportTradesToCsv } from '@/lib/exportCsv';
import { Skeleton } from '@/components/ui/skeleton';
import { BookOpen } from 'lucide-react';

type StatusFilter = 'ALL' | SignalStatus;
type ModeFilter = 'ALL' | TradingMode;

export default function JournalPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL');
  const [modeFilter, setModeFilter] = useState<ModeFilter>('ALL');
  const [inspectSignal, setInspectSignal] = useState<TradingSignal | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);

  const queryMode = modeFilter === 'ALL' ? undefined : modeFilter;
  const { data: signals, isLoading } = useJournalSignals(queryMode);

  const filtered = useMemo(() => {
    if (!signals) return [];

    return signals.filter((s) => {
      // Status filter
      if (statusFilter !== 'ALL' && s.status?.toLowerCase() !== statusFilter) return false;

      // Search
      if (search) {
        const q = search.toLowerCase();
        const sym = getSymbol(s).toLowerCase();
        const side = getSide(s);
        const status = (s.status || '').toLowerCase();
        const notes = (getNotes(s) || '').toLowerCase();
        const mode = (s.mode || s.run_mode || '').toLowerCase();
        if (
          !sym.includes(q) &&
          !side.includes(q) &&
          !status.includes(q) &&
          !notes.includes(q) &&
          !mode.includes(q)
        ) {
          return false;
        }
      }

      return true;
    });
  }, [signals, statusFilter, search]);

  const handleInspect = (signal: TradingSignal) => {
    setInspectSignal(signal);
    setInspectorOpen(true);
  };

  const handleExport = () => {
    if (filtered.length > 0) {
      exportTradesToCsv(filtered);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-zinc-100">Trade Journal</h1>
      </div>

      {/* Filters */}
      <JournalFilters
        search={search}
        onSearchChange={setSearch}
        statusFilter={statusFilter}
        onStatusChange={setStatusFilter}
        modeFilter={modeFilter}
        onModeChange={setModeFilter}
        onExport={handleExport}
        resultCount={filtered.length}
      />

      {/* Table */}
      {isLoading ? (
        <div className="space-y-2">
          {[...Array(8)].map((_, i) => (
            <Skeleton key={i} className="h-10 rounded bg-[#1e222d]" />
          ))}
        </div>
      ) : filtered.length > 0 ? (
        <TradeTable signals={filtered} onInspect={handleInspect} />
      ) : (
        <div className="tv-card p-12 flex flex-col items-center justify-center">
          <BookOpen className="w-10 h-10 text-zinc-700 mb-3" />
          <span className="text-sm text-zinc-500">
            {signals && signals.length > 0
              ? 'No trades match your filters'
              : 'No trade data available'}
          </span>
        </div>
      )}

      {/* Signal Inspector Sheet */}
      <SignalInspector
        signal={inspectSignal}
        open={inspectorOpen}
        onOpenChange={setInspectorOpen}
      />
    </div>
  );
}
