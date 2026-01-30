'use client';

import { useState, useMemo } from 'react';
import { useTradingSignals } from '@/hooks/useTradingSignals';
import {
  TradingSignal,
  TradingMode,
  getSymbol,
  getSide,
  getScore,
  getPnl,
  getNotes,
} from '@/types/trading';
import { SignalInspector } from '@/components/SignalInspector';
import { ScoreRing } from '@/components/SignalCard';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { formatDistanceToNowStrict } from 'date-fns';
import {
  Radio,
  CheckCircle2,
  ShieldX,
  Filter,
  XCircle,
  Clock,
  TrendingUp,
  TrendingDown,
  Activity,
  AlertCircle,
  Zap,
} from 'lucide-react';

// =============================================================================
// UTILITY HELPERS
// =============================================================================

/**
 * Safe float conversion - prevents toFixed crashes on null/undefined values
 * CRITICAL: Use this for PnL display to handle null safely
 *
 * @param val - The value to convert
 * @param decimals - Number of decimal places (default: 2)
 * @returns Formatted string or "--" for null values
 */
export function safeFloat(val: number | null | undefined, decimals: number = 2): string {
  if (val === null || val === undefined || Number.isNaN(val)) {
    return '--';
  }
  return val.toFixed(decimals);
}

/**
 * Truncate text to specified length with ellipsis
 * SPEC: Reason column should be truncated to 40 chars
 *
 * @param text - Text to truncate
 * @param maxLength - Maximum length (default: 40)
 * @returns Truncated string
 */
export function truncateText(text: string | null | undefined, maxLength: number = 40): string {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trim() + '...';
}

/**
 * Get display reason from signal (notes or filter_reason, truncated)
 * SPEC: Reason Column - Map from `notes` OR `filter_reason`. Truncate to 40 chars.
 *
 * @param signal - Trading signal
 * @returns Truncated reason string
 */
export function getDisplayReason(signal: TradingSignal): string {
  const notes = getNotes(signal);
  const reason = notes || signal.filter_reason;
  return truncateText(reason, 40);
}

/**
 * Format relative time in compact form (e.g., "2m ago")
 */
function formatRelativeTime(date: Date): string {
  return formatDistanceToNowStrict(date, { addSuffix: true });
}

// =============================================================================
// STATUS BADGE COMPONENT
// =============================================================================

/**
 * Status Badge Component - Maps DB status to UI display
 *
 * SPEC Mapping:
 * - `active` → LIVE (Blue Pulse)
 * - `ai_rejected` → VETO (Red Shield)
 * - `filtered` → FILTER (Gray)
 * - `closed` → CLOSED (Green/Red based on PnL)
 */
interface StatusBadgeProps {
  status: TradingSignal['status'];
  pnl?: number | null;
  compact?: boolean;
}

