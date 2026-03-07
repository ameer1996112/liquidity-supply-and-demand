'use client';

import { cn } from '@/lib/utils';
import { Sparkles, TrendingUp, TrendingDown } from 'lucide-react';
import type { TradingSignal } from '@/types/trading';
import { getSymbol, getSide, getScore } from '@/types/trading';

interface BestSetupCardProps {
  signal: TradingSignal | null;
  className?: string;
}

/**
 * Highlights the highest-confidence signal of the current session.
 * Shows symbol, side, entry model, zone type, and AI score.
 */
export function BestSetupCard({ signal, className }: BestSetupCardProps) {
  if (!signal) return null;

  const symbol = getSymbol(signal);
  const side = getSide(signal);
  const isLong = side === 'buy';
  const aiScore = getScore(signal);
  const entryModel = signal.entry_model ?? signal.zone_type ?? 'S&D Zone';
  const grade =
    signal.zone_grade ??
    (aiScore != null
      ? aiScore >= 80
        ? 'A'
        : aiScore >= 60
        ? 'B+'
        : 'C+'
      : null);

  const sideColor = isLong ? '#0ecb81' : '#f6465d';
  const sideBg = isLong ? 'rgba(14,203,129,0.08)' : 'rgba(246,70,93,0.08)';
  const sideBorder = isLong ? 'rgba(14,203,129,0.2)' : 'rgba(246,70,93,0.2)';

  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-xl border px-4 py-3',
        'bg-gradient-to-br from-[var(--to-surface)] to-[var(--to-surface-raised)]',
        'transition-all duration-200 hover:-translate-y-[1px]',
        className
      )}
      style={{ borderColor: 'rgba(139,92,246,0.25)' }}
    >
      {/* Purple glow top-left */}
      <div
        className='pointer-events-none absolute -left-4 -top-4 h-16 w-16 rounded-full opacity-20'
        style={{
          background: 'radial-gradient(circle, #8b5cf6 0%, transparent 70%)',
        }}
      />

      {/* Header */}
      <div className='mb-2 flex items-center gap-1.5'>
        <Sparkles className='h-3 w-3 text-[#8b5cf6]' />
        <span
          className='text-[9px] font-bold uppercase tracking-[0.18em] text-[#8b5cf6]'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          Best Setup Today
        </span>
      </div>

      {/* Main content */}
      <div className='flex items-center justify-between gap-3'>
        <div className='flex items-center gap-2.5'>
          {/* Side badge */}
          <div
            className='flex h-8 w-8 items-center justify-center rounded-lg'
            style={{
              backgroundColor: sideBg,
              border: `1px solid ${sideBorder}`,
            }}
          >
            {isLong ? (
              <TrendingUp className='h-4 w-4' style={{ color: sideColor }} />
            ) : (
              <TrendingDown className='h-4 w-4' style={{ color: sideColor }} />
            )}
          </div>

          <div>
            <div className='flex items-center gap-2'>
              <span
                className='text-[15px] font-bold text-[var(--to-text-primary)]'
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                {symbol}
              </span>
              <span
                className='text-[9px] font-bold uppercase px-1.5 py-0.5 rounded'
                style={{
                  backgroundColor: sideBg,
                  color: sideColor,
                  border: `1px solid ${sideBorder}`,
                }}
              >
                {isLong ? 'LONG' : 'SHORT'}
              </span>
            </div>
            <div
              className='text-[10px] text-[var(--to-text-dim)] mt-0.5'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              {entryModel}
            </div>
          </div>
        </div>

        {/* AI Score */}
        {aiScore != null && (
          <div className='flex flex-col items-end'>
            <span
              className='text-[20px] font-bold tabular-nums leading-none'
              style={{ color: '#8b5cf6', fontFamily: 'var(--font-mono)' }}
            >
              {Math.round(aiScore)}
            </span>
            <span
              className='text-[9px] text-[var(--to-text-dim)] mt-0.5'
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              AI Score
            </span>
            {grade && (
              <span
                className='mt-1 text-[10px] font-bold px-1.5 py-0.5 rounded'
                style={{
                  backgroundColor: 'rgba(139,92,246,0.12)',
                  color: '#a78bfa',
                  border: '1px solid rgba(139,92,246,0.25)',
                }}
              >
                {grade}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
