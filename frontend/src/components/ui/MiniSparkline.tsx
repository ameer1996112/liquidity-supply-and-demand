'use client';

import { useMemo } from 'react';

interface SparklinePoint {
  value: number;
}

interface MiniSparklineProps {
  data: (number | SparklinePoint)[];
  width?: number;
  height?: number;
  /** Color for positive trend */
  positiveColor?: string;
  /** Color for negative trend */
  negativeColor?: string;
  /** Color for neutral/flat */
  neutralColor?: string;
  /** Show area fill under the line */
  fill?: boolean;
  className?: string;
  strokeWidth?: number;
}

function normalize(raw: (number | SparklinePoint)[]): number[] {
  return raw.map((d) => (typeof d === 'number' ? d : d.value));
}

/**
 * Lightweight inline sparkline chart using SVG.
 * No external chart library dependency — pure SVG path.
 * Auto-colors based on first vs last value (positive = green, negative = red).
 */
export function MiniSparkline({
  data,
  width = 80,
  height = 28,
  positiveColor = 'var(--to-long)',
  negativeColor = 'var(--to-short)',
  neutralColor = 'var(--to-text-dim)',
  fill = true,
  className,
  strokeWidth = 1.5,
}: MiniSparklineProps) {
  const values = useMemo(() => normalize(data), [data]);

  const path = useMemo(() => {
    if (values.length < 2) return { line: '', area: '' };

    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;

    const pad = strokeWidth + 1;
    const innerH = height - pad * 2;
    const innerW = width - pad * 2;

    const points = values.map((v, i) => {
      const x = pad + (i / (values.length - 1)) * innerW;
      const y = pad + innerH - ((v - min) / range) * innerH;
      return [x, y] as [number, number];
    });

    const line = points
      .map(
        ([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`
      )
      .join(' ');

    const area =
      `${line} L${points[points.length - 1][0].toFixed(2)},${(
        height - pad
      ).toFixed(2)}` +
      ` L${points[0][0].toFixed(2)},${(height - pad).toFixed(2)} Z`;

    return { line, area };
  }, [values, width, height, strokeWidth]);

  const trend = useMemo(() => {
    if (values.length < 2) return 'neutral';
    const delta = values[values.length - 1] - values[0];
    if (delta > 0) return 'positive';
    if (delta < 0) return 'negative';
    return 'neutral';
  }, [values]);

  const color =
    trend === 'positive'
      ? positiveColor
      : trend === 'negative'
      ? negativeColor
      : neutralColor;

  if (values.length < 2) {
    return (
      <svg
        width={width}
        height={height}
        className={className}
        aria-hidden='true'
      >
        <line
          x1={0}
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke={neutralColor}
          strokeWidth={strokeWidth}
          strokeDasharray='3 3'
          opacity={0.4}
        />
      </svg>
    );
  }

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      aria-hidden='true'
      style={{ overflow: 'visible' }}
    >
      {fill && <path d={path.area} fill={color} opacity={0.12} />}
      <path
        d={path.line}
        fill='none'
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap='round'
        strokeLinejoin='round'
      />
      {/* End dot */}
      {values.length > 0 &&
        (() => {
          const last = values[values.length - 1];
          const min = Math.min(...values);
          const max = Math.max(...values);
          const range = max - min || 1;
          const pad = strokeWidth + 1;
          const innerH = height - pad * 2;
          const innerW = width - pad * 2;
          const x = pad + innerW;
          const y = pad + innerH - ((last - min) / range) * innerH;
          return (
            <circle
              cx={x.toFixed(2)}
              cy={y.toFixed(2)}
              r={2.5}
              fill={color}
              opacity={0.9}
            />
          );
        })()}
    </svg>
  );
}
