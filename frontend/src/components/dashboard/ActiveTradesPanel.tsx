'use client';

import { useMemo } from 'react';
import { useTradingSignals } from '@/hooks/useTradingSignals';
import { TradingSignal, TradingMode } from '@/types/trading';
import { ActiveTradeRow } from './ActiveTradeRow';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Radio, Radar } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ActiveTradesPanelProps {
  mode?: TradingMode;
  onSelectSignal: (signal: TradingSignal) => void;
}

export function ActiveTradesPanel({ mode, onSelectSignal }: ActiveTradesPanelProps) {
  const { data: signals = [], isLoading } = useTradingSignals(mode);

  const activeTrades = useMemo(
    () => signals.filter((s) => {
      const status = s.status?.toLowerCase();
      return status === 'active' || status === 'executed';
    }),
    [signals]
  );

  return (
    <div className="tv-card flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#2a2e39]">
        <div className="flex items-center gap-2">
          <Radio className="w-4 h-4 text-[#2962ff]" />
          <span className="font-mono text-xs font-semibold text-zinc-300 uppercase tracking-wider">
            Active Trades
          </span>
        </div>
        <span
          className={cn(
            'font-mono text-xs font-bold px-2 py-0.5 rounded',
            activeTrades.length > 0
              ? 'bg-[#2962ff]/15 text-[#2962ff]'
              : 'bg-[#2a2e39] text-zinc-500'
          )}
        >
          {activeTrades.length}
        </span>
      </div>

      {/* Content */}
      <ScrollArea className="flex-1 px-2 py-2">
        {isLoading ? (
          <div className="space-y-2 px-1">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-14 w-full rounded-md bg-[#1e222d]" />
            ))}
          </div>
        ) : activeTrades.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-center">
            <Radar className="w-8 h-8 text-zinc-700 mb-3" />
            <span className="text-xs text-zinc-600 font-mono">No active trades</span>
            <span className="text-[10px] text-zinc-700 font-mono mt-1">Monitoring signals...</span>
          </div>
        ) : (
          <div className="space-y-1.5">
            {activeTrades.map((signal) => (
              <ActiveTradeRow
                key={signal.id}
                signal={signal}
                onClick={() => onSelectSignal(signal)}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
