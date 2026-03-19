'use client';

import { useState, useMemo } from 'react';
import { useTradingSignals } from '@/hooks/useTradingSignals';
import { TradingSignal, TradingMode, getPnl } from '@/types/trading';
import { SignalCard, SignalCardSkeleton } from '@/components/SignalCard';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import {
  Layers,
  Radio,
  ShieldX,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  Inbox,
} from 'lucide-react';

type FilterTab = 'all' | 'live' | 'ai_rejects' | 'wins' | 'losses';

interface FilterConfig {
  id: FilterTab;
  label: string;
  icon: React.ReactNode;
  filter: (signal: TradingSignal) => boolean;
  accentColor: string;
}

const FILTER_TABS: FilterConfig[] = [
  {
    id: 'all',
    label: 'ALL',
    icon: <Layers className='w-3.5 h-3.5' />,
    filter: () => true,
    accentColor:
      'data-[state=active]:bg-[var(--to-surface-raised)] data-[state=active]:text-[var(--to-text-primary)]',
  },
  {
    id: 'live',
    label: 'LIVE TRADES',
    icon: <Radio className='w-3.5 h-3.5' />,
    filter: (s) => (s.status ?? '').toLowerCase() === 'active',
    accentColor:
      'data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400',
  },
  {
    id: 'ai_rejects',
    label: 'AI REJECTS',
    icon: <ShieldX className='w-3.5 h-3.5' />,
    filter: (s) => (s.status ?? '').toLowerCase().includes('reject'),
    accentColor:
      'data-[state=active]:bg-rose-500/20 data-[state=active]:text-rose-400',
  },
  {
    id: 'wins',
    label: 'WINS',
    icon: <TrendingUp className='w-3.5 h-3.5' />,
    filter: (s) => {
      const pnl = getPnl(s);
      return pnl !== null && pnl > 0;
    },
    accentColor:
      'data-[state=active]:bg-[var(--to-long)]/20 data-[state=active]:text-[var(--to-long)]',
  },
  {
    id: 'losses',
    label: 'LOSSES',
    icon: <TrendingDown className='w-3.5 h-3.5' />,
    filter: (s) => {
      const pnl = getPnl(s);
      return pnl !== null && pnl < 0;
    },
    accentColor:
      'data-[state=active]:bg-rose-500/20 data-[state=active]:text-rose-400',
  },
];

// Filter tab button component
function FilterTabButton({
  config,
  isActive,
  count,
  onClick,
}: {
  config: FilterConfig;
  isActive: boolean;
  count: number;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      data-state={isActive ? 'active' : 'inactive'}
      className={cn(
        'flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all',
        'text-[11px] font-mono font-semibold uppercase tracking-wider',
        'border border-transparent',
        'hover:bg-[var(--to-surface-raised)]/50',
        'data-[state=inactive]:text-[var(--to-text-dim)]',
        config.accentColor,
      )}
    >
      {config.icon}
      <span>{config.label}</span>
      <span
        className={cn(
          'ml-1 px-1.5 py-0.5 rounded text-[10px]',
          isActive ? 'bg-white/10' : 'bg-[var(--to-surface-raised)] text-[var(--to-text-dim)]',
        )}
      >
        {count}
      </span>
    </button>
  );
}

// Empty state component
function EmptyState({
  filter,
  mode,
}: {
  filter: FilterTab;
  mode?: TradingMode;
}) {
  const getMessage = () => {
    switch (filter) {
      case 'live':
        return 'No active trades at the moment';
      case 'ai_rejects':
        return 'No AI-rejected signals';
      case 'wins':
        return 'No winning trades yet';
      case 'losses':
        return 'No losing trades - great performance!';
      default:
        return mode
          ? `No ${mode.toLowerCase()} signals have been generated yet`
          : 'Waiting for trading signals from the bot...';
    }
  };

  return (
    <div className='flex flex-col items-center justify-center py-20 text-center'>
      <div className='w-16 h-16 rounded-full bg-[var(--to-surface-raised)]/50 flex items-center justify-center mb-4'>
        <Inbox className='w-8 h-8 text-[var(--to-text-dim)]' />
      </div>
      <h3 className='font-mono text-sm text-[var(--to-text-dim)] mb-2'>No Signals Found</h3>
      <p className='text-xs text-[var(--to-text-dim)] max-w-xs'>{getMessage()}</p>
    </div>
  );
}

