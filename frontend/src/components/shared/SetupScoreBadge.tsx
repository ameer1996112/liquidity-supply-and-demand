'use client';

import { cn } from '@/lib/utils';
import type { TradingSignal } from '@/types/trading';

interface SetupScoreBadgeProps {
  signal: Pick<
    TradingSignal,
    | 'setup_score'
    | 'setup_grade'
    | 'setup_score_version'
    | 'setup_strengths'
    | 'setup_weaknesses'
  >;
  compact?: boolean;
  className?: string;
}

function scoreTone(score: number): string {
  if (score >= 85) return 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300';
  if (score >= 75) return 'border-lime-400/35 bg-lime-400/10 text-lime-300';
  if (score >= 60) return 'border-amber-400/35 bg-amber-400/10 text-amber-300';
  if (score >= 45) return 'border-orange-400/35 bg-orange-400/10 text-orange-300';
  return 'border-red-400/35 bg-red-400/10 text-red-300';
}

export function hasSetupScore(signal: SetupScoreBadgeProps['signal']): boolean {
  return signal.setup_score !== null && signal.setup_score !== undefined;
}

export function formatSetupScore(signal: SetupScoreBadgeProps['signal']): string {
  if (!hasSetupScore(signal)) return '--';
  const score = Number(signal.setup_score);
  const scoreLabel = Number.isFinite(score) ? score.toFixed(score % 1 === 0 ? 0 : 1) : '--';
  return `${signal.setup_grade || 'SET'} ${scoreLabel}`;
}

export function SetupScoreBadge({ signal, compact = false, className }: SetupScoreBadgeProps) {
  if (!hasSetupScore(signal)) {
    return null;
  }

  const score = Number(signal.setup_score);
  const strengths = signal.setup_strengths?.slice(0, 2).join(', ');
  const weaknesses = signal.setup_weaknesses?.slice(0, 2).join(', ');
  const titleParts = [
    signal.setup_score_version ? `Model: ${signal.setup_score_version}` : null,
    strengths ? `Strengths: ${strengths}` : null,
    weaknesses ? `Watch: ${weaknesses}` : null,
  ].filter(Boolean);

  return (
    <span
      className={cn(
        'inline-flex min-w-[4.25rem] items-center justify-center rounded border px-1.5 py-0.5 font-mono text-[10px] font-bold tabular-nums',
        scoreTone(score),
        compact && 'min-w-[3.4rem] px-1 text-[9px]',
        className,
      )}
      title={titleParts.join(' | ') || 'Setup score'}
      data-testid='setup-score-badge'
    >
      {formatSetupScore(signal)}
    </span>
  );
}