function StatusBadge({ status, pnl, compact = false }: StatusBadgeProps) {
  const normalized = status?.toLowerCase();

  // For closed trades, color based on PnL
  const isWin = pnl !== null && pnl !== undefined && pnl > 0;
  const isLoss = pnl !== null && pnl !== undefined && pnl < 0;

  const configs: Record<string, { icon: React.ReactNode; label: string; className: string }> = {
    // SPEC: active → LIVE (Blue Pulse)
    active: {
      icon: <Radio className={cn('w-3 h-3', !compact && 'animate-pulse')} />,
      label: 'LIVE',
      className: cn(
        'bg-blue-500/20 text-blue-400 border-blue-500/40',
        !compact && 'shadow-[0_0_12px_rgba(59,130,246,0.3)] animate-pulse'
      ),
    },
    // SPEC: closed → CLOSED (Green/Red based on PnL)
    closed: {
      icon: <CheckCircle2 className="w-3 h-3" />,
      label: 'CLOSED',
      className: isWin
        ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
        : isLoss
        ? 'bg-rose-500/20 text-rose-400 border-rose-500/40'
        : 'bg-zinc-500/20 text-zinc-400 border-zinc-500/40',
    },
    executed: {
      icon: <CheckCircle2 className="w-3 h-3" />,
      label: 'FILLED',
      className: isWin
        ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
        : isLoss
        ? 'bg-rose-500/20 text-rose-400 border-rose-500/40'
        : 'bg-zinc-500/20 text-zinc-400 border-zinc-500/40',
    },
    // SPEC: ai_rejected → VETO (Red Shield)
    ai_rejected: {
      icon: <ShieldX className="w-3 h-3" />,
      label: 'VETO',
      className: 'bg-rose-500/20 text-rose-400 border-rose-500/40 shadow-[0_0_8px_rgba(244,63,94,0.2)]',
    },
    // SPEC: filtered → FILTER (Gray)
    filtered: {
      icon: <Filter className="w-3 h-3" />,
      label: 'FILTER',
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
    label: status?.toUpperCase() || 'UNKNOWN',
    className: 'bg-zinc-500/20 text-zinc-500 border-zinc-500/40',
  };

  return (
    <Badge
      className={cn(
        'font-mono text-[9px] font-semibold uppercase tracking-wider gap-1 border px-1.5 py-0.5',
        config.className
      )}
    >
      {config.icon}
      {!compact && config.label}
    </Badge>
  );
}

// =============================================================================
// SIDE BADGE COMPONENT
// =============================================================================

function SideBadge({ side, compact = false }: { side: 'buy' | 'sell'; compact?: boolean }) {
  const isBuy = side === 'buy';
  return (
    <Badge
      className={cn(
        'font-mono text-[10px] font-bold border-0 gap-0.5',
        compact ? 'px-1.5 py-0.5' : 'px-2 py-0.5',
        isBuy
          ? 'bg-emerald-500/20 text-emerald-400'
          : 'bg-rose-500/20 text-rose-400'
      )}
    >
      {isBuy ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
      {!compact && side.toUpperCase()}
    </Badge>
  );
}

// =============================================================================
// PNL DISPLAY COMPONENT
// =============================================================================

/**
 * PnL Display Component
 * SPEC: Handle `null` safely (display "--")
 * SAFETY: signal.pnl?.toFixed(2) ?? '--'
 */
function PnLDisplay({ pnl }: { pnl: number | null }) {
  // SPEC: Handle null safely - display "--"
  if (pnl === null || pnl === undefined) {
    return <span className="font-mono text-xs text-zinc-600">--</span>;
  }

  const isPositive = pnl >= 0;
  return (
    <span
      className={cn(
        'font-mono text-xs font-bold tabular-nums',
        isPositive ? 'text-emerald-400' : 'text-rose-400'
      )}
    >
      {isPositive ? '+' : ''}
      {pnl.toFixed(2)}
    </span>
  );
}

// =============================================================================
// LOADING STATE - Terminal Skeleton
// =============================================================================

function LoadingTable() {
  return (
    <div className="space-y-1">
      {[...Array(8)].map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-4 px-4 py-3 border-b border-zinc-800/50"
        >
          <Skeleton className="h-4 w-16 bg-zinc-800" />
          <Skeleton className="h-5 w-20 bg-zinc-800" />
          <Skeleton className="h-8 w-8 rounded-full bg-zinc-800" />
          <Skeleton className="h-4 w-48 bg-zinc-800 flex-1" />
          <Skeleton className="h-4 w-12 bg-zinc-800" />
          <Skeleton className="h-4 w-16 bg-zinc-800" />
        </div>
      ))}
    </div>
  );
}

// =============================================================================
// EMPTY STATE - Terminal Style
// =============================================================================

function EmptyState({ mode }: { mode?: TradingMode }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="relative w-20 h-20 mb-6">
        <div className="absolute inset-0 rounded-full border border-zinc-800 animate-ping opacity-20" />
        <div className="absolute inset-2 rounded-full border border-zinc-700 animate-pulse" />
        <div className="absolute inset-0 rounded-full bg-zinc-900/80 flex items-center justify-center">
          <Activity className="w-8 h-8 text-zinc-600" />
        </div>
      </div>
      <h3 className="font-mono text-sm text-zinc-400 mb-2 uppercase tracking-wider">
        No Signals Found
      </h3>
      <p className="text-xs text-zinc-600 max-w-xs font-mono">
        {mode === 'LIVE'
          ? 'Awaiting live trading signals from the bot...'
          : mode === 'PAPER'
          ? 'No paper trading signals in the queue.'
          : 'Monitoring for incoming signals...'}
      </p>
      <div className="mt-4 flex items-center gap-2 text-[10px] font-mono text-zinc-700">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500/50 animate-pulse" />
        System Online
      </div>
    </div>
  );
}

// =============================================================================
// ERROR STATE
// =============================================================================

function ErrorState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="relative w-20 h-20 mb-6">
        <div className="absolute inset-0 rounded-full bg-rose-500/10 animate-pulse" />
        <div className="absolute inset-0 rounded-full border border-rose-500/30 flex items-center justify-center">
          <AlertCircle className="w-8 h-8 text-rose-400" />
        </div>
      </div>
      <h3 className="font-mono text-sm text-rose-400 mb-2 uppercase tracking-wider">
        Connection Error
      </h3>
      <p className="text-xs text-zinc-500 max-w-xs font-mono">
        Failed to establish data feed. Check connection and retry.
      </p>
    </div>
  );
}

// =============================================================================
// SIGNAL ROW COMPONENT - High Density Table Row
// =============================================================================

