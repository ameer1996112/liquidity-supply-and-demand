'use client';

import {
  TradingSignal,
  getSymbol,
  getSide,
  getScore,
  getPnl,
} from '@/types/trading';
import { cn } from '@/lib/utils';
import { safeFloat, getDisplayReason, getPriceDecimals } from '@/lib/format';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { SideBadge } from '@/components/shared/SideBadge';
import { PnLDisplay } from '@/components/shared/PnLDisplay';
import { formatDistanceToNow, format } from 'date-fns';
import { Sparkles } from 'lucide-react';

// ============================================================================
// AI CONFIDENCE PROGRESS BAR
// ============================================================================

function ConfidenceBar({ score }: { score: number | null }) {
  if (score === null) {
    return (
      <div className='w-full space-y-1'>
        <div className='flex items-center justify-between'>
          <span className='text-[10px] font-mono text-zinc-500 uppercase tracking-wider flex items-center gap-1'>
            <Sparkles className='w-3 h-3' />
            AI Confidence
          </span>
          <span className='font-mono text-xs text-zinc-600'>N/A</span>
        </div>
        <div className='h-2 w-full bg-zinc-800/50 rounded-full overflow-hidden'>
          <div className='h-full w-0 bg-zinc-700 rounded-full' />
        </div>
      </div>
    );
  }

  const getBarColor = (s: number) => {
    if (s >= 80) return 'bg-gradient-to-r from-emerald-500 to-emerald-400';
    if (s >= 60) return 'bg-gradient-to-r from-amber-500 to-amber-400';
    return 'bg-gradient-to-r from-rose-500 to-rose-400';
  };

  const getTextColor = (s: number) => {
    if (s >= 80) return 'text-emerald-400';
    if (s >= 60) return 'text-amber-400';
    return 'text-rose-400';
  };

  const getGlow = (s: number) => {
    if (s >= 80) return 'shadow-[0_0_10px_rgba(16,185,129,0.4)]';
    if (s >= 60) return 'shadow-[0_0_10px_rgba(245,158,11,0.4)]';
    return 'shadow-[0_0_10px_rgba(239,68,68,0.4)]';
  };

  return (
    <div className='w-full space-y-1.5'>
      <div className='flex items-center justify-between'>
        <span className='text-[10px] font-mono text-zinc-500 uppercase tracking-wider flex items-center gap-1'>
          <Sparkles className='w-3 h-3' />
          AI Confidence
        </span>
        <span
          className={cn('font-mono text-xs font-bold', getTextColor(score))}
        >
          {score}%
        </span>
      </div>
      <div className='h-2 w-full bg-zinc-800/50 rounded-full overflow-hidden'>
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500 ease-out',
            getBarColor(score),
            getGlow(score),
          )}
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
}

// ============================================================================
// CIRCULAR SCORE RING (COMPACT VERSION)
// ============================================================================

// Exported for use in other components (e.g., compact displays)
export function ScoreRing({
  score,
  size = 'md',
}: {
  score: number | null;
  size?: 'sm' | 'md';
}) {
  if (score === null) {
    return (
      <div
        className={cn(
          'relative flex items-center justify-center',
          size === 'sm' ? 'w-12 h-12' : 'w-16 h-16',
        )}
      >
        <div className='absolute inset-0 rounded-full border-2 border-zinc-800' />
        <span className='font-mono text-[10px] text-zinc-600'>--</span>
      </div>
    );
  }

  const radius = size === 'sm' ? 20 : 28;
  const viewBox = size === 'sm' ? '0 0 48 48' : '0 0 64 64';
  const center = size === 'sm' ? 24 : 32;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  const getColor = (s: number) => {
    if (s >= 80)
      return {
        stroke: '#10b981',
        text: 'text-emerald-400',
        glow: 'drop-shadow-[0_0_8px_rgba(16,185,129,0.5)]',
      };
    if (s >= 60)
      return {
        stroke: '#f59e0b',
        text: 'text-amber-400',
        glow: 'drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]',
      };
    return {
      stroke: '#ef4444',
      text: 'text-red-400',
      glow: 'drop-shadow-[0_0_8px_rgba(239,68,68,0.5)]',
    };
  };

  const colors = getColor(score);

  return (
    <div
      className={cn(
        'relative flex items-center justify-center',
        size === 'sm' ? 'w-12 h-12' : 'w-16 h-16',
        colors.glow,
      )}
      role='img'
      aria-label={`AI Score: ${score}%`}
    >
      <svg
        className={cn('-rotate-90', size === 'sm' ? 'w-12 h-12' : 'w-16 h-16')}
        viewBox={viewBox}
      >
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill='none'
          stroke='#27272a'
          strokeWidth={size === 'sm' ? 3 : 4}
        />
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill='none'
          stroke={colors.stroke}
          strokeWidth={size === 'sm' ? 3 : 4}
          strokeLinecap='round'
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className='transition-all duration-500'
        />
      </svg>
      <span
        className={cn(
          'absolute font-mono font-bold',
          size === 'sm' ? 'text-[10px]' : 'text-sm',
          colors.text,
        )}
      >
        {score}%
      </span>
    </div>
  );
}

