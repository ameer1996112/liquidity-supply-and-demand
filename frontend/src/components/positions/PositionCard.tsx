'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  ActivePosition,
  useClosePosition,
  usePartialClose,
} from '@/hooks/usePositions';
import { ModifySLTPDialog } from './ModifySLTPDialog';
import { X, Pencil, Scissors, Loader2 } from 'lucide-react';
import { formatDistanceToNowStrict } from 'date-fns';

function PriceLabel({ label, value }: { label: string; value: number | null }) {
  return (
    <div className='flex flex-col gap-0.5'>
      <span className='text-[9px] uppercase tracking-wider text-zinc-600 font-mono'>
        {label}
      </span>
      <span className='font-mono text-xs tabular-nums text-zinc-300'>
        {value != null ? value.toFixed(value > 100 ? 2 : 5) : '—'}
      </span>
    </div>
  );
}

export function PositionCard({ position }: { position: ActivePosition }) {
  const [showModify, setShowModify] = useState(false);
  const [confirmClose, setConfirmClose] = useState(false);
  const closePosition = useClosePosition();
  const partialClose = usePartialClose();

  const isBuy = position.side.toLowerCase() === 'buy';
  const pnlPositive = (position.live_pnl ?? 0) >= 0;

  const holdTime = position.created_at
    ? formatDistanceToNowStrict(new Date(position.created_at), {
        addSuffix: false,
      })
    : '—';

  const handleClose = () => {
    if (!confirmClose) {
      setConfirmClose(true);
      setTimeout(() => setConfirmClose(false), 3000);
      return;
    }
    closePosition.mutate({ signalId: position.id });
    setConfirmClose(false);
  };

  const handlePartialClose = () => {
    partialClose.mutate({ signalId: position.id, closePercent: 50 });
  };

  return (
    <>
      <div
        className={cn(
          'tv-card border-l-2 transition-colors',
          pnlPositive ? 'border-l-[#26a69a]' : 'border-l-[#ef5350]',
        )}
      >
        <div className='p-4 space-y-3'>
          {/* Header: Symbol + Side + PnL */}
          <div className='flex items-center justify-between'>
            <div className='flex items-center gap-2'>
              <span className='font-mono text-sm font-bold text-zinc-100'>
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
                <span className='font-mono text-[9px] px-1 py-0.5 rounded bg-[#2a2e39] text-zinc-500 uppercase'>
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

          {/* Prices grid */}
          <div className='grid grid-cols-4 gap-3'>
            <PriceLabel label='Entry' value={position.entry} />
            <PriceLabel label='Current' value={position.current_price} />
            <PriceLabel label='SL' value={position.sl} />
            <PriceLabel label='TP' value={position.tp} />
          </div>

          {/* Meta row */}
          <div className='flex items-center justify-between text-[10px] font-mono text-zinc-500'>
            <span>Size: {position.size}</span>
            {position.rr_ratio && (
              <span>R:R 1:{position.rr_ratio.toFixed(1)}</span>
            )}
            <span suppressHydrationWarning>Hold: {holdTime}</span>
            {position.entry_model && <span>{position.entry_model}</span>}
          </div>

          {/* Action buttons */}
          <div className='flex items-center gap-2 pt-1 border-t border-[#2a2e39]'>
            <button
              onClick={handleClose}
              disabled={closePosition.isPending}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider transition-colors',
                confirmClose
                  ? 'bg-[#ef5350] text-white'
                  : 'bg-[#ef5350]/15 text-[#ef5350] hover:bg-[#ef5350]/25',
              )}
            >
              {closePosition.isPending ? (
                <Loader2 className='w-3 h-3 animate-spin' />
              ) : (
                <X className='w-3 h-3' />
              )}
              {confirmClose ? 'Confirm' : 'Close'}
            </button>

            <button
              onClick={() => setShowModify(true)}
              className='flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider bg-blue-500/15 text-blue-400 hover:bg-blue-500/25 transition-colors'
            >
              <Pencil className='w-3 h-3' />
              SL/TP
            </button>

            <button
              onClick={handlePartialClose}
              disabled={partialClose.isPending}
              className='flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider bg-amber-500/15 text-amber-400 hover:bg-amber-500/25 transition-colors'
            >
              {partialClose.isPending ? (
                <Loader2 className='w-3 h-3 animate-spin' />
              ) : (
                <Scissors className='w-3 h-3' />
              )}
              50%
            </button>
          </div>
        </div>
      </div>

      <ModifySLTPDialog
        open={showModify}
        onOpenChange={setShowModify}
        signalId={position.id}
        currentSL={position.sl}
        currentTP={position.tp}
      />
    </>
  );
}
