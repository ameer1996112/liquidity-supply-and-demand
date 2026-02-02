'use client';

import { TradingSignal, getSymbol, getSide, getScore, getPnl, getNotes } from '@/types/trading';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { formatDistanceToNow, format } from 'date-fns';
import {
  Radio,
  CheckCircle2,
  ShieldX,
  Filter,
  XCircle,
  Clock,
  TrendingUp,
  TrendingDown,
  Sparkles,
} from 'lucide-react';

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Safe float display - handles null/undefined values
 */
function safeFloat(val: number | null | undefined, decimals: number = 2): string {
  if (val === null || val === undefined || Number.isNaN(val)) {
    return '--';
  }
  return val.toFixed(decimals);
}

/**
 * Truncate text to specified length with ellipsis
 */
function truncateText(text: string | null | undefined, maxLength: number = 40): string {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trim() + '…';
}

/**
 * Get display reason from signal (notes or filter_reason, truncated to 40 chars)
 */
function getDisplayReason(signal: TradingSignal): string {
  const notes = getNotes(signal);
  const reason = notes || signal.filter_reason;
  return truncateText(reason, 40);
}

// ============================================================================
// AI CONFIDENCE PROGRESS BAR
// ============================================================================

function ConfidenceBar({ score }: { score: number | null }) {
  if (score === null) {
    return (
      <div className="w-full space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider flex items-center gap-1">
            <Sparkles className="w-3 h-3" />
            AI Confidence
          </span>
          <span className="font-mono text-xs text-zinc-600">N/A</span>
        </div>
        <div className="h-2 w-full bg-zinc-800/50 rounded-full overflow-hidden">
          <div className="h-full w-0 bg-zinc-700 rounded-full" />
        </div>
      </div>
    );
  }

  const getBarColor = (s: number) => {
    if (s >= 80) return 'bg-gradient-to-r from-emerald-500 to-emerald-400';
    if (s >= 60) return 'bg-gradient-to-r from-amber-500 to-amber-400';
    return 'bg-gradient-to-r from-rose-500 to-rose-400';
  };

  const getTextColor = (s: number) => {
    if (s >= 80) return 'text-emerald-400';
    if (s >= 60) return 'text-amber-400';
    return 'text-rose-400';
  };

  const getGlow = (s: number) => {
    if (s >= 80) return 'shadow-[0_0_10px_rgba(16,185,129,0.4)]';
    if (s >= 60) return 'shadow-[0_0_10px_rgba(245,158,11,0.4)]';
    return 'shadow-[0_0_10px_rgba(239,68,68,0.4)]';
  };

  return (
    <div className="w-full space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider flex items-center gap-1">
          <Sparkles className="w-3 h-3" />
          AI Confidence
        </span>
        <span className={cn('font-mono text-xs font-bold', getTextColor(score))}>
          {score}%
        </span>
      </div>
      <div className="h-2 w-full bg-zinc-800/50 rounded-full overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500 ease-out',
            getBarColor(score),
            getGlow(score)
          )}
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
}

// ============================================================================
// CIRCULAR SCORE RING (COMPACT VERSION)
// ============================================================================

// Exported for use in other components (e.g., compact displays)
export function ScoreRing({ score, size = 'md' }: { score: number | null; size?: 'sm' | 'md' }) {
  const dimensions = size === 'sm' ? { w: 12, h: 12, r: 4, sw: 2 } : { w: 16, h: 16, r: 6, sw: 3 };

  if (score === null) {
    return (
      <div className={cn('relative flex items-center justify-center', `w-${dimensions.w} h-${dimensions.h}`)}>
        <div className="absolute inset-0 rounded-full border-2 border-zinc-800" />
        <span className="font-mono text-[10px] text-zinc-600">--</span>
      </div>
    );
  }

  const radius = size === 'sm' ? 20 : 28;
  const viewBox = size === 'sm' ? '0 0 48 48' : '0 0 64 64';
  const center = size === 'sm' ? 24 : 32;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  const getColor = (s: number) => {
    if (s >= 80) return { stroke: '#10b981', text: 'text-emerald-400', glow: 'drop-shadow-[0_0_8px_rgba(16,185,129,0.5)]' };
    if (s >= 60) return { stroke: '#f59e0b', text: 'text-amber-400', glow: 'drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]' };
    return { stroke: '#ef4444', text: 'text-red-400', glow: 'drop-shadow-[0_0_8px_rgba(239,68,68,0.5)]' };
  };

  const colors = getColor(score);

  return (
    <div className={cn(
      'relative flex items-center justify-center',
      size === 'sm' ? 'w-12 h-12' : 'w-16 h-16',
      colors.glow
    )}>
      <svg className={cn('-rotate-90', size === 'sm' ? 'w-12 h-12' : 'w-16 h-16')} viewBox={viewBox}>
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="#27272a"
          strokeWidth={size === 'sm' ? 3 : 4}
        />
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={colors.stroke}
          strokeWidth={size === 'sm' ? 3 : 4}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className="transition-all duration-500"
        />
      </svg>
      <span className={cn(
        'absolute font-mono font-bold',
        size === 'sm' ? 'text-[10px]' : 'text-sm',
        colors.text
      )}>
        {score}%
      </span>
    </div>
  );
}

