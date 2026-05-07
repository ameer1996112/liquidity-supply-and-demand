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
  Crosshair,
  ShieldAlert,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TradingSignal, SignalStatus } from '@/types/trading';
import { getPnl } from '@/types/trading';
import type { CouncilSummary } from '@/lib/api';
import type { ActivePosition } from '@/hooks/usePositions';
import { DataTable, type DataTableColumn } from '@/components/shared/DataTable';
import { TableEmptyState } from '@/components/shared/TableStates';
import {
  Mono,
  PnLText,
} from '@/components/ui/typography';
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

// =============================================================================
// SAFE RENDER WRAPPER — prevents a single cell crash from collapsing the table
// =============================================================================

/**
 * Wraps a column render function with a try/catch. If the render throws,
 * logs the error and shows an 'ERR' indicator instead of propagating the
 * exception through DataTable's data.map() and silently emptying the table.
 */
function safeRender<T>(
  id: string,
  fn: (row: T) => React.ReactNode
): (row: T) => React.ReactNode {
  return (row: T) => {
    try {
      return fn(row);
    } catch (err) {
      console.error(`[SignalTable] ${id} render error:`, err, row);
      return (
        <span
          className='font-mono text-[9px] text-[var(--to-short)]/70'
          title={String(err)}
        >
          ERR
        </span>
      );
    }
  };
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
      className={cn('inline-flex items-center gap-1 w-full', align === 'right' && 'justify-end')}
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
        'inline-flex min-w-[54px] justify-center rounded border px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider',
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

  // Columns — computed inline so headers always reflect current sort state
  const columns: DataTableColumn<TradingSignal>[] = [
    {
      id: 'created_at',
      align: 'left',
      width: 'w-[64px]',
      header: <SortHeader field='created_at' label='Age' sortField={sortField} sortDir={sortDir} onSort={handleSort} />,
      render: (signal) => (
        <span
          className='inline-flex items-center rounded border border-[var(--to-border)]/60 bg-[var(--to-surface-raised)]/35 px-1.5 py-1 font-mono text-[10px] tabular-nums text-[var(--to-text-primary)]'
          style={{ fontFamily: 'var(--font-mono)' }}
          title={new Date(signal.created_at).toLocaleString()}
        >
          {relativeTime(signal.created_at)}
        </span>
      ),
    },
    {
      id: 'symbol',
      align: 'left',
      width: 'w-[136px]',
      header: <SortHeader field='symbol' label='Market' sortField={sortField} sortDir={sortDir} onSort={handleSort} />,
      render: (signal) => (
        <div className='inline-flex min-w-0 flex-col gap-1'>
          <Mono size='lg' bold className='text-text-primary tracking-wide'>
            {signal.symbol}
          </Mono>
          <div className='inline-flex flex-wrap gap-1'>
            {(signal as any).account_name && (
              <span
                style={{
                  fontSize: 9,
                  padding: '1px 5px',
                  borderRadius: 3,
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border)',
                  color: 'var(--text-muted)',
                  fontFamily: 'var(--font-mono)',
                  letterSpacing: '0.03em',
                  whiteSpace: 'nowrap',
                }}
              >
                {(signal as any).account_name}
              </span>
            )}
            {getSignalStrategyBadge(signal) && (
              <span
                style={{
                  fontSize: 9,
                  padding: '1px 5px',
                  borderRadius: 3,
                  background: 'color-mix(in srgb, var(--to-accent-blue) 12%, transparent)',
                  border: '1px solid color-mix(in srgb, var(--to-accent-blue) 30%, var(--border))',
                  color: 'var(--to-accent-blue)',
                  fontFamily: 'var(--font-mono)',
                  letterSpacing: '0.03em',
                  whiteSpace: 'nowrap',
                }}
              >
                {getSignalStrategyBadge(signal)}
              </span>
            )}
          </div>
        </div>
      ),
    },
    {
      id: 'side',
      align: 'left',
      width: 'w-[64px]',
      header: <SortHeader field='side' label='Bias' sortField={sortField} sortDir={sortDir} onSort={handleSort} />,
      render: (signal) => <SideBadge side={signal.side} />,
    },
    {
      id: 'entry',
      align: 'right',
      isNumeric: true,
      width: 'w-[176px]',
      header: <SortHeader field='entry' label='Trade Plan' align='right' sortField={sortField} sortDir={sortDir} onSort={handleSort} />,
      render: safeRender('entry', (signal) => {
        const broker = brokerMap[String(signal.id)];
        const entry = signal.entry ?? signal.price;
        const currentPrice = broker?.current_price;
        const sl = signal.sl ?? signal.stop_loss;
        const tp = signal.tp ?? signal.take_profit;
        const entryFormatted = formatSignalPrice(signal.symbol, entry);
        const slStr = formatSignalPrice(signal.symbol, sl);
        const tpStr = formatSignalPrice(signal.symbol, tp);
        const currPriceNum = currentPrice != null ? Number(currentPrice) : null;
        const titleText = currPriceNum != null && !isNaN(currPriceNum)
          ? `Live: ${formatSignalPrice(signal.symbol, currPriceNum)}`
          : `Entry: ${entryFormatted} · SL: ${slStr} · TP: ${tpStr}`;
        return (
          <div
            className='inline-flex flex-col items-end gap-1 font-mono text-[10px] tabular-nums'
            style={{ fontFamily: 'var(--font-mono)' }}
            title={titleText}
          >
            <span className='inline-flex items-center gap-1 text-[var(--to-text-secondary)]'>
              {currentPrice != null ? (
                <Wifi className='h-[9px] w-[9px] shrink-0 text-[var(--to-long)]/60' />
              ) : (
                <Crosshair className='h-[9px] w-[9px] shrink-0 text-[var(--to-text-dim)]/60' />
              )}
              <span className='text-[8px] uppercase tracking-wider text-[var(--to-text-dim)]'>Entry</span>
              <span className='font-semibold text-[var(--to-text-secondary)]'>{entryFormatted}</span>
            </span>
            <span className='inline-flex items-center gap-1'>
              <span className='rounded bg-[var(--to-short)]/10 px-1 py-0.5 text-[var(--to-short)]/85'>
                SL {slStr}
              </span>
              <span className='rounded bg-[var(--to-long)]/10 px-1 py-0.5 text-[var(--to-long)]/85'>
                TP {tpStr}
              </span>
            </span>
          </div>
        );
      }),
    },
    {
      id: 'pnl',
      align: 'right',
      isNumeric: true,
      width: 'w-[86px]',
      header: <SortHeader field='pnl' label='Result' align='right' sortField={sortField} sortDir={sortDir} onSort={handleSort} />,
      render: safeRender('pnl', (signal) => {
        const broker = brokerMap[String(signal.id)];
        const livePnl = broker?.live_pnl;
        const dbPnl = getPnl(signal);
        const shouldShowLivePnl = isOpenStatus(signal.status) && !hasRealizedClose(signal) && livePnl != null;

        if (shouldShowLivePnl) {
          const isPos = livePnl >= 0;
          return (
            <span
              className={cn(
                'inline-flex items-center gap-1 font-mono text-[10px] font-bold tabular-nums',
                isPos ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]',
              )}
              style={{ fontFamily: 'var(--font-mono)' }}
              title='Live broker P&L'
            >
              <span
                className={cn(
                  'h-1.5 w-1.5 rounded-full shrink-0 animate-pulse',
                  isPos ? 'bg-[var(--to-long)]' : 'bg-[var(--to-short)]',
                )}
              />
              {(() => {
                const n = Number(livePnl);
                return isNaN(n) ? '—' : `${n > 0 ? '+' : ''}${n.toFixed(2)}`;
              })()}
            </span>
          );
        }

        return <PnLText value={dbPnl} variant='currency' size='sm' />;
      }),
    },
    {
      id: 'risk',
      align: 'right',
      isNumeric: true,
      width: 'w-[92px]',
      header: <SortHeader field='risk' label='At Risk' align='right' sortField={sortField} sortDir={sortDir} onSort={handleSort} />,
      render: safeRender('risk', (signal) => {
        const risk = calculateJournalRisk(signal);
        return (
          <span
            className='inline-flex items-center justify-end gap-1 rounded border border-[var(--to-short)]/20 bg-[var(--to-short)]/8 px-1.5 py-1 font-mono text-[10px] font-bold tabular-nums text-[var(--to-short)]'
            style={{ fontFamily: 'var(--font-mono)' }}
            title={formatJournalRiskTitle(risk)}
          >
            <ShieldAlert className='h-3 w-3 opacity-70' strokeWidth={1.7} />
            {formatJournalRisk(risk)}
          </span>
        );
      }),
    },
    {
      id: 'setup_score',
      align: 'right',
      isNumeric: true,
      width: 'w-[76px]',
      header: <SortHeader field='setup_score' label='Setup Q' align='right' sortField={sortField} sortDir={sortDir} onSort={handleSort} />,
      render: (signal) => (
        <div className='inline-flex w-full justify-end'>
          <SetupScoreBadge signal={signal} compact />
        </div>
      ),
    },
    {
      id: 'score',
      align: 'right',
      isNumeric: true,
      width: 'w-[44px]',
      header: (
        <button
          type='button'
          className='inline-flex items-center justify-end gap-1 w-full'
          onClick={() => handleSort('score')}
        >
          <TrendingUp className='h-2.5 w-2.5' strokeWidth={1.5} />
          <span>AI Conv.</span>
          {sortField === 'score' ? (
            sortDir === 'asc' ? <ArrowUp className='h-2.5 w-2.5' /> : <ArrowDown className='h-2.5 w-2.5' />
          ) : (
            <ArrowUpDown className='h-2.5 w-2.5 opacity-30' />
          )}
        </button>
      ),
      render: (signal) => {
        const score = signal.score ?? signal.ai_confidence;
        if (score == null)
          return <span className='font-mono text-[10px] text-[var(--to-text-dim)]/40'>—</span>;
        const color =
          score >= 70 ? 'text-[var(--to-long)]' : score >= 50 ? 'text-[var(--to-warning)]' : 'text-[var(--to-short)]';
        return (
          <span
            className={cn('font-mono text-[10px] font-bold tabular-nums', color)}
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            {Math.round(score)}
          </span>
        );
      },
    },
    {
      id: 'council',
      align: 'right',
      isNumeric: true,
      width: 'w-[80px]',
      header: (
        <span className='inline-flex items-center justify-end gap-1 w-full'>
          <Brain className='h-2.5 w-2.5 opacity-60' strokeWidth={1.5} />
          <span>Council</span>
        </span>
      ),
      render: safeRender('council', (signal) => (
        <CouncilBadge
          summary={councilMap[String(signal.id)]}
          suppressPending={isTerminalStatus(signal.status)}
        />
      )),
    },
    {
      id: 'status',
      align: 'left',
      width: 'w-[80px]',
      header: <SortHeader field='status' label='State' sortField={sortField} sortDir={sortDir} onSort={handleSort} />,
      render: (signal) => {
        const broker = brokerMap[String(signal.id)];
        return <StatusBadge status={signal.status} isStale={broker?.is_stale} />;
      },
    },
  ];

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

      {/* Scrollable table */}
      <div className='flex-1 min-h-0 overflow-auto scrollbar-thin'>
        {sorted.length === 0 ? (
          <TableEmptyState
            title={`No ${activeFilter === 'all' ? '' : activeFilter + ' '}signals`}
            description='Try a different filter.'
          />
        ) : (
          <DataTable
            columns={columns}
            data={sorted}
            compact
            stickyHeader
            className='overflow-visible'
            getRowId={(signal) => signal.id}
            onRowClick={(signal) => onSelectSignal?.(signal)}
            getRowClassName={(signal) => {
              const broker = brokerMap[String(signal.id)];
              const border = sideBorderColor(signal.side);
              if (broker?.is_stale)      return cn('opacity-60 border-l-2', border);
              if (isOpenStatus(signal.status)) return cn('bg-blue-950/20 border-l-2', border);
              return cn('border-l-2', border);
            }}
          />
        )}
      </div>
    </div>
  );
}
