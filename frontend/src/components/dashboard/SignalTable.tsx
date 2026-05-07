'use client';

import { useState, useMemo, useCallback } from 'react';
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Brain,
  TrendingUp,
  Wifi,
  AlertTriangle,
  ShieldAlert,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TradingSignal, SignalStatus } from '@/types/trading';
import { getPnl } from '@/types/trading';
import type { CouncilSummary } from '@/lib/api';
import type { ActivePosition } from '@/hooks/usePositions';
import { TableEmptyState } from '@/components/shared/TableStates';
import { PnLText } from '@/components/ui/typography';
import { SetupScoreBadge } from '@/components/shared/SetupScoreBadge';
import { calculateJournalRisk, formatJournalRisk, formatJournalRiskTitle } from '@/components/journal/riskFormat';

// =============================================================================
// TYPES
// =============================================================================

type SortField =
  | 'created_at'
  | 'symbol'
  | 'side'
  | 'entry'
  | 'risk'
  | 'pnl'
  | 'status'
  | 'setup_score'
  | 'score';
type SortDir = 'asc' | 'desc';
type FilterTab = 'all' | 'open' | 'closed' | 'rejected' | 'filtered';

interface SignalTableProps {
  signals: TradingSignal[];
  councilMap?: Record<string, CouncilSummary>;
  brokerMap?: Record<string, ActivePosition>;
  onSelectSignal?: (signal: TradingSignal) => void;
  maxRows?: number;
  className?: string;
  accountFilter?: string;
  onAccountFilterChange?: (name: string | undefined) => void;
  accountNames?: string[];
  accountSignalCounts?: Record<string, number>;
  strategyFilter?: string;
  onStrategyFilterChange?: (strategyId: string | undefined) => void;
  strategyOptions?: Array<{ value: string; label: string }>;
  strategySignalCounts?: Record<string, number>;
}

// =============================================================================
// HELPERS — pure functions, defined at module level
// =============================================================================