// ============================================================================
// SIGNAL CARD COMPONENT
// ============================================================================

interface SignalCardProps {
  signal: TradingSignal;
  onInspect?: (signal: TradingSignal) => void;
}

/**
 * Signal Card Component - Mission Control v2
 *
 * Layout:
 * - Top Row: Symbol + Side Badge (Green for Buy, Red for Sell)
 * - Middle: Progress Bar for `score` (AI Confidence)
 * - Bottom: `notes` (reasoning) and formatted timestamp
 * - Interactive: Clicking the card opens a Sheet with full JSON details
 */
export function SignalCard({ signal, onInspect }: SignalCardProps) {
  const symbol = getSymbol(signal);
  const side = getSide(signal);
  const score = getScore(signal);
  const pnl = getPnl(signal);
  const reason = getDisplayReason(signal);
  const decimals = getPriceDecimals(symbol);

  const normalized = signal.status?.toLowerCase();
  const isActive = normalized === 'active';
  const isAiRejected = normalized === 'ai_rejected';
  const isClosed = normalized === 'closed';
  const isWin = pnl !== null && pnl > 0;
  const isLoss = pnl !== null && pnl < 0;

  const handleCardClick = () => {
    onInspect?.(signal);
  };

  return (
    <div
      role='button'
      tabIndex={0}
      onClick={handleCardClick}
      onKeyDown={(e) => e.key === 'Enter' && handleCardClick()}
      className={cn(
        'group relative bg-zinc-900/70 border rounded-lg overflow-hidden',
        'transition-all duration-200 cursor-pointer select-none',
        'hover:bg-zinc-900/90 hover:border-zinc-600',
        'hover:shadow-[0_0_20px_rgba(0,0,0,0.5)]',
        'hover:scale-[1.02]',
        'focus:outline-none focus:ring-2 focus:ring-blue-500/50',
        isActive &&
          'border-blue-500/50 bg-blue-950/20 shadow-[0_0_15px_rgba(59,130,246,0.15)]',
        isAiRejected && 'border-rose-500/40 bg-rose-950/10',
        isClosed && isWin && 'border-emerald-500/40 bg-emerald-950/10',
        isClosed && isLoss && 'border-rose-500/30 bg-rose-950/5',
        !isActive && !isAiRejected && !isClosed && 'border-zinc-800',
      )}
    >
      {/* Active indicator pulse effect */}
      {isActive && (
        <div className='absolute inset-0 bg-gradient-to-r from-blue-500/10 via-transparent to-transparent pointer-events-none animate-pulse' />
      )}

      {/* TOP ROW: Symbol + Side Badge */}
      <div className='flex items-center justify-between p-3 border-b border-zinc-800/60'>
        <div className='flex items-center gap-2.5'>
          <span className='font-mono text-base font-bold text-zinc-100 tracking-tight'>
            {symbol}
          </span>
          <SideBadge side={side} />
        </div>
        <StatusBadge status={signal.status} pnl={pnl} />
      </div>

      {/* MIDDLE: AI Confidence Score + Broker Ticket */}
      <div className='px-3 pt-3 pb-2 space-y-1.5'>
        <ConfidenceBar score={score} />
        {signal.broker_order_id && (
          <div className='flex items-center justify-between'>
            <span className='text-[10px] font-mono text-zinc-600 uppercase'>
              Ticket
            </span>
            <span className='font-mono text-xs text-zinc-400'>
              {signal.broker_order_id}
            </span>
          </div>
        )}
      </div>

      {/* Trade Metrics Row */}
      <div className='px-3 pb-2 flex items-center justify-between gap-4'>
        {/* Entry Price */}
        <div className='flex items-center gap-2'>
          {(signal.price ?? signal.entry) ? (
            <>
              <span className='text-[10px] font-mono text-zinc-600 uppercase'>
                Entry
              </span>
              <span className='font-mono text-xs text-zinc-400'>
                {safeFloat(signal.price ?? signal.entry, decimals)}
              </span>
            </>
          ) : (
            <span className='text-[10px] font-mono text-zinc-700'>--</span>
          )}
        </div>

        {/* R:R Ratio */}
        {signal.rr_ratio && (
          <div className='flex items-center gap-1.5'>
            <span className='text-[10px] font-mono text-zinc-600 uppercase'>
              R:R
            </span>
            <span className='font-mono text-xs text-zinc-400'>
              1:{safeFloat(signal.rr_ratio, 1)}
            </span>
          </div>
        )}

        {/* PnL Display */}
        <div className='flex flex-col items-end gap-0.5'>
          <div className='flex items-center gap-1.5'>
            <span className='text-[10px] font-mono text-zinc-600 uppercase'>
              PnL
            </span>
            <PnLDisplay pnl={pnl} size='sm' />
          </div>
          {/* Exit price for closed trades */}
          {isClosed && signal.exit_price !== undefined && (
            <div className='flex items-center gap-1.5'>
              <span className='text-[10px] font-mono text-zinc-600 uppercase'>
                Exit
              </span>
              <span className='font-mono text-[10px] text-zinc-500'>
                {safeFloat(signal.exit_price, decimals)}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* BOTTOM: Notes (reasoning) + Formatted Timestamp */}
      <div className='px-3 pb-3 space-y-2'>
        <div className='min-h-[32px]'>
          {reason ? (
            <p className='text-[11px] font-mono text-zinc-500 leading-relaxed line-clamp-2'>
              {reason}
            </p>
          ) : (
            <p className='text-[11px] font-mono text-zinc-700 italic'>
              No reasoning provided
            </p>
          )}
        </div>

        {/* Timestamp Footer */}
        <div className='flex items-center justify-between pt-2 border-t border-zinc-800/40'>
          <span
            className='font-mono text-[10px] text-zinc-600'
            suppressHydrationWarning
          >
            {formatDistanceToNow(new Date(signal.created_at), {
              addSuffix: true,
            })}
          </span>
          <span
            className='font-mono text-[10px] text-zinc-700'
            suppressHydrationWarning
          >
            {format(new Date(signal.created_at), 'HH:mm:ss')}
          </span>
        </div>
      </div>

      {/* Hover overlay hint */}
      <div className='absolute inset-0 bg-gradient-to-t from-zinc-950/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none' />
    </div>
  );
}

// ============================================================================
// SKELETON LOADER
// ============================================================================

export function SignalCardSkeleton() {
  return (
    <div className='bg-zinc-900/70 border border-zinc-800 rounded-lg overflow-hidden animate-pulse'>
      <div className='flex items-center justify-between p-3 border-b border-zinc-800/60'>
        <div className='flex items-center gap-2.5'>
          <div className='h-5 w-20 bg-zinc-800 rounded' />
          <div className='h-5 w-14 bg-zinc-800 rounded-full' />
        </div>
        <div className='h-5 w-16 bg-zinc-800 rounded-full' />
      </div>
      <div className='px-3 pt-3 pb-2 space-y-1.5'>
        <div className='flex items-center justify-between'>
          <div className='h-3 w-24 bg-zinc-800 rounded' />
          <div className='h-3 w-10 bg-zinc-800 rounded' />
        </div>
        <div className='h-2 w-full bg-zinc-800 rounded-full' />
      </div>
      <div className='px-3 pb-2 flex items-center justify-between gap-4'>
        <div className='h-3 w-20 bg-zinc-800 rounded' />
        <div className='h-3 w-14 bg-zinc-800 rounded' />
        <div className='h-3 w-16 bg-zinc-800 rounded' />
      </div>
      <div className='px-3 pb-3 space-y-2'>
        <div className='space-y-1'>
          <div className='h-3 w-full bg-zinc-800 rounded' />
          <div className='h-3 w-3/4 bg-zinc-800 rounded' />
        </div>
        <div className='flex items-center justify-between pt-2 border-t border-zinc-800/40'>
          <div className='h-2.5 w-16 bg-zinc-800 rounded' />
          <div className='h-2.5 w-14 bg-zinc-800 rounded' />
        </div>
      </div>
    </div>
  );
}
