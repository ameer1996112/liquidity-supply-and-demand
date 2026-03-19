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
import { AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTwoStepConfirm } from '@/hooks/useTwoStepConfirm';

export type KillSwitchMode = 'engage' | 'reset';

interface KillSwitchConfirmDialogProps {
  open: boolean;
  mode: KillSwitchMode;
  onOpenChange: (open: boolean) => void;
  onConfirm: (reason: string) => void;
  isPending?: boolean;
}

export function KillSwitchConfirmDialog({
  open,
  mode,
  onOpenChange,
  onConfirm,
  isPending,
}: KillSwitchConfirmDialogProps) {
  const [phrase, setPhrase] = useState('');
  const [reason, setReason] = useState('');
  const confirmState = useTwoStepConfirm();

  useEffect(() => {
    if (open) {
      setPhrase('');
      setReason('');
    }
  }, [open]);

  const engaging = mode === 'engage';
  const requirePhrase = engaging;
  const phraseOk = !requirePhrase || phrase.trim().toUpperCase() === 'HALT';

  const handleConfirm = () => {
    if (!phraseOk || isPending) return;
    const fallbackReason = engaging
      ? 'Global kill switch engaged from dashboard'
      : 'Global kill switch reset from dashboard';
    onConfirm(reason.trim() || fallbackReason);
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side='top'
        className='bg-[#131722] border-b border-[#2a2e39] max-w-2xl mx-auto mt-10 rounded-lg shadow-2xl'
        showCloseButton
      >
        <SheetHeader>
          <SheetTitle className='flex items-center gap-2 font-mono text-sm text-[var(--to-text-primary)]'>
            <AlertTriangle className='h-4 w-4 text-[var(--to-short)]' />
            {engaging
              ? 'Engage Global Kill Switch'
              : 'Reset Global Kill Switch'}
          </SheetTitle>
          <SheetDescription className='mt-1 text-[11px] text-[var(--to-text-dim)] font-mono leading-relaxed'>
            {engaging
              ? 'This will HALT ALL ACCOUNTS and block new trade execution across the system. Existing open positions will remain open until you close them manually.'
              : 'This will allow new trades to be executed again, subject to existing risk guard rails and account configuration.'}
          </SheetDescription>
        </SheetHeader>

        <div className='px-4 pb-3 pt-2 space-y-4'>
          {engaging && (
            <div className='space-y-2 rounded-md border border-[var(--to-short)]/30 bg-red-500/5 p-3'>
              <p className='font-mono text-[10px] text-red-300 uppercase tracking-[0.14em]'>
                Impact
              </p>
              <ul className='list-disc pl-4 space-y-1 text-[11px] text-[var(--to-text-secondary)] font-mono'>
                <li>Halts all accounts from opening NEW positions.</li>
                <li>Existing open positions remain live until closed.</li>
                <li>
                  Worker processes will reject execution while the kill switch
                  is active (audit logged in kill_switch_log and trade_events).
                </li>
              </ul>
            </div>
          )}

          <div className='space-y-2'>
            <label className='block text-[10px] font-mono uppercase tracking-[0.14em] text-[var(--to-text-dim)]'>
              {engaging ? 'Type HALT to confirm' : 'Optional reason'}
            </label>
            {engaging && (
              <input
                id='kill-switch-confirm-phrase'
                type='text'
                value={phrase}
                onChange={(e) => setPhrase(e.target.value)}
                placeholder='HALT'
                className='w-full rounded border border-[#2a2e39] bg-[#1e222d] px-3 py-1.5 text-xs font-mono text-[var(--to-text-primary)] placeholder:text-[var(--to-text-dim)] focus:border-red-500 focus:outline-none'
              />
            )}
            <textarea
              id='kill-switch-reason'
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              placeholder={
                engaging
                  ? 'Optional: Why are you halting trading? (e.g., news event, platform incident)'
                  : 'Optional: Why are you resuming trading?'
              }
              className='w-full rounded border border-[#2a2e39] bg-[#1e222d] px-3 py-1.5 text-xs font-mono text-[var(--to-text-primary)] placeholder:text-[var(--to-text-dim)] focus:border-zinc-500 focus:outline-none'
            />
          </div>
        </div>

        <SheetFooter className='flex flex-row items-center justify-end gap-2 border-t border-[#2a2e39] bg-[#0f131c]/80'>
          <button
            type='button'
            onClick={() => onOpenChange(false)}
            className='rounded border border-zinc-700 bg-[var(--to-surface-raised)] px-3 py-1.5 text-[10px] font-mono text-[var(--to-text-secondary)] hover:bg-[var(--to-surface-raised)]'
          >
            Cancel
          </button>
          <button
            type='button'
            onClick={() => confirmState.requestConfirm(handleConfirm)}
            disabled={!phraseOk || !!isPending}
            className={cn(
              'flex items-center gap-1.5 rounded px-3 py-1.5 text-[10px] font-mono font-semibold uppercase tracking-wider transition-colors',
              engaging
                ? 'border-red-500 bg-red-600 text-white hover:bg-red-500 disabled:border-red-900 disabled:bg-red-900 disabled:text-[var(--to-short)]'
                : 'border-emerald-500 bg-emerald-600 text-white hover:bg-emerald-500 disabled:border-emerald-900 disabled:bg-emerald-900 disabled:text-[var(--to-long)]',
              confirmState.armed && 'ring-2 ring-red-400/60',
            )}
          >
            {confirmState.armed
              ? `Confirm (${confirmState.secondsRemaining ?? 2}s)`
              : engaging
                ? 'Engage Kill Switch'
                : 'Reset Kill Switch'}
          </button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
