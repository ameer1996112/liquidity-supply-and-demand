'use client';

import { SetupEvidence } from '@/types/trading';

interface SetupEvidenceDetailProps {
  evidence?: SetupEvidence | null;
}

function formatZoneSummary(evidence?: SetupEvidence | null): string {
  const zone = evidence?.focus_zone;
  if (!zone) return 'No focus zone';
  if (zone.high != null && zone.low != null) {
    return `${zone.label || 'Zone'} ${zone.low.toFixed(4)} - ${zone.high.toFixed(4)}`;
  }
  if (zone.price != null) {
    return `${zone.label || 'Zone'} @ ${zone.price.toFixed(4)}`;
  }
  return zone.label || 'No focus zone';
}

export function SetupEvidenceDetail({ evidence }: SetupEvidenceDetailProps) {
  if (!evidence) {
    return (
      <div className='text-[11px] text-[var(--to-text-dim)]'>
        Setup evidence unavailable
      </div>
    );
  }

  const snapshot = evidence.pine_snapshot;
  const topLabels = snapshot?.top_labels || [];

  return (
    <div className='space-y-3'>
      {evidence.focus_image?.url ? (
        <img
          src={evidence.focus_image.url}
          alt='Setup evidence'
          className='w-full max-w-md rounded-lg border border-[var(--to-border)]'
        />
      ) : (
        <div className='text-[11px] text-[var(--to-text-dim)]'>
          {evidence.reason || 'Setup image unavailable'}
        </div>
      )}

      <div className='grid gap-2 text-[11px]'>
        <div>
          <span className='text-[var(--to-text-dim)]'>Zone</span>
          <span className='ml-2 font-mono text-[var(--to-text-secondary)]'>
            {formatZoneSummary(evidence)}
          </span>
        </div>
        <div>
          <span className='text-[var(--to-text-dim)]'>Snapshot</span>
          <span className='ml-2 font-mono text-[var(--to-text-secondary)]'>
            {topLabels.join(' • ') || 'No Pine labels captured'}
          </span>
        </div>
        <div>
          <span className='text-[var(--to-text-dim)]'>Counts</span>
          <span className='ml-2 font-mono text-[var(--to-text-secondary)]'>
            {`${snapshot?.zone_count ?? 0} zones / ${snapshot?.label_count ?? 0} labels`}
          </span>
        </div>
      </div>
    </div>
  );
}