// Error state component
function ErrorState() {
  return (
    <div className='flex flex-col items-center justify-center py-20 text-center'>
      <div className='w-16 h-16 rounded-full bg-rose-500/10 flex items-center justify-center mb-4'>
        <AlertCircle className='w-8 h-8 text-rose-400' />
      </div>
      <h3 className='font-mono text-sm text-rose-400 mb-2'>Connection Error</h3>
      <p className='text-xs text-[var(--to-text-dim)] max-w-xs'>
        Failed to load trading signals. Check your connection and try again.
      </p>
    </div>
  );
}

// Loading skeleton grid
function LoadingGrid() {
  return (
    <div className='grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4'>
      {[...Array(8)].map((_, i) => (
        <SignalCardSkeleton key={i} />
      ))}
    </div>
  );
}

interface SignalGridProps {
  mode?: TradingMode;
  onSelectSignal?: (signal: TradingSignal) => void;
}

export function SignalGrid({ mode, onSelectSignal }: SignalGridProps) {
  const [activeFilter, setActiveFilter] = useState<FilterTab>('all');
  const { data: signals = [], isLoading, error } = useTradingSignals(mode);

  // Calculate counts for each filter
  const filterCounts = useMemo(() => {
    return FILTER_TABS.reduce(
      (acc, tab) => {
        acc[tab.id] = signals.filter(tab.filter).length;
        return acc;
      },
      {} as Record<FilterTab, number>,
    );
  }, [signals]);

  // Apply active filter
  const filteredSignals = useMemo(() => {
    const config = FILTER_TABS.find((t) => t.id === activeFilter);
    if (!config) return signals;
    return signals.filter(config.filter);
  }, [signals, activeFilter]);

  if (error) {
    return <ErrorState />;
  }

  return (
    <div className='space-y-4'>
      {/* Filter Tabs */}
      <div className='flex items-center gap-1 p-1 bg-zinc-900/50 border border-zinc-800/50 rounded-lg overflow-x-auto scrollbar-thin'>
        {FILTER_TABS.map((tab) => (
          <FilterTabButton
            key={tab.id}
            config={tab}
            isActive={activeFilter === tab.id}
            count={filterCounts[tab.id]}
            onClick={() => setActiveFilter(tab.id)}
          />
        ))}
      </div>

      {/* Signal Grid */}
      {isLoading ? (
        <LoadingGrid />
      ) : filteredSignals.length === 0 && signals.length > 0 ? (
        <div className='flex flex-col items-center justify-center py-20 text-center'>
          <p className='font-mono text-sm text-amber-400/90'>
            Loaded {signals.length} signals, but hidden by filters.
          </p>
          <p className='font-mono text-xs text-[var(--to-text-dim)] mt-2'>
            Sample run_mode: [{signals[0]?.mode ?? 'N/A'}], status: [
            {signals[0]?.status ?? 'N/A'}]
          </p>
          <button
            onClick={() => setActiveFilter('all')}
            className='mt-4 text-[11px] font-mono text-blue-400 hover:text-blue-300 uppercase tracking-wider'
          >
            Show All
          </button>
        </div>
      ) : filteredSignals.length === 0 ? (
        <EmptyState filter={activeFilter} mode={mode} />
      ) : (
        <ScrollArea className='h-[calc(100vh-240px)]'>
          <div className='grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 pr-4'>
            {filteredSignals.map((signal) => (
              <SignalCard
                key={signal.id}
                signal={signal}
                onInspect={onSelectSignal}
              />
            ))}
          </div>
        </ScrollArea>
      )}

      {/* Signal Count Footer */}
      {!isLoading && filteredSignals.length > 0 && (
        <div className='flex items-center justify-between pt-2 border-t border-zinc-800/50'>
          <span className='text-[11px] text-[var(--to-text-dim)] font-mono'>
            Showing {filteredSignals.length} of {signals.length} signals
          </span>
          {activeFilter !== 'all' && (
            <button
              onClick={() => setActiveFilter('all')}
              className='text-[11px] text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] font-mono uppercase tracking-wider'
            >
              Clear Filter
            </button>
          )}
        </div>
      )}
    </div>
  );
}
