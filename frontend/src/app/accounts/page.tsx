'use client';

import { Users } from 'lucide-react';

export default function AccountsPlaceholderPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-zinc-100">
          Multi-Account Manager
        </h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          Manage multiple broker accounts (Funded, Eval, Personal) and copy
          trading. Coming next: AccountCard, CopyConfigurator, CapitalAllocator.
        </p>
      </div>
      <div className="flex flex-col items-center justify-center rounded-lg border border-[#2a2e39] bg-[#1e222d]/50 py-16 text-zinc-500">
        <Users className="h-12 w-12 mb-3 opacity-50" />
        <p className="text-sm">Accounts page — in progress</p>
      </div>
    </div>
  );
}
