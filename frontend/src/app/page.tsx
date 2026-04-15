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
  // Which account row is selected in the strip — filters the signal table
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
  // Fetch signals for ALL accounts (no broker_profile_id filter) so every account's
  // signals appear in the table. The AccountStrip handles per-account filtering client-side.
  const { data: signals = [], isLoading: signalsLoading } = useTradingSignals(signalMode);
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

  // Signal count per account — shown as badges in the AccountStrip
  const signalCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const s of signals) {
      const nameRaw = (s as any).account_name;
      const name = typeof nameRaw === 'string' ? nameRaw.trim() : nameRaw;
      if (name) counts[name] = (counts[name] ?? 0) + 1;
    }
    return counts;
  }, [signals]);

  // All distinct account names seen in signals (includes deleted accounts like ACG-DEMO)
  // Used as filter options in the signal table — ensures archived account signals are reachable.
  const signalAccountNames = useMemo(() => Object.keys(signalCounts).sort(), [signalCounts]);

  // Merge live accounts with archived ones derived from signals.
  // Archived accounts (deleted from account_strategies) appear with minimal info
  // so the AccountStrip still shows them and their signal count badges.
  const allAccountsForStrip = useMemo(() => {
    // Drop accounts that were explicitly archived in the DB (Paper, old ACG-DEMO, etc.)
    const liveAccounts = accounts.filter((a) => !a.is_archived && a.status !== 'archived');
    const liveNames = new Set(liveAccounts.map((a) => a.account_name));
    const archivedEntries = signalAccountNames
      .filter((name) => !liveNames.has(name))
      .map((name) => ({
        account_name: name,
        connection_status: 'disconnected' as const,
        balance: null,
        equity: null,
        account_type: undefined,
        prop_firm_name: undefined,
        daily_pnl: undefined,
        daily_pnl_pct: undefined,
      }));
    return [...liveAccounts, ...(archivedEntries as any[])];
  }, [accounts, signalAccountNames]);

  // SignalTable filter pills are derived from signals (to keep deleted/archived accounts reachable),
  // plus the currently-selected account (so selecting a 0-signal account still shows an active pill).
  const filterAccountNames = useMemo(() => {
    const names = new Set(signalAccountNames);
    const selected = signalAccountFilter?.trim();
    if (selected) names.add(selected);
    return Array.from(names).sort();
  }, [signalAccountNames, signalAccountFilter]);

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

        {/* ── Account strip — click a row to filter signals below ── */}
        <section>
          <p className='kpi-meta mb-2'>Accounts</p>
          <AccountStrip
            accounts={allAccountsForStrip}
            isLoading={accountsLoading}
            activeAccount={signalAccountFilter}
            onAccountSelect={(name) => setSignalAccountFilter(name?.trim() || undefined)}
            signalCounts={signalCounts}
          />
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
                  onAccountFilterChange={(name) => setSignalAccountFilter(name?.trim() || undefined)}
                  accountNames={filterAccountNames}
                  accountSignalCounts={signalCounts}
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
