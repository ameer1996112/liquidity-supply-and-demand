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
  Zap,
  Activity,
} from 'lucide-react';

// ============================================================================
// UTILITY HELPERS - Exported for use across the application
// ============================================================================

/**
 * Safe float conversion - prevents toFixed crashes on null/undefined values
 * CRITICAL: Use this for PnL display to handle null safely
 *
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
 * SPEC: Reason column should be truncated to 40 chars
 *
 * @param text - Text to truncate
 * @param maxLength - Maximum length (default: 40)
 * @returns Truncated string
 */
export function truncateText(text: string | null | undefined, maxLength: number = 40): string {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trim() + '…';
}

/**
 * Get display reason from signal (notes or filter_reason, truncated)
 * SPEC: Reason Column - Map from `notes` OR `filter_reason`. Truncate to 40 chars.
 *
 * @param signal - Trading signal
 * @returns Truncated reason string
 */
export function getDisplayReason(signal: TradingSignal): string {
  const notes = getNotes(signal);
  const reason = notes || signal.filter_reason;
  return truncateText(reason, 40);
}

// ============================================================================
// LOADING STATE - Cyberpunk Grid Skeleton
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
// EMPTY STATE - Bloomberg Terminal Style
// ============================================================================

function EmptyState({ mode }: { mode?: TradingMode }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="relative w-20 h-20 mb-6">
        {/* Animated rings */}
        <div className="absolute inset-0 rounded-full border border-zinc-800 animate-ping opacity-20" />
        <div className="absolute inset-2 rounded-full border border-zinc-700 animate-pulse" />
        <div className="absolute inset-0 rounded-full bg-zinc-900/80 flex items-center justify-center">
          <Activity className="w-8 h-8 text-zinc-600" />
        </div>
      </div>
      <h3 className="font-mono text-sm text-zinc-400 mb-2 uppercase tracking-wider">
        No Signals Found
      </h3>
      <p className="text-xs text-zinc-600 max-w-xs font-mono">
        {mode === 'LIVE'
          ? 'Awaiting live trading signals from the bot...'
          : mode === 'PAPER'
          ? 'No paper trading signals in the queue.'
          : 'Monitoring for incoming signals...'}
      </p>
      <div className="mt-4 flex items-center gap-2 text-[10px] font-mono text-zinc-700">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500/50 animate-pulse" />
        System Online
      </div>
    </div>
  );
}

// ============================================================================
// ERROR STATE - Alert Display
// ============================================================================

function ErrorState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="relative w-20 h-20 mb-6">
        <div className="absolute inset-0 rounded-full bg-rose-500/10 animate-pulse" />
        <div className="absolute inset-0 rounded-full border border-rose-500/30 flex items-center justify-center">
          <AlertCircle className="w-8 h-8 text-rose-400" />
        </div>
      </div>
      <h3 className="font-mono text-sm text-rose-400 mb-2 uppercase tracking-wider">
        Connection Error
      </h3>
      <p className="text-xs text-zinc-500 max-w-xs font-mono">
        Failed to establish data feed. Check connection and retry.
      </p>
      <div className="mt-4 flex items-center gap-2 text-[10px] font-mono text-rose-500/70">
        <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
        Feed Disconnected
      </div>
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
      {/* ═══════════════════════════════════════════════════════════════════
          MODE TABS - Bloomberg Terminal meets Cyberpunk
          SPEC: Tabs for "Live Feed" vs "Paper Trading" (filter by run_mode)
          ═══════════════════════════════════════════════════════════════════ */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)}>
        <TabsList className="bg-zinc-950/80 border border-zinc-800 p-1 shadow-[0_0_20px_rgba(0,0,0,0.3)]">
          {/* All Signals Tab */}
          <TabsTrigger
            value="all"
            className={cn(
              'flex items-center gap-1.5 px-4 py-2 rounded transition-all duration-200',
              'text-[11px] font-mono font-semibold uppercase tracking-wider',
              'data-[state=active]:bg-zinc-800 data-[state=active]:text-zinc-100',
              'data-[state=active]:shadow-[inset_0_1px_0_rgba(255,255,255,0.1)]',
              'data-[state=inactive]:text-zinc-500 data-[state=inactive]:hover:text-zinc-400'
            )}
          >
            <Zap className="w-3.5 h-3.5" />
            <span>All Signals</span>
            <span className={cn(
              'ml-1 px-1.5 py-0.5 rounded text-[10px] font-bold',
              activeTab === 'all' ? 'bg-zinc-700 text-zinc-200' : 'bg-zinc-800/80 text-zinc-500'
            )}>
              {counts.all}
            </span>
          </TabsTrigger>

          {/* Live Feed Tab - SPEC: Filter by run_mode=LIVE */}
          <TabsTrigger
            value="LIVE"
            className={cn(
              'flex items-center gap-1.5 px-4 py-2 rounded transition-all duration-200',
              'text-[11px] font-mono font-semibold uppercase tracking-wider',
              'data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400',
              'data-[state=active]:shadow-[0_0_15px_rgba(59,130,246,0.2),inset_0_1px_0_rgba(59,130,246,0.2)]',
              'data-[state=inactive]:text-zinc-500 data-[state=inactive]:hover:text-zinc-400'
            )}
          >
            <Radio className={cn('w-3.5 h-3.5', activeTab === 'LIVE' && 'animate-pulse')} />
            <span>Live Feed</span>
            <span className={cn(
              'ml-1 px-1.5 py-0.5 rounded text-[10px] font-bold',
              activeTab === 'LIVE' ? 'bg-blue-500/30 text-blue-300' : 'bg-zinc-800/80 text-zinc-500'
            )}>
              {counts.LIVE}
            </span>
          </TabsTrigger>

          {/* Paper Trading Tab - SPEC: Filter by run_mode=PAPER */}
          <TabsTrigger
            value="PAPER"
            className={cn(
              'flex items-center gap-1.5 px-4 py-2 rounded transition-all duration-200',
              'text-[11px] font-mono font-semibold uppercase tracking-wider',
              'data-[state=active]:bg-amber-500/20 data-[state=active]:text-amber-400',
              'data-[state=active]:shadow-[0_0_15px_rgba(245,158,11,0.2),inset_0_1px_0_rgba(245,158,11,0.2)]',
              'data-[state=inactive]:text-zinc-500 data-[state=inactive]:hover:text-zinc-400'
            )}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Paper Trading</span>
            <span className={cn(
              'ml-1 px-1.5 py-0.5 rounded text-[10px] font-bold',
              activeTab === 'PAPER' ? 'bg-amber-500/30 text-amber-300' : 'bg-zinc-800/80 text-zinc-500'
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

      {/* ═══════════════════════════════════════════════════════════════════
          SIGNAL COUNT FOOTER
          ═══════════════════════════════════════════════════════════════════ */}
      {!isLoading && filteredSignals.length > 0 && (
        <div className="flex items-center justify-between pt-3 border-t border-zinc-800/50">
          <div className="flex items-center gap-3">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500/70 animate-pulse" />
            <span className="text-[11px] text-zinc-500 font-mono uppercase tracking-wider">
              Displaying <span className="text-zinc-300 font-semibold">{filteredSignals.length}</span> of{' '}
              <span className="text-zinc-400">{allSignals.length}</span> signals
            </span>
          </div>
          {activeTab !== 'all' && (
            <button
              onClick={() => setActiveTab('all')}
              className={cn(
                'text-[11px] font-mono uppercase tracking-wider px-3 py-1 rounded',
                'text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800/50',
                'border border-transparent hover:border-zinc-700',
                'transition-all duration-200'
              )}
            >
              Show All →
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