// ============================================================================
// STATUS BADGE - Matches exact spec for status icons
// ============================================================================

/**
 * Status Badge Component
 * - active: Blue Pulse Badge with Radio icon
 * - ai_rejected: Red Shield Icon
 * - closed: Green Check Icon
 */
function StatusBadge({ status }: { status: TradingSignal['status'] }) {
  const normalized = status?.toLowerCase();

  const configs: Record<string, { icon: React.ReactNode; label: string; className: string }> = {
    // SPEC: active → Blue Pulse Badge
    active: {
      icon: <Radio className="w-3 h-3 animate-pulse" />,
      label: 'LIVE',
      className: 'bg-blue-500/20 text-blue-400 border-blue-500/40 shadow-[0_0_12px_rgba(59,130,246,0.3)] animate-pulse',
    },
    // SPEC: closed → Green Check Icon
    closed: {
      icon: <CheckCircle2 className="w-3 h-3" />,
      label: 'CLOSED',
      className: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
    },
    executed: {
      icon: <CheckCircle2 className="w-3 h-3" />,
      label: 'FILLED',
      className: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
    },
    // SPEC: ai_rejected → Red Shield Icon
    ai_rejected: {
      icon: <ShieldX className="w-3 h-3" />,
      label: 'AI VETO',
      className: 'bg-rose-500/20 text-rose-400 border-rose-500/40 shadow-[0_0_8px_rgba(244,63,94,0.2)]',
    },
    filtered: {
      icon: <Filter className="w-3 h-3" />,
      label: 'FILTERED',
      className: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/40',
    },
    failed: {
      icon: <XCircle className="w-3 h-3" />,
      label: 'FAILED',
      className: 'bg-rose-500/20 text-rose-400 border-rose-500/40',
    },
    pending: {
      icon: <Clock className="w-3 h-3" />,
      label: 'PENDING',
      className: 'bg-amber-500/20 text-amber-400 border-amber-500/40',
    },
  };

  const config = configs[normalized || ''] || {
    icon: <Clock className="w-3 h-3" />,
    label: status || 'UNKNOWN',
    className: 'bg-zinc-500/20 text-zinc-500 border-zinc-500/40',
  };

  return (
    <Badge className={cn(
      'font-mono text-[10px] font-semibold uppercase tracking-wider gap-1 border',
      config.className
    )}>
      {config.icon}
      {config.label}
    </Badge>
  );
}

// Side badge (BUY/SELL)
function SideBadge({ side }: { side: 'buy' | 'sell' }) {
  const isBuy = side === 'buy';
  return (
    <Badge
      className={cn(
        'font-mono text-xs font-bold px-2.5 py-1 border-0 gap-1',
        isBuy
          ? 'bg-emerald-500/20 text-emerald-400'
          : 'bg-rose-500/20 text-rose-400'
      )}
    >
      {isBuy ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      {side.toUpperCase()}
    </Badge>
  );
}

// ============================================================================
// PNL DISPLAY - Handles null safely with "--"
// ============================================================================

/**
 * PnL Display Component
 * SPEC: Handle `null` safely (display "--")
 */
function PnLDisplay({ pnl, size = 'md' }: { pnl: number | null; size?: 'sm' | 'md' | 'lg' }) {
  const sizeClasses = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base',
  };

  // SPEC: Handle null safely - display "--"
  if (pnl === null || pnl === undefined) {
    return (
      <div className={cn('font-mono font-bold text-zinc-600', sizeClasses[size])}>
        --
      </div>
    );
  }

  const isPositive = pnl >= 0;
  return (
    <div className={cn(
      'font-mono font-bold',
      sizeClasses[size],
      isPositive ? 'text-emerald-400' : 'text-rose-400'
    )}>
      {isPositive ? '+' : ''}{safeFloat(pnl, 2)}
    </div>
  );
}

