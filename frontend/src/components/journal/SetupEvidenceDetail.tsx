'use client';

import { useState } from 'react';
import { SetupEvidence } from '@/types/trading';
import { cn } from '@/lib/utils';
import { Expand } from 'lucide-react';
import { SetupEvidenceModal } from './SetupEvidenceModal';

interface SetupEvidenceDetailProps {
  evidence?: SetupEvidence | null;
  fallback?: SetupEvidenceFallback | null;
}

export interface SetupEvidenceFallback {
  symbol: string;
  zoneType?: string | null;
  zoneGrade?: string | null;
  entryModel?: string | null;
  session?: number | null;
  entry?: number | null;
  stopLoss?: number | null;
  takeProfit?: number | null;
  slPips?: number | null;
  score?: number | null;
  rrRatio?: number | null;
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

const SESSION_LABELS: Record<number, string> = {
  0: 'Asia',
  1: 'London',
  2: 'New York',
  3: 'Off session',
};

function hasFallbackSetup(fallback?: SetupEvidenceFallback | null): boolean {
  return Boolean(
    fallback?.zoneType ||
      fallback?.zoneGrade ||
      fallback?.entryModel ||
      fallback?.entry != null ||
      fallback?.stopLoss != null ||
      fallback?.takeProfit != null ||
      fallback?.score != null,
  );
}

function formatPrice(value?: number | null): string {
  if (value == null) return '--';
  return value.toFixed(Math.abs(value) >= 100 ? 2 : 5);
}

export function SetupEvidenceDetail({ evidence, fallback }: SetupEvidenceDetailProps) {
  const [modalOpen, setModalOpen] = useState(false);

  if (!evidence && !hasFallbackSetup(fallback)) {
    return (
      <div className='rounded-xl border border-[var(--to-border)] bg-[var(--to-surface-raised)]/30 p-3 text-[11px] text-[var(--to-text-dim)]'>
        Setup evidence unavailable
      </div>
    );
  }

  if (!evidence && fallback) {
    const zoneLabel = [fallback.zoneType, fallback.zoneGrade]
      .filter(Boolean)
      .join(' ')
      .toUpperCase();

    return (
      <div className='space-y-3 rounded-xl border border-amber-500/20 bg-amber-500/5 p-3'>
        <div className='flex flex-wrap items-center gap-2'>
          <span className='inline-flex items-center rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-amber-300'>
            zone setup
          </span>
          <span className='font-mono text-[11px] text-[var(--to-text-secondary)]'>
            {zoneLabel || `${fallback.symbol} setup`}
          </span>
        </div>

        <div className='text-[11px] leading-relaxed text-[var(--to-text-dim)]'>
          MCP setup image is not attached to this signal, showing the captured zone setup fields instead.
        </div>

        <div className='grid gap-2 text-[11px]'>
          <div>
            <span className='text-[var(--to-text-dim)]'>Symbol</span>
            <span className='ml-2 font-mono text-[var(--to-text-secondary)]'>
              {fallback.symbol}
            </span>
          </div>
          <div>
            <span className='text-[var(--to-text-dim)]'>Zone</span>
            <span className='ml-2 font-mono text-[var(--to-text-secondary)]'>
              {zoneLabel || '--'}
            </span>
          </div>
          <div>
            <span className='text-[var(--to-text-dim)]'>Model</span>
            <span className='ml-2 font-mono text-[var(--to-text-secondary)]'>
              {fallback.entryModel?.toUpperCase() || '--'}
            </span>
          </div>
          <div>
            <span className='text-[var(--to-text-dim)]'>Session</span>
            <span className='ml-2 font-mono text-[var(--to-text-secondary)]'>
              {fallback.session != null ? SESSION_LABELS[fallback.session] || fallback.session : '--'}
            </span>
          </div>
          <div>
            <span className='text-[var(--to-text-dim)]'>Entry / SL / TP</span>
            <span className='ml-2 font-mono text-[var(--to-text-secondary)]'>
              {formatPrice(fallback.entry)} / {formatPrice(fallback.stopLoss)} /{' '}
              {formatPrice(fallback.takeProfit)}
            </span>
          </div>
          <div>
            <span className='text-[var(--to-text-dim)]'>SL Pips / R:R</span>
            <span className='ml-2 font-mono text-[var(--to-text-secondary)]'>
              {fallback.slPips != null ? fallback.slPips.toFixed(1) : '--'} /{' '}
              {fallback.rrRatio != null ? `1:${fallback.rrRatio.toFixed(1)}` : '--'}
            </span>
          </div>
          <div>
            <span className='text-[var(--to-text-dim)]'>Setup Score</span>
            <span className='ml-2 font-mono text-[var(--to-text-secondary)]'>
              {fallback.score != null ? fallback.score : '--'}
            </span>
          </div>
        </div>
      </div>
    );
  }

  if (!evidence) {
    return null;
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
    <div className='space-y-3 rounded-xl border border-emerald-400/15 bg-[#0a1017]/70 p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]'>
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
            className='group relative block overflow-hidden rounded-lg border border-emerald-400/20 bg-[#05080d] shadow-[0_12px_36px_rgba(0,0,0,0.35)]'
            onClick={() => setModalOpen(true)}
          >
            <img
              src={evidence.focus_image.url}
              alt='Setup evidence preview'
              className='w-full max-w-md rounded-lg object-cover opacity-90 transition duration-300 group-hover:scale-[1.015] group-hover:opacity-100'
            />
            <span className='pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(0,0,0,0.05),rgba(0,0,0,0.45))] opacity-80 transition group-hover:opacity-45' />
            <span className='pointer-events-none absolute left-2 top-2 inline-flex items-center rounded-full border border-emerald-300/25 bg-black/70 px-2 py-1 font-mono text-[9px] uppercase tracking-wide text-emerald-200'>
              Chart
            </span>
            <span className='pointer-events-none absolute right-2 top-2 inline-flex items-center gap-1 rounded-full border border-white/10 bg-black/75 px-2 py-1 text-[10px] font-medium text-white shadow-lg backdrop-blur'>
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
