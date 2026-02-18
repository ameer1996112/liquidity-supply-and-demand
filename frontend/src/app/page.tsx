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
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useTradingMode } from '@/providers/TradingModeProvider';
import { TradingSignal } from '@/types/trading';
import { Radio, FlaskConical, CandlestickChart, Server } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function DashboardPage() {
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(
    null
  );
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const { mode: activeMode, setMode } = useTradingMode();

  const handleSelectSignal = (signal: TradingSignal) => {
    setSelectedSignal(signal);
    setInspectorOpen(true);
  };

  return (
    <div className='flex h-full min-h-0 flex-col'>
      {/* Header */}
      <div className='mb-4 flex items-center justify-between gap-3 shrink-0'>
        <div>
          <h1 className='page-title text-xl font-semibold'>Dashboard</h1>
          <p className='page-subtitle mt-1 text-xs sm:text-sm'>
            Live command center for signals, execution, and portfolio health.
          </p>
        </div>

        {/* Mode Tabs */}
        <Tabs
          value={activeMode.toLowerCase()}
          onValueChange={(v) => setMode(v === 'live' ? 'LIVE' : 'PAPER')}
        >
          <TabsList className='surface-soft rounded-xl border border-[rgba(95,119,163,0.34)] p-1'>
            <TabsTrigger
              value='live'
              className={cn(
                'data-[state=active]:bg-[rgba(46,201,170,0.18)] data-[state=active]:text-[#2ec9aa]',
                'data-[state=inactive]:text-[#95a5c8]',
                'flex items-center gap-2 rounded-lg px-4 py-1.5 transition-colors'
              )}
            >
              <Radio className='w-3.5 h-3.5' />
              <span className='font-mono text-[11px] font-semibold uppercase tracking-wider'>
                Live
              </span>
            </TabsTrigger>
            <TabsTrigger
              value='paper'
              className={cn(
                'data-[state=active]:bg-[rgba(255,177,79,0.18)] data-[state=active]:text-[#ffb14f]',
                'data-[state=inactive]:text-[#95a5c8]',
                'flex items-center gap-2 rounded-lg px-4 py-1.5 transition-colors'
              )}
            >
              <FlaskConical className='w-3.5 h-3.5' />
              <span className='font-mono text-[11px] font-semibold uppercase tracking-wider'>
                Paper
              </span>
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Modern Pro Exchange Layout: 50 / 25 / 25 */}
      <div className='grid min-h-0 flex-1 grid-cols-1 gap-4 xl:grid-cols-4'>
        {/* 50% — Technical Analysis Quadrant */}
        <section className='tv-card col-span-1 flex min-h-0 flex-col overflow-hidden xl:col-span-2'>
          <div className='tv-divider flex items-center justify-between border-b px-4 py-2.5'>
            <div className='flex items-center gap-2'>
              <CandlestickChart className='h-4 w-4 text-[#8ca5ff]' />
              <span className='text-[11px] font-semibold uppercase tracking-[0.14em] text-[#c7d4ed]'>
                Technical Analysis
              </span>
            </div>
            <div className='flex items-center gap-2 text-[10px] text-[#9eb0d2]'>
              <span className='status-dot status-dot-active pulse-active' />
              Live Feed
            </div>
          </div>

          <div className='scrollbar-thin flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4'>
            <div className='min-h-[200px]'>
              <MiniEquityChart mode={activeMode} />
            </div>
            <div className='grid grid-cols-1 gap-4 lg:grid-cols-2'>
              <ExecutionQualityWidget />
              <PortfolioRiskWidget />
            </div>
            <EvaluationDashboard />
          </div>
        </section>

        {/* 25% — Active Positions */}
        <section className='col-span-1 min-h-0 overflow-hidden'>
          <ActiveTradesPanel
            mode={activeMode}
            onSelectSignal={handleSelectSignal}
          />
        </section>

        {/* 25% — Bot Config + Logs */}
        <section className='col-span-1 flex min-h-0 flex-col gap-4 overflow-hidden'>
          <div className='tv-card shrink-0'>
            <div className='tv-divider flex items-center justify-between border-b px-4 py-2.5'>
              <div className='flex items-center gap-2'>
                <Server className='h-4 w-4 text-[#8ca5ff]' />
                <span className='text-[11px] font-semibold uppercase tracking-[0.14em] text-[#c7d4ed]'>
                  Bot Runtime
                </span>
              </div>
              <span className='status-dot status-dot-active pulse-active' />
            </div>
            <div className='p-3'>
              <PineConfigStatus />
            </div>
          </div>

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