interface SignalRowProps {
  signal: TradingSignal;
  onClick: () => void;
}

function SignalRow({ signal, onClick }: SignalRowProps) {
  const symbol = getSymbol(signal);
  const side = getSide(signal);
  const score = getScore(signal);
  const pnl = getPnl(signal);
  const reason = getDisplayReason(signal);
  const normalized = signal.status?.toLowerCase();
  const isActive = normalized === 'active';

  return (
    <TableRow
      onClick={onClick}
      className={cn(
        'cursor-pointer transition-all duration-150 border-b border-zinc-800/50',
        'hover:bg-zinc-800/50 hover:shadow-[inset_0_0_0_1px_rgba(59,130,246,0.2)]',
        isActive && 'bg-blue-950/20 border-l-2 border-l-blue-500',
        !isActive && 'border-l-2 border-l-transparent'
      )}
    >
      {/* Column 1: Time - Relative "2m ago" */}
      <TableCell className="py-2 px-3 w-[90px]">
        <span className="font-mono text-[11px] text-zinc-500 tabular-nums whitespace-nowrap">
          {formatRelativeTime(new Date(signal.created_at))}
        </span>
      </TableCell>

      {/* Column 2: Signal - Symbol + Side Badge */}
      <TableCell className="py-2 px-3 w-[140px]">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-bold text-zinc-100 tracking-tight">
            {symbol}
          </span>
          <SideBadge side={side} compact />
        </div>
      </TableCell>

      {/* Column 3: AI Brain - Score Ring + Status Badge */}
      <TableCell className="py-2 px-3 w-[120px]">
        <div className="flex items-center gap-2">
          <ScoreRing score={score} size="sm" />
          <StatusBadge status={signal.status} pnl={pnl} compact />
        </div>
      </TableCell>

      {/* Column 4: Reason - Truncated notes (max 40 chars) */}
      <TableCell className="py-2 px-3">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="font-mono text-[11px] text-zinc-500 line-clamp-1 cursor-help">
                {reason || <span className="text-zinc-700 italic">No reason</span>}
              </span>
            </TooltipTrigger>
            {(signal.notes || signal.filter_reason) && (
              <TooltipContent
                side="bottom"
                className="max-w-sm bg-zinc-900 border-zinc-700 text-zinc-300"
              >
                <p className="text-xs">{signal.notes || signal.filter_reason}</p>
              </TooltipContent>
            )}
          </Tooltip>
        </TooltipProvider>
      </TableCell>

      {/* Column 5: R:R - Risk/Reward Ratio */}
      <TableCell className="py-2 px-3 w-[70px] text-right">
        <span className="font-mono text-[11px] text-zinc-400 tabular-nums">
          {signal.rr_ratio ? `1:${safeFloat(signal.rr_ratio, 1)}` : '--'}
        </span>
      </TableCell>

      {/* Column 6: PnL - Color-coded profit (Green +, Red -) */}
      <TableCell className="py-2 px-3 w-[80px] text-right">
        <PnLDisplay pnl={pnl} />
      </TableCell>
    </TableRow>
  );
}

// =============================================================================
// MAIN SIGNAL FEED COMPONENT - High Density Terminal Grid
// =============================================================================

interface SignalFeedProps {
  defaultMode?: TradingMode;
  onSelectSignal?: (signal: TradingSignal) => void;
}

/**
 * SignalFeed - High-Density Terminal Grid Component
 *
 * SPEC:
 * - Visual Style: Dark Mode, Monospace numbers (JetBrains Mono), Compact rows
 * - Columns: Time | Signal (Symbol + Side) | AI Brain (Score + Status) | Reason | R:R | PnL
 * - Interaction: Click row to expand detailed Sheet with full JSON
 * - CONSTRAINT: ZERO FILTERS - Show ALL signals including ai_rejected and filtered
 */
