'use client';

import { useState } from 'react';
import { SetupEvidence } from '@/types/trading';
import { cn } from '@/lib/utils';
import { Expand } from 'lucide-react';
import { SetupEvidenceModal } from './SetupEvidenceModal';

interface SetupEvidenceDetailProps {
  evidence?: SetupEvidence | null;
}

function getEvidenceStatus(evidence?: SetupEvidence | null): 'ok' | 'degraded' | 'missing' {
  return evidence?.status || (evidence?.focus_image?.url ? 'ok' : 'missing');
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
  const [modalOpen, setModalOpen] = useState(false);

  if (!evidence) {
    return (
      <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/30 p-3 text-[11px] text-[var(--to-text-dim)]'>
        Setup evidence unavailable
      </div>
    );
  }

  const snapshot = evidence.pine_snapshot;
  const topLabels = snapshot?.top_labels || [];
  const status = getEvidenceStatus(evidence);
  const statusClass =
    status === 'ok'
      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
      : status === 'degraded'
        ? 'border-amber-500/30 bg-amber-500/10 text-amber-300'
        : 'border-[var(--to-border)] bg-[var(--to-surface-raised)] text-[var(--to-text-dim)]';

  return (
    <div className='space-y-3 rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/20 p-3'>
      <div className='flex flex-wrap items-center gap-2'>
        <span
          className={cn(
            'inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide',
            statusClass,
          )}
        >
          {status}
        </span>
        <span className='text-[11px] font-mono text-[var(--to-text-secondary)]'>
          {formatZoneSummary(evidence)}
        </span>
      </div>

      {evidence.focus_image?.url ? (
        <>
          <button
            type='button'
            aria-label='Open setup evidence'
            className='group relative block overflow-hidden rounded-lg border border-[var(--to-border)]'
            onClick={() => setModalOpen(true)}
          >
            <img
              src={evidence.focus_image.url}
              alt='Setup evidence preview'
              className='w-full max-w-md rounded-lg object-cover transition duration-200 group-hover:scale-[1.01]'
            />
            <span className='pointer-events-none absolute right-2 top-2 inline-flex items-center gap-1 rounded-full bg-black/70 px-2 py-1 text-[10px] font-medium text-white'>
              <Expand className='h-3 w-3' />
              View
            </span>
          </button>
          <SetupEvidenceModal
            evidence={evidence}
            open={modalOpen}
            onClose={() => setModalOpen(false)}
          />
        </>
      ) : (
        <div className='text-[11px] text-[var(--to-text-dim)]'>
          {evidence.reason || 'Setup image unavailable'}
        </div>
      )}

      <div className='grid gap-2 text-[11px]'>
        <div>
          <span className='text-[var(--to-text-dim)]'>Focus Zone</span>
          <span className='ml-2 font-mono text-[var(--to-text-secondary)]'>
            {formatZoneSummary(evidence)}
          </span>
        </div>
        <div>
          <span className='text-[var(--to-text-dim)]'>Pine Snapshot</span>
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
        {evidence.reason ? (
          <div>
            <span className='text-[var(--to-text-dim)]'>Reason</span>
            <span className='ml-2 font-mono text-[var(--to-text-secondary)]'>
              {evidence.reason}
            </span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
