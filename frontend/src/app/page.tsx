'use client';

import { useState } from 'react';
import { SignalInspector } from '@/components/SignalInspector';
import { ActiveTradesPanel } from '@/components/dashboard/ActiveTradesPanel';
import { RecentSignalsPanel } from '@/components/dashboard/RecentSignalsPanel';
import { MiniEquityChart } from '@/components/dashboard/MiniEquityChart';
import { EvaluationDashboard } from '@/components/evaluation/EvaluationDashboard';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { TradingSignal, TradingMode } from '@/types/trading';
import { Radio, FlaskConical } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function DashboardPage() {
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [activeMode, setActiveMode] = useState<TradingMode>('LIVE');

  const handleSelectSignal = (signal: TradingSignal) => {
    setSelectedSignal(signal);
    setInspectorOpen(true);
  };

  return (
    <div className="h-[calc(100vh-5rem)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold text-zinc-100">Dashboard</h1>

        {/* Mode Tabs */}
        <Tabs
          defaultValue="live"
          onValueChange={(v) => setActiveMode(v === 'live' ? 'LIVE' : 'PAPER')}
        >
          <TabsList className="bg-[#1e222d] border border-[#2a2e39] p-1">
            <TabsTrigger
              value="live"
              className={cn(
                'data-[state=active]:bg-[#26a69a]/15 data-[state=active]:text-[#26a69a]',
                'data-[state=inactive]:text-zinc-500',
                'flex items-center gap-2 px-4 py-1.5 rounded transition-colors'
              )}
            >
              <Radio className="w-3.5 h-3.5" />
              <span className="font-mono text-[11px] font-semibold uppercase tracking-wider">
                Live
              </span>
            </TabsTrigger>
            <TabsTrigger
              value="paper"
              className={cn(
                'data-[state=active]:bg-[#ff9800]/15 data-[state=active]:text-[#ff9800]',
                'data-[state=inactive]:text-zinc-500',
                'flex items-center gap-2 px-4 py-1.5 rounded transition-colors'
              )}
            >
              <FlaskConical className="w-3.5 h-3.5" />
              <span className="font-mono text-[11px] font-semibold uppercase tracking-wider">
                Paper
              </span>
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* 2-Panel Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 h-[calc(100%-3rem)]">
        {/* Left Panel: Active Trades + Equity Chart + Evaluation */}
        <div className="flex flex-col gap-4 overflow-y-auto">
          <div className="flex-1 min-h-0">
            <ActiveTradesPanel mode={activeMode} onSelectSignal={handleSelectSignal} />
          </div>
          <MiniEquityChart mode={activeMode} />
          <EvaluationDashboard />
        </div>

        {/* Right Panel: Recent Signals Table */}
        <div className="lg:col-span-2 min-h-0">
          <RecentSignalsPanel mode={activeMode} onSelectSignal={handleSelectSignal} />
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
