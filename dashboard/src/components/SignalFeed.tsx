'use client';

import { useState, useMemo } from 'react';
import { useTradingSignals } from '@/hooks/useTradingSignals';
import { TradingSignal, TradingMode, getNotes } from '@/types/trading';
import { SignalCard, SignalCardSkeleton } from '@/components/SignalCard';
import { SignalInspector } from '@/components/SignalInspector';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import {
  Radio,
  FileText,
  AlertCircle,
  Inbox,
  Zap,
} from 'lucide-react';

// ============================================================================
// UTILITY HELPERS
// ============================================================================

/**
 * Safe float conversion - prevents toFixed crashes on null/undefined values
 * @param val - The value to convert
 * @param decimals - Number of decimal places (default: 2)
 * @returns Formatted string or "--" for null values
 */
export function safeFloat(val: number | null | undefined, decimals: number = 2): string {
  if (val === null || val === undefined || Number.isNaN(val)) {
    return '--';
  }
  return val.toFixed(decimals);
}

/**
 * Truncate text to specified length with ellipsis
 * @param text - Text to truncate
 * @param maxLength - Maximum length (default: 40)
 * @returns Truncated string
 */
export function truncateText(text: string | null | undefined, maxLength: number = 40): string {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trim() + '...';
}

/**
 * Get display reason from signal (notes or filter_reason, truncated)
 * @param signal - Trading signal
 * @returns Truncated reason string
 */
export function getDisplayReason(signal: TradingSignal): string {
  const notes = getNotes(signal);
  const reason = notes || signal.filter_reason;
  return truncateText(reason, 40);
}

// ============================================================================
// LOADING STATE
// ============================================================================

function LoadingGrid() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {[...Array(6)].map((_, i) => (
        <SignalCardSkeleton key={i} />
      ))}
    </div>
  );
}

// ============================================================================
// EMPTY STATE
// ============================================================================

function EmptyState({ mode }: { mode?: TradingMode }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 rounded-full bg-zinc-800/50 flex items-center justify-center mb-4">
        <Inbox className="w-8 h-8 text-zinc-600" />
      </div>
      <h3 className="font-mono text-sm text-zinc-400 mb-2">No Signals Found</h3>
      <p className="text-xs text-zinc-600 max-w-xs">
        {mode === 'LIVE'
          ? 'No live trading signals have been generated yet.'
          : mode === 'PAPER'
          ? 'No paper trading signals have been generated yet.'
          : 'Waiting for trading signals from the bot...'}
      </p>
    </div>
  );
}

// ============================================================================
// ERROR STATE
// ============================================================================

function ErrorState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 rounded-full bg-rose-500/10 flex items-center justify-center mb-4">
        <AlertCircle className="w-8 h-8 text-rose-400" />
      </div>
      <h3 className="font-mono text-sm text-rose-400 mb-2">Connection Error</h3>
      <p className="text-xs text-zinc-500 max-w-xs">
        Failed to load trading signals. Check your connection and try again.
      </p>
    </div>
  );
}

// ============================================================================
// SIGNAL GRID COMPONENT
// ============================================================================

interface SignalGridViewProps {
  signals: TradingSignal[];
  onSelectSignal?: (signal: TradingSignal) => void;
  mode?: TradingMode;
}

function SignalGridView({ signals, onSelectSignal, mode }: SignalGridViewProps) {
  if (signals.length === 0) {
    return <EmptyState mode={mode} />;
  }

  return (
    <ScrollArea className="h-[calc(100vh-280px)]">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pr-4">
        {signals.map((signal) => (
          <SignalCard
            key={signal.id}
            signal={signal}
            onInspect={onSelectSignal}
          />
        ))}
      </div>
    </ScrollArea>
  );
}

// ============================================================================
// MAIN SIGNAL FEED COMPONENT
// ============================================================================

interface SignalFeedProps {
  defaultMode?: TradingMode;
  onSelectSignal?: (signal: TradingSignal) => void;
}

