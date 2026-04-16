'use client';

import { SetupEvidence } from '@/types/trading';
import { cn } from '@/lib/utils';

interface SetupEvidenceModalProps {
  evidence?: SetupEvidence | null;
  open: boolean;
  onClose: () => void;
}

function formatZoneSummary(evidence?: SetupEvidence | null): string {
  const zone = evidence?.focus_zone;
  if (!zone) return 'No focus zone detected';
  if (zone.high != null && zone.low != null) {
    return `${zone.label || 'Zone'} ${zone.low.toFixed(4)} - ${zone.high.toFixed(4)}`;
  }
  if (zone.price != null) {
    return `${zone.label || 'Zone'} @ ${zone.price.toFixed(4)}`;
  }
  return zone.label || 'No focus zone detected';
}

export function SetupEvidenceModal({
  evidence,
  open,
  onClose,
}: SetupEvidenceModalProps) {
  if (!open || !evidence?.focus_image?.url) {
    return null;
  }

  const status = evidence.status || 'ok';
  const statusClass =
    status === 'ok'
      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
      : 'border-amber-500/30 bg-amber-500/10 text-amber-300';

  return (
    <div
      role='dialog'
      aria-modal='true'
      aria-label='Setup Evidence'
      className='fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6'
    >
      <div className='w-full max-w-5xl rounded-2xl border border-[var(--to-border)] bg-[#0B1220] p-5 shadow-2xl'>
        <div className='mb-4 flex items-start justify-between gap-4'>
          <div className='space-y-2'>
            <p className='text-[10px] uppercase tracking-[0.3em] text-[var(--to-text-dim)]'>
              Setup Evidence
            </p>
            <h3 className='text-sm font-semibold text-[var(--to-text-primary)]'>
              {formatZoneSummary(evidence)}
            </h3>
            <span
              className={cn(
                'inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide',
                statusClass,
              )}
            >
              {status}
            </span>
          </div>
          <button
            type='button'
            onClick={onClose}
            className='rounded-md border border-[var(--to-border)] px-2 py-1 text-[11px] text-[var(--to-text-secondary)] transition hover:text-[var(--to-text-primary)]'
          >
            Close
          </button>
        </div>

        <img
          src={evidence.focus_image.url}
          alt='Focused setup evidence'
          className='max-h-[75vh] w-full rounded-xl border border-[var(--to-border)] object-contain'
        />
      </div>
    </div>
  );
}