// ============================================================================
// SIGNAL CARD COMPONENT
// ============================================================================

interface SignalCardProps {
  signal: TradingSignal;
  onInspect?: (signal: TradingSignal) => void;
}

/**
 * Signal Card Component - Mission Control v2
 *
 * SPEC Layout:
 * - Top Row: Symbol + Side Badge (Green for Buy, Red for Sell)
 * - Middle: Progress Bar for `score` (AI Confidence)
 * - Bottom: `notes` (reasoning) and formatted timestamp
 * - Interactive: Clicking the card opens a Sheet with full JSON details
 */
export function SignalCard({ signal, onInspect }: SignalCardProps) {
  // SPEC: Use correct field mappings
  const symbol = getSymbol(signal);        // maps from `symbol` field
  const side = getSide(signal);            // maps from `side` field
  const score = getScore(signal);          // maps from `score` field (0-100)
  const pnl = getPnl(signal);              // maps from `pnl` field
  const reason = getDisplayReason(signal); // maps from `notes` OR `filter_reason`, truncated to 40 chars

  const normalized = signal.status?.toLowerCase();
  const isActive = normalized === 'active';
  const isAiRejected = normalized === 'ai_rejected';
  const isClosed = normalized === 'closed';
  const isWin = pnl !== null && pnl > 0;
  const isLoss = pnl !== null && pnl < 0;

  // Handle card click - opens Sheet with full JSON
  const handleCardClick = () => {
    onInspect?.(signal);
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleCardClick}
      onKeyDown={(e) => e.key === 'Enter' && handleCardClick()}
      className={cn(
        // Base styles - Bloomberg Terminal meets Cyberpunk
        'group relative bg-zinc-900/70 border rounded-lg overflow-hidden',
        'transition-all duration-200 cursor-pointer select-none',
        // Hover states
        'hover:bg-zinc-900/90 hover:border-zinc-600',
        'hover:shadow-[0_0_20px_rgba(0,0,0,0.5)]',
        'hover:scale-[1.02]',
        // Focus states
        'focus:outline-none focus:ring-2 focus:ring-blue-500/50',
        // Status-based borders
        isActive && 'border-blue-500/50 bg-blue-950/20 shadow-[0_0_15px_rgba(59,130,246,0.15)]',
        isAiRejected && 'border-rose-500/40 bg-rose-950/10',
        isClosed && isWin && 'border-emerald-500/40 bg-emerald-950/10',
        isClosed && isLoss && 'border-rose-500/30 bg-rose-950/5',
        !isActive && !isAiRejected && !isClosed && 'border-zinc-800'
      )}
    >
      {/* Active indicator pulse effect */}
      {isActive && (
        <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 via-transparent to-transparent pointer-events-none animate-pulse" />
      )}

      {/* ═══════════════════════════════════════════════════════════════════
          TOP ROW: Symbol + Side Badge
          SPEC: Symbol from `symbol` field, Side Badge (Green=Buy, Red=Sell)
          ═══════════════════════════════════════════════════════════════════ */}
      <div className="flex items-center justify-between p-3 border-b border-zinc-800/60">
        <div className="flex items-center gap-2.5">
          {/* Asset Symbol */}
          <span className="font-mono text-base font-bold text-zinc-100 tracking-tight">
            {symbol}
          </span>
          {/* Side Badge - Green for Buy, Red for Sell */}
          <SideBadge side={side} />
        </div>
        {/* Status Badge */}
        <StatusBadge status={signal.status} />
      </div>

      {/* ═══════════════════════════════════════════════════════════════════
          MIDDLE: Progress Bar for AI Confidence Score
          SPEC: Map from `score` field (0-100)
          ═══════════════════════════════════════════════════════════════════ */}
      <div className="px-3 pt-3 pb-2">
        <ConfidenceBar score={score} />
      </div>

      {/* Trade Metrics Row */}
      <div className="px-3 pb-2 flex items-center justify-between gap-4">
        {/* Entry Price */}
        <div className="flex items-center gap-2">
          {(signal.price ?? signal.entry) ? (
            <>
              <span className="text-[10px] font-mono text-zinc-600 uppercase">Entry</span>
              <span className="font-mono text-xs text-zinc-400">
                {safeFloat(signal.price ?? signal.entry, symbol.includes('JPY') ? 3 : symbol.includes('BTC') ? 2 : 5)}
              </span>
            </>
          ) : (
            <span className="text-[10px] font-mono text-zinc-700">--</span>
          )}
        </div>

        {/* R:R Ratio */}
        {signal.rr_ratio && (
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-mono text-zinc-600 uppercase">R:R</span>
            <span className="font-mono text-xs text-zinc-400">1:{safeFloat(signal.rr_ratio, 1)}</span>
          </div>
        )}

        {/* PnL Display - SPEC: Handle null safely with "--" */}
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-mono text-zinc-600 uppercase">PnL</span>
          <PnLDisplay pnl={pnl} size="sm" />
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════
          BOTTOM: Notes (reasoning) + Formatted Timestamp
          SPEC: Map from `notes` OR `filter_reason`, truncated to 40 chars
          ═══════════════════════════════════════════════════════════════════ */}
      <div className="px-3 pb-3 space-y-2">
        {/* Reasoning Text */}
        <div className="min-h-[32px]">
          {reason ? (
            <p className="text-[11px] font-mono text-zinc-500 leading-relaxed line-clamp-2">
              {reason}
            </p>
          ) : (
            <p className="text-[11px] font-mono text-zinc-700 italic">
              No reasoning provided
            </p>
          )}
        </div>

        {/* Timestamp Footer */}
        <div className="flex items-center justify-between pt-2 border-t border-zinc-800/40">
          <span className="font-mono text-[10px] text-zinc-600">
            {formatDistanceToNow(new Date(signal.created_at), { addSuffix: true })}
          </span>
          <span className="font-mono text-[10px] text-zinc-700">
            {format(new Date(signal.created_at), 'HH:mm:ss')}
          </span>
        </div>
      </div>

      {/* Hover overlay hint */}
      <div className="absolute inset-0 bg-gradient-to-t from-zinc-950/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
    </div>
  );
}

