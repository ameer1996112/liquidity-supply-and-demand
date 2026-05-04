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
import { TradePermissionsPanel } from '@/components/dashboard/TradePermissionsPanel';
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
import { useTradePermissionsDashboard } from '@/hooks/useTradePermissionsDashboard';
import { useAccountsComparison } from '@/hooks/useAccounts';
import type { TradingSignal } from '@/types/trading';
import { TableSkeleton } from '@/components/shared/TableStates';
import { cn } from '@/lib/utils';
import { buildOpenPositionFallback } from '@/components/dashboard/openPositionFallback';
import {
  buildEnabledAccountNames,
  countSignalsByAccount,
  filterSignalsByEnabledAccounts,
} from '@/components/dashboard/latestSignalsFilter';

export default function DashboardPage() {
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [showLog, setShowLog] = useState(false);
  // Which account row is selected in the strip — filters the signal table
  const [signalAccountFilter, setSignalAccountFilter] = useState<string | undefined>(undefined);
  const [signalStrategyFilter, setSignalStrategyFilter] = useState<string | undefined>(undefined);

  useEffect(() => { setMounted(true); }, []);

  const { mode: activeMode } = useTradingMode();
  const { broker_profile_id, activeProfile } = useActiveAccount();
  const { status, isConnected } = useConnectionHealth();

  // When a specific account is active, use its run_mode so PAPER accounts show their signals.
  // Fallback to the manually selected activeMode when no account is selected.
  const signalMode = (activeProfile?.run_mode as typeof activeMode | undefined) ?? activeMode;

  const { data: dashboardSummary, isLoading: summaryLoading } = useDashboardSummary();
  const { data: tradePermissions, isLoading: tradePermissionsLoading } = useTradePermissionsDashboard();
  const { data: accounts = [], isLoading: accountsLoading } = useAccountsComparison();
  // Fetch signals for ALL accounts (no broker_profile_id filter) so every account's
  // signals appear in the table. The AccountStrip handles per-account filtering client-side.
  const { data: signals = [], isLoading: signalsLoading } = useTradingSignals(signalMode);
  const { data: positionsData, isLoading: positionsLoading, isError: positionsError } = useActivePositions();

  const enabledAccountNames = useMemo(
    () => buildEnabledAccountNames(accounts),
    [accounts],
  );
  const visibleSignals = useMemo(
    () => filterSignalsByEnabledAccounts(signals, enabledAccountNames),
    [enabledAccountNames, signals],
  );

  const signalIds = useMemo(() => visibleSignals.map((s) => s.id), [visibleSignals]);
  const councilMap = useCouncilSummaries(signalIds);

  const brokerMap = useMemo(() => {
    const map: Record<string, import('@/hooks/usePositions').ActivePosition> = {};
    for (const pos of positionsData?.positions ?? []) {
      map[String(pos.id)] = pos;
    }
    return map;
  }, [positionsData]);

  const fallbackOpenPositions = useMemo(() => {
    return buildOpenPositionFallback(visibleSignals);
  }, [visibleSignals]);

  const dashboardPositions = useMemo(() => {
    const livePositions = positionsData?.positions ?? [];
    return livePositions.length > 0 ? livePositions : fallbackOpenPositions;
  }, [fallbackOpenPositions, positionsData]);

  const usingSignalFallback = dashboardPositions === fallbackOpenPositions && fallbackOpenPositions.length > 0;

  // Signal count per account — shown as badges in the AccountStrip
  const signalCounts = useMemo(() => {
    return countSignalsByAccount(visibleSignals);
  }, [visibleSignals]);

  const { strategyCounts, strategyOptions } = useMemo(() => {
    const counts: Record<string, number> = {};
    const labels = new Map<string, string>();

    for (const signal of visibleSignals) {
      const strategyId = signal.strategy_id?.trim();
      const strategyName = signal.strategy_name?.trim();
      const key = strategyId || strategyName;
      if (!key) continue;

      counts[key] = (counts[key] ?? 0) + 1;
      labels.set(key, strategyName || strategyId || key);
    }

    return {
      strategyCounts: counts,
      strategyOptions: Array.from(labels.entries())
        .sort((left, right) => left[1].localeCompare(right[1]))
        .map(([value, label]) => ({ value, label })),
    };
  }, [visibleSignals]);

  const allAccountsForStrip = useMemo(() => {
    return accounts.filter((account) =>
      enabledAccountNames.some(
        (name) => name.toLowerCase() === account.account_name?.trim().toLowerCase(),
      ),
    );
  }, [accounts, enabledAccountNames]);

  // SignalTable filter pills include only accounts currently enabled for trading.
  const filterAccountNames = useMemo(() => {
    const namesByKey = new Map<string, string>();

    for (const name of enabledAccountNames) {
      namesByKey.set(name.toLowerCase(), name);
    }

    const selected = signalAccountFilter?.trim();
    if (selected && enabledAccountNames.some((name) => name.toLowerCase() === selected.toLowerCase())) {
      namesByKey.set(selected.toLowerCase(), selected);
    }

    return Array.from(namesByKey.values()).sort((left, right) =>
      left.localeCompare(right)
    );
  }, [enabledAccountNames, signalAccountFilter]);

  useEffect(() => {
    if (signalAccountFilter && filterAccountNames.includes(signalAccountFilter)) {
      return;
    }

    const activeProfileName = activeProfile?.name?.trim();
    const preferredAccount =
      (activeProfileName && filterAccountNames.includes(activeProfileName)
        ? activeProfileName
        : undefined) ||
      filterAccountNames[0];

    if (preferredAccount && preferredAccount !== signalAccountFilter) {
      setSignalAccountFilter(preferredAccount);
    } else if (!preferredAccount && signalAccountFilter) {
      setSignalAccountFilter(undefined);
    }
  }, [
    activeProfile?.name,
    filterAccountNames,
    signalAccountFilter,
  ]);

  // Keep for log
  void useSignalStats(broker_profile_id);
  const strategyName = visibleSignals[0]?.entry_model ?? visibleSignals[0]?.zone_type ?? 'Liquidity S&D';

  const { entries: logEntries, clear: clearLog } = useDashboardLog({
    signals: visibleSignals,
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

        <TradePermissionsPanel
          data={tradePermissions}
          isLoading={tradePermissionsLoading}
        />

        {/* ── Open positions ── */}
        <OpenPositionsTable
          positions={dashboardPositions}
          isLoading={positionsLoading && dashboardPositions.length === 0 && !positionsError}
          isFallback={usingSignalFallback}
        />

        {/* ── Signal table + Live log ── */}
        <div className='flex min-h-[320px] flex-1 flex-col gap-3 xl:flex-row'>
          <section className='glow-card flex min-h-[280px] flex-1 flex-col overflow-hidden'>
            <div className='to-panel-header'>
              <div className='flex items-center gap-2'>
                <span className='panel-label'>Latest Signals</span>
                <span className='rounded-full bg-[var(--to-surface-raised)] border border-[var(--to-border)] px-2 py-0.5 font-mono text-[9px] tabular-nums text-[var(--to-text-dim)]'>
                  {visibleSignals.length}
                </span>
              </div>
              <ConnectionPill />
            </div>
            <div className='h-0 flex-1 overflow-hidden p-2'>
              {signalsLoading && visibleSignals.length === 0 ? (
                <TableSkeleton rowCount={8} columnCount={6} />
              ) : (
                <SignalTable
                  signals={visibleSignals}
                  councilMap={councilMap}
                  brokerMap={brokerMap}
                  onSelectSignal={handleSelectSignal}
                  maxRows={150}
                  accountFilter={signalAccountFilter}
                  onAccountFilterChange={(name) => setSignalAccountFilter(name?.trim() || undefined)}
                  accountNames={filterAccountNames}
                  accountSignalCounts={signalCounts}
                  strategyFilter={signalStrategyFilter}
                  onStrategyFilterChange={(strategyId) => setSignalStrategyFilter(strategyId?.trim() || undefined)}
                  strategyOptions={strategyOptions}
                  strategySignalCounts={strategyCounts}
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
