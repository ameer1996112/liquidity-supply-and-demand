'use client';

import { useState } from 'react';
import { StatsTicker } from '@/components/StatsTicker';
import { SignalGrid } from '@/components/SignalGrid';
import { SignalInspector } from '@/components/SignalInspector';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { TradingSignal } from '@/types/trading';
import { Radio, FlaskConical, RefreshCw, Cpu } from 'lucide-react';
import { DebugStatus } from '@/components/DebugStatus';
import { Button } from '@/components/ui/button';
import { useRefreshSignals } from '@/hooks/useTradingSignals';
import { cn } from '@/lib/utils';

export default function DashboardPage() {
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const refreshSignals = useRefreshSignals();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleSelectSignal = (signal: TradingSignal) => {
    setSelectedSignal(signal);
    setInspectorOpen(true);
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refreshSignals();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col">
      {/* Stats Ticker Header */}
      <StatsTicker />

      {/* Main Content */}
      <main className="flex-1 p-4">
        <Tabs defaultValue="live" className="w-full">
          {/* Tab Header with Actions */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-4">
              {/* Brand/Title */}
              <div className="flex items-center gap-2 pr-4 border-r border-zinc-800">
                <Cpu className="w-5 h-5 text-emerald-500" />
                <span className="font-mono text-sm font-bold text-zinc-200 tracking-tight">
                  MISSION CONTROL
                </span>
              </div>

              {/* Mode Tabs */}
              <TabsList className="bg-zinc-900/50 border border-zinc-800/50 p-1">
                <TabsTrigger
                  value="live"
                  className={cn(
                    'data-[state=active]:bg-emerald-500/20 data-[state=active]:text-emerald-400',
                    'data-[state=inactive]:text-zinc-500',
                    'flex items-center gap-2 px-4 py-2 rounded transition-colors'
                  )}
                >
                  <Radio className="w-3.5 h-3.5" />
                  <span className="font-mono text-[11px] font-semibold uppercase tracking-wider">
                    Live
                  </span>
                  <span className="ml-1 px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-[10px] font-mono animate-pulse">
                    LIVE
                  </span>
                </TabsTrigger>
                <TabsTrigger
                  value="paper"
                  className={cn(
                    'data-[state=active]:bg-amber-500/20 data-[state=active]:text-amber-400',
                    'data-[state=inactive]:text-zinc-500',
                    'flex items-center gap-2 px-4 py-2 rounded transition-colors'
                  )}
                >
                  <FlaskConical className="w-3.5 h-3.5" />
                  <span className="font-mono text-[11px] font-semibold uppercase tracking-wider">
                    Paper
                  </span>
                  <span className="ml-1 px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 text-[10px] font-mono">
                    SIM
                  </span>
                </TabsTrigger>
              </TabsList>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={isRefreshing}
                className={cn(
                  'border-zinc-800 bg-zinc-900/50 text-zinc-400',
                  'hover:text-zinc-100 hover:bg-zinc-800/50 hover:border-zinc-700',
                  'h-9 px-3'
                )}
              >
                <RefreshCw
                  className={cn(
                    'w-4 h-4 mr-2',
                    isRefreshing && 'animate-spin'
                  )}
                />
                <span className="font-mono text-[11px] uppercase tracking-wider">Refresh</span>
              </Button>
            </div>
          </div>

          {/* Tab Content */}
          <TabsContent value="live" className="mt-0">
            <SignalGrid mode="LIVE" onSelectSignal={handleSelectSignal} />
          </TabsContent>

          <TabsContent value="paper" className="mt-0">
            <SignalGrid mode="PAPER" onSelectSignal={handleSelectSignal} />
          </TabsContent>
        </Tabs>
      </main>

      {/* Signal Inspector Sheet */}
      <SignalInspector
        signal={selectedSignal}
        open={inspectorOpen}
        onOpenChange={setInspectorOpen}
      />

      {/* Footer */}
      <footer className="border-t border-zinc-800/50 py-2 px-4 mb-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-[10px] text-zinc-600 font-mono">
              Mission Control v2.0
            </span>
            <span className="text-zinc-800">|</span>
            <span className="text-[10px] text-zinc-600 font-mono">
              Cyber-Industrial UI
            </span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-[10px] text-zinc-600 font-mono">
              {new Date().toLocaleDateString('en-US', {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              })}
            </span>
          </div>
        </div>
      </footer>

      {/* Debug Status Banner */}
      <DebugStatus />
    </div>
  );
}
