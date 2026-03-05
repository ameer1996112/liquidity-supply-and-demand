'use client';

import { useMemo } from 'react';
import { Radio, Activity, TrendingUp, TrendingDown } from 'lucide-react';
import { formatDistanceToNowStrict } from 'date-fns';

import { useTradingSignals } from '@/hooks/useTradingSignals';
import {
  TradingSignal,
  TradingMode,
  getSymbol,
  getSide,
  getPnl,
} from '@/types/trading';
import { isSignalOpen } from '@/domain/metrics/tradingMetrics';
import {
  TableEmptyState,
  TableSkeleton,
} from '@/components/shared/TableStates';
import { ClientDate } from '@/components/ui/ClientDate';
import {
  EMPTY_VALUE,
  formatNumber,
  normalizeNegativeZero,
} from '@/lib/formatters';
import { cn } from '@/lib/utils';
import { DataTable, type DataTableColumn } from '@/components/shared/DataTable';

// ── Types ─────────────────────────────────────────────────────────────────────

interface ActiveTradesPanelProps {
  mode?: TradingMode;
  onSelectSignal: (signal: TradingSignal) => void;
  compact?: boolean;
}

// ── Cell components ───────────────────────────────────────────────────────────

function SideCell({ signal }: { signal: TradingSignal }) {
  const side = getSide(signal);
  const isBuy = side === 'buy';
  return (
    <div className='flex items-center gap-1.5'>
      <span className='font-mono text-xs font-bold text-text-primary'>
        {getSymbol(signal)}
      </span>
      <span
        className={cn(
          'inline-flex items-center gap-0.5 rounded px-1 py-0 font-mono text-[9px] font-bold',
          isBuy ? 'bg-long/15 text-long' : 'bg-short/15 text-short'
        )}
      >
        {isBuy ? (
          <TrendingUp className='h-2.5 w-2.5' />
        ) : (
          <TrendingDown className='h-2.5 w-2.5' />
        )}
        {side.toUpperCase()}
      </span>
    </div>
  );
}

function TriggerCell({ signal }: { signal: TradingSignal }) {
  const entryModel = (signal.entry_model ?? '').toLowerCase();
  const exitType = (signal.exit_type ?? '').toLowerCase();
  let label: string | null = null;
  let cls = '';

  if (exitType.includes('dir') || entryModel.includes('dir')) {
    label = 'DIR';
    cls = 'trigger-dir-close';
  } else if (entryModel.includes('boc') || entryModel.includes('break')) {
    label = 'BoC';
    cls = 'trigger-boc';
  } else if (
    entryModel.includes('flip') ||
    entryModel.includes('zone') ||
    signal.zone_type
  ) {
    label = 'FLIP';
    cls = 'trigger-flip';
  }

  if (!label) return <span className='text-text-dim'>—</span>;
  return (
    <span className={cn('rounded px-1.5 py-0 text-[9px] font-bold', cls)}>
      {label}
    </span>
  );
}

function EntryCell({ signal }: { signal: TradingSignal }) {
  const entry = signal.price ?? signal.entry;
  const symbol = getSymbol(signal);
  return (
    <span className='font-mono text-[11px] tabular-nums text-text-secondary'>
      {entry != null
        ? Number(entry).toFixed(symbol.includes('JPY') ? 3 : 5)
        : EMPTY_VALUE}
    </span>
  );
}

function RrCell({ signal }: { signal: TradingSignal }) {
  return (
    <span className='font-mono text-[11px] tabular-nums text-text-dim'>
      {signal.rr_ratio
        ? `1:${formatNumber(signal.rr_ratio, { decimals: 1 })}`
        : EMPTY_VALUE}
    </span>
  );
}

function AgeCell({ signal }: { signal: TradingSignal }) {
  return (
    <ClientDate
      className='font-mono text-[10px] tabular-nums text-text-dim'
      render={() =>
        formatDistanceToNowStrict(new Date(signal.created_at), {
          addSuffix: false,
        })
      }
    />
  );
}

function PnlCell({ signal }: { signal: TradingSignal }) {
  const pnl = normalizeNegativeZero(getPnl(signal));
  if (pnl == null) {
    return (
      <span className='font-mono text-xs text-text-dim'>{EMPTY_VALUE}</span>
    );
  }
  const isPos = pnl >= 0;
  return (
    <span
      className={cn(
        'font-mono text-xs font-bold tabular-nums',
        isPos ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]'
      )}
    >
      {pnl > 0 ? '+' : ''}
      {formatNumber(pnl, { decimals: 2 })}
    </span>
  );
}

