'use client';

import { RiskRulesPanel } from '@/components/rules/RiskRulesPanel';
import { StrategyRulesPanel } from '@/components/rules/StrategyRulesPanel';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { ShieldCheck, BookOpen } from 'lucide-react';

export default function RulesPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold text-zinc-100">Rules</h1>

      <Tabs defaultValue="risk">
        <TabsList>
          <TabsTrigger value="risk" className="gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5" />
            Risk Rules
          </TabsTrigger>
          <TabsTrigger value="strategy" className="gap-1.5">
            <BookOpen className="w-3.5 h-3.5" />
            Strategy Rules
          </TabsTrigger>
        </TabsList>

        <TabsContent value="risk" className="mt-4">
          <RiskRulesPanel />
        </TabsContent>

        <TabsContent value="strategy" className="mt-4">
          <StrategyRulesPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
