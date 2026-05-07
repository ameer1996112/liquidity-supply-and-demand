'use client';

import { useEffect } from 'react';
import { SetupEvidence } from '@/types/trading';
import { cn } from '@/lib/utils';
import { Expand, Maximize2, X } from 'lucide-react';

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
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  if (!open || !evidence?.focus_image?.url) {
    return null;
  }

  const status = evidence.status || 'ok';
  const zone = evidence.focus_zone;
  const statusClass =
    status === 'ok'
      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
      : 'border-amber-500/30 bg-amber-500/10 text-amber-300';
  const imageUrl = evidence.focus_image.url;

  return (
    <div
      role='dialog'
      aria-modal='true'
      aria-label='Setup Evidence'
      className='fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-3 backdrop-blur-md sm:p-6'
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className='relative grid max-h-[94vh] w-full max-w-7xl overflow-hidden rounded-xl border border-emerald-400/20 bg-[#070b10] shadow-[0_24px_90px_rgba(0,0,0,0.72)] lg:grid-cols-[300px_minmax(0,1fr)]'>
        <div className='pointer-events-none absolute inset-0 bg-[linear-gradient(135deg,rgba(16,185,129,0.12),transparent_28%,rgba(59,130,246,0.08)_68%,transparent)]' />

        <aside className='relative border-b border-white/10 bg-[#0b1118]/95 p-4 lg:border-b-0 lg:border-r'>
          <div className='flex items-start justify-between gap-3'>
            <div>
              <p className='font-mono text-[10px] uppercase tracking-[0.32em] text-emerald-300/80'>
                Setup Evidence
              </p>
              <h3 className='mt-2 text-base font-semibold leading-tight text-white'>
                {formatZoneSummary(evidence)}
              </h3>
            </div>
            <button
              type='button'
              onClick={onClose}
              aria-label='Close setup evidence'
              className='inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-white/15 bg-white/8 text-white shadow-lg transition hover:border-emerald-300/50 hover:bg-emerald-400/15 focus:outline-none focus:ring-2 focus:ring-emerald-300'
            >
              <X className='h-4 w-4' />
            </button>
          </div>

          <div className='mt-5 flex flex-wrap gap-2'>
            <span
              className={cn(
                'inline-flex items-center rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-wide',
                statusClass,
              )}
            >
              {status}
            </span>
            {zone?.source ? (
              <span className='inline-flex items-center rounded-full border border-white/10 bg-white/5 px-2.5 py-1 font-mono text-[10px] uppercase tracking-wide text-slate-300'>
                {zone.source}
              </span>
            ) : null}
          </div>

          <dl className='mt-6 grid gap-3 text-[11px]'>
            <div className='rounded-lg border border-white/10 bg-white/[0.03] p-3'>
              <dt className='font-mono uppercase tracking-widest text-slate-500'>Zone</dt>
              <dd className='mt-1 font-mono text-slate-200'>{formatZoneSummary(evidence)}</dd>
            </div>
            {zone?.id != null ? (
              <div className='rounded-lg border border-white/10 bg-white/[0.03] p-3'>
                <dt className='font-mono uppercase tracking-widest text-slate-500'>Zone ID</dt>
                <dd className='mt-1 font-mono text-emerald-300'>{zone.id}</dd>
              </div>
            ) : null}
            {zone?.high != null && zone?.low != null ? (
              <div className='grid grid-cols-2 gap-2'>
                <div className='rounded-lg border border-white/10 bg-white/[0.03] p-3'>
                  <dt className='font-mono uppercase tracking-widest text-slate-500'>Low</dt>
                  <dd className='mt-1 font-mono text-slate-200'>{zone.low.toFixed(5)}</dd>
                </div>
                <div className='rounded-lg border border-white/10 bg-white/[0.03] p-3'>
                  <dt className='font-mono uppercase tracking-widest text-slate-500'>High</dt>
                  <dd className='mt-1 font-mono text-slate-200'>{zone.high.toFixed(5)}</dd>
                </div>
              </div>
            ) : null}
          </dl>

          <p className='mt-6 font-mono text-[10px] leading-relaxed text-slate-500'>
            Press ESC or click outside the viewer to close.
          </p>
        </aside>

        <section className='relative flex min-h-0 items-center justify-center bg-[#05080d] p-4 sm:p-6'>
          <div className='absolute left-4 top-4 z-10 inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/55 px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-slate-300 backdrop-blur'>
            <Maximize2 className='h-3 w-3 text-emerald-300' />
            Chart Capture
          </div>
          <a
            href={imageUrl}
            target='_blank'
            rel='noreferrer'
            className='absolute right-4 top-4 z-10 inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/55 px-3 py-1.5 font-mono text-[10px] uppercase tracking-wide text-slate-300 backdrop-blur transition hover:border-emerald-300/50 hover:text-white'
          >
            <Expand className='h-3 w-3 text-emerald-300' />
            Open
          </a>
          <div className='relative max-h-[84vh] w-full overflow-hidden rounded-lg border border-white/10 bg-[#c8ccd5] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06),0_20px_70px_rgba(0,0,0,0.55)]'>
            <img
              src={imageUrl}
              alt='Focused setup evidence'
              className='max-h-[84vh] w-full object-contain'
            />
          </div>
        </section>
      </div>
    </div>
  );
}
