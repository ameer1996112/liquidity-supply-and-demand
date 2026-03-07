'use client';

interface CircularGaugeProps {
  value: number;
  limit: number;
  label: string;
  sublabel?: string;
  size?: number;
  colorZones?: { at: number; color: string }[];
  unit?: string;
  strokeWidth?: number;
}

/**
 * Reusable circular SVG gauge.
 * Extracted from PropFirmPage — used on Risk Monitor and Prop Firm pages.
 */
export function CircularGauge({
  value,
  limit,
  label,
  sublabel,
  size = 120,
  colorZones,
  unit = '%',
  strokeWidth = 8,
}: CircularGaugeProps) {
  const radius = 46;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.min(value / (limit || 1), 1);
  const fillLength = pct * circumference;

  // Determine color from zones or default green→amber→red
  let color = '#0ecb81';
  if (colorZones) {
    for (const zone of colorZones) {
      if (value >= zone.at) color = zone.color;
    }
  } else {
    const utilPct = pct * 100;
    if (utilPct > 80) color = '#f6465d';
    else if (utilPct > 50) color = '#f0b90b';
  }

  return (
    <div className='flex flex-col items-center gap-2'>
      <div className='relative' style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox='0 0 100 100'>
          {/* Track */}
          <circle
            cx='50'
            cy='50'
            r={radius}
            fill='none'
            stroke='#1e2329'
            strokeWidth={strokeWidth}
          />
          {/* Fill — starts at top (−90°) */}
          <circle
            cx='50'
            cy='50'
            r={radius}
            fill='none'
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap='round'
            strokeDasharray={`${fillLength} ${circumference - fillLength}`}
            strokeDashoffset={circumference * 0.25}
            style={{
              transition: 'stroke-dasharray 0.6s ease, stroke 0.4s ease',
              filter: `drop-shadow(0 0 4px ${color}60)`,
            }}
          />
        </svg>
        {/* Center text */}
        <div className='absolute inset-0 flex flex-col items-center justify-center'>
          <span
            className='text-xl font-bold tabular-nums'
            style={{ color, fontFamily: 'var(--font-mono)' }}
          >
            {(value ?? 0).toFixed(2)}
            {unit}
          </span>
          <span className='text-[10px] text-[var(--to-text-dim)] mt-0.5'>
            / {limit}
            {unit}
          </span>
        </div>
      </div>
      <div className='text-center'>
        <div className='text-[13px] font-semibold text-[var(--to-text-primary)]'>
          {label}
        </div>
        {sublabel && (
          <div className='text-[11px] text-[var(--to-text-dim)] mt-0.5'>
            {sublabel}
          </div>
        )}
      </div>
    </div>
  );
}
