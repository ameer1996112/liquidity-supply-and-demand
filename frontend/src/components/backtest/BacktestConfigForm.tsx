'use client';

import { useState } from 'react';
import { useStartBacktest } from '@/hooks/useBacktest';
import { Play, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

function FormField({
  label,
  value,
  onChange,
  type = 'text',
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <div className="space-y-1">
      <label className="text-[10px] uppercase tracking-wider text-zinc-500 font-mono">
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-[#131722] border border-[#2a2e39] rounded px-2.5 py-1.5 text-xs font-mono text-zinc-300 focus:outline-none focus:border-[#26a69a] transition-colors"
      />
    </div>
  );
}

export function BacktestConfigForm() {
  const startBacktest = useStartBacktest();
  const [name, setName] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [riskPercent, setRiskPercent] = useState('1.0');
  const [minScore, setMinScore] = useState('60');
  const [mlConfidence, setMlConfidence] = useState('0.60');

  const handleSubmit = () => {
    startBacktest.mutate({
      name: name || `Backtest ${new Date().toLocaleDateString()}`,
      config_overrides: {
        risk_percent: parseFloat(riskPercent) || 1.0,
        pine_min_score: parseFloat(minScore) || 60,
        ml_min_confidence: parseFloat(mlConfidence) || 0.6,
      },
      signal_source: 'date_range',
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    });

    // Reset form
    setName('');
  };

  return (
    <div className="tv-card">
      <div className="px-4 py-3 border-b border-[#2a2e39]">
        <span className="font-mono text-xs text-zinc-400 uppercase tracking-wider">
          New Backtest
        </span>
      </div>
      <div className="p-4 space-y-3">
        <FormField label="Name" value={name} onChange={setName} placeholder="e.g. High Score Test" />

        <div className="grid grid-cols-2 gap-3">
          <FormField label="Date From" value={dateFrom} onChange={setDateFrom} type="date" />
          <FormField label="Date To" value={dateTo} onChange={setDateTo} type="date" />
        </div>

        <div className="pt-2 border-t border-[#2a2e39]">
          <span className="text-[9px] uppercase tracking-wider text-zinc-600 font-mono">
            Config Overrides
          </span>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <FormField label="Risk %" value={riskPercent} onChange={setRiskPercent} type="number" />
          <FormField label="Min Score" value={minScore} onChange={setMinScore} type="number" />
          <FormField label="ML Conf" value={mlConfidence} onChange={setMlConfidence} type="number" />
        </div>

        <button
          onClick={handleSubmit}
          disabled={startBacktest.isPending}
          className={cn(
            'w-full flex items-center justify-center gap-2 py-2 rounded-md',
            'font-mono text-xs font-semibold uppercase tracking-wider transition-colors',
            startBacktest.isPending
              ? 'bg-[#2a2e39] text-zinc-500 cursor-not-allowed'
              : 'bg-[#26a69a] text-white hover:bg-[#26a69a]/90',
          )}
        >
          {startBacktest.isPending ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Play className="w-3.5 h-3.5" />
          )}
          {startBacktest.isPending ? 'Starting...' : 'Run Backtest'}
        </button>
      </div>
    </div>
  );
}
