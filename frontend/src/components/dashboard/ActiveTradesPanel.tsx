'use client';

import { useMemo } from 'react';
import { useTradingSignals } from '@/hooks/useTradingSignals';
import { TradingSignal, TradingMode } from '@/types/trading';
import { ActiveTradeRow } from './ActiveTradeRow';
import { isSignalOpen } from '@/domain/metrics/tradingMetrics';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { Radio, Activity } from 'lucide-react';
import { cn } from '@/lib/utils';
import { PanelEmptyState } from '@/components/shared/PanelEmptyState';

interface ActiveTradesPanelProps {
  mode?: TradingMode;
  onSelectSignal: (signal: TradingSignal) => void;
  compact?: boolean;
}

export function ActiveTradesPanel({
  mode,
  onSelectSignal,
  compact = false,
}: ActiveTradesPanelProps) {
  const { data: signals = [], isLoading } = useTradingSignals(mode);

  const activeTrades = useMemo(() => signals.filter(isSignalOpen), [signals]);

  return (
    <div className='tv-card flex h-full min-h-0 flex-col overflow-hidden'>
      {/* Header */}
      <div className='tv-divider flex shrink-0 items-center justify-between border-b px-3 py-2'>
        <div className='flex items-center gap-2'>
          <Radio className='h-3.5 w-3.5 text-indigo-400' />
          <span
            className='panel-label'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            Active Positions
          </span>
        </div>
        <span
          className={cn(
            'rounded px-2 py-0.5 text-[10px] font-bold tabular-nums',
            activeTrades.length > 0
              ? 'bg-indigo-600/20 text-indigo-300'
              : 'bg-slate-800 text-slate-500'
          )}
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {activeTrades.length}
        </span>
      </div>

      {/* Content */}
      <ScrollArea
        className={cn('min-h-0 flex-1 px-2 py-2', compact && 'py-1.5')}
      >
        {isLoading ? (
          <div className='space-y-1.5 px-1'>
            {[...Array(3)].map((_, i) => (
              <Skeleton
                key={i}
                className='h-10 w-full rounded-md bg-slate-800/60'
              />
            ))}
          </div>
        ) : activeTrades.length === 0 ? (
          <PanelEmptyState
            icon={<Activity className='h-4 w-4' />}
            title='No active positions'
            description={
              compact
                ? 'Waiting for the next valid setup'
                : 'Waiting for valid 5m entry confirmations'
            }
          />
        ) : (
          <div className='space-y-1'>
            {activeTrades.map((signal) => (
              <ActiveTradeRow
                key={signal.id}
                signal={signal}
                onSelectSignal={onSelectSignal}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
