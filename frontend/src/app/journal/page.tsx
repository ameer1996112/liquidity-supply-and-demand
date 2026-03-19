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
import { BookOpen, CalendarDays, List, Flame, Snowflake } from 'lucide-react';
import { useConnectionHealth } from '@/hooks/useConnectionHealth';
import { PageStatusBanner } from '@/components/shared/PageStatusBanner';
import { PanelEmptyState } from '@/components/shared/PanelEmptyState';
import { PatternAnalysis } from '@/components/journal/PatternAnalysis';
import { CalendarPnlView } from '@/components/journal/CalendarPnlView';
import { cn } from '@/lib/utils';
import { getPnl } from '@/types/trading';

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
  const [viewMode, setViewMode] = useState<'table' | 'calendar'>('table');

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

  // Streak calculation
  const { currentStreak, streakType } = useMemo(() => {
    if (!signals || signals.length === 0)
      return { currentStreak: 0, streakType: 'none' as const };
    const closed = signals.filter((s) => getPnl(s) != null);
    if (closed.length === 0)
      return { currentStreak: 0, streakType: 'none' as const };
    const lastPnl = getPnl(closed[0]) ?? 0;
    const type = lastPnl >= 0 ? 'win' : 'loss';
    let count = 0;
    for (const s of closed) {
      const p = getPnl(s) ?? 0;
      if ((type === 'win' && p >= 0) || (type === 'loss' && p < 0)) count++;
      else break;
    }
    return {
      currentStreak: count,
      streakType: type as 'win' | 'loss' | 'none',
    };
  }, [signals]);

  return (
    <div className='space-y-4'>
      {/* Header */}
      <div className='flex items-start justify-between gap-3 flex-wrap'>
        <div>
          <div className='flex items-center gap-2'>
            <BookOpen className='h-4 w-4 text-[var(--to-text-dim)]' />
            <h1 className='page-title text-lg font-semibold'>Trade Journal</h1>
            {/* Streak indicator */}
            {currentStreak >= 2 && (
              <div
                className={cn(
                  'flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-bold',
                  streakType === 'win'
                    ? 'bg-[var(--to-long)]/12 text-[var(--to-long)] border border-[var(--to-long)]/25'
                    : 'bg-[var(--to-short)]/12 text-[var(--to-short)] border border-[var(--to-short)]/25'
                )}
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {streakType === 'win' ? (
                  <Flame className='h-3 w-3' />
                ) : (
                  <Snowflake className='h-3 w-3' />
                )}
                {currentStreak} {streakType === 'win' ? 'W' : 'L'} streak
              </div>
            )}
          </div>
          <p className='page-subtitle mt-0.5 text-xs'>
            Full history of signals, executions, and outcomes.
          </p>
        </div>

        {/* View mode toggle */}
        <div className='flex items-center gap-1 rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)] p-0.5'>
          <button
            onClick={() => setViewMode('table')}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[10px] font-medium transition-colors',
              viewMode === 'table'
                ? 'bg-[var(--to-surface-raised)] text-[var(--to-text-primary)]'
                : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]'
            )}
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            <List className='h-3 w-3' />
            Table
          </button>
          <button
            onClick={() => setViewMode('calendar')}
            className={cn(
              'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[10px] font-medium transition-colors',
              viewMode === 'calendar'
                ? 'bg-[var(--to-surface-raised)] text-[var(--to-text-primary)]'
                : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]'
            )}
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            <CalendarDays className='h-3 w-3' />
            Calendar
          </button>
        </div>
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

      {/* Calendar view */}
      {viewMode === 'calendar' ? (
        signals && signals.length > 0 ? (
          <CalendarPnlView signals={signals} />
        ) : (
          <div className='tv-card p-4'>
            <PanelEmptyState
              title='No trade data'
              description='Trades will appear here after execution.'
            />
          </div>
        )
      ) : (
        <>
          {/* Pattern Analysis Insights */}
          {signals && signals.length >= 3 && (
            <PatternAnalysis signals={signals} />
          )}

          {/* Table */}
          {isLoading ? (
            <div className='space-y-1.5'>
              {[...Array(8)].map((_, i) => (
                <Skeleton key={i} className='h-9 rounded-lg bg-[var(--to-surface-raised)]/60' />
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
        </>
      )}

      <SignalInspector
        signal={inspectSignal}
        open={inspectorOpen}
        onOpenChange={setInspectorOpen}
      />
    </div>
  );
}