/** Relative time: "2m", "1h", "3d" */
function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h`;
  return `${Math.floor(diff / 86_400_000)}d`;
}

function isOpenStatus(status: string): boolean {
  const s = String(status).toLowerCase();
  return s === 'open' || s === 'active' || s === 'executed' || s === 'pending' || s === 'spin';
}

function isClosedStatus(status: string): boolean {
  return String(status).toLowerCase() === 'closed';
}

function isRejectedStatus(status: string): boolean {
  const s = String(status).toLowerCase();
  return (
    s === 'ai_rejected' ||
    s === 'failed' ||
    s === 'risk_rejected' ||
    s === 'kill_switch_blocked' ||
    s === 'staleness_rejected' ||
    s === 'execution_failed' ||
    s === 'unexecuted' ||
    s === 'received'
  );
}

function isFilteredStatus(status: string): boolean {
  const s = String(status).toLowerCase();
  return s === 'filtered' || s === 'symbol_blacklisted';
}

function isTerminalStatus(status: string): boolean {
  return isClosedStatus(status) || isRejectedStatus(status) || isFilteredStatus(status);
}

function hasRealizedClose(signal: TradingSignal): boolean {
  return Boolean(signal.closed_at || signal.exit_price != null || isTerminalStatus(signal.status));
}

/** Left-border color class based on signal side */
function sideBorderColor(side: string): string {
  const s = (side ?? '').toLowerCase();
  if (s === 'buy' || s === 'long') return 'border-l-[var(--to-long)]';
  if (s === 'sell' || s === 'short') return 'border-l-[var(--to-short)]';
  return 'border-l-[var(--to-border)]';
}

function getSortValue(signal: TradingSignal, field: SortField): string | number {
  switch (field) {
    case 'created_at': return new Date(signal.created_at).getTime();
    case 'symbol':     return signal.symbol;
    case 'side':       return signal.side;
    case 'entry':      return signal.entry ?? signal.price ?? 0;
    case 'risk':       return calculateJournalRisk(signal)?.riskUsd ?? 0;
    case 'pnl':        return getPnl(signal) ?? 0;
    case 'status':     return signal.status;
    case 'setup_score': return signal.setup_score ?? -1;
    case 'score':      return signal.score ?? signal.ai_confidence ?? 0;
    default:           return '';
  }
}

function getSignalStrategyKey(signal: TradingSignal): string | undefined {
  const strategyId = signal.strategy_id?.trim();
  if (strategyId) return strategyId;

  const strategyName = signal.strategy_name?.trim();
  return strategyName || undefined;
}

function getSignalStrategyBadge(signal: TradingSignal): string | null {
  const key = getSignalStrategyKey(signal);
  if (!key) return null;

  const version = signal.strategy_version?.trim();
  return version ? `${key}@${version}` : key;
}

const STATUS_STYLES: Record<string, { label: string; bg: string; text: string }> = {
  open:                { label: 'OPEN',      bg: 'bg-[var(--to-long)]/12',          text: 'text-[var(--to-long)]' },
  active:              { label: 'OPEN',      bg: 'bg-[var(--to-long)]/12',          text: 'text-[var(--to-long)]' },
  executed:            { label: 'OPEN',      bg: 'bg-[var(--to-long)]/12',          text: 'text-[var(--to-long)]' },
  pending:             { label: 'PENDING',   bg: 'bg-[var(--to-warning)]/12',       text: 'text-[var(--to-warning)]' },
  spin:                { label: 'PENDING',   bg: 'bg-[var(--to-warning)]/12',       text: 'text-[var(--to-warning)]' },
  received:            { label: 'RECEIVED',  bg: 'bg-[var(--to-warning)]/10',       text: 'text-[var(--to-warning)]/80' },
  closed:              { label: 'CLOSED',    bg: 'bg-[var(--to-text-dim)]/12',      text: 'text-[var(--to-text-dim)]' },
  filtered:            { label: 'FILTERED',  bg: 'bg-[var(--to-short)]/8',          text: 'text-[var(--to-short)]/70' },
  ai_rejected:         { label: 'REJECTED',  bg: 'bg-[var(--to-short)]/12',         text: 'text-[var(--to-short)]' },
  failed:              { label: 'FAILED',    bg: 'bg-[var(--to-short)]/12',         text: 'text-[var(--to-short)]' },
  execution_failed:    { label: 'EXEC FAIL', bg: 'bg-orange-500/10',                text: 'text-orange-400' },
  symbol_blacklisted:  { label: 'FILTERED',  bg: 'bg-[var(--to-short)]/8',          text: 'text-[var(--to-short)]/70' },
  risk_rejected:       { label: 'RISK',      bg: 'bg-[var(--to-short)]/8',          text: 'text-[var(--to-short)]/70' },
  kill_switch_blocked: { label: 'KILL SW',   bg: 'bg-[var(--to-short)]/12',         text: 'text-[var(--to-short)]' },
  staleness_rejected:  { label: 'STALE',     bg: 'bg-[var(--to-warning)]/10',       text: 'text-[var(--to-warning)]/70' },
};

// =============================================================================
// SUB-COMPONENTS — defined outside SignalTable to avoid recreation on render
// =============================================================================

interface SortHeaderProps {
  field: SortField;
  label: string;
  align?: 'left' | 'right';
  sortField: SortField;
  sortDir: SortDir;
  onSort: (field: SortField) => void;
}

function SortHeader({ field, label, align = 'left', sortField, sortDir, onSort }: SortHeaderProps) {
  return (
    <button
      type='button'
      className={cn(
        'inline-flex w-full items-center gap-1 text-[10px] font-semibold uppercase text-[var(--to-text-dim)]',
        align === 'right' && 'justify-end',
      )}
      onClick={() => onSort(field)}
    >
      <span>{label}</span>
      {sortField === field ? (
        sortDir === 'asc' ? (
          <ArrowUp className='h-2.5 w-2.5' />
        ) : (
          <ArrowDown className='h-2.5 w-2.5' />
        )
      ) : (
        <ArrowUpDown className='h-2.5 w-2.5 opacity-30' />
      )}
    </button>
  );
}

function StatusBadge({ status, isStale }: { status: SignalStatus; isStale?: boolean }) {
  const normalized = String(status).toLowerCase();
  const style = STATUS_STYLES[normalized] ?? {
    label: String(status).toUpperCase(),
    bg: 'bg-[var(--to-surface-raised)]',
    text: 'text-[var(--to-text-dim)]',
  };

  return (
    <div className='inline-flex items-center gap-1'>
      <span
        className={cn(
          'inline-flex items-center rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider',
          style.bg,
          style.text,
        )}
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        {style.label}
      </span>
      {isStale && (
        <span title='Stale'><AlertTriangle className='h-2.5 w-2.5 text-[var(--to-warning)]' /></span>
      )}
    </div>
  );
}

function SideBadge({ side }: { side: string }) {
  const isBuy = side.toLowerCase() === 'buy';
  return (
    <span
      className={cn(
        'inline-flex min-w-[46px] justify-center rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase',
        isBuy
          ? 'border-[var(--to-long)]/25 bg-[var(--to-long)]/12 text-[var(--to-long)]'
          : 'border-[var(--to-short)]/25 bg-[var(--to-short)]/12 text-[var(--to-short)]',
      )}
      style={{ fontFamily: 'var(--font-mono)' }}
    >
      {isBuy ? 'BUY' : 'SELL'}
    </span>
  );
}

function formatSignalPrice(symbol: string, value?: number | null): string {
  if (value == null) return '—';
  const normalized = symbol.toUpperCase();
  const decimals = normalized.includes('JPY')
    ? 3
    : normalized.includes('XAU') || normalized.includes('GOLD') || normalized.includes('BTC')
      ? 2
      : 5;
  return Number(value).toFixed(decimals);
}

const SIGNAL_GRID_STYLE = {
  gridTemplateColumns:
    '64px minmax(150px,1.2fr) 64px minmax(92px,0.8fr) minmax(92px,0.8fr) minmax(92px,0.8fr) 96px 96px 76px 64px 92px',
} as const;

const SIGNAL_TABLE_MIN_WIDTH = 'min-w-[1120px]';

interface SignalBlotterHeaderProps {
  sortField: SortField;
  sortDir: SortDir;
  onSort: (field: SortField) => void;
}

function SignalBlotterHeader({ sortField, sortDir, onSort }: SignalBlotterHeaderProps) {
  return (
    <div
      className={cn(
        'sticky top-0 z-10 grid items-center border-b border-[var(--to-border)] bg-[#0d1219]/95 px-3 py-2 backdrop-blur',
        SIGNAL_TABLE_MIN_WIDTH,
      )}
      style={SIGNAL_GRID_STYLE}
    >
      <SortHeader field='created_at' label='Time' sortField={sortField} sortDir={sortDir} onSort={onSort} />
      <SortHeader field='symbol' label='Symbol' sortField={sortField} sortDir={sortDir} onSort={onSort} />
      <SortHeader field='side' label='Side' sortField={sortField} sortDir={sortDir} onSort={onSort} />
      <SortHeader field='entry' label='Entry' align='right' sortField={sortField} sortDir={sortDir} onSort={onSort} />
      <SortHeader field='entry' label='SL' align='right' sortField={sortField} sortDir={sortDir} onSort={onSort} />
      <SortHeader field='entry' label='TP' align='right' sortField={sortField} sortDir={sortDir} onSort={onSort} />
      <SortHeader field='pnl' label='P&L' align='right' sortField={sortField} sortDir={sortDir} onSort={onSort} />
      <SortHeader field='risk' label='Risk' align='right' sortField={sortField} sortDir={sortDir} onSort={onSort} />
      <SortHeader field='setup_score' label='Setup' align='right' sortField={sortField} sortDir={sortDir} onSort={onSort} />
      <button
        type='button'
        className='inline-flex w-full items-center justify-end gap-1 text-[10px] font-semibold uppercase text-[var(--to-text-dim)]'
        onClick={() => onSort('score')}
      >
        <TrendingUp className='h-2.5 w-2.5' strokeWidth={1.5} />
        <span>AI</span>
        {sortField === 'score' ? (
          sortDir === 'asc' ? <ArrowUp className='h-2.5 w-2.5' /> : <ArrowDown className='h-2.5 w-2.5' />
        ) : (
          <ArrowUpDown className='h-2.5 w-2.5 opacity-30' />
        )}
      </button>
      <SortHeader field='status' label='Status' sortField={sortField} sortDir={sortDir} onSort={onSort} />
    </div>
  );
}

interface SignalBlotterRowProps {
  signal: TradingSignal;
  broker?: ActivePosition;
  council?: CouncilSummary;
  onSelect?: (signal: TradingSignal) => void;
}

function PriceCell({
  symbol,
  value,
  tone = 'neutral',
}: {
  symbol: string;
  value?: number | null;
  tone?: 'neutral' | 'long' | 'short';
}) {
  const toneClass =
    tone === 'long'
      ? 'text-[var(--to-long)]'
      : tone === 'short'
        ? 'text-[var(--to-short)]'
        : 'text-[var(--to-text-secondary)]';

  return (
    <span className={cn('block text-right font-mono text-[11px] font-medium tabular-nums', toneClass)}>
      {formatSignalPrice(symbol, value)}
    </span>
  );
}

function SignalBlotterRow({ signal, broker, council, onSelect }: SignalBlotterRowProps) {
  const entry = signal.entry ?? signal.price;
  const sl = signal.sl ?? signal.stop_loss;
  const tp = signal.tp ?? signal.take_profit;
  const risk = calculateJournalRisk(signal);
  const livePnl = broker?.live_pnl;
  const dbPnl = getPnl(signal);
  const shouldShowLivePnl = isOpenStatus(signal.status) && !hasRealizedClose(signal) && livePnl != null;
  const score = signal.score ?? signal.ai_confidence;
  const scoreColor =
    score == null
      ? 'text-[var(--to-text-dim)]/40'
      : score >= 70
        ? 'text-[var(--to-long)]'
        : score >= 50
          ? 'text-[var(--to-warning)]'
          : 'text-[var(--to-short)]';

  return (
    <button
      type='button'
      className={cn(
        'group grid items-center border-b border-[var(--to-border)]/40 px-3 py-2 text-left transition-colors duration-150',
        SIGNAL_TABLE_MIN_WIDTH,
        'bg-[#0d1218]/90 hover:bg-[#121821]',
        'border-l-2',
        sideBorderColor(signal.side),
        broker?.is_stale && 'opacity-70',
        isOpenStatus(signal.status) && 'bg-[#101824]',
      )}
      style={SIGNAL_GRID_STYLE}
      onClick={() => onSelect?.(signal)}
    >
      <span
        className='inline-flex w-fit items-center rounded border border-[var(--to-border)]/45 bg-black/10 px-1.5 py-0.5 font-mono text-[10px] tabular-nums text-[var(--to-text-secondary)]'
        title={new Date(signal.created_at).toLocaleString()}
      >
        {relativeTime(signal.created_at)}
      </span>

      <div className='flex min-w-0 flex-col gap-0.5'>
        <span className='truncate text-[13px] font-semibold text-[var(--to-text-primary)]'>
          {signal.symbol}
        </span>
        <div className='flex min-w-0 items-center gap-1.5 text-[9px] text-[var(--to-text-dim)]'>
          {(signal as any).account_name && (
            <span className='truncate'>
              {(signal as any).account_name}
            </span>
          )}
          {(signal as any).account_name && getSignalStrategyBadge(signal) && (
            <span className='text-[var(--to-border)]'>/</span>
          )}
          {getSignalStrategyBadge(signal) && (
            <span className='truncate'>
              {getSignalStrategyBadge(signal)}
            </span>
          )}
        </div>
      </div>

      <SideBadge side={signal.side} />

      <div title={`Entry: ${formatSignalPrice(signal.symbol, entry)}`}>
        <PriceCell symbol={signal.symbol} value={entry} />
      </div>

      <div title={`Stop Loss: ${formatSignalPrice(signal.symbol, sl)}`}>
        <PriceCell symbol={signal.symbol} value={sl} tone='short' />
      </div>

      <div title={`Take Profit: ${formatSignalPrice(signal.symbol, tp)}`}>
        <PriceCell symbol={signal.symbol} value={tp} tone='long' />
      </div>

      <div className='flex justify-end'>
        {shouldShowLivePnl ? (
          <span
            className={cn(
              'inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[11px] font-bold tabular-nums',
              livePnl >= 0
                ? 'bg-[var(--to-long)]/8 text-[var(--to-long)]'
                : 'bg-[var(--to-short)]/8 text-[var(--to-short)]',
            )}
            title='Live broker P&L'
          >
            <span
              className={cn(
                'h-1.5 w-1.5 rounded-full animate-pulse',
                livePnl >= 0 ? 'bg-[var(--to-long)]' : 'bg-[var(--to-short)]',
              )}
            />
            {`${livePnl > 0 ? '+' : ''}${Number(livePnl).toFixed(2)}`}
          </span>
        ) : (
          <PnLText value={dbPnl} variant='currency' size='sm' />
        )}
      </div>

      <div className='flex justify-end'>
        <span
          className='inline-flex items-center gap-1 rounded border border-[var(--to-short)]/15 bg-[var(--to-short)]/7 px-1.5 py-0.5 font-mono text-[10px] font-medium tabular-nums text-[var(--to-short)]'
          title={formatJournalRiskTitle(risk)}
        >
          <ShieldAlert className='h-2.5 w-2.5 opacity-65' strokeWidth={1.7} />
          {formatJournalRisk(risk)}
        </span>
      </div>

      <div className='flex justify-end'>
        <SetupScoreBadge signal={signal} compact />
      </div>

      <div className='flex justify-end font-mono text-[11px] font-medium tabular-nums'>
        <span className={cn(scoreColor)}>{score == null ? '—' : Math.round(score)}</span>
      </div>

      <div className='flex items-center justify-between gap-2'>
        <CouncilBadge summary={council} suppressPending={isTerminalStatus(signal.status)} />
        <StatusBadge status={signal.status} isStale={broker?.is_stale} />
      </div>
    </button>
  );
}

function CouncilPlaceholder({ title }: { title?: string }) {
  return (
    <span className='font-mono text-[10px] text-[var(--to-text-dim)]/40' title={title}>
      —
    </span>
  );
}

function CouncilBadge({
  summary,
  suppressPending,
}: {
  summary: CouncilSummary | undefined;
  suppressPending?: boolean;
}) {
  if (!summary) return <CouncilPlaceholder />;

  const isAllow = summary.recommendation === 'allow';
  const conf = summary.confidence;
  const voteEntries = Object.entries(summary.votes || {});
  const hasVotes = voteEntries.length > 0;
  const isPending =
    summary.status === 'pending' || summary.recommendation === 'pending';

  if (isPending && suppressPending) {
    return <CouncilPlaceholder title='Council result was not finalized for this completed signal' />;
  }

  if (isPending) {
    return (
      <div
        className='inline-flex items-center justify-end gap-1'
        title='Council is still processing this signal'
      >
        <Brain className='h-3 w-3 shrink-0 text-[var(--to-warning)]/50' strokeWidth={1.5} />
        <span
          className='font-mono text-[9px] text-[var(--to-warning)]/80 uppercase tracking-wider'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          processing
        </span>
      </div>
    );
  }

  // No votes = fallback / council skipped / Risk Judge parse failed
  // The backend emits confidence=50 + votes={} in all skip paths.
  if (!hasVotes) {
    return (
      <div
        className='inline-flex items-center justify-end gap-1'
        title='Council skipped or timed out — no vote detail available'
      >
        <Brain className='h-3 w-3 shrink-0 text-[var(--to-text-dim)]/30' strokeWidth={1.5} />
        <span
          className='font-mono text-[10px] tabular-nums text-[var(--to-text-dim)]/50'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          {conf}%
        </span>
        <span
          className='font-mono text-[8px] text-[var(--to-text-dim)]/35 uppercase tracking-wider'
          style={{ fontFamily: 'var(--font-mono)' }}
        >
          skip
        </span>
      </div>
    );
  }

  const confColor =
    conf >= 70 ? 'text-[var(--to-long)]' : conf >= 50 ? 'text-[var(--to-warning)]' : 'text-[var(--to-short)]';
  const allowCount = voteEntries.filter(([, v]) => v === 'allow').length;
  const blockCount = voteEntries.filter(([, v]) => v === 'block').length;

  return (
    <div className='inline-flex items-center justify-end gap-1'>
      <Brain
        className={cn('h-3 w-3 shrink-0', isAllow ? 'text-[var(--to-long)]/60' : 'text-[var(--to-short)]/60')}
        strokeWidth={1.5}
      />
      <span
        className={cn('font-mono text-[10px] font-bold tabular-nums', confColor)}
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        {conf}%
      </span>
      <span
        className='font-mono text-[9px] tabular-nums text-[var(--to-text-dim)]/60'
        style={{ fontFamily: 'var(--font-mono)' }}
      >
        {allowCount}✓{blockCount}✗
      </span>
    </div>
  );
}

// =============================================================================
// FILTER TABS CONFIG
// =============================================================================

const FILTER_TABS: { id: FilterTab; label: string }[] = [
  { id: 'all',      label: 'All' },
  { id: 'open',     label: 'Open' },
  { id: 'closed',   label: 'Closed' },
  { id: 'rejected', label: 'Rejected' },
  { id: 'filtered', label: 'Filtered' },
];

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function SignalTable({
  signals,
  councilMap = {},
  brokerMap = {},
  onSelectSignal,
  maxRows = 100,
  className,
  accountFilter,
  onAccountFilterChange,
  accountNames,
  accountSignalCounts,
  strategyFilter,
  onStrategyFilterChange,
  strategyOptions,
  strategySignalCounts,
}: SignalTableProps) {
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortDir, setSortDir]     = useState<SortDir>('desc');
  const [activeFilter, setActiveFilter] = useState<FilterTab>('all');

  const handleSort = useCallback(
    (field: SortField) => {
      if (sortField === field) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortField(field);
        setSortDir('desc');
      }
    },
    [sortField],
  );

  // Tab counts — single pass
  const tabCounts = useMemo(() => {
    const counts: Record<FilterTab, number> = { all: signals.length, open: 0, closed: 0, rejected: 0, filtered: 0 };
    for (const s of signals) {
      if      (isOpenStatus(s.status))     counts.open++;
      else if (isClosedStatus(s.status))   counts.closed++;
      else if (isRejectedStatus(s.status)) counts.rejected++;
      else if (isFilteredStatus(s.status)) counts.filtered++;
    }
    return counts;
  }, [signals]);

  const filtered = useMemo(() => {
    let result = signals;
    if (activeFilter === 'open')     result = result.filter((s) => isOpenStatus(s.status));
    else if (activeFilter === 'closed')   result = result.filter((s) => isClosedStatus(s.status));
    else if (activeFilter === 'rejected') result = result.filter((s) => isRejectedStatus(s.status));
    else if (activeFilter === 'filtered') result = result.filter((s) => isFilteredStatus(s.status));
    if (accountFilter) {
      const normalizedFilter = accountFilter.trim();
      result = result.filter((s) => {
        const raw = (s as any).account_name;
        const normalized = typeof raw === 'string' ? raw.trim() : raw;
        return normalized === normalizedFilter;
      });
    }
    if (strategyFilter) {
      const normalizedStrategy = strategyFilter.trim();
      result = result.filter((s) => getSignalStrategyKey(s) === normalizedStrategy);
    }
    return result;
  }, [signals, activeFilter, accountFilter, strategyFilter]);

  const sorted = useMemo(() => {
    const slice = filtered.slice(0, maxRows);
    return [...slice].sort((a, b) => {
      const va = getSortValue(a, sortField);
      const vb = getSortValue(b, sortField);
      const cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [filtered, sortField, sortDir, maxRows]);

  if (signals.length === 0) {
    return (
      <TableEmptyState
        title='No signals yet'
        description='Waiting for the next trading signal from the bot.'
      />
    );
  }

  return (
    <div className={cn('flex flex-col h-full min-h-0', className)}>
      {/* Account filter pills */}
      {accountNames && accountNames.length > 0 && (
        <div style={{ display: 'flex', gap: 6, padding: '10px 0', flexWrap: 'wrap' }}>
          {accountNames.map(name => (
            <button
              key={name}
              onClick={() => onAccountFilterChange?.(name)}
              style={{
                padding: '4px 12px',
                borderRadius: 20,
                border: '1px solid',
                borderColor: accountFilter === name ? 'var(--live-blue)' : 'var(--border)',
                background: accountFilter === name ? 'var(--live-blue-dim)' : 'transparent',
                color: accountFilter === name ? 'var(--live-blue)' : 'var(--text-muted)',
                fontSize: 11,
                fontFamily: 'var(--font-display)',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 120ms ease',
                letterSpacing: '0.04em',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              {name.toUpperCase()}
              {accountSignalCounts?.[name] !== undefined && (
                <span style={{ opacity: 0.6, fontSize: 10 }}>
                  {accountSignalCounts[name]}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
      {strategyOptions && strategyOptions.length > 0 && (
        <div style={{ display: 'flex', gap: 6, padding: '0 0 10px', flexWrap: 'wrap' }}>
          <button
            onClick={() => onStrategyFilterChange?.(undefined)}
            style={{
              padding: '4px 12px',
              borderRadius: 20,
              border: '1px solid',
              borderColor: strategyFilter == null ? 'var(--to-accent-blue)' : 'var(--border)',
              background: strategyFilter == null
                ? 'color-mix(in srgb, var(--to-accent-blue) 14%, transparent)'
                : 'transparent',
              color: strategyFilter == null ? 'var(--to-accent-blue)' : 'var(--text-muted)',
              fontSize: 11,
              fontFamily: 'var(--font-display)',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 120ms ease',
              letterSpacing: '0.04em',
            }}
          >
            ALL STRATEGIES
          </button>
          {strategyOptions.map((strategy) => (
            <button
              key={strategy.value}
              onClick={() => onStrategyFilterChange?.(strategy.value)}
              style={{
                padding: '4px 12px',
                borderRadius: 20,
                border: '1px solid',
                borderColor:
                  strategyFilter === strategy.value ? 'var(--to-accent-blue)' : 'var(--border)',
                background:
                  strategyFilter === strategy.value
                    ? 'color-mix(in srgb, var(--to-accent-blue) 14%, transparent)'
                    : 'transparent',
                color:
                  strategyFilter === strategy.value ? 'var(--to-accent-blue)' : 'var(--text-muted)',
                fontSize: 11,
                fontFamily: 'var(--font-display)',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 120ms ease',
                letterSpacing: '0.04em',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              {strategy.label}
              {strategySignalCounts?.[strategy.value] !== undefined && (
                <span style={{ opacity: 0.6, fontSize: 10 }}>
                  {strategySignalCounts[strategy.value]}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
      {/* Filter tabs */}
      <div className='shrink-0 flex items-center gap-1 px-1 pb-1 flex-wrap'>
        {FILTER_TABS.map((tab) => (
          <button
            key={tab.id}
            type='button'
            onClick={() => setActiveFilter(tab.id)}
            className={cn(
              'inline-flex items-center gap-1 rounded px-2 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-wider transition-colors',
              activeFilter === tab.id
                ? 'bg-[var(--to-accent)]/20 text-[var(--to-accent)]'
                : 'text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)]',
            )}
          >
            {tab.label}
            {tabCounts[tab.id] > 0 && (
              <span
                className={cn(
                  'rounded-full px-1 py-px text-[8px] tabular-nums',
                  activeFilter === tab.id ? 'bg-[var(--to-accent)]/30' : 'bg-[var(--to-surface-raised)]',
                )}
              >
                {tabCounts[tab.id]}
              </span>
            )}
          </button>
        ))}
        {Object.keys(brokerMap).length > 0 && (
          <span className='ml-auto inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[8px] text-[var(--to-long)]/70'>
            <Wifi className='h-2.5 w-2.5' />
            broker live
          </span>
        )}
      </div>

      {/* Scrollable signal blotter */}
      <div className='flex-1 min-h-0 overflow-auto scrollbar-thin'>
        {sorted.length === 0 ? (
          <TableEmptyState
            title={`No ${activeFilter === 'all' ? '' : activeFilter + ' '}signals`}
            description='Try a different filter.'
          />
        ) : (
          <div className={cn(
            'overflow-hidden rounded-md border border-[var(--to-border)]/60 bg-[#090d13]',
            SIGNAL_TABLE_MIN_WIDTH,
          )}>
            <SignalBlotterHeader
              sortField={sortField}
              sortDir={sortDir}
              onSort={handleSort}
            />
            <div>
              {sorted.map((signal) => (
                <SignalBlotterRow
                  key={signal.id}
                  signal={signal}
                  broker={brokerMap[String(signal.id)]}
                  council={councilMap[String(signal.id)]}
                  onSelect={onSelectSignal}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
