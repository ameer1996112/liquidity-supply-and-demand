'use client';

import { cn } from '@/lib/utils';

interface HeatmapCell {
  value: number;
  label?: string;
}

interface HeatmapChartProps {
  title: string;
  rows: string[];
  columns: string[];
  data: number[][];
  valueLabel?: string;
}

function interpolateColor(value: number, min: number, max: number): string {
  if (max === min) return 'bg-[#2a2e39]';
  const ratio = (value - min) / (max - min);

  if (value === 0) return 'bg-[#2a2e39]';
  if (value > 0) {
    const intensity = Math.min(ratio / (max > 0 ? 1 : 0.5), 1);
    if (intensity > 0.7) return 'bg-[#26a69a]/60';
    if (intensity > 0.4) return 'bg-[#26a69a]/35';
    return 'bg-[#26a69a]/15';
  }
  const intensity = Math.min(Math.abs(ratio), 1);
  if (intensity > 0.7) return 'bg-[#ef5350]/60';
  if (intensity > 0.4) return 'bg-[#ef5350]/35';
  return 'bg-[#ef5350]/15';
}

export function HeatmapChart({
  title,
  rows,
  columns,
  data,
  valueLabel = 'PnL',
}: HeatmapChartProps) {
  const allValues = data.flat();
  const min = Math.min(...allValues, 0);
  const max = Math.max(...allValues, 0);

  return (
    <div className="glow-card p-4">
      <span className="font-mono text-xs text-[var(--to-text-dim)] uppercase tracking-wider">
        {title}
      </span>

      <div className="mt-3 overflow-x-auto">
        <div
          className="grid gap-0.5"
          style={{
            gridTemplateColumns: `80px repeat(${columns.length}, minmax(50px, 1fr))`,
          }}
        >
          {/* Header row */}
          <div />
          {columns.map((col) => (
            <div
              key={col}
              className="text-[9px] text-[var(--to-text-dim)] font-mono uppercase tracking-wider text-center py-1"
            >
              {col}
            </div>
          ))}

          {/* Data rows */}
          {rows.map((row, ri) => (
            <>
              <div
                key={`label-${row}`}
                className="text-[10px] text-[var(--to-text-dim)] font-mono uppercase tracking-wider flex items-center"
              >
                {row}
              </div>
              {columns.map((col, ci) => {
                const val = data[ri]?.[ci] ?? 0;
                return (
                  <div
                    key={`${row}-${col}`}
                    className={cn(
                      'rounded-sm flex items-center justify-center py-2',
                      interpolateColor(val, min, max),
                    )}
                    title={`${row} / ${col}: $${val.toFixed(2)}`}
                  >
                    <span
                      className={cn(
                        'font-mono text-[10px] tabular-nums',
                        val > 0 && 'text-[#26a69a]',
                        val < 0 && 'text-[#ef5350]',
                        val === 0 && 'text-[var(--to-text-dim)]',
                      )}
                    >
                      {val !== 0 ? `$${val.toFixed(0)}` : '—'}
                    </span>
                  </div>
                );
              })}
            </>
          ))}
        </div>
      </div>
    </div>
  );
}
