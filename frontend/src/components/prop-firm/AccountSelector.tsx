'use client';

import { cn } from '@/lib/utils';

interface AccountSelectorProps {
  accounts: string[];
  selectedAccount: string;
  onSelect: (account: string) => void;
}

export function AccountSelector({
  accounts,
  selectedAccount,
  onSelect,
}: AccountSelectorProps) {
  return (
    <div className='flex items-center gap-1.5 flex-wrap'>
      <span className='text-[11px] text-zinc-600 font-mono mr-1'>
        Account:
      </span>
      {accounts.map((acc) => (
        <button
          key={acc}
          onClick={() => onSelect(acc)}
          className={cn(
            'px-3 py-1.5 rounded-lg text-[11px] font-bold font-mono uppercase tracking-wide transition-all border',
            selectedAccount === acc
              ? 'text-amber-400 border-amber-500/40 bg-amber-500/15'
              : 'text-zinc-600 border-[#2a2e39] hover:text-zinc-400'
          )}
        >
          {acc}
        </button>
      ))}
    </div>
  );
}
