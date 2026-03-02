'use client';

/**
 * ActiveTradeRow — kept for any legacy callers that render individual trade rows
 * outside the TanStack Table context (e.g. mobile card layout).
 *
 * All colours now use design-system tokens (--to-*). No inline fontFamily styles.
 */

import { TradingSignal, getSymbol, getSide, getPnl } from '@/types/trading';
import { cn } from '@/lib/utils';
import { formatDistanceToNowStrict } from 'date-fns';
import { ClientDate } from '@/components/ui/ClientDate';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { EMPTY_VALUE, formatNumber, normalizeNegativeZero } from '@/lib/formatters';

interface ActiveTradeRowProps {
  signal: TradingSignal;
  onSelectSignal: (signal: TradingSignal) => void;
}

function getTriggerLabel(signal: TradingSignal): string | null {
  const entryModel = (signal.entry_model ?? '').toLowerCase();
  const exitType = (signal.exit_type ?? '').toLowerCase();
  if (exitType.includes('dir') || entryModel.includes('dir')) return 'DIR CLOSE';
  if (entryModel.includes('boc') || entryModel.includes('break')) return 'BoC';
  if (entryModel.includes('flip') || entryModel.includes('zone') || signal.zone_type) return 'FLIP';
  return null;
}

export function ActiveTradeRow({ signal, onSelectSignal }: ActiveTradeRowProps) {
  const symbol = getSymbol(signal);
  const side = getSide(signal);
  const pnl = normalizeNegativeZero(getPnl(signal));
  const isBuy = side === 'buy';
  const entry = signal.price ?? signal.entry;
  const rr = signal.rr_ratio;
  const trigger = getTriggerLabel(signal);

  return (
    <button
      onClick={() => onSelectSignal(signal)}
      className={cn(
        'flex w-full cursor-pointer items-center gap-2 rounded px-2.5 py-2 text-left',
        'border-l-2 border-l-[var(--to-accent-blue)]/40 bg-[var(--to-surface-raised)]/40',
        'transition-colors duration-100 hover:bg-[var(--to-surface-raised)]',
      )}
    >
      {/* Symbol + direction */}
      <div className='flex min-w-[90px] items-center gap-1.5'>
        <span className='font-mono text-xs font-bold text-[var(--to-text-primary)]'>
          {symbol}
        </span>
        <span
          className={cn(
            'inline-flex items-center gap-0.5 rounded px-1 py-0 font-mono text-[9px] font-bold',
            isBuy
              ? 'bg-[var(--to-long)]/15 text-[var(--to-long)]'
              : 'bg-[var(--to-short)]/15 text-[var(--to-short)]',
          )}
        >
          {isBuy ? <TrendingUp className='h-2.5 w-2.5' /> : <TrendingDown className='h-2.5 w-2.5' />}
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
            trigger === 'DIR CLOSE' && 'trigger-dir-close',
          )}
        >
          {trigger}
        </span>
      )}

      {/* Entry price */}
      <div className='flex min-w-[60px] flex-col'>
        <span className='kpi-meta'>Entry</span>
        <span className='font-mono text-[11px] tabular-nums text-[var(--to-text-secondary)]'>
          {entry != null
            ? Number(entry).toFixed(symbol.includes('JPY') ? 3 : 5)
            : EMPTY_VALUE}
        </span>
      </div>

      {/* R:R */}
      <div className='flex min-w-[36px] flex-col'>
        <span className='kpi-meta'>R:R</span>
        <span className='font-mono text-[11px] tabular-nums text-[var(--to-text-dim)]'>
          {rr ? `1:${formatNumber(rr, { decimals: 1 })}` : EMPTY_VALUE}
        </span>
      </div>

      {/* Time held */}
      <div className='flex-1 text-right'>
        <ClientDate
          className='font-mono text-[10px] tabular-nums text-[var(--to-text-dim)]'
          render={() =>
            formatDistanceToNowStrict(new Date(signal.created_at), { addSuffix: false })
          }
        />
      </div>

      {/* PnL */}
      <div className='min-w-[52px] text-right'>
        {pnl != null ? (
          <span
            className={cn(
              'font-mono text-xs font-bold tabular-nums',
              pnl >= 0 ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]',
            )}
          >
            {pnl > 0 ? '+' : ''}
            {formatNumber(pnl, { decimals: 2 })}
          </span>
        ) : (
          <span className='font-mono text-xs text-[var(--to-text-dim)]'>{EMPTY_VALUE}</span>
        )}
      </div>
    </button>
  );
}
