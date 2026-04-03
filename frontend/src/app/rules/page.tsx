'use client';

import { RiskRulesPanel } from '@/components/rules/RiskRulesPanel';
import { StrategyRulesPanel } from '@/components/rules/StrategyRulesPanel';
import { GuardsPanel } from '@/components/rules/GuardsPanel';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Shield, ShieldCheck, BookOpen } from 'lucide-react';

export default function RulesPage() {
  return (
    <div className='space-y-5'>
      {/* Page header */}
      <div className='flex items-center gap-3'>
        <div className='flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/10 border border-indigo-500/20'>
          <Shield className='h-4 w-4 text-indigo-400' />
        </div>
        <div>
          <h1 className='page-title text-lg font-semibold'>Rules & Guards</h1>
          <p className='page-subtitle mt-0.5 text-[11px]'>
            Trade protection, risk guardrails, and strategy execution rules
          </p>
        </div>
      </div>

      <Tabs defaultValue='guards'>
        <TabsList className='surface-soft rounded-lg border border-[var(--to-border)] p-0.5'>
          <TabsTrigger
            value='guards'
            className='flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[11px] font-medium data-[state=active]:bg-indigo-600/20 data-[state=active]:text-indigo-300 data-[state=inactive]:text-[var(--to-text-dim)]'
            style={{ fontFamily: 'var(--font-sans)' }}
          >
            <Shield className='h-3.5 w-3.5' />
            Guards
          </TabsTrigger>
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

        <TabsContent value='guards' className='mt-4'>
          <GuardsPanel />
        </TabsContent>

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
