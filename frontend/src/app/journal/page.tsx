'use client';

import { useState, useMemo } from 'react';
import { useJournalSignals } from '@/hooks/useJournalSignals';
import {
  TradingSignal,
  TradingMode,
  SignalStatus,
  getSymbol,
  getSide,
  getNotes,
} from '@/types/trading';
import { JournalFilters } from '@/components/journal/JournalFilters';
import { TradeTable } from '@/components/journal/TradeTable';
import { SignalInspector } from '@/components/SignalInspector';
import { exportTradesToCsv } from '@/lib/exportCsv';
import { Skeleton } from '@/components/ui/skeleton';
import { BookOpen } from 'lucide-react';
import { useConnectionHealth } from '@/hooks/useConnectionHealth';
import { PageStatusBanner } from '@/components/shared/PageStatusBanner';
import { PanelEmptyState } from '@/components/shared/PanelEmptyState';
import { PatternAnalysis } from '@/components/journal/PatternAnalysis';

type StatusFilter = 'ALL' | SignalStatus;
type ModeFilter = 'ALL' | TradingMode;

export default function JournalPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL');
  const [modeFilter, setModeFilter] = useState<ModeFilter>('ALL');
  const [inspectSignal, setInspectSignal] = useState<TradingSignal | null>(
    null,
  );
  const [inspectorOpen, setInspectorOpen] = useState(false);

  const queryMode = modeFilter === 'ALL' ? undefined : modeFilter;
  const { data: signals, isLoading } = useJournalSignals(queryMode);

  const filtered = useMemo(() => {
    if (!signals) return [];
    return signals.filter((s) => {
      if (statusFilter !== 'ALL' && s.status?.toLowerCase() !== statusFilter)
        return false;
      if (search) {
        const q = search.toLowerCase();
        const sym = getSymbol(s).toLowerCase();
        const side = getSide(s);
        const status = (s.status || '').toLowerCase();
        const notes = (getNotes(s) || '').toLowerCase();
        const mode = (s.mode || s.run_mode || '').toLowerCase();
        const model = (s.entry_model || '').toLowerCase();
        const zone = (s.zone_type || '').toLowerCase();
        if (
          !sym.includes(q) &&
          !side.includes(q) &&
          !status.includes(q) &&
          !notes.includes(q) &&
          !mode.includes(q) &&
          !model.includes(q) &&
          !zone.includes(q)
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
    if (filtered.length > 0) exportTradesToCsv(filtered);
  };

  const { status } = useConnectionHealth();

  return (
    <div className='space-y-4'>
      {/* Header */}
      <div>
        <div className='flex items-center gap-2'>
          <BookOpen className='h-4 w-4 text-slate-400' />
          <h1 className='page-title text-lg font-semibold'>Trade Journal</h1>
        </div>
        <p className='page-subtitle mt-0.5 text-xs'>
          Full history of signals, executions, and outcomes.
        </p>
      </div>

      <PageStatusBanner status={status} surfaceLabel='Signals & journal' />

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

      {/* Pattern Analysis Insights */}
      {signals && signals.length >= 3 && <PatternAnalysis signals={signals} />}

      {/* Table */}
      {isLoading ? (
        <div className='space-y-1.5'>
          {[...Array(8)].map((_, i) => (
            <Skeleton key={i} className='h-9 rounded-lg bg-slate-800/60' />
          ))}
        </div>
      ) : filtered.length > 0 ? (
        <TradeTable signals={filtered} onInspect={handleInspect} />
      ) : (
        <div className='tv-card p-4'>
          <PanelEmptyState
            title={
              signals && signals.length > 0
                ? 'No matching trades'
                : 'No trade data'
            }
            description={
              signals && signals.length > 0
                ? 'Adjust filters to see results.'
                : 'Trades will appear here after execution.'
            }
          />
        </div>
      )}

      <SignalInspector
        signal={inspectSignal}
        open={inspectorOpen}
        onOpenChange={setInspectorOpen}
      />
    </div>
  );
}
