'use client';

import { TradingSignal, getSymbol, getSide, getScore, getPnl, getNotes } from '@/types/trading';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { formatDistanceToNow } from 'date-fns';
import {
  Radio,
  CheckCircle2,
  ShieldX,
  Filter,
  XCircle,
  Clock,
  Eye,
  TrendingUp,
  TrendingDown,
} from 'lucide-react';

// Circular progress ring for AI Score
function ScoreRing({ score }: { score: number | null }) {
  if (score === null) {
    return (
      <div className="relative w-16 h-16 flex items-center justify-center">
        <div className="absolute inset-0 rounded-full border-2 border-zinc-800" />
        <span className="font-mono text-xs text-zinc-600">N/A</span>
      </div>
    );
  }

  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  const getColor = (s: number) => {
    if (s >= 80) return { stroke: '#10b981', text: 'text-emerald-400', glow: 'drop-shadow-[0_0_8px_rgba(16,185,129,0.5)]' };
    if (s >= 60) return { stroke: '#f59e0b', text: 'text-amber-400', glow: 'drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]' };
    return { stroke: '#ef4444', text: 'text-red-400', glow: 'drop-shadow-[0_0_8px_rgba(239,68,68,0.5)]' };
  };

  const colors = getColor(score);

  return (
    <div className={cn('relative w-16 h-16 flex items-center justify-center', colors.glow)}>
      <svg className="w-16 h-16 -rotate-90" viewBox="0 0 64 64">
        {/* Background ring */}
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          stroke="#27272a"
          strokeWidth="4"
        />
        {/* Progress ring */}
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          stroke={colors.stroke}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className="transition-all duration-500"
        />
      </svg>
      <span className={cn('absolute font-mono text-sm font-bold', colors.text)}>
        {score}%
      </span>
    </div>
  );
}

