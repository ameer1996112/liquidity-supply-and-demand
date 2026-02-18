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
import { Radio, FlaskConical } from 'lucide-react';
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

      {/* Pine Config Status */}
      <div className='mb-4 shrink-0'>
        <PineConfigStatus />
      </div>

      {/* 2-Panel Responsive Layout — fills remaining height */}
      <div className='grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[1.1fr_1.9fr]'>
        {/* Left Panel: Widget Stack */}
        <div className='scrollbar-thin flex min-h-0 flex-col gap-4 overflow-y-auto lg:pr-2'>
          {/* Active Trades */}
          <div className='min-h-[150px] max-h-[230px] shrink-0 overflow-hidden'>
            <ActiveTradesPanel
              mode={activeMode}
              onSelectSignal={handleSelectSignal}
            />
          </div>

          {/* Equity Chart */}
          <div className='min-h-[170px] shrink-0'>
            <MiniEquityChart mode={activeMode} />
          </div>

          {/* Execution Quality */}
          <div className='min-h-[190px] shrink-0'>
            <ExecutionQualityWidget />
          </div>

          {/* Portfolio Risk */}
          <div className='min-h-[190px] shrink-0'>
            <PortfolioRiskWidget />
          </div>

          {/* Evaluation Dashboard */}
          <div className='shrink-0'>
            <EvaluationDashboard />
          </div>
        </div>

        {/* Right Panel: Signals Table */}
        <div className='min-h-0 flex flex-1 overflow-hidden'>
          <RecentSignalsPanel
            mode={activeMode}
            onSelectSignal={handleSelectSignal}
          />
        </div>
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
