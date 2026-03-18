'use client';

import { Trophy, Clock, ChevronRight, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';
import { AccountSelector } from './AccountSelector';

function PhaseBadge({ phase }: { phase: string }) {
  const labels: Record<
    string,
    { label: string; text: string; bg: string; border: string }
  > = {
    phase1: {
      label: 'Phase 1',
      text: 'text-zinc-400',
      bg: 'bg-zinc-500/10',
      border: 'border-zinc-500/20',
    },
    phase2: {
      label: 'Phase 2',
      text: 'text-blue-400',
      bg: 'bg-blue-500/10',
      border: 'border-blue-500/20',
    },
    funded: {
      label: 'Funded',
      text: 'text-[#f0b90b]',
      bg: 'bg-[#f0b90b]/10',
      border: 'border-[#f0b90b]/30',
    },
  };
  const meta = labels[phase] ?? {
    label: phase.toUpperCase(),
    text: 'text-zinc-500',
    bg: 'bg-zinc-500/5',
    border: 'border-zinc-500/20',
  };
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold uppercase tracking-wider font-mono border',
        meta.text,
        meta.bg,
        meta.border
      )}
    >
      <Trophy className='h-3 w-3' />
      {meta.label}
    </span>
  );
}

interface ChallengeHeaderProps {
  accountName: string;
  evaluationPhase: string;
  daysRemaining: number | null;
  accountOptions: string[];
  selectedAccount: string;
  onSelectAccount: (account: string) => void;
  dataUpdatedAt: number | undefined;
  onReset: () => void;
  isResetting: boolean;
}

export function ChallengeHeader({
  accountName,
  evaluationPhase,
  daysRemaining,
  accountOptions,
  selectedAccount,
  onSelectAccount,
  dataUpdatedAt,
  onReset,
  isResetting,
}: ChallengeHeaderProps) {
  return (
    <div className='tv-card p-6'>
      <div className='flex flex-col md:flex-row md:items-center md:justify-between gap-4'>
        <div className='space-y-3'>
          <div className='flex items-center gap-3'>
            <div className='flex h-12 w-12 items-center justify-center rounded-xl border border-amber-500/30 bg-amber-500/10'>
              <Trophy className='h-6 w-6 text-amber-400' />
            </div>
            <div>
              <h1 className='text-[22px] font-black text-zinc-100 tracking-tight'>
                Prop Firm Challenge
              </h1>
              <div className='flex items-center gap-2 mt-1'>
                <span className='text-[12px] text-zinc-500 font-mono'>
                  {accountName}
                </span>
                <ChevronRight className='h-3 w-3 text-zinc-700' />
                <PhaseBadge phase={evaluationPhase} />
                {daysRemaining !== null && (
                  <div className='flex items-center gap-1 ml-2 text-[11px] text-zinc-600 font-mono'>
                    <Clock className='h-3 w-3' />
                    {daysRemaining} days remaining
                  </div>
                )}
              </div>
            </div>
          </div>

          <AccountSelector
            accounts={accountOptions}
            selectedAccount={selectedAccount}
            onSelect={onSelectAccount}
          />
        </div>

        <div className='flex items-center gap-3'>
          {dataUpdatedAt && (
            <span className='text-[11px] text-zinc-600 font-mono'>
              Updated {format(new Date(dataUpdatedAt), 'HH:mm:ss')}
            </span>
          )}
          <button
            onClick={onReset}
            disabled={isResetting}
            className='flex items-center gap-1.5 px-4 py-2 rounded-lg border border-[#2a2e39] text-[12px] text-zinc-400 hover:bg-[#1e222d] transition-colors'
          >
            <RefreshCw
              className={cn(
                'h-3.5 w-3.5',
                isResetting && 'animate-spin'
              )}
            />
            Reset Daily
          </button>
        </div>
      </div>
    </div>
  );
}