export function SignalFeed({ defaultMode, onSelectSignal }: SignalFeedProps) {
  const [inspectedSignal, setInspectedSignal] = useState<TradingSignal | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);

  // Fetch ALL signals - SPEC: Zero filters, we need to see EVERYTHING
  const { data: allSignals = [], isLoading, error } = useTradingSignals(defaultMode);

  // Count signals by status for header stats
  const stats = useMemo(() => {
    const live = allSignals.filter((s) => s.status?.toLowerCase() === 'active').length;
    const veto = allSignals.filter((s) => s.status?.toLowerCase() === 'ai_rejected').length;
    const filtered = allSignals.filter((s) => s.status?.toLowerCase() === 'filtered').length;
    const closed = allSignals.filter((s) =>
      ['closed', 'executed'].includes(s.status?.toLowerCase() || '')
    ).length;
    return { live, veto, filtered, closed, total: allSignals.length };
  }, [allSignals]);

  // Handle row click - opens Sheet with full JSON
  const handleRowClick = (signal: TradingSignal) => {
    setInspectedSignal(signal);
    setInspectorOpen(true);
    onSelectSignal?.(signal);
  };

  if (error) {
    return <ErrorState />;
  }

  return (
    <div className="flex flex-col h-full">
      {/* ═══════════════════════════════════════════════════════════════════════
          HEADER - Signal Count Stats
          ═══════════════════════════════════════════════════════════════════════ */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 bg-zinc-950/50">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-zinc-500" />
          <span className="font-mono text-xs text-zinc-400 uppercase tracking-wider">
            Signal Feed
          </span>
          {defaultMode && (
            <Badge
              className={cn(
                'font-mono text-[9px] uppercase border-0 px-1.5 py-0.5',
                defaultMode === 'LIVE'
                  ? 'bg-blue-500/20 text-blue-400'
                  : 'bg-amber-500/20 text-amber-400'
              )}
            >
              {defaultMode}
            </Badge>
          )}
        </div>

        {/* Quick Stats */}
        <div className="flex items-center gap-4 text-[10px] font-mono">
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
            <span className="text-zinc-500">LIVE</span>
            <span className="text-blue-400 font-bold">{stats.live}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
            <span className="text-zinc-500">VETO</span>
            <span className="text-rose-400 font-bold">{stats.veto}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-zinc-500" />
            <span className="text-zinc-500">FILTER</span>
            <span className="text-zinc-400 font-bold">{stats.filtered}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            <span className="text-zinc-500">CLOSED</span>
            <span className="text-emerald-400 font-bold">{stats.closed}</span>
          </div>
          <div className="pl-2 border-l border-zinc-800">
            <span className="text-zinc-500">TOTAL</span>
            <span className="text-zinc-300 font-bold ml-1.5">{stats.total}</span>
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════
          TABLE GRID - High Density Terminal Style
          ═══════════════════════════════════════════════════════════════════════ */}
      <ScrollArea className="flex-1">
        {isLoading ? (
          <LoadingTable />
        ) : allSignals.length === 0 ? (
          <EmptyState mode={defaultMode} />
        ) : (
          <Table className="table-dense">
            <TableHeader className="sticky top-0 bg-zinc-950/95 backdrop-blur-sm z-10">
              <TableRow className="border-b border-zinc-800 hover:bg-transparent">
                <TableHead className="font-mono text-[10px] text-zinc-600 uppercase tracking-wider py-2 px-3 w-[90px]">
                  Time
                </TableHead>
                <TableHead className="font-mono text-[10px] text-zinc-600 uppercase tracking-wider py-2 px-3 w-[140px]">
                  Signal
                </TableHead>
                <TableHead className="font-mono text-[10px] text-zinc-600 uppercase tracking-wider py-2 px-3 w-[120px]">
                  AI Brain
                </TableHead>
                <TableHead className="font-mono text-[10px] text-zinc-600 uppercase tracking-wider py-2 px-3">
                  Reason
                </TableHead>
                <TableHead className="font-mono text-[10px] text-zinc-600 uppercase tracking-wider py-2 px-3 w-[70px] text-right">
                  R:R
                </TableHead>
                <TableHead className="font-mono text-[10px] text-zinc-600 uppercase tracking-wider py-2 px-3 w-[80px] text-right">
                  PnL
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {allSignals.map((signal) => (
                <SignalRow
                  key={signal.id}
                  signal={signal}
                  onClick={() => handleRowClick(signal)}
                />
              ))}
            </TableBody>
          </Table>
        )}
      </ScrollArea>

      {/* ═══════════════════════════════════════════════════════════════════════
          FOOTER - Connection Status
          ═══════════════════════════════════════════════════════════════════════ */}
      <div className="flex items-center justify-between px-4 py-2 border-t border-zinc-800 bg-zinc-950/50">
        <div className="flex items-center gap-2 text-[10px] font-mono text-zinc-600">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500/70 animate-pulse" />
          <span>Realtime Connected</span>
        </div>
        <span className="text-[10px] font-mono text-zinc-700">
          Showing {allSignals.length} of 50 max
        </span>
      </div>

      {/* Signal Inspector Sheet */}
      <SignalInspector
        signal={inspectedSignal}
        open={inspectorOpen}
        onOpenChange={setInspectorOpen}
      />
    </div>
  );
}

// =============================================================================
// ALTERNATIVE EXPORT: SignalFeedGrid (Card-based layout)
// =============================================================================

// Re-export the card-based grid view as an alternative
export { SignalFeed as SignalFeedTable };
