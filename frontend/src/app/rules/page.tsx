'use client';

import { RiskRulesPanel } from '@/components/rules/RiskRulesPanel';
import { StrategyRulesPanel } from '@/components/rules/StrategyRulesPanel';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ShieldCheck, BookOpen } from 'lucide-react';

export default function RulesPage() {
  return (
    <div className='space-y-4'>
      <div>
        <h1 className='page-title text-lg font-semibold'>Rules</h1>
        <p className='page-subtitle mt-0.5 text-xs'>
          Risk guardrails and strategy execution rules.
        </p>
      </div>

      <Tabs defaultValue='risk'>
        <TabsList className='surface-soft rounded-lg border border-[var(--to-border)] p-0.5'>
          <TabsTrigger
            value='risk'
            className='flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[11px] font-medium data-[state=active]:bg-indigo-600/20 data-[state=active]:text-indigo-300 data-[state=inactive]:text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            <ShieldCheck className='h-3.5 w-3.5' />
            Risk Rules
          </TabsTrigger>
          <TabsTrigger
            value='strategy'
            className='flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[11px] font-medium data-[state=active]:bg-indigo-600/20 data-[state=active]:text-indigo-300 data-[state=inactive]:text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            <BookOpen className='h-3.5 w-3.5' />
            Strategy Rules
          </TabsTrigger>
        </TabsList>

        <TabsContent value='risk' className='mt-4'>
          <RiskRulesPanel />
        </TabsContent>

        <TabsContent value='strategy' className='mt-4'>
          <StrategyRulesPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
