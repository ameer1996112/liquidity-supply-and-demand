'use client';

import { useState, useEffect } from 'react';
import { useModifySLTP } from '@/hooks/usePositions';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useConnectionHealth } from '@/hooks/useConnectionHealth';
import { useTwoStepConfirm } from '@/hooks/useTwoStepConfirm';

export function ModifySLTPDialog({
  open,
  onOpenChange,
  signalId,
  currentSL,
  currentTP,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  signalId: number;
  currentSL: number | null;
  currentTP: number | null;
}) {
  const [sl, setSl] = useState('');
  const [tp, setTp] = useState('');
  const modifySLTP = useModifySLTP();
  const { isConnected } = useConnectionHealth();
  const { armed, secondsRemaining, requestConfirm, reset } =
    useTwoStepConfirm();

  useEffect(() => {
    if (open) {
      setSl(currentSL != null ? String(currentSL) : '');
      setTp(currentTP != null ? String(currentTP) : '');
      reset();
    }
  }, [open, currentSL, currentTP, reset]);

  const handleSubmit = () => {
    const newSL = sl ? parseFloat(sl) : undefined;
    const newTP = tp ? parseFloat(tp) : undefined;

    if (newSL === undefined && newTP === undefined) return;

    modifySLTP.mutate(
      { signalId, sl: newSL, tp: newTP },
      {
        onSuccess: () => onOpenChange(false),
      },
    );
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className='bg-[#131722] border-l border-[#2a2e39]'>
        <SheetHeader>
          <SheetTitle className='font-mono text-sm text-zinc-200'>
            Modify SL / TP
          </SheetTitle>
          <SheetDescription className='sr-only'>
            Update stop loss and take profit levels for this position.
          </SheetDescription>
        </SheetHeader>

        <div className='mt-6 space-y-4'>
          <div className='space-y-1'>
            <label className='text-[10px] uppercase tracking-wider text-zinc-500 font-mono'>
              Stop Loss
            </label>
            <input
              id='modify-stop-loss'
              type='number'
              step='any'
              value={sl}
              onChange={(e) => setSl(e.target.value)}
              placeholder={currentSL != null ? String(currentSL) : 'Enter SL'}
              className='w-full bg-[#1e222d] border border-[#2a2e39] rounded px-2.5 py-1.5 text-xs font-mono text-zinc-300 focus:outline-none focus:border-[#26a69a] transition-colors'
            />
          </div>

          <div className='space-y-1'>
            <label className='text-[10px] uppercase tracking-wider text-zinc-500 font-mono'>
              Take Profit
            </label>
            <input
              id='modify-take-profit'
              type='number'
              step='any'
              value={tp}
              onChange={(e) => setTp(e.target.value)}
              placeholder={currentTP != null ? String(currentTP) : 'Enter TP'}
              className='w-full bg-[#1e222d] border border-[#2a2e39] rounded px-2.5 py-1.5 text-xs font-mono text-zinc-300 focus:outline-none focus:border-[#26a69a] transition-colors'
            />
          </div>

          <button
            onClick={() => requestConfirm(handleSubmit)}
            disabled={modifySLTP.isPending || !isConnected}
            className={cn(
              'w-full flex items-center justify-center gap-2 py-2 rounded-md',
              'font-mono text-xs font-semibold uppercase tracking-wider transition-colors',
              modifySLTP.isPending
                ? 'bg-[#2a2e39] text-zinc-500 cursor-not-allowed'
                : !isConnected
                  ? 'bg-[#2a2e39] text-zinc-600 cursor-not-allowed'
                  : 'bg-blue-500 text-white hover:bg-blue-500/90',
              armed && 'ring-2 ring-blue-300/60',
            )}
          >
            {modifySLTP.isPending && (
              <Loader2 className='w-3.5 h-3.5 animate-spin' />
            )}
            {modifySLTP.isPending
              ? 'Updating...'
              : armed
                ? `Confirm (${secondsRemaining ?? 2}s)`
                : 'Update SL/TP'}
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
