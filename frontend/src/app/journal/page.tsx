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

type StatusFilter = 'ALL' | SignalStatus;
type ModeFilter = 'ALL' | TradingMode;

export default function JournalPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL');
  const [modeFilter, setModeFilter] = useState<ModeFilter>('ALL');
  const [inspectSignal, setInspectSignal] = useState<TradingSignal | null>(
    null
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
        <div className='space-y-1.5'>
          {[...Array(8)].map((_, i) => (
            <Skeleton key={i} className='h-9 rounded-lg bg-slate-800/60' />
          ))}
        </div>
      ) : filtered.length > 0 ? (
        <TradeTable signals={filtered} onInspect={handleInspect} />
      ) : (
        <div className='tv-card'>
          <div className='empty-state py-14'>
            <span className='empty-state-text'>
              {signals && signals.length > 0
                ? '[ NO MATCHING TRADES ]'
                : '[ NO TRADE DATA ]'}
            </span>
            <span
              className='mt-1 text-[10px] text-slate-700'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {signals && signals.length > 0
                ? 'adjust filters to see results'
                : 'trades will appear here after execution'}
            </span>
          </div>
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
