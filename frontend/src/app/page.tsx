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
    null,
  );
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const { mode: activeMode, setMode } = useTradingMode();

  const handleSelectSignal = (signal: TradingSignal) => {
    setSelectedSignal(signal);
    setInspectorOpen(true);
  };

  return (
    <div className='h-full flex flex-col min-h-0'>
      {/* Header */}
      <div className='flex items-center justify-between mb-4 shrink-0'>
        <h1 className='text-lg font-semibold text-zinc-100'>Dashboard</h1>

        {/* Mode Tabs */}
        <Tabs
          value={activeMode.toLowerCase()}
          onValueChange={(v) => setMode(v === 'live' ? 'LIVE' : 'PAPER')}
        >
          <TabsList className='bg-[#1e222d] border border-[#2a2e39] p-1'>
            <TabsTrigger
              value='live'
              className={cn(
                'data-[state=active]:bg-[#26a69a]/15 data-[state=active]:text-[#26a69a]',
                'data-[state=inactive]:text-zinc-500',
                'flex items-center gap-2 px-4 py-1.5 rounded transition-colors',
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
                'data-[state=active]:bg-[#ff9800]/15 data-[state=active]:text-[#ff9800]',
                'data-[state=inactive]:text-zinc-500',
                'flex items-center gap-2 px-4 py-1.5 rounded transition-colors',
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
      <div className='grid grid-cols-1 lg:grid-cols-3 gap-4 flex-1 min-h-0'>
        {/* Left Panel: Widget Stack */}
        <div className='flex flex-col gap-4 overflow-y-auto scrollbar-thin min-h-0 lg:pr-2'>
          {/* Active Trades */}
          <div className='min-h-[140px] max-h-[220px] shrink-0 overflow-hidden'>
            <ActiveTradesPanel
              mode={activeMode}
              onSelectSignal={handleSelectSignal}
            />
          </div>

          {/* Equity Chart */}
          <div className='shrink-0 min-h-[160px]'>
            <MiniEquityChart mode={activeMode} />
          </div>

          {/* Execution Quality */}
          <div className='shrink-0 min-h-[180px]'>
            <ExecutionQualityWidget />
          </div>

          {/* Portfolio Risk */}
          <div className='shrink-0 min-h-[180px]'>
            <PortfolioRiskWidget />
          </div>

          {/* Evaluation Dashboard */}
          <div className='shrink-0'>
            <EvaluationDashboard />
          </div>
        </div>

        {/* Right Panel: Signals Table */}
        <div className='lg:col-span-2 min-h-0 flex flex-1 overflow-hidden'>
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
