'use client';

import { TradingSignal, getSymbol, getSide, getPnl } from '@/types/trading';
import { cn } from '@/lib/utils';
import { formatDistanceToNowStrict } from 'date-fns';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { normalizeSignedZero, safeFloat } from '@/lib/format';

interface ActiveTradeRowProps {
  signal: TradingSignal;
  onSelectSignal: (signal: TradingSignal) => void;
}

// Derive trigger label from signal fields
function getTriggerLabel(signal: TradingSignal): string | null {
  const entryModel = (signal.entry_model ?? '').toLowerCase();
  const exitType = (signal.exit_type ?? '').toLowerCase();
  if (exitType.includes('dir') || entryModel.includes('dir'))
    return 'DIR CLOSE';
  if (entryModel.includes('boc') || entryModel.includes('break')) return 'BoC';
  if (
    entryModel.includes('flip') ||
    entryModel.includes('zone') ||
    signal.zone_type
  )
    return 'FLIP';
  return null;
}

export function ActiveTradeRow({
  signal,
  onSelectSignal,
}: ActiveTradeRowProps) {
  const symbol = getSymbol(signal);
  const side = getSide(signal);
  const pnl = normalizeSignedZero(getPnl(signal));
  const isBuy = side === 'buy';
  const entry = signal.price ?? signal.entry;
  const rr = signal.rr_ratio;
  const timeHeld = formatDistanceToNowStrict(new Date(signal.created_at), {
    addSuffix: false,
  });
  const trigger = getTriggerLabel(signal);

  return (
    <button
      onClick={() => onSelectSignal(signal)}
      className={cn(
        'w-full flex items-center gap-2 px-2.5 py-2 rounded-lg',
        'border-l-2 border-l-indigo-500/60 bg-slate-800/40',
        'hover:bg-slate-800/70 transition-colors cursor-pointer text-left'
      )}
    >
      {/* Symbol + direction */}
      <div className='flex items-center gap-1.5 min-w-[90px]'>
        <span
          className='text-xs font-bold text-slate-100'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {symbol}
        </span>
        <span
          className={cn(
            'flex items-center gap-0.5 rounded px-1 py-0 text-[9px] font-bold',
            isBuy
              ? 'bg-emerald-500/15 text-emerald-400'
              : 'bg-red-500/15 text-red-400'
          )}
        >
          {isBuy ? (
            <TrendingUp className='h-2.5 w-2.5' />
          ) : (
            <TrendingDown className='h-2.5 w-2.5' />
          )}
          {side.toUpperCase()}
        </span>
      </div>

      {/* Trigger badge */}
      {trigger && (
        <span
          className={cn(
            'shrink-0 rounded px-1.5 py-0 text-[9px] font-bold',
            trigger === 'FLIP' && 'trigger-flip',
            trigger === 'BoC' && 'trigger-boc',
            trigger === 'DIR CLOSE' && 'trigger-dir-close'
          )}
        >
          {trigger}
        </span>
      )}

      {/* Entry price */}
      <div className='flex flex-col min-w-[60px]'>
        <span
          className='text-[9px] uppercase text-slate-600'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          Entry
        </span>
        <span
          className='text-[11px] text-slate-300 tabular-nums'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {entry != null
            ? Number(entry).toFixed(symbol.includes('JPY') ? 3 : 5)
            : '—'}
        </span>
      </div>

      {/* R:R */}
      <div className='flex flex-col min-w-[36px]'>
        <span
          className='text-[9px] uppercase text-slate-600'
          style={{ fontFamily: 'var(--font-sans)' }}
        >
          R:R
        </span>
        <span
          className='text-[11px] text-slate-400 tabular-nums'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {rr ? `1:${rr.toFixed(1)}` : '—'}
        </span>
      </div>

      {/* Time held */}
      <div className='flex-1 text-right'>
        <span
          className='text-[10px] text-slate-600'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {timeHeld}
        </span>
      </div>

      {/* PnL */}
      <div className='min-w-[52px] text-right'>
        {pnl != null ? (
          <span
            className={cn(
              'text-xs font-bold tabular-nums',
              pnl >= 0 ? 'text-emerald-400' : 'text-red-400'
            )}
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {pnl > 0 ? '+' : ''}
            {safeFloat(pnl, 2)}
          </span>
        ) : (
          <span
            className='text-xs text-slate-600'
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            —
          </span>
        )}
      </div>
    </button>
  );
}
