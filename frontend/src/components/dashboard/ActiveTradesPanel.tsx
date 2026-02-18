'use client';

import { useMemo } from 'react';
import { useTradingSignals } from '@/hooks/useTradingSignals';
import { TradingSignal, TradingMode } from '@/types/trading';
import { ActiveTradeRow } from './ActiveTradeRow';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Radio } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ActiveTradesPanelProps {
  mode?: TradingMode;
  onSelectSignal: (signal: TradingSignal) => void;
}

export function ActiveTradesPanel({
  mode,
  onSelectSignal,
}: ActiveTradesPanelProps) {
  const { data: signals = [], isLoading } = useTradingSignals(mode);

  const activeTrades = useMemo(
    () =>
      signals.filter((s) => {
        const status = s.status?.toLowerCase();
        return status === 'active' || status === 'executed';
      }),
    [signals]
  );

  return (
    <div className='tv-card flex h-full min-h-0 flex-col overflow-hidden'>
      {/* Header */}
      <div className='tv-divider flex items-center justify-between border-b px-3 py-2'>
        <div className='flex items-center gap-2'>
          <Radio className='h-3.5 w-3.5 text-[#8ca5ff]' />
          <span className='text-[11px] font-semibold uppercase tracking-[0.12em] text-[#c7d4ed]'>
            Active Positions
          </span>
        </div>
        <span
          className={cn(
            'rounded px-2 py-0.5 font-mono text-[10px] font-bold',
            activeTrades.length > 0
              ? 'bg-[#6e8dff] text-white'
              : 'bg-[rgba(30,44,71,0.85)] text-[#8ea0c3]'
          )}
        >
          {activeTrades.length}
        </span>
      </div>

      {/* Content */}
      <ScrollArea className='min-h-0 flex-1 px-2 py-2'>
        {isLoading ? (
          <div className='space-y-1.5 px-1'>
            {[...Array(3)].map((_, i) => (
              <Skeleton
                key={i}
                className='h-10 w-full rounded-md bg-[rgba(31,45,74,0.55)]'
              />
            ))}
          </div>
        ) : activeTrades.length === 0 ? (
          <div className='flex flex-col items-center justify-center py-10 text-center'>
            <div className='radar-scan mb-3' />
            <span className='font-mono text-[11px] text-[#a1b1cf]'>
              Scanning market
            </span>
            <span className='mt-1 text-[10px] text-[#7b8cb0]'>
              No active positions
            </span>
          </div>
        ) : (
          <div className='space-y-1.5'>
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
