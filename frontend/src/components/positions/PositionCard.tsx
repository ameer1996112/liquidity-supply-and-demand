'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import {
  ActivePosition,
  useClosePosition,
  usePartialClose,
} from '@/hooks/usePositions';
import { ModifySLTPDialog } from './ModifySLTPDialog';
import { ClosePositionDialog } from './ClosePositionDialog';
import { X, Pencil, Scissors, Loader2 } from 'lucide-react';
import { formatDistanceToNowStrict } from 'date-fns';
import { ClientDate } from '@/components/ui/ClientDate';
import { PnLText } from '@/components/ui/typography';
import { useConnectionHealth } from '@/hooks/useConnectionHealth';

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
  const [showCloseDialog, setShowCloseDialog] = useState(false);
  const closePosition = useClosePosition();
  const partialClose = usePartialClose();
  const { isConnected } = useConnectionHealth();

  const isBuy = position.side.toLowerCase() === 'buy';
  const pnlPositive = (position.live_pnl ?? 0) >= 0;

  const handleClose = () => {
    setShowCloseDialog(true);
  };

  const handlePartialClose = () => {
    partialClose.mutate({ signalId: position.id, closePercent: 50 });
  };

  return (
    <>
      <div
        className={cn(
          'tv-card border-l-2 transition-colors',
          pnlPositive ? 'border-l-[var(--to-long)]' : 'border-l-[var(--to-short)]',
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
                    ? 'bg-[var(--to-long)]/15 text-[var(--to-long)]'
                    : 'bg-[var(--to-short)]/15 text-[var(--to-short)]',
                )}
              >
                {position.side}
              </span>
              {position.zone_type && (
                <span className='font-mono text-[9px] px-1 py-0.5 rounded bg-[var(--to-surface-raised)] text-[var(--to-text-secondary)] uppercase'>
                  {position.zone_type}
                </span>
              )}
            </div>
            <div className='text-right'>
              <PnLText
                value={position.live_pnl}
                variant='currency'
                size='xl'
              />
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
            {position.created_at ? (
              <ClientDate
                render={() =>
                  `Hold: ${formatDistanceToNowStrict(new Date(position.created_at!), { addSuffix: false })}`
                }
              />
            ) : (
              <span>Hold: —</span>
            )}
            {position.entry_model && <span>{position.entry_model}</span>}
          </div>

          {/* Action buttons */}
          <div className='flex items-center gap-2 pt-1 border-t border-panel-border-subtle'>
            <button
              onClick={handleClose}
              disabled={closePosition.isPending || !isConnected}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider transition-colors',
                'bg-[var(--to-short)]/15 text-[var(--to-short)] hover:bg-[var(--to-short)]/25 disabled:opacity-60 disabled:cursor-not-allowed',
              )}
            >
              {closePosition.isPending ? (
                <Loader2 className='w-3 h-3 animate-spin' />
              ) : (
                <X className='w-3 h-3' />
              )}
              Close
            </button>

            <button
              onClick={() => setShowModify(true)}
              disabled={!isConnected}
              className='flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider bg-[var(--to-accent-blue)]/15 text-[var(--to-accent-blue)] hover:bg-[var(--to-accent-blue)]/25 transition-colors disabled:opacity-60 disabled:cursor-not-allowed'
            >
              <Pencil className='w-3 h-3' />
              SL/TP
            </button>

            <button
              onClick={handlePartialClose}
              disabled={partialClose.isPending || !isConnected}
              className='flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider bg-[var(--to-warning)]/15 text-[var(--to-warning)] hover:bg-[var(--to-warning)]/25 transition-colors'
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

      <ClosePositionDialog
        open={showCloseDialog}
        onOpenChange={setShowCloseDialog}
        position={position}
        isSubmitting={closePosition.isPending}
        onConfirm={(reason) => {
          closePosition.mutate({ signalId: position.id, reason });
          setShowCloseDialog(false);
        }}
      />
    </>
  );
}
