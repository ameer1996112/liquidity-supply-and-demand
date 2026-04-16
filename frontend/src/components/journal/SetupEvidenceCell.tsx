'use client';

import { Image as ImageIcon } from 'lucide-react';
import { SetupEvidence } from '@/types/trading';

interface SetupEvidenceCellProps {
  evidence?: SetupEvidence | null;
}

export function SetupEvidenceCell({ evidence }: SetupEvidenceCellProps) {
  if (!evidence || !evidence.focus_image?.url) {
    return <span className='text-[var(--to-text-dim)] text-[11px]'>--</span>;
  }

  return (
    <button
      type='button'
      data-testid='setup-evidence-icon'
      className='inline-flex items-center justify-center rounded-md border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-1.5 py-1 text-[var(--to-text-secondary)]'
      aria-label='Setup evidence available'
      tabIndex={-1}
    >
      <ImageIcon className='h-3 w-3' />
    </button>
  );
}