function AccountCell({ signal }: { signal: TradingSignal }) {
  if (!signal.account_name)
    return <span className='text-[var(--to-text-dim)]'>—</span>;
  return (
    <span
      className='rounded bg-[var(--to-surface-raised)] px-1.5 py-0.5 font-mono text-[9px] text-[var(--to-text-dim)] truncate max-w-[80px] block'
      title={signal.account_name}
    >
      {signal.account_name}
    </span>
  );
}

// ── Panel ─────────────────────────────────────────────────────────────────────

export function ActiveTradesPanel({
  mode,
  onSelectSignal,
  compact = false,
}: ActiveTradesPanelProps) {
  const { data: signals = [], isLoading } = useTradingSignals(mode);
  const activeTrades = useMemo(() => signals.filter(isSignalOpen), [signals]);

  const columns: DataTableColumn<TradingSignal>[] = [
    {
      id: 'symbol',
      header: 'Symbol',
      render: (signal) => <SideCell signal={signal} />,
    },
    {
      id: 'trigger',
      header: 'Type',
      render: (signal) => <TriggerCell signal={signal} />,
    },
    {
      id: 'entry',
      header: 'Entry',
      isNumeric: true,
      align: 'right',
      render: (signal) => <EntryCell signal={signal} />,
    },
    {
      id: 'rr',
      header: 'R:R',
      isNumeric: true,
      align: 'right',
      render: (signal) => <RrCell signal={signal} />,
    },
    {
      id: 'age',
      header: 'Age',
      isNumeric: true,
      align: 'right',
      render: (signal) => <AgeCell signal={signal} />,
    },
    {
      id: 'account',
      header: 'Account',
      align: 'left',
      render: (signal) => <AccountCell signal={signal} />,
    },
    {
      id: 'pnl',
      header: 'PnL',
      isNumeric: true,
      align: 'right',
      render: (signal) => <PnlCell signal={signal} />,
    },
  ];

  return (
    <div className='to-panel flex h-full min-h-0 flex-col overflow-hidden'>
      {/* Header */}
      <div className='to-panel-header'>
        <div className='flex items-center gap-2'>
          {activeTrades.length > 0 ? (
            <span className='relative flex h-2 w-2'>
              <span className='absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--to-long)] opacity-60' />
              <span className='relative inline-flex h-2 w-2 rounded-full bg-[var(--to-long)]' />
            </span>
          ) : (
            <Radio className='h-3.5 w-3.5 text-[var(--to-text-dim)]' />
          )}
          <span className='panel-label'>Active Positions</span>
        </div>
        <span
          className={cn(
            'rounded px-2 py-0.5 font-mono text-[10px] font-bold tabular-nums',
            activeTrades.length > 0
              ? 'bg-[var(--to-long)]/15 text-[var(--to-long)]'
              : 'bg-[var(--to-surface-raised)] text-[var(--to-text-dim)]'
          )}
        >
          {activeTrades.length}
        </span>
      </div>

      {/* Body */}
      <div
        className={cn(
          'scrollbar-thin min-h-0 flex-1 overflow-y-auto',
          compact && 'py-0'
        )}
      >
        {isLoading ? (
          <div className='p-2'>
            <TableSkeleton rowCount={3} columnCount={6} />
          </div>
        ) : activeTrades.length === 0 ? (
          <TableEmptyState
            icon={<Activity className='h-4 w-4' />}
            title='No active positions'
            description={
              compact
                ? 'Waiting for the next valid setup'
                : 'Waiting for valid 5m entry confirmations'
            }
          />
        ) : (
          <DataTable<TradingSignal>
            columns={columns}
            data={activeTrades}
            compact
            stickyHeader={false}
            getRowId={(signal) => signal.id}
            onRowClick={onSelectSignal}
            getRowClassName={(signal) => {
              const pnl = getPnl(signal);
              if (pnl == null) return 'border-l-2 border-l-[var(--to-border)]';
              return pnl >= 0
                ? 'border-l-2 border-l-[var(--to-long)]/50'
                : 'border-l-2 border-l-[var(--to-short)]/50';
            }}
          />
        )}
      </div>
    </div>
  );
}
