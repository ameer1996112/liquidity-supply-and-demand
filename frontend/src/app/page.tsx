'use client';

import { useState } from 'react';
import { SignalInspector } from '@/components/SignalInspector';
import { ActiveTradesPanel } from '@/components/dashboard/ActiveTradesPanel';
import { RecentSignalsPanel } from '@/components/dashboard/RecentSignalsPanel';
import { MiniEquityChart } from '@/components/dashboard/MiniEquityChart';
import { ExecutionQualityWidget } from '@/components/dashboard/ExecutionQualityWidget';
import { PortfolioRiskWidget } from '@/components/dashboard/PortfolioRiskWidget';
import { EvaluationDashboard } from '@/components/evaluation/EvaluationDashboard';
import { PineConfigStatus } from '@/components/dashboard/PineConfigStatus';
import { useTradingMode } from '@/providers/TradingModeProvider';
import { TradingSignal } from '@/types/trading';
import { CandlestickChart, Server, Radio } from 'lucide-react';

export default function DashboardPage() {
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(
    null
  );
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const { mode: activeMode } = useTradingMode();

  const handleSelectSignal = (signal: TradingSignal) => {
    setSelectedSignal(signal);
    setInspectorOpen(true);
  };

  return (
    <div className='flex h-full min-h-0 flex-col gap-3'>
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className='flex shrink-0 items-center justify-between gap-3'>
        <div>
          <h1 className='page-title text-lg font-semibold'>Dashboard</h1>
          <p className='page-subtitle text-xs'>
            Live command center · market orders · 5-minute zones
          </p>
        </div>

        {/* 5m Timeframe badge — always visible */}
        <div className='flex items-center gap-2'>
          <span className='tf-badge'>
            <Radio className='h-3 w-3' />
            5M
          </span>
          <span
            className={
              activeMode === 'LIVE'
                ? 'flex items-center gap-1.5 rounded-md border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 font-mono text-[10px] font-semibold uppercase tracking-wider text-emerald-400'
                : 'flex items-center gap-1.5 rounded-md border border-amber-500/20 bg-amber-500/10 px-2.5 py-1 font-mono text-[10px] font-semibold uppercase tracking-wider text-amber-400'
            }
          >
            <span className='status-dot status-dot-active pulse-active' />
            {activeMode}
          </span>
        </div>
      </div>

      {/* ── Main grid: 50 / 25 / 25 ─────────────────────────────── */}
      <div className='grid min-h-0 flex-1 grid-cols-1 gap-3 xl:grid-cols-4'>
        {/* ── Col 1-2: Technical Analysis (50%) ─────────────────── */}
        <section className='tv-card col-span-1 flex min-h-0 flex-col overflow-hidden xl:col-span-2'>
          <div className='tv-divider flex shrink-0 items-center justify-between border-b px-3 py-2'>
            <div className='flex items-center gap-2'>
              <CandlestickChart className='h-3.5 w-3.5 text-indigo-400' />
              <span
                className='panel-label'
                style={{ fontFamily: 'var(--font-sans)' }}
              >
                Technical Analysis
              </span>
            </div>
            <div className='flex items-center gap-1.5'>
              <span className='status-dot status-dot-active pulse-active' />
              <span
                className='text-[9px] text-slate-500'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                LIVE FEED
              </span>
            </div>
          </div>

          <div className='scrollbar-thin flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3'>
            <div className='min-h-[180px]'>
              <MiniEquityChart mode={activeMode} />
            </div>
            <div className='grid grid-cols-1 gap-3 lg:grid-cols-2'>
              <ExecutionQualityWidget />
              <PortfolioRiskWidget />
            </div>
            <EvaluationDashboard />
          </div>
        </section>

        {/* ── Col 3: Active Positions (25%) ─────────────────────── */}
        <section className='col-span-1 min-h-0 overflow-hidden'>
          <ActiveTradesPanel
            mode={activeMode}
            onSelectSignal={handleSelectSignal}
          />
        </section>

        {/* ── Col 4: Bot Config + Signal Log (25%) ──────────────── */}
        <section className='col-span-1 flex min-h-0 flex-col gap-3 overflow-hidden'>
          {/* Bot Runtime panel */}
          <div className='tv-card shrink-0'>
            <div className='tv-divider flex items-center justify-between border-b px-3 py-2'>
              <div className='flex items-center gap-2'>
                <Server className='h-3.5 w-3.5 text-indigo-400' />
                <span
                  className='panel-label'
                  style={{ fontFamily: 'var(--font-sans)' }}
                >
                  Bot Runtime
                </span>
              </div>
              <span className='status-dot status-dot-active pulse-active' />
            </div>
            <div className='p-3'>
              <PineConfigStatus />
            </div>
          </div>

          {/* Recent Signals */}
          <div className='min-h-0 flex-1 overflow-hidden'>
            <RecentSignalsPanel
              mode={activeMode}
              onSelectSignal={handleSelectSignal}
            />
          </div>
        </section>
      </div>

      {/* Signal Inspector Sheet */}
      <SignalInspector
        signal={selectedSignal}
        open={inspectorOpen}
        onOpenChange={setInspectorOpen}
      />
    </div>
  );
}
