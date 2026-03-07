'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Activity } from 'lucide-react';
import type { TradingSignal } from '@/types/trading';
import { getSymbol, getSide, getPnl } from '@/types/trading';
import { isSignalOpen } from '@/domain/metrics/tradingMetrics';

interface LivePnlTickerProps {
  signals: TradingSignal[];
  className?: string;
}

/**
 * Horizontal scrolling ticker showing live floating P&L for open positions.
 * Auto-scrolls continuously. Pauses on hover.
 */
export function LivePnlTicker({ signals, className }: LivePnlTickerProps) {
  const openPositions = signals.filter(isSignalOpen);
  const [paused, setPaused] = useState(false);

  if (openPositions.length === 0) return null;

  // Duplicate items for seamless infinite scroll
  const items = [...openPositions, ...openPositions];

  return (
    <div
      className={cn(
        'relative flex items-center overflow-hidden rounded-lg border border-[var(--to-border)] bg-[var(--to-surface)]',
        'h-8 shrink-0',
        className
      )}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      {/* Left label */}
      <div className='flex shrink-0 items-center gap-1.5 border-r border-[var(--to-border)] bg-[var(--to-surface-raised)] px-3 h-full'>
        <Activity className='h-3 w-3 text-[var(--to-warning)]' />
        <span
          className='text-[9px] font-bold uppercase tracking-[0.18em] text-[var(--to-text-dim)]'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          Live
        </span>
      </div>

      {/* Scrolling track */}
      <div className='relative flex-1 overflow-hidden'>
        <div
          className='flex items-center'
          style={{
            animation: paused
              ? 'none'
              : `ticker-scroll ${Math.max(
                  openPositions.length * 5,
                  15
                )}s linear infinite`,
            whiteSpace: 'nowrap',
          }}
        >
          {items.map((signal, idx) => {
            const pnl = getPnl(signal);
            const symbol = getSymbol(signal);
            const side = getSide(signal);
            const isLong = side === 'buy';
            const pnlPositive = (pnl ?? 0) >= 0;

            return (
              <div
                key={`${signal.id}-${idx}`}
                className='inline-flex items-center gap-2 px-4 border-r border-[var(--to-border)]/40'
              >
                <span
                  className='text-[9px] px-1.5 py-0.5 rounded font-bold uppercase'
                  style={{
                    backgroundColor: isLong
                      ? 'rgba(14,203,129,0.12)'
                      : 'rgba(246,70,93,0.12)',
                    color: isLong ? '#0ecb81' : '#f6465d',
                  }}
                >
                  {isLong ? '▲' : '▼'}
                </span>
                <span
                  className='text-[11px] font-semibold text-[var(--to-text-primary)]'
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  {symbol}
                </span>
                {pnl != null && (
                  <span
                    className='text-[11px] font-bold tabular-nums'
                    style={{
                      color: pnlPositive ? '#0ecb81' : '#f6465d',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {pnlPositive ? '+' : ''}${pnl.toFixed(2)}
                  </span>
                )}
                {signal.entry_model && (
                  <span
                    className='text-[9px] text-[var(--to-text-dim)]'
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    {signal.entry_model}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Right fade gradient */}
      <div className='pointer-events-none absolute right-0 top-0 bottom-0 w-12 bg-gradient-to-l from-[var(--to-surface)] to-transparent' />

      {/* Ticker scroll keyframe injected inline */}
      <style>{`
        @keyframes ticker-scroll {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
      `}</style>
    </div>
  );
}