// ============================================================================
// SKELETON LOADER - Matches new card layout
// ============================================================================

export function SignalCardSkeleton() {
  return (
    <div className="bg-zinc-900/70 border border-zinc-800 rounded-lg overflow-hidden animate-pulse">
      {/* Header - Symbol + Side Badge */}
      <div className="flex items-center justify-between p-3 border-b border-zinc-800/60">
        <div className="flex items-center gap-2.5">
          <div className="h-5 w-20 bg-zinc-800 rounded" />
          <div className="h-5 w-14 bg-zinc-800 rounded-full" />
        </div>
        <div className="h-5 w-16 bg-zinc-800 rounded-full" />
      </div>

      {/* Middle - Confidence Bar */}
      <div className="px-3 pt-3 pb-2 space-y-1.5">
        <div className="flex items-center justify-between">
          <div className="h-3 w-24 bg-zinc-800 rounded" />
          <div className="h-3 w-10 bg-zinc-800 rounded" />
        </div>
        <div className="h-2 w-full bg-zinc-800 rounded-full" />
      </div>

      {/* Metrics Row */}
      <div className="px-3 pb-2 flex items-center justify-between gap-4">
        <div className="h-3 w-20 bg-zinc-800 rounded" />
        <div className="h-3 w-14 bg-zinc-800 rounded" />
        <div className="h-3 w-16 bg-zinc-800 rounded" />
      </div>

      {/* Bottom - Reasoning + Timestamp */}
      <div className="px-3 pb-3 space-y-2">
        <div className="space-y-1">
          <div className="h-3 w-full bg-zinc-800 rounded" />
          <div className="h-3 w-3/4 bg-zinc-800 rounded" />
        </div>
        <div className="flex items-center justify-between pt-2 border-t border-zinc-800/40">
          <div className="h-2.5 w-16 bg-zinc-800 rounded" />
          <div className="h-2.5 w-14 bg-zinc-800 rounded" />
        </div>
      </div>
    </div>
  );
}
