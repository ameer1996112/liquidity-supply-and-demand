'use client';

import { useCallback, useMemo, useState, useEffect } from 'react';
import { SignalInspector } from '@/components/SignalInspector';
import { SignalTable } from '@/components/dashboard/SignalTable';
import { LiveLog } from '@/components/dashboard/LiveLog';
import { ConnectionPill } from '@/components/dashboard/ConnectionPill';
import { MarketSessionBanner } from '@/components/dashboard/MarketSessionBanner';
import { PageStatusBanner } from '@/components/shared/PageStatusBanner';
import { AggregateBar } from '@/components/dashboard/AggregateBar';
import { AccountStrip } from '@/components/dashboard/AccountStrip';
import { OpenPositionsTable } from '@/components/dashboard/OpenPositionsTable';
import { useTradingMode } from '@/providers/TradingModeProvider';
import { useActiveAccount } from '@/providers/ActiveAccountProvider';
import {
  useSignalStats,
  useTradingSignals,
  useCouncilSummaries,
} from '@/hooks/useTradingSignals';
import { useConnectionHealth } from '@/hooks/useConnectionHealth';
import { useActivePositions } from '@/hooks/usePositions';
import { useDashboardLog } from '@/hooks/useDashboardLog';
import { useDashboardSummary } from '@/hooks/useDashboardSummary';
import { useAccountsComparison } from '@/hooks/useAccounts';
import type { TradingSignal } from '@/types/trading';
import { TableSkeleton } from '@/components/shared/TableStates';
import { cn } from '@/lib/utils';

export default function DashboardPage() {
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [showLog, setShowLog] = useState(false);
  const [signalAccountFilter, setSignalAccountFilter] = useState<string | undefined>(undefined);

  useEffect(() => { setMounted(true); }, []);

  const { mode: activeMode } = useTradingMode();
  const { broker_profile_id, activeProfile } = useActiveAccount();
  const { status, isConnected } = useConnectionHealth();

  // When a specific account is active, use its run_mode so PAPER accounts show their signals.
  // Fallback to the manually selected activeMode when no account is selected.
  const signalMode = (activeProfile?.run_mode as typeof activeMode | undefined) ?? activeMode;

  const { data: dashboardSummary, isLoading: summaryLoading } = useDashboardSummary();
  const { data: accounts = [], isLoading: accountsLoading } = useAccountsComparison();
  const { data: signals = [], isLoading: signalsLoading } = useTradingSignals(signalMode, broker_profile_id);
  const { data: positionsData, isLoading: positionsLoading } = useActivePositions();

  const signalIds = useMemo(() => signals.map((s) => s.id), [signals]);
  const councilMap = useCouncilSummaries(signalIds);

  const brokerMap = useMemo(() => {
    const map: Record<string, import('@/hooks/usePositions').ActivePosition> = {};
    for (const pos of positionsData?.positions ?? []) {
      map[String(pos.id)] = pos;
    }
    return map;
  }, [positionsData]);

  // Keep for log
  void useSignalStats(broker_profile_id);
  const strategyName = signals[0]?.entry_model ?? signals[0]?.zone_type ?? 'Liquidity S&D';

  const { entries: logEntries, clear: clearLog } = useDashboardLog({
    signals,
    activeMode,
    isConnected,
    strategyName,
    timeframe: '5M',
    mounted,
  });

  const handleSelectSignal = useCallback((signal: TradingSignal) => {
    setSelectedSignal(signal);
    setInspectorOpen(true);
  }, []);

  return (
    <div className='flex h-full min-h-0 flex-col'>
      {/* ── Aggregate bar (pinned) ── */}
      <AggregateBar
        summary={dashboardSummary}
        isLoading={summaryLoading}
        isConnected={isConnected}
      />

      <div className='flex flex-1 min-h-0 flex-col gap-3 overflow-y-auto p-3'>
        {/* ── Status banners ── */}
        <PageStatusBanner status={status} surfaceLabel='Dashboard' />
        <MarketSessionBanner />

        {/* ── Account strip ── */}
        <section>
          <p className='kpi-meta mb-2'>Accounts</p>
          <AccountStrip accounts={accounts} isLoading={accountsLoading} />
        </section>

        {/* ── Open positions ── */}
        <OpenPositionsTable
          positions={positionsData?.positions ?? []}
          isLoading={positionsLoading}
        />

        {/* ── Signal table + Live log ── */}
        <div className='flex min-h-[320px] flex-1 flex-col gap-3 xl:flex-row'>
          <section className='glow-card flex min-h-[280px] flex-1 flex-col overflow-hidden'>
            <div className='to-panel-header'>
              <div className='flex items-center gap-2'>
                <span className='panel-label'>Latest Signals</span>
                <span className='rounded-full bg-[var(--to-surface-raised)] border border-[var(--to-border)] px-2 py-0.5 font-mono text-[9px] tabular-nums text-[var(--to-text-dim)]'>
                  {signals.length}
                </span>
              </div>
              <ConnectionPill />
            </div>
            <div className='h-0 flex-1 overflow-hidden p-2'>
              {signalsLoading && signals.length === 0 ? (
                <TableSkeleton rowCount={8} columnCount={6} />
              ) : (
                <SignalTable
                  signals={signals}
                  councilMap={councilMap}
                  brokerMap={brokerMap}
                  onSelectSignal={handleSelectSignal}
                  maxRows={150}
                  accountFilter={signalAccountFilter}
                  onAccountFilterChange={setSignalAccountFilter}
                  accountNames={dashboardSummary?.accounts.map((a) => a.name) ?? []}
                />
              )}
            </div>
          </section>

          <aside className='flex min-h-0 w-full flex-col gap-2 xl:w-[320px]'>
            <button
              className='xl:hidden text-[11px] text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] transition-colors py-1 px-0.5 text-left'
              onClick={() => setShowLog((prev) => !prev)}
            >
              {showLog ? 'Hide Live Log ▲' : 'Show Live Log ▼'}
            </button>
            <section
              className={cn(
                'min-h-0 flex-1 overflow-hidden',
                !showLog && 'hidden xl:block'
              )}
            >
              <LiveLog entries={logEntries} onClear={clearLog} className='h-full' />
            </section>
          </aside>
        </div>
      </div>



      <SignalInspector
        signal={selectedSignal}
        open={inspectorOpen}
        onOpenChange={setInspectorOpen}
      />
    </div>
  );
}
