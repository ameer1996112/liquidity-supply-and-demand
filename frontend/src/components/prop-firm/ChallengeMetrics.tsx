'use client';

import { CircularGauge } from '@/components/ui/CircularGauge';

interface ChallengeMetricsProps {
  dailyPct: number;
  dailyLimitPct: number;
  trailingPct: number;
  trailingLimitPct: number;
  consistencyPct: number;
  consistencyLimitPct?: number;
}

function ZoneLabel({
  value,
  limit,
  thresholds = { safe: 0.6, caution: 0.8 },
}: {
  value: number;
  limit: number;
  thresholds?: { safe: number; caution: number };
}) {
  if (limit <= 0) return null;
  if (value < limit * thresholds.safe) {
    return <span className='text-[#0ecb81]'>Safe Zone</span>;
  } else if (value < limit * thresholds.caution) {
    return <span className='text-[#f0b90b]'>Caution Zone</span>;
  } else {
    return <span className='text-[#f6465d]'>Danger Zone</span>;
  }
}

export function ChallengeMetrics({
  dailyPct,
  dailyLimitPct,
  trailingPct,
  trailingLimitPct,
  consistencyPct,
  consistencyLimitPct = 0,
}: ChallengeMetricsProps) {
  const hasDailyRule = dailyLimitPct > 0;
  const hasTrailingRule = trailingLimitPct > 0;
  const hasConsistencyRule = consistencyLimitPct > 0;

  const gauges = [
    hasDailyRule && {
      key: 'daily',
      value: dailyPct,
      limit: dailyLimitPct,
      label: 'Daily Drawdown',
      thresholds: { safe: 0.6, caution: 0.8 },
    },
    hasTrailingRule && {
      key: 'trailing',
      value: trailingPct,
      limit: trailingLimitPct,
      label: 'Max Drawdown',
      thresholds: { safe: 0.6, caution: 0.8 },
    },
    hasConsistencyRule && {
      key: 'consistency',
      value: consistencyPct,
      limit: consistencyLimitPct = 0,
      label: 'Consistency Rule',
      thresholds: { safe: 0.75, caution: 0.9 },
    },
  ].filter(Boolean) as Array<{
    key: string;
    value: number;
    limit: number;
    label: string;
    thresholds: { safe: number; caution: number };
  }>;

  if (gauges.length === 0) return null;

  const colClass =
    gauges.length === 1
      ? 'grid-cols-1 max-w-xs mx-auto'
      : gauges.length === 2
      ? 'grid-cols-1 md:grid-cols-2'
      : 'grid-cols-1 md:grid-cols-3';

  return (
    <div className='glow-card p-6'>
      <h3 className='text-[13px] font-bold text-[var(--to-text-dim)] uppercase tracking-widest font-mono mb-4'>
        Challenge Metrics
      </h3>

      <div className={`grid ${colClass} gap-6`}>
        {gauges.map((g) => (
          <div key={g.key} className='flex flex-col items-center'>
            <CircularGauge
              value={g.value}
              limit={g.limit}
              label={g.label}
              sublabel={`Limit: ${g.limit}%`}
              size={150}
              colorZones={[
                { at: 0, color: '#0ecb81' },
                { at: g.limit * g.thresholds.safe, color: '#f0b90b' },
                { at: g.limit * g.thresholds.caution, color: '#f6465d' },
              ]}
            />
            <div className='mt-2 text-[12px]'>
              <ZoneLabel
                value={g.value}
                limit={g.limit}
                thresholds={g.thresholds}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
