'use client';

import { useState } from 'react';
import { StatsTicker } from '@/components/StatsTicker';
import { SignalFeed } from '@/components/SignalFeed';
import { SignalInspector } from '@/components/SignalInspector';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { TradingSignal } from '@/types/trading';
import { Radio, FlaskConical, RefreshCw } from 'lucide-react';
import { DebugStatus } from '@/components/DebugStatus';
import { Button } from '@/components/ui/button';
import { useRefreshSignals } from '@/hooks/useTradingSignals';
import { cn } from '@/lib/utils';

export default function DashboardPage() {
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(
    null
  );
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
            <TabsList className="bg-zinc-900/50 border border-zinc-800/50 p-1">
              <TabsTrigger
                value="live"
                className={cn(
                  'data-[state=active]:bg-emerald-500/20 data-[state=active]:text-emerald-400',
                  'data-[state=inactive]:text-zinc-400',
                  'flex items-center gap-2 px-4 py-2 rounded transition-colors'
                )}
              >
                <Radio className="w-3.5 h-3.5" />
                <span className="font-mono text-xs font-semibold uppercase tracking-wider">
                  Live Operations
                </span>
                <span className="ml-1 px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 text-[10px] font-mono">
                  LIVE
                </span>
              </TabsTrigger>
              <TabsTrigger
                value="paper"
                className={cn(
                  'data-[state=active]:bg-amber-500/20 data-[state=active]:text-amber-400',
                  'data-[state=inactive]:text-zinc-400',
                  'flex items-center gap-2 px-4 py-2 rounded transition-colors'
                )}
              >
                <FlaskConical className="w-3.5 h-3.5" />
                <span className="font-mono text-xs font-semibold uppercase tracking-wider">
                  Simulation
                </span>
                <span className="ml-1 px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 text-[10px] font-mono">
                  PAPER
                </span>
              </TabsTrigger>
            </TabsList>

            {/* Actions */}
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
                disabled={isRefreshing}
                className="border-zinc-800 bg-zinc-900/50 text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800/50"
              >
                <RefreshCw
                  className={cn(
                    'w-4 h-4 mr-2',
                    isRefreshing && 'animate-spin'
                  )}
                />
                <span className="font-mono text-xs">Refresh</span>
              </Button>
            </div>
          </div>

          {/* Tab Content */}
          <TabsContent value="live" className="mt-0">
            <SignalFeed mode="LIVE" onSelectSignal={handleSelectSignal} />
          </TabsContent>

          <TabsContent value="paper" className="mt-0">
            <SignalFeed mode="PAPER" onSelectSignal={handleSelectSignal} />
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
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-zinc-600 font-mono">
              Mission Control v1.0
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
