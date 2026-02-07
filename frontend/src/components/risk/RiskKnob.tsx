'use client';

import { useCallback } from 'react';
import { cn } from '@/lib/utils';

const MIN = 0.1;
const MAX = 5;
const STEP = 0.1;

export interface RiskKnobProps {
  /** Current risk per trade (percent), e.g. 1.0 */
  value: number;
  /** Called when user changes value (debounced or on commit) */
  onChange: (value: number) => void;
  disabled?: boolean;
  isUpdating?: boolean;
  className?: string;
}

/** Circular dial + slider for RISK_PER_TRADE (0.1% - 5%). */
export function RiskKnob({
  value,
  onChange,
  disabled = false,
  isUpdating = false,
  className,
}: RiskKnobProps) {
  const clamped = Math.max(MIN, Math.min(MAX, value));
  const percent = ((clamped - MIN) / (MAX - MIN)) * 100; // 0..100 for fill

  const handleSliderChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const v = parseFloat(e.target.value);
      if (!Number.isNaN(v)) onChange(v);
    },
    [onChange]
  );

  return (
    <div className={cn('flex flex-col items-center gap-4', className)}>
      {/* Circular gauge */}
      <div className="relative w-32 h-32">
        <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
          <circle
            cx="50"
            cy="50"
            r="42"
            fill="none"
            stroke="currentColor"
            strokeWidth="8"
            className="text-[#2a2e39]"
          />
          <circle
            cx="50"
            cy="50"
            r="42"
            fill="none"
            stroke="currentColor"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={`${percent * 2.64} 264`}
            className="text-emerald-500 transition-[stroke-dasharray] duration-200"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="font-mono text-xl font-bold text-zinc-100 tabular-nums">
            {clamped.toFixed(1)}%
          </span>
        </div>
      </div>
      <div className="w-full max-w-[200px] space-y-1">
        <input
          type="range"
          min={MIN}
          max={MAX}
          step={STEP}
          value={clamped}
          onChange={handleSliderChange}
          disabled={disabled || isUpdating}
          className={cn(
            'w-full h-2 rounded-full appearance-none cursor-pointer',
            'bg-[#2a2e39] [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4',
            '[&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-emerald-500 [&::-webkit-slider-thumb]:cursor-pointer',
            '[&::-webkit-slider-thumb]:border-0 [&::-webkit-slider-thumb]:shadow-md',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        />
        <div className="flex justify-between text-[10px] font-mono text-zinc-500">
          <span>{MIN}%</span>
          <span>Risk per trade</span>
          <span>{MAX}%</span>
        </div>
      </div>
      {isUpdating && (
        <p className="text-[10px] font-mono text-amber-500">Updating…</p>
      )}
    </div>
  );
}
