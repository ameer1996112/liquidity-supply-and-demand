'use client';

import { useState } from 'react';
import { Shield, ShieldCheck } from 'lucide-react';

import { AccountGuardsView } from '@/components/rules/AccountGuardsView';
import { GlobalGuardsView } from '@/components/rules/GlobalGuardsView';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export function GuardsPanel() {
  const [scope, setScope] = useState<'global' | 'account'>('global');

  return (
    <div className="space-y-4">
      <Tabs value={scope} onValueChange={(value) => setScope(value as 'global' | 'account')}>
        <TabsList className="surface-soft rounded-lg border border-[var(--to-border)] p-0.5">
          <TabsTrigger
            value="global"
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[11px] font-medium data-[state=active]:bg-indigo-600/20 data-[state=active]:text-indigo-300 data-[state=inactive]:text-[var(--to-text-dim)]"
          >
            <Shield className="h-3.5 w-3.5" />
            Global
          </TabsTrigger>
          <TabsTrigger
            value="account"
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[11px] font-medium data-[state=active]:bg-indigo-600/20 data-[state=active]:text-indigo-300 data-[state=inactive]:text-[var(--to-text-dim)]"
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            Per Account
          </TabsTrigger>
        </TabsList>

        <TabsContent value="global" className="mt-4">
          <GlobalGuardsView />
        </TabsContent>

        <TabsContent value="account" className="mt-4">
          <AccountGuardsView />
        </TabsContent>
      </Tabs>
    </div>
  );
}
