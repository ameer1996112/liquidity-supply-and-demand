'use client';

import { Image as ImageIcon } from 'lucide-react';
import { SetupEvidence } from '@/types/trading';
import { cn } from '@/lib/utils';

interface SetupEvidenceCellProps {
  evidence?: SetupEvidence | null;
}

const STATE_STYLES: Record<string, { label: string; className: string }> = {
  ok: {
    label: 'Setup evidence ok',
    className:
      'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
  },
  degraded: {
    label: 'Setup evidence degraded',
    className:
      'border-amber-500/30 bg-amber-500/10 text-amber-400',
  },
  missing: {
    label: 'Setup evidence missing',
    className:
      'border-[var(--to-border)] bg-[var(--to-surface-raised)] text-[var(--to-text-dim)]',
  },
};

export function SetupEvidenceCell({ evidence }: SetupEvidenceCellProps) {
  const status =
    evidence?.status || (evidence?.focus_image?.url ? 'ok' : 'missing');
  const style = STATE_STYLES[status] || STATE_STYLES.missing;

  return (
    <span
      data-testid='setup-evidence-icon'
      className={cn(
        'inline-flex items-center justify-center rounded-md border px-1.5 py-1 transition-colors',
        style.className,
      )}
      aria-label={style.label}
      title={style.label}
    >
      <ImageIcon className='h-3 w-3' />
    </span>
  );
}
