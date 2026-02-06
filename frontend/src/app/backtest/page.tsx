'use client';

import { useState } from 'react';
import { useBacktestRuns } from '@/hooks/useBacktest';
import { BacktestConfigForm } from '@/components/backtest/BacktestConfigForm';
import { BacktestRunsList } from '@/components/backtest/BacktestRunsList';
import { BacktestResults } from '@/components/backtest/BacktestResults';
import { FlaskConical } from 'lucide-react';

export default function BacktestPage() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const { data: runsData } = useBacktestRuns();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-2">
        <FlaskConical className="w-5 h-5 text-zinc-400" />
        <h1 className="text-lg font-semibold text-zinc-100">
          Backtesting Sandbox
        </h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Config + Run History */}
        <div className="space-y-4">
          <BacktestConfigForm />
          <BacktestRunsList
            runs={runsData?.runs || []}
            selectedRunId={selectedRunId}
            onSelect={setSelectedRunId}
          />
        </div>

        {/* Right: Results */}
        <div className="lg:col-span-2">
          <BacktestResults runId={selectedRunId} />
        </div>
      </div>
    </div>
  );
}