export function SignalFeed({ defaultMode, onSelectSignal }: SignalFeedProps) {
  const [activeTab, setActiveTab] = useState<'all' | 'LIVE' | 'PAPER'>(defaultMode ?? 'all');
  const [inspectedSignal, setInspectedSignal] = useState<TradingSignal | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);

  // Fetch all signals
  const { data: allSignals = [], isLoading, error } = useTradingSignals();

  // Filter signals by mode
  const filteredSignals = useMemo(() => {
    if (activeTab === 'all') return allSignals;
    return allSignals.filter((s) => s.mode === activeTab);
  }, [allSignals, activeTab]);

  // Count signals per mode
  const counts = useMemo(() => ({
    all: allSignals.length,
    LIVE: allSignals.filter((s) => s.mode === 'LIVE').length,
    PAPER: allSignals.filter((s) => s.mode === 'PAPER').length,
  }), [allSignals]);

  // Handle signal inspection
  const handleInspect = (signal: TradingSignal) => {
    setInspectedSignal(signal);
    setInspectorOpen(true);
    onSelectSignal?.(signal);
  };

  if (error) {
    return <ErrorState />;
  }

  return (
    <div className="space-y-4">
      {/* Mode Tabs */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)}>
        <TabsList className="bg-zinc-900/50 border border-zinc-800 p-1">
          <TabsTrigger
            value="all"
            className={cn(
              'flex items-center gap-1.5 px-4 py-1.5',
              'text-[11px] font-mono font-semibold uppercase tracking-wider',
              'data-[state=active]:bg-zinc-800 data-[state=active]:text-zinc-100',
              'data-[state=inactive]:text-zinc-500'
            )}
          >
            <Zap className="w-3.5 h-3.5" />
            <span>All Signals</span>
            <span className="ml-1 px-1.5 py-0.5 rounded bg-zinc-800/80 text-[10px]">
              {counts.all}
            </span>
          </TabsTrigger>
          <TabsTrigger
            value="LIVE"
            className={cn(
              'flex items-center gap-1.5 px-4 py-1.5',
              'text-[11px] font-mono font-semibold uppercase tracking-wider',
              'data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400',
              'data-[state=inactive]:text-zinc-500'
            )}
          >
            <Radio className="w-3.5 h-3.5" />
            <span>Live Feed</span>
            <span className={cn(
              'ml-1 px-1.5 py-0.5 rounded text-[10px]',
              activeTab === 'LIVE' ? 'bg-blue-500/30' : 'bg-zinc-800/80'
            )}>
              {counts.LIVE}
            </span>
          </TabsTrigger>
          <TabsTrigger
            value="PAPER"
            className={cn(
              'flex items-center gap-1.5 px-4 py-1.5',
              'text-[11px] font-mono font-semibold uppercase tracking-wider',
              'data-[state=active]:bg-amber-500/20 data-[state=active]:text-amber-400',
              'data-[state=inactive]:text-zinc-500'
            )}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Paper Trading</span>
            <span className={cn(
              'ml-1 px-1.5 py-0.5 rounded text-[10px]',
              activeTab === 'PAPER' ? 'bg-amber-500/30' : 'bg-zinc-800/80'
            )}>
              {counts.PAPER}
            </span>
          </TabsTrigger>
        </TabsList>

        {/* Grid Content */}
        <TabsContent value="all" className="mt-4">
          {isLoading ? (
            <LoadingGrid />
          ) : (
            <SignalGridView
              signals={filteredSignals}
              onSelectSignal={handleInspect}
            />
          )}
        </TabsContent>

        <TabsContent value="LIVE" className="mt-4">
          {isLoading ? (
            <LoadingGrid />
          ) : (
            <SignalGridView
              signals={filteredSignals}
              onSelectSignal={handleInspect}
              mode="LIVE"
            />
          )}
        </TabsContent>

        <TabsContent value="PAPER" className="mt-4">
          {isLoading ? (
            <LoadingGrid />
          ) : (
            <SignalGridView
              signals={filteredSignals}
              onSelectSignal={handleInspect}
              mode="PAPER"
            />
          )}
        </TabsContent>
      </Tabs>

      {/* Signal Count Footer */}
      {!isLoading && filteredSignals.length > 0 && (
        <div className="flex items-center justify-between pt-2 border-t border-zinc-800/50">
          <span className="text-[11px] text-zinc-600 font-mono">
            Showing {filteredSignals.length} of {allSignals.length} signals
          </span>
          {activeTab !== 'all' && (
            <button
              onClick={() => setActiveTab('all')}
              className="text-[11px] text-zinc-500 hover:text-zinc-300 font-mono uppercase tracking-wider transition-colors"
            >
              Show All
            </button>
          )}
        </div>
      )}

      {/* Signal Inspector Sheet */}
      <SignalInspector
        signal={inspectedSignal}
        open={inspectorOpen}
        onOpenChange={setInspectorOpen}
      />
    </div>
  );
}
