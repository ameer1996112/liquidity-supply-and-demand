'use client';

import { useEffect, useState } from 'react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetFooter,
} from '@/components/ui/sheet';
import { AlertTriangle, X } from 'lucide-react';
import { type ActivePosition } from '@/hooks/usePositions';
import { cn } from '@/lib/utils';
import { useTwoStepConfirm } from '@/hooks/useTwoStepConfirm';

interface ClosePositionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  position: ActivePosition;
  onConfirm: (reason: string) => void;
  isSubmitting?: boolean;
}

export function ClosePositionDialog({
  open,
  onOpenChange,
  position,
  onConfirm,
  isSubmitting,
}: ClosePositionDialogProps) {
  const [reason, setReason] = useState('');
  const { armed, secondsRemaining, requestConfirm, reset } =
    useTwoStepConfirm();

  useEffect(() => {
    if (open) {
      setReason('');
      reset();
    }
  }, [open, reset]);

  const handleConfirm = () => {
    if (isSubmitting) return;
    const fallback = 'Manual close from UI';
    onConfirm(reason.trim() || fallback);
  };

  const isBuy = position.side.toLowerCase() === 'buy';
  const pnlPositive = (position.live_pnl ?? 0) >= 0;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side='right'
        className='bg-[#131722] border-l border-[#2a2e39] sm:max-w-md'
      >
        <SheetHeader>
          <SheetTitle className='flex items-center gap-2 font-mono text-sm text-[var(--to-text-primary)]'>
            <AlertTriangle className='h-4 w-4 text-amber-400' />
            Confirm Manual Close
          </SheetTitle>
          <SheetDescription className='mt-1 text-[11px] text-[var(--to-text-dim)] font-mono leading-relaxed'>
            This will send a CLOSE order to the broker and mark this trade as
            manually closed. Open PnL will be realized at the current market
            price.
          </SheetDescription>
        </SheetHeader>

        <div className='mt-4 space-y-4 px-4'>
          <div className='rounded-md border border-[#2a2e39] bg-[#1b202b] p-3'>
            <div className='flex items-center justify-between'>
              <div className='flex items-center gap-2'>
                <span className='font-mono text-sm font-bold text-[var(--to-text-primary)]'>
                  {position.symbol}
                </span>
                <span
                  className={cn(
                    'font-mono text-[10px] px-1.5 py-0.5 rounded font-semibold uppercase',
                    isBuy
                      ? 'bg-[#26a69a]/15 text-[#26a69a]'
                      : 'bg-[#ef5350]/15 text-[#ef5350]',
                  )}
                >
                  {position.side}
                </span>
                {position.zone_type && (
                  <span className='font-mono text-[9px] px-1 py-0.5 rounded bg-[#2a2e39] text-[var(--to-text-dim)] uppercase'>
                    {position.zone_type}
                  </span>
                )}
              </div>
              <div className='text-right'>
                <span
                  className={cn(
                    'font-mono text-lg font-bold tabular-nums',
                    pnlPositive ? 'text-[#26a69a]' : 'text-[#ef5350]',
                  )}
                >
                  {position.live_pnl != null
                    ? `${position.live_pnl >= 0 ? '+' : ''}$${position.live_pnl.toFixed(2)}`
                    : '—'}
                </span>
              </div>
            </div>

            <div className='mt-3 grid grid-cols-2 gap-3 text-[11px] font-mono text-[var(--to-text-secondary)]'>
              <div>
                <div className='text-[9px] uppercase tracking-[0.14em] text-[var(--to-text-dim)]'>
                  Entry
                </div>
                <div className='tabular-nums'>
                  {position.entry != null ? position.entry : '—'}
                </div>
              </div>
              <div>
                <div className='text-[9px] uppercase tracking-[0.14em] text-[var(--to-text-dim)]'>
                  Size (lots)
                </div>
                <div className='tabular-nums'>{position.size}</div>
              </div>
              <div>
                <div className='text-[9px] uppercase tracking-[0.14em] text-[var(--to-text-dim)]'>
                  Stop Loss
                </div>
                <div className='tabular-nums'>
                  {position.sl != null ? position.sl : '—'}
                </div>
              </div>
              <div>
                <div className='text-[9px] uppercase tracking-[0.14em] text-[var(--to-text-dim)]'>
                  Take Profit
                </div>
                <div className='tabular-nums'>
                  {position.tp != null ? position.tp : '—'}
                </div>
              </div>
            </div>
          </div>

          <div className='space-y-2'>
            <label className='block text-[10px] font-mono uppercase tracking-[0.14em] text-[var(--to-text-dim)]'>
              Reason (optional)
            </label>
            <textarea
              id='close-position-reason'
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              placeholder='Why are you closing this trade? (e.g., risk management, news, deviation from plan)'
              className='w-full rounded border border-[#2a2e39] bg-[#1e222d] px-3 py-1.5 text-xs font-mono text-[var(--to-text-primary)] placeholder:text-[var(--to-text-dim)] focus:border-amber-500 focus:outline-none'
            />
          </div>
        </div>

        <SheetFooter className='mt-auto flex flex-row items-center justify-end gap-2 border-t border-[#2a2e39] bg-[#0f131c]/80 px-4 py-3'>
          <button
            type='button'
            onClick={() => onOpenChange(false)}
            className='inline-flex items-center gap-1 rounded border border-zinc-700 bg-[var(--to-surface-raised)] px-3 py-1.5 text-[10px] font-mono text-[var(--to-text-secondary)] hover:bg-[var(--to-surface-raised)]'
          >
            <X className='h-3 w-3' />
            Cancel
          </button>
          <button
            type='button'
            onClick={() => requestConfirm(handleConfirm)}
            disabled={!!isSubmitting}
            className={cn(
              'inline-flex items-center gap-1 rounded px-3 py-1.5 text-[10px] font-mono font-semibold uppercase tracking-wider transition-colors',
              'border-red-500 bg-red-600 text-white hover:bg-red-500 disabled:border-red-900 disabled:bg-red-900 disabled:text-[var(--to-short)]',
              armed && 'ring-2 ring-red-400/60',
            )}
          >
            {armed ? `Confirm (${secondsRemaining ?? 2}s)` : 'Close Position'}
          </button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