// Status badge with icon
function StatusBadge({ status }: { status: TradingSignal['status'] }) {
  const normalized = status?.toLowerCase();

  const configs: Record<string, { icon: React.ReactNode; label: string; className: string }> = {
    active: {
      icon: <Radio className="w-3 h-3" />,
      label: 'LIVE',
      className: 'bg-blue-500/20 text-blue-400 border-blue-500/30 animate-pulse',
    },
    closed: {
      icon: <CheckCircle2 className="w-3 h-3" />,
      label: 'CLOSED',
      className: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    },
    executed: {
      icon: <CheckCircle2 className="w-3 h-3" />,
      label: 'FILLED',
      className: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    },
    ai_rejected: {
      icon: <ShieldX className="w-3 h-3" />,
      label: 'AI VETO',
      className: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
    },
    filtered: {
      icon: <Filter className="w-3 h-3" />,
      label: 'FILTERED',
      className: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',
    },
    failed: {
      icon: <XCircle className="w-3 h-3" />,
      label: 'FAILED',
      className: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
    },
    pending: {
      icon: <Clock className="w-3 h-3" />,
      label: 'PENDING',
      className: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    },
  };

  const config = configs[normalized || ''] || {
    icon: <Clock className="w-3 h-3" />,
    label: status || 'UNKNOWN',
    className: 'bg-zinc-500/20 text-zinc-500 border-zinc-500/30',
  };

  return (
    <Badge className={cn('font-mono text-[10px] font-semibold uppercase tracking-wider gap-1', config.className)}>
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

// PnL display
function PnLDisplay({ pnl }: { pnl: number | null }) {
  if (pnl === null) return null;

  const isPositive = pnl >= 0;
  return (
    <div className={cn(
      'font-mono text-sm font-bold',
      isPositive ? 'text-emerald-400' : 'text-rose-400'
    )}>
      {isPositive ? '+' : ''}${pnl.toFixed(2)}
    </div>
  );
}

interface SignalCardProps {
  signal: TradingSignal;
  onInspect?: (signal: TradingSignal) => void;
}

export function SignalCard({ signal, onInspect }: SignalCardProps) {
  const symbol = getSymbol(signal);
  const side = getSide(signal);
  const score = getScore(signal);
  const pnl = getPnl(signal);
  const notes = getNotes(signal);
  const normalized = signal.status?.toLowerCase();
  const isActive = normalized === 'active';
  const isWin = pnl !== null && pnl > 0;
  const isLoss = pnl !== null && pnl < 0;

  return (
    <div
      className={cn(
        'group relative bg-zinc-900/60 border rounded-lg overflow-hidden transition-all duration-200',
        'hover:bg-zinc-900/80 hover:border-zinc-700',
        isActive && 'border-blue-500/50 bg-blue-500/5',
        !isActive && 'border-zinc-800/60',
        isWin && 'border-emerald-500/30',
        isLoss && 'border-rose-500/30'
      )}
    >
      {/* Active indicator glow */}
      {isActive && (
        <div className="absolute inset-0 bg-gradient-to-r from-blue-500/5 to-transparent pointer-events-none" />
      )}

      {/* Card Header */}
      <div className="flex items-center justify-between p-3 border-b border-zinc-800/50">
        <div className="flex items-center gap-2">
          <span className="font-mono text-base font-bold text-zinc-100">{symbol}</span>
          <SideBadge side={side} />
        </div>
        <StatusBadge status={signal.status} />
      </div>

      {/* Card Body */}
      <div className="p-3 flex items-start gap-4">
        {/* AI Score Ring */}
        <ScoreRing score={score} />

        {/* Info Section */}
        <div className="flex-1 min-w-0 space-y-2">
          {/* Time & PnL Row */}
          <div className="flex items-center justify-between">
            <span className="font-mono text-[11px] text-zinc-500">
              {formatDistanceToNow(new Date(signal.created_at), { addSuffix: true })}
            </span>
            <PnLDisplay pnl={pnl} />
          </div>

          {/* Entry Price */}
          {(signal.price ?? signal.entry) && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-zinc-500 uppercase">Entry</span>
              <span className="font-mono text-xs text-zinc-300">
                ${(signal.price ?? signal.entry)?.toFixed(symbol.includes('JPY') ? 3 : symbol.includes('BTC') ? 2 : 5)}
              </span>
            </div>
          )}

          {/* Risk/Reward */}
          {signal.rr_ratio && (
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-zinc-500 uppercase">R:R</span>
              <span className="font-mono text-xs text-zinc-300">1:{signal.rr_ratio.toFixed(1)}</span>
            </div>
          )}
        </div>
      </div>

      {/* Card Footer - Reasoning */}
      <div className="px-3 pb-3">
        {notes ? (
          <p className="text-[11px] text-zinc-500 line-clamp-2 leading-relaxed">
            {notes}
          </p>
        ) : (
          <p className="text-[11px] text-zinc-600 italic">No reasoning provided</p>
        )}
      </div>

      {/* Inspect Button */}
      <div className="px-3 pb-3">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onInspect?.(signal)}
          className={cn(
            'w-full h-8 border-zinc-800 bg-zinc-950/50 text-zinc-400',
            'hover:bg-zinc-800/50 hover:text-zinc-100 hover:border-zinc-700',
            'font-mono text-[11px] uppercase tracking-wider'
          )}
        >
          <Eye className="w-3 h-3 mr-1.5" />
          Inspect
        </Button>
      </div>
    </div>
  );
}

// Skeleton loader for SignalCard
export function SignalCardSkeleton() {
  return (
    <div className="bg-zinc-900/60 border border-zinc-800/60 rounded-lg overflow-hidden animate-pulse">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-zinc-800/50">
        <div className="flex items-center gap-2">
          <div className="h-5 w-16 bg-zinc-800 rounded" />
          <div className="h-5 w-12 bg-zinc-800 rounded" />
        </div>
        <div className="h-5 w-16 bg-zinc-800 rounded" />
      </div>

      {/* Body */}
      <div className="p-3 flex items-start gap-4">
        <div className="w-16 h-16 bg-zinc-800 rounded-full" />
        <div className="flex-1 space-y-2">
          <div className="flex justify-between">
            <div className="h-3 w-20 bg-zinc-800 rounded" />
            <div className="h-4 w-16 bg-zinc-800 rounded" />
          </div>
          <div className="h-3 w-24 bg-zinc-800 rounded" />
          <div className="h-3 w-16 bg-zinc-800 rounded" />
        </div>
      </div>

      {/* Footer */}
      <div className="px-3 pb-3 space-y-3">
        <div className="h-8 w-full bg-zinc-800 rounded" />
        <div className="h-8 w-full bg-zinc-800 rounded" />
      </div>
    </div>
  );
}
