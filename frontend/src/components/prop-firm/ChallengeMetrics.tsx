'use client';

import { CircularGauge } from '@/components/ui/CircularGauge';

interface ChallengeMetricsProps {
  dailyPct: number;
  dailyLimitPct: number;
  trailingPct: number;
  trailingLimitPct: number;
  consistencyPct: number;
  consistencyLimitPct: number;
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
  consistencyLimitPct,
}: ChallengeMetricsProps) {
  return (
    <div className='tv-card p-6'>
      <h3 className='text-[13px] font-bold text-zinc-400 uppercase tracking-widest font-mono mb-4'>
        Challenge Metrics
      </h3>

      <div className='grid grid-cols-1 md:grid-cols-3 gap-6'>
        <div className='flex flex-col items-center'>
          <CircularGauge
            value={dailyPct}
            limit={dailyLimitPct}
            label='Daily Drawdown'
            sublabel={`Limit: ${dailyLimitPct}%`}
            size={150}
            colorZones={[
              { at: 0, color: '#0ecb81' },
              { at: dailyLimitPct * 0.6, color: '#f0b90b' },
              { at: dailyLimitPct * 0.8, color: '#f6465d' },
            ]}
          />
          <div className='mt-2 text-[12px]'>
            <ZoneLabel value={dailyPct} limit={dailyLimitPct} />
          </div>
        </div>

        <div className='flex flex-col items-center'>
          <CircularGauge
            value={trailingPct}
            limit={trailingLimitPct}
            label='Max Drawdown'
            sublabel={`Limit: ${trailingLimitPct}%`}
            size={150}
            colorZones={[
              { at: 0, color: '#0ecb81' },
              { at: trailingLimitPct * 0.6, color: '#f0b90b' },
              { at: trailingLimitPct * 0.8, color: '#f6465d' },
            ]}
          />
          <div className='mt-2 text-[12px]'>
            <ZoneLabel value={trailingPct} limit={trailingLimitPct} />
          </div>
        </div>

        <div className='flex flex-col items-center'>
          <CircularGauge
            value={consistencyPct}
            limit={consistencyLimitPct}
            label='Consistency Rule'
            sublabel={`Limit: ${consistencyLimitPct}%`}
            size={150}
            colorZones={[
              { at: 0, color: '#0ecb81' },
              { at: consistencyLimitPct * 0.75, color: '#f0b90b' },
              { at: consistencyLimitPct * 0.9, color: '#f6465d' },
            ]}
          />
          <div className='mt-2 text-[12px]'>
            <ZoneLabel
              value={consistencyPct}
              limit={consistencyLimitPct}
              thresholds={{ safe: 0.75, caution: 0.9 }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
