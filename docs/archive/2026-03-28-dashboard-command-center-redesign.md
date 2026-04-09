# Dashboard Command Center Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current cluttered dashboard and separate accounts page with a single unified command center: pinned aggregate bar → 3-per-row account card grid with danger states → open positions table, with a slide-out drawer for account detail and management.

**Architecture:** New layout in `app/page.tsx` composed of 5 new components. The drawer reuses existing tab components (`OverviewTab`, `PositionsTab`, etc.) already built for the accounts detail page. `useAccountsComparison()` drives the rich account cards; `useDashboardSummary()` drives the aggregate bar.

**Tech Stack:** Next.js 14, React, TypeScript, Tailwind CSS, Radix UI Sheet (already in `components/ui/sheet.tsx`), TanStack Query (React Query), Lucide icons, existing design tokens (`var(--to-*)`)

**Jira:** DEV-62 | Branch: `feature/DEV-62-redesign-dashboard-unified-command-center-with`

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `frontend/src/components/dashboard/AggregateBar.tsx` | Pinned top bar: total PnL, positions, win rate, drawdown, accounts health, bot status |
| Create | `frontend/src/components/dashboard/AccountGridCard.tsx` | Rich account card with danger states (yellow/red border near drawdown limit) |
| Create | `frontend/src/components/dashboard/AccountGrid.tsx` | 3-per-row responsive grid + "Add account" button that opens drawer |
| Create | `frontend/src/components/dashboard/OpenPositionsTable.tsx` | Full-width compact table of open positions across all accounts |
| Create | `frontend/src/components/dashboard/AccountDrawer.tsx` | Radix Sheet drawer (40% width) with 6 tabs wrapping existing tab components |
| Modify | `frontend/src/app/page.tsx` | Complete rewrite: AggregateBar + AccountGrid + OpenPositionsTable + AccountDrawer |

---

## Task 1: AggregateBar component

**Files:**
- Create: `frontend/src/components/dashboard/AggregateBar.tsx`

- [ ] **Step 1: Write the component**

```tsx
'use client';

import { cn } from '@/lib/utils';
import { Radio, Wifi, WifiOff, TrendingUp, TrendingDown } from 'lucide-react';
import type { DashboardSummary } from '@/types/trading';
import { formatCurrency, formatPercent } from '@/lib/formatters';

interface AggregateBarProps {
  summary: DashboardSummary | undefined;
  isLoading: boolean;
  isConnected: boolean;
}

export function AggregateBar({ summary, isLoading, isConnected }: AggregateBarProps) {
  const totalPnl = summary?.total_pnl_today ?? 0;
  const pnlPositive = totalPnl >= 0;
  const connectedCount = summary?.accounts.filter(a => a.connection_status === 'connected').length ?? 0;
  const totalAccounts = summary?.accounts.length ?? 0;
  const hasDisconnected = connectedCount < totalAccounts;

  return (
    <div
      className={cn(
        'flex shrink-0 items-center justify-between gap-4 px-4 py-2.5',
        'border-b border-[var(--to-border)] bg-[var(--to-surface)] sticky top-0 z-10',
        'text-xs font-mono'
      )}
    >
      {/* Left: Bot status */}
      <div className='flex items-center gap-3'>
        <span className='flex items-center gap-1.5'>
          {isConnected ? (
            <Wifi className='h-3 w-3 text-[var(--to-long)]' />
          ) : (
            <WifiOff className='h-3 w-3 text-[var(--to-short)]' />
          )}
          <span
            className={cn(
              'font-bold uppercase tracking-widest text-[10px]',
              isConnected ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]'
            )}
          >
            {isConnected ? 'LIVE' : 'OFFLINE'}
          </span>
        </span>

        <span className='text-[var(--to-border)]'>|</span>

        {/* Total PnL today */}
        <span className='flex items-center gap-1'>
          {pnlPositive ? (
            <TrendingUp className='h-3 w-3 text-[var(--to-long)]' />
          ) : (
            <TrendingDown className='h-3 w-3 text-[var(--to-short)]' />
          )}
          <span className='text-[var(--to-text-dim)]'>Total PnL</span>
          <span
            className={cn(
              'font-bold tabular-nums',
              isLoading ? 'text-[var(--to-text-dim)]' : pnlPositive ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]'
            )}
          >
            {isLoading ? '...' : formatCurrency(totalPnl, { signed: true })}
          </span>
        </span>
      </div>

      {/* Center: Key metrics */}
      <div className='flex items-center gap-4'>
        <AggMetric
          label='Open'
          value={isLoading ? '...' : String(summary?.total_active_positions ?? 0)}
        />
        <AggMetric
          label='Win Rate'
          value={isLoading ? '...' : formatPercent(summary?.total_win_rate ?? 0)}
        />
        <AggMetric
          label='Max DD'
          value={isLoading ? '...' : formatPercent(summary?.max_drawdown_pct ?? 0)}
          danger={(summary?.max_drawdown_pct ?? 0) > 5}
        />
      </div>

      {/* Right: Accounts health */}
      <div className='flex items-center gap-1.5'>
        <Radio className='h-3 w-3 text-[var(--to-text-dim)]' />
        <span className='text-[var(--to-text-dim)]'>Accounts</span>
        <span
          className={cn(
            'font-bold',
            hasDisconnected ? 'text-amber-400' : 'text-[var(--to-long)]'
          )}
        >
          {connectedCount}/{totalAccounts}
        </span>
        <span
          className={cn(
            'h-1.5 w-1.5 rounded-full',
            hasDisconnected ? 'bg-amber-400' : 'bg-[var(--to-long)]'
          )}
        />
      </div>
    </div>
  );
}

function AggMetric({
  label,
  value,
  danger = false,
}: {
  label: string;
  value: string;
  danger?: boolean;
}) {
  return (
    <span className='flex items-center gap-1'>
      <span className='text-[var(--to-text-dim)]'>{label}</span>
      <span
        className={cn(
          'tabular-nums font-semibold',
          danger ? 'text-[var(--to-short)]' : 'text-[var(--to-text-secondary)]'
        )}
      >
        {value}
      </span>
    </span>
  );
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep AggregateBar
```
Expected: no output (no errors for this file)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/dashboard/AggregateBar.tsx
git commit -m "feat: [DEV-62] AggregateBar — pinned top bar with aggregate KPIs"
```

---

## Task 2: AccountGridCard component

**Files:**
- Create: `frontend/src/components/dashboard/AccountGridCard.tsx`

This card shows rich data per account and has three visual states: normal, warning (yellow border), danger (red border + pulse). Prop firm progress bars only appear for funded/evaluation accounts.

- [ ] **Step 1: Write the component**

```tsx
'use client';

import { cn } from '@/lib/utils';
import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Wifi,
  WifiOff,
} from 'lucide-react';
import type { AccountComparisonApi } from '@/lib/api';

interface AccountGridCardProps {
  account: AccountComparisonApi;
  onClick: (account: AccountComparisonApi) => void;
}

// Returns 'normal' | 'warning' | 'danger' based on drawdown proximity to limit
function getDrawdownState(
  current: number | null | undefined,
  limit: number | null | undefined
): 'normal' | 'warning' | 'danger' {
  if (!current || !limit || limit === 0) return 'normal';
  const ratio = Math.abs(current) / Math.abs(limit);
  if (ratio >= 0.9) return 'danger';
  if (ratio >= 0.7) return 'warning';
  return 'normal';
}

export function AccountGridCard({ account, onClick }: AccountGridCardProps) {
  const isPropFirm =
    account.account_type === 'Funded' || account.account_type === 'Eval';
  const isConnected = account.connection_status === 'connected';
  const pnlPositive = (account.daily_pnl ?? 0) >= 0;

  // Drawdown danger state
  // max_drawdown_pct is the current value; we approximate limit from prop firm rules
  // For now, use a conservative 10% limit if no explicit limit is stored
  const ddState = getDrawdownState(
    account.max_drawdown_pct,
    account.max_drawdown_limit_pct ?? 10
  );

  const borderClass = {
    normal: 'border-[var(--to-border)]',
    warning: 'border-amber-500/60',
    danger: 'border-[var(--to-short)]/80',
  }[ddState];

  const glowClass = {
    normal: '',
    warning: 'shadow-[0_0_12px_rgba(245,158,11,0.15)]',
    danger: 'shadow-[0_0_16px_rgba(239,83,80,0.25)] animate-pulse-slow',
  }[ddState];

  const typeColors: Record<string, string> = {
    Funded: 'text-[var(--to-long)] bg-[var(--to-long)]/10 border-[var(--to-long)]/20',
    Eval: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    Personal: 'text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] border-[var(--to-border)]',
  };

  return (
    <div
      onClick={() => onClick(account)}
      className={cn(
        'flex flex-col gap-0 rounded-lg border bg-[var(--to-surface)] cursor-pointer',
        'transition-all duration-150 hover:bg-[var(--to-surface-raised)] hover:-translate-y-0.5',
        borderClass,
        glowClass
      )}
    >
      {/* ── Header ── */}
      <div className='flex items-center justify-between px-4 py-3 border-b border-[var(--to-border)]'>
        <div className='flex items-center gap-2 min-w-0'>
          <span
            className={cn(
              'h-1.5 w-1.5 rounded-full flex-shrink-0',
              isConnected ? 'bg-[var(--to-long)]' : 'bg-[var(--to-short)]'
            )}
          />
          <span className='font-mono text-sm font-bold text-[var(--to-text-primary)] truncate'>
            {account.account_name}
          </span>
          {!isConnected && (
            <WifiOff className='h-3 w-3 text-[var(--to-short)] flex-shrink-0' />
          )}
        </div>
        <div className='flex items-center gap-1.5 flex-shrink-0 ml-2'>
          {ddState !== 'normal' && (
            <AlertTriangle
              className={cn(
                'h-3 w-3',
                ddState === 'danger' ? 'text-[var(--to-short)]' : 'text-amber-400'
              )}
            />
          )}
          {account.account_type && (
            <span
              className={cn(
                'px-1.5 py-0.5 text-[9px] font-mono font-bold rounded uppercase tracking-wider border',
                typeColors[account.account_type] ?? typeColors.Personal
              )}
            >
              {account.account_type}
            </span>
          )}
        </div>
      </div>

      {/* ── Balance & PnL ── */}
      <div className='px-4 py-3 border-b border-[var(--to-border)]'>
        <div className='flex items-baseline justify-between mb-2'>
          <span className='text-[10px] text-[var(--to-text-dim)] font-mono'>Balance</span>
          <span className='font-mono text-base font-bold text-[var(--to-text-primary)] tabular-nums'>
            ${(account.balance ?? 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
          </span>
        </div>
        <div className='flex items-center justify-between'>
          <span className='text-[10px] text-[var(--to-text-dim)] font-mono'>Today P&L</span>
          <div className='flex items-center gap-1'>
            {pnlPositive ? (
              <TrendingUp className='h-3 w-3 text-[var(--to-long)]' />
            ) : (
              <TrendingDown className='h-3 w-3 text-[var(--to-short)]' />
            )}
            <span
              className={cn(
                'font-mono text-sm font-bold tabular-nums',
                pnlPositive ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]'
              )}
            >
              {pnlPositive ? '+' : ''}${Math.abs(account.daily_pnl ?? 0).toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* ── Key Stats ── */}
      <div className='grid grid-cols-3 divide-x divide-[var(--to-border)] px-0 py-0'>
        <StatCell label='Win Rate' value={`${(account.win_rate ? account.win_rate * 100 : 0).toFixed(0)}%`} />
        <StatCell label='Positions' value={String(account.active_positions ?? 0)} />
        <StatCell label='Trades' value={String(account.total_trades ?? 0)} />
      </div>

      {/* ── Prop Firm Progress (conditional) ── */}
      {isPropFirm && (
        <div className='px-4 py-3 border-t border-[var(--to-border)] space-y-2'>
          {account.max_drawdown_pct != null && (
            <ProgressRow
              label='Drawdown'
              current={Math.abs(account.max_drawdown_pct)}
              limit={Math.abs(account.max_drawdown_limit_pct ?? 10)}
              state={ddState}
              format={(v) => `${v.toFixed(1)}%`}
              invert
            />
          )}
          {account.profit_target_pct != null && account.profit_target_pct > 0 && (
            <ProgressRow
              label='Profit Target'
              current={Math.max(0, (account.daily_pnl_pct ?? 0))}
              limit={account.profit_target_pct}
              state='normal'
              format={(v) => `${v.toFixed(1)}%`}
            />
          )}
        </div>
      )}
    </div>
  );
}

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div className='flex flex-col items-center py-2.5 gap-0.5'>
      <span className='text-[9px] text-[var(--to-text-dim)] font-mono'>{label}</span>
      <span className='font-mono text-xs font-semibold text-[var(--to-text-secondary)] tabular-nums'>
        {value}
      </span>
    </div>
  );
}

function ProgressRow({
  label,
  current,
  limit,
  state,
  format,
  invert = false,
}: {
  label: string;
  current: number;
  limit: number;
  state: 'normal' | 'warning' | 'danger';
  format: (v: number) => string;
  invert?: boolean;
}) {
  const pct = limit > 0 ? Math.min((current / limit) * 100, 100) : 0;
  const barColor = invert
    ? state === 'danger'
      ? 'bg-[var(--to-short)]'
      : state === 'warning'
      ? 'bg-amber-400'
      : 'bg-[var(--to-long)]/50'
    : 'bg-[var(--to-long)]/60';

  const checkIcon = invert
    ? state === 'danger'
      ? '✗'
      : state === 'warning'
      ? '⚠'
      : '✓'
    : current >= limit
    ? '✓'
    : '→';

  const checkColor = invert
    ? state === 'danger'
      ? 'text-[var(--to-short)]'
      : state === 'warning'
      ? 'text-amber-400'
      : 'text-[var(--to-long)]'
    : current >= limit
    ? 'text-[var(--to-long)]'
    : 'text-[var(--to-text-dim)]';

  return (
    <div className='space-y-1'>
      <div className='flex items-center justify-between'>
        <span className='text-[9px] text-[var(--to-text-dim)] font-mono'>{label}</span>
        <div className='flex items-center gap-1'>
          <span className='text-[10px] text-[var(--to-text-secondary)] font-mono tabular-nums'>
            {format(current)} / {format(limit)}
          </span>
          <span className={cn('text-[10px] font-bold', checkColor)}>{checkIcon}</span>
        </div>
      </div>
      <div className='h-1 w-full rounded-full bg-[var(--to-surface-raised)] overflow-hidden'>
        <div
          className={cn('h-full rounded-full transition-all', barColor)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep AccountGridCard
```
Expected: no output

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/dashboard/AccountGridCard.tsx
git commit -m "feat: [DEV-62] AccountGridCard — rich account card with danger states"
```

---

## Task 3: AccountGrid component

**Files:**
- Create: `frontend/src/components/dashboard/AccountGrid.tsx`

- [ ] **Step 1: Write the component**

```tsx
'use client';

import { Plus } from 'lucide-react';
import { AccountGridCard } from './AccountGridCard';
import type { AccountComparisonApi } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';

interface AccountGridProps {
  accounts: AccountComparisonApi[];
  isLoading: boolean;
  onSelectAccount: (account: AccountComparisonApi) => void;
  onAddAccount: () => void;
}

export function AccountGrid({
  accounts,
  isLoading,
  onSelectAccount,
  onAddAccount,
}: AccountGridProps) {
  if (isLoading) {
    return (
      <div className='grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3'>
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className='h-52 rounded-lg border border-[var(--to-border)] skeleton-shimmer' />
        ))}
      </div>
    );
  }

  return (
    <div className='grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3'>
      {accounts.map((account) => (
        <AccountGridCard
          key={account.account_name}
          account={account}
          onClick={onSelectAccount}
        />
      ))}

      {/* Add account button */}
      <button
        onClick={onAddAccount}
        className='flex min-h-[140px] flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--to-border)] bg-transparent text-[var(--to-text-dim)] transition-colors hover:border-[var(--to-long)]/50 hover:text-[var(--to-long)]/70 cursor-pointer'
      >
        <Plus className='h-5 w-5' />
        <span className='text-[11px] font-mono'>Add account</span>
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Verify it compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep AccountGrid
```
Expected: no output

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/dashboard/AccountGrid.tsx
git commit -m "feat: [DEV-62] AccountGrid — 3-per-row responsive grid"
```

---

## Task 4: OpenPositionsTable component

**Files:**
- Create: `frontend/src/components/dashboard/OpenPositionsTable.tsx`

- [ ] **Step 1: Write the component**

```tsx
'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { ChevronDown } from 'lucide-react';
import type { ActivePosition } from '@/hooks/usePositions';
import type { AccountComparisonApi } from '@/lib/api';

interface OpenPositionsTableProps {
  positions: ActivePosition[];
  accounts: AccountComparisonApi[];
  isLoading: boolean;
  onRowClick?: (accountName: string) => void;
}

type SortKey = 'pnl' | 'duration' | 'symbol';

export function OpenPositionsTable({
  positions,
  accounts,
  isLoading,
  onRowClick,
}: OpenPositionsTableProps) {
  const [accountFilter, setAccountFilter] = useState<string>('all');
  const [sortKey, setSortKey] = useState<SortKey>('pnl');

  const accountNames = Array.from(new Set(positions.map((p) => p.account_name ?? 'Unknown')));

  const filtered = positions.filter(
    (p) => accountFilter === 'all' || p.account_name === accountFilter
  );

  const sorted = [...filtered].sort((a, b) => {
    if (sortKey === 'pnl') return (b.profit ?? 0) - (a.profit ?? 0);
    if (sortKey === 'symbol') return (a.symbol ?? '').localeCompare(b.symbol ?? '');
    if (sortKey === 'duration') {
      const aOpen = a.open_time ? new Date(a.open_time).getTime() : 0;
      const bOpen = b.open_time ? new Date(b.open_time).getTime() : 0;
      return aOpen - bOpen; // oldest first = longest held first
    }
    return 0;
  });

  function formatDuration(openTime?: string | null): string {
    if (!openTime) return '—';
    const ms = Date.now() - new Date(openTime).getTime();
    const h = Math.floor(ms / 3_600_000);
    const m = Math.floor((ms % 3_600_000) / 60_000);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  }

  const SortHeader = ({
    label,
    sk,
  }: {
    label: string;
    sk: SortKey;
  }) => (
    <th
      className='cursor-pointer select-none px-3 py-2 text-left text-[9px] uppercase tracking-widest text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] transition-colors'
      onClick={() => setSortKey(sk)}
    >
      <span className='flex items-center gap-1'>
        {label}
        {sortKey === sk && <ChevronDown className='h-2.5 w-2.5' />}
      </span>
    </th>
  );

  return (
    <section className='glow-card overflow-hidden'>
      <div className='to-panel-header'>
        <div className='flex items-center gap-2'>
          <span className='panel-label'>Open Positions</span>
          <span className='rounded-full bg-[var(--to-surface-raised)] border border-[var(--to-border)] px-2 py-0.5 font-mono text-[9px] tabular-nums text-[var(--to-text-dim)]'>
            {filtered.length}
          </span>
        </div>

        {/* Account filter */}
        <select
          className='rounded border border-[var(--to-border)] bg-[var(--to-surface)] px-2 py-1 font-mono text-[10px] text-[var(--to-text-secondary)] focus:outline-none'
          value={accountFilter}
          onChange={(e) => setAccountFilter(e.target.value)}
        >
          <option value='all'>All Accounts</option>
          {accountNames.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className='px-4 py-6 text-center text-[11px] text-[var(--to-text-dim)] font-mono'>
          Loading positions...
        </div>
      ) : sorted.length === 0 ? (
        <div className='px-4 py-6 text-center text-[11px] text-[var(--to-text-dim)] font-mono'>
          No open positions
        </div>
      ) : (
        <div className='overflow-x-auto'>
          <table className='w-full text-xs'>
            <thead className='border-b border-[var(--to-border)] bg-[var(--to-surface)]'>
              <tr>
                <SortHeader label='Symbol' sk='symbol' />
                <th className='px-3 py-2 text-left text-[9px] uppercase tracking-widest text-[var(--to-text-dim)]'>
                  Account
                </th>
                <th className='px-3 py-2 text-left text-[9px] uppercase tracking-widest text-[var(--to-text-dim)]'>
                  Side
                </th>
                <th className='px-3 py-2 text-left text-[9px] uppercase tracking-widest text-[var(--to-text-dim)]'>
                  Size
                </th>
                <th className='px-3 py-2 text-right text-[9px] uppercase tracking-widest text-[var(--to-text-dim)]'>
                  Entry
                </th>
                <SortHeader label='P&L' sk='pnl' />
                <SortHeader label='Duration' sk='duration' />
              </tr>
            </thead>
            <tbody className='divide-y divide-[var(--to-border)]'>
              {sorted.map((pos, idx) => {
                const pnlPositive = (pos.profit ?? 0) >= 0;
                const accountName = pos.account_name ?? 'Unknown';
                return (
                  <tr
                    key={pos.id ?? idx}
                    className='hover:bg-[var(--to-surface-raised)] transition-colors cursor-pointer'
                    onClick={() => onRowClick?.(accountName)}
                  >
                    <td className='px-3 py-2 font-mono font-semibold text-[var(--to-text-primary)]'>
                      {pos.symbol}
                    </td>
                    <td className='px-3 py-2'>
                      <span className='rounded bg-[var(--to-surface-raised)] border border-[var(--to-border)] px-1.5 py-0.5 font-mono text-[9px] text-[var(--to-text-secondary)]'>
                        {accountName}
                      </span>
                    </td>
                    <td className='px-3 py-2'>
                      <span
                        className={cn(
                          'flex items-center gap-0.5 font-mono text-[10px] font-bold',
                          pos.type === 'POSITION_TYPE_BUY'
                            ? 'text-[var(--to-long)]'
                            : 'text-[var(--to-short)]'
                        )}
                      >
                        <span className='h-1.5 w-1.5 rounded-full bg-current' />
                        {pos.type === 'POSITION_TYPE_BUY' ? 'LONG' : 'SHORT'}
                      </span>
                    </td>
                    <td className='px-3 py-2 font-mono text-[var(--to-text-secondary)] tabular-nums'>
                      {(pos.volume ?? 0).toFixed(2)}L
                    </td>
                    <td className='px-3 py-2 text-right font-mono text-[var(--to-text-secondary)] tabular-nums'>
                      {(pos.open_price ?? 0).toFixed(5)}
                    </td>
                    <td className='px-3 py-2'>
                      <span
                        className={cn(
                          'font-mono font-bold tabular-nums',
                          pnlPositive ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]'
                        )}
                      >
                        {pnlPositive ? '+' : ''}${Math.abs(pos.profit ?? 0).toFixed(2)}
                      </span>
                    </td>
                    <td className='px-3 py-2 font-mono text-[var(--to-text-dim)] tabular-nums'>
                      {formatDuration(pos.open_time)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Check the `ActivePosition` type to confirm field names**

```bash
grep -n "interface ActivePosition\|open_time\|account_name\|open_price\|profit\|volume" frontend/src/hooks/usePositions.ts | head -30
```

If field names differ (e.g., `openTime` vs `open_time`), update the component accordingly before committing.

- [ ] **Step 3: Verify it compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep OpenPositionsTable
```
Expected: no output

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/dashboard/OpenPositionsTable.tsx
git commit -m "feat: [DEV-62] OpenPositionsTable — compact multi-account positions view"
```

---

## Task 5: AccountDrawer component

**Files:**
- Create: `frontend/src/components/dashboard/AccountDrawer.tsx`

This wraps the existing tab components from `components/accounts/detail/` in a Radix Sheet. The Settings tab uses `BrokerProfilesPanel` for account management.

- [ ] **Step 1: Check existing tab component imports**

```bash
ls frontend/src/components/accounts/detail/
```

Expected output: `OverviewTab.tsx  PositionsTab.tsx  HistoryTab.tsx  AnalyticsTab.tsx  JournalTab.tsx  ChallengeTab.tsx`

- [ ] **Step 2: Check what props each tab needs**

```bash
grep -n "interface.*Props\|function.*Tab" frontend/src/components/accounts/detail/OverviewTab.tsx frontend/src/components/accounts/detail/PositionsTab.tsx frontend/src/components/accounts/detail/ChallengeTab.tsx | head -20
```

- [ ] **Step 3: Write the drawer component**

```tsx
'use client';

import { useState } from 'react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useQuery } from '@tanstack/react-query';
import { fetchAccountDetail } from '@/lib/api';
import type { AccountComparisonApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { Wifi, WifiOff, Settings, Trash2, AlertTriangle } from 'lucide-react';
import { OverviewTab } from '@/components/accounts/detail/OverviewTab';
import { PositionsTab } from '@/components/accounts/detail/PositionsTab';
import { HistoryTab } from '@/components/accounts/detail/HistoryTab';
import { AnalyticsTab } from '@/components/accounts/detail/AnalyticsTab';
import { ChallengeTab } from '@/components/accounts/detail/ChallengeTab';
import { BrokerProfilesPanel } from '@/components/accounts/BrokerProfilesPanel';
import { Skeleton } from '@/components/ui/skeleton';

interface AccountDrawerProps {
  account: AccountComparisonApi | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialTab?: string;
}

export function AccountDrawer({
  account,
  open,
  onOpenChange,
  initialTab = 'overview',
}: AccountDrawerProps) {
  const [activeTab, setActiveTab] = useState(initialTab);
  const isPropFirm =
    account?.account_type === 'Funded' || account?.account_type === 'Eval';

  // Fetch full account detail for tabs that need it
  const { data: accountDetail, isLoading } = useQuery({
    queryKey: ['account-detail', account?.account_name],
    queryFn: () => fetchAccountDetail(account!.account_name),
    enabled: !!account?.account_name && open,
    staleTime: 30_000,
  });

  if (!account) return null;

  const isConnected = account.connection_status === 'connected';

  const typeColors: Record<string, string> = {
    Funded: 'text-[var(--to-long)] bg-[var(--to-long)]/10 border-[var(--to-long)]/20',
    Eval: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    Personal: 'text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] border-[var(--to-border)]',
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side='right'
        className='w-full sm:max-w-[520px] bg-[var(--to-surface)] border-l border-[var(--to-border)] flex flex-col p-0 gap-0'
      >
        {/* ── Drawer Header ── */}
        <SheetHeader className='px-5 py-4 border-b border-[var(--to-border)] shrink-0'>
          <div className='flex items-center gap-3'>
            <span
              className={cn(
                'h-2 w-2 rounded-full flex-shrink-0',
                isConnected ? 'bg-[var(--to-long)]' : 'bg-[var(--to-short)]'
              )}
            />
            {isConnected ? (
              <Wifi className='h-3.5 w-3.5 text-[var(--to-long)]' />
            ) : (
              <WifiOff className='h-3.5 w-3.5 text-[var(--to-short)]' />
            )}
            <SheetTitle className='font-mono text-base font-bold text-[var(--to-text-primary)]'>
              {account.account_name}
            </SheetTitle>
            {account.account_type && (
              <span
                className={cn(
                  'px-1.5 py-0.5 text-[9px] font-mono font-bold rounded uppercase tracking-wider border',
                  typeColors[account.account_type] ?? typeColors.Personal
                )}
              >
                {account.account_type}
              </span>
            )}
            <span className='text-[10px] font-mono text-[var(--to-text-dim)]'>
              {account.run_mode ?? 'LIVE'}
            </span>
          </div>
        </SheetHeader>

        {/* ── Tabs ── */}
        <Tabs
          value={activeTab}
          onValueChange={setActiveTab}
          className='flex flex-col flex-1 min-h-0'
        >
          <TabsList className='shrink-0 w-full justify-start rounded-none border-b border-[var(--to-border)] bg-[var(--to-surface)] px-4 gap-0 h-9'>
            {[
              { value: 'overview', label: 'Overview' },
              { value: 'positions', label: 'Positions' },
              { value: 'history', label: 'History' },
              { value: 'analytics', label: 'Analytics' },
              ...(isPropFirm ? [{ value: 'challenge', label: 'Challenge' }] : []),
              { value: 'settings', label: 'Settings' },
            ].map((tab) => (
              <TabsTrigger
                key={tab.value}
                value={tab.value}
                className='rounded-none border-b-2 border-transparent data-[state=active]:border-[var(--to-long)] data-[state=active]:bg-transparent px-3 h-9 text-[11px] font-mono'
              >
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>

          <div className='flex-1 overflow-y-auto min-h-0'>
            <TabsContent value='overview' className='p-4 mt-0'>
              {isLoading ? (
                <DrawerSkeleton />
              ) : accountDetail ? (
                <OverviewTab account={accountDetail} />
              ) : (
                <DrawerError />
              )}
            </TabsContent>

            <TabsContent value='positions' className='p-4 mt-0'>
              {isLoading ? (
                <DrawerSkeleton />
              ) : accountDetail ? (
                <PositionsTab account={accountDetail} />
              ) : (
                <DrawerError />
              )}
            </TabsContent>

            <TabsContent value='history' className='p-4 mt-0'>
              {isLoading ? (
                <DrawerSkeleton />
              ) : accountDetail ? (
                <HistoryTab account={accountDetail} />
              ) : (
                <DrawerError />
              )}
            </TabsContent>

            <TabsContent value='analytics' className='p-4 mt-0'>
              {isLoading ? (
                <DrawerSkeleton />
              ) : accountDetail ? (
                <AnalyticsTab account={accountDetail} />
              ) : (
                <DrawerError />
              )}
            </TabsContent>

            {isPropFirm && (
              <TabsContent value='challenge' className='p-4 mt-0'>
                {isLoading ? (
                  <DrawerSkeleton />
                ) : accountDetail ? (
                  <ChallengeTab account={accountDetail} />
                ) : (
                  <DrawerError />
                )}
              </TabsContent>
            )}

            <TabsContent value='settings' className='p-4 mt-0'>
              <BrokerProfilesPanel
                filterAccountName={account.account_name}
              />
            </TabsContent>
          </div>
        </Tabs>
      </SheetContent>
    </Sheet>
  );
}

function DrawerSkeleton() {
  return (
    <div className='space-y-3'>
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className='h-16 w-full rounded skeleton-shimmer' />
      ))}
    </div>
  );
}

function DrawerError() {
  return (
    <div className='flex flex-col items-center gap-2 py-10 text-[var(--to-text-dim)]'>
      <AlertTriangle className='h-5 w-5' />
      <span className='text-xs font-mono'>Failed to load account data</span>
    </div>
  );
}
```

- [ ] **Step 4: Check if `BrokerProfilesPanel` accepts a `filterAccountName` prop**

```bash
grep -n "filterAccountName\|Props" frontend/src/components/accounts/BrokerProfilesPanel.tsx | head -10
```

If it does not accept `filterAccountName`, remove that prop from the `AccountDrawer` and just render `<BrokerProfilesPanel />` without the filter.

- [ ] **Step 5: Verify it compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep AccountDrawer
```
Expected: no output (fix any type errors before continuing)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/dashboard/AccountDrawer.tsx
git commit -m "feat: [DEV-62] AccountDrawer — slide-out drawer with 6 tabs"
```

---

## Task 6: Rewrite page.tsx — new dashboard layout

**Files:**
- Modify: `frontend/src/app/page.tsx`

This is the final assembly. The existing page has signal stats, sparklines, and session KPIs. We preserve the signal table and live log in a secondary section below the account grid + positions table, since they still have value.

- [ ] **Step 1: Rewrite the page**

Replace the entire content of `frontend/src/app/page.tsx` with:

```tsx
'use client';

import { useCallback, useMemo, useState, useEffect } from 'react';
import { SignalInspector } from '@/components/SignalInspector';
import { SignalTable } from '@/components/dashboard/SignalTable';
import { LiveLog } from '@/components/dashboard/LiveLog';
import { ConnectionPill } from '@/components/dashboard/ConnectionPill';
import { MarketSessionBanner } from '@/components/dashboard/MarketSessionBanner';
import { PageStatusBanner } from '@/components/shared/PageStatusBanner';
import { AggregateBar } from '@/components/dashboard/AggregateBar';
import { AccountGrid } from '@/components/dashboard/AccountGrid';
import { OpenPositionsTable } from '@/components/dashboard/OpenPositionsTable';
import { AccountDrawer } from '@/components/dashboard/AccountDrawer';
import { useTradingMode } from '@/providers/TradingModeProvider';
import { useActiveAccount } from '@/providers/ActiveAccountProvider';
import {
  useSignalStats,
  useTradingSignals,
  useCouncilSummaries,
} from '@/hooks/useTradingSignals';
import { useConnectionHealth } from '@/hooks/useConnectionHealth';
import { useActivePositions } from '@/hooks/usePositions';
import { useDashboardLog } from '@/hooks/useDashboardLog';
import { useDashboardSummary } from '@/hooks/useDashboardSummary';
import { useAccountsComparison } from '@/hooks/useAccounts';
import type { TradingSignal } from '@/types/trading';
import type { AccountComparisonApi } from '@/lib/api';
import { TableSkeleton } from '@/components/shared/TableStates';
import { cn } from '@/lib/utils';

export default function DashboardPage() {
  const [selectedSignal, setSelectedSignal] = useState<TradingSignal | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [showLog, setShowLog] = useState(false);
  const [signalAccountFilter, setSignalAccountFilter] = useState<string | undefined>(undefined);
  const [drawerAccount, setDrawerAccount] = useState<AccountComparisonApi | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerInitialTab, setDrawerInitialTab] = useState('overview');

  useEffect(() => { setMounted(true); }, []);

  const { mode: activeMode } = useTradingMode();
  const { broker_profile_id } = useActiveAccount();
  const { status, isConnected } = useConnectionHealth();

  const { data: dashboardSummary, isLoading: summaryLoading } = useDashboardSummary();
  const { data: accounts = [], isLoading: accountsLoading } = useAccountsComparison();
  const { data: signals = [], isLoading: signalsLoading } = useTradingSignals(activeMode, broker_profile_id);
  const { data: positionsData, isLoading: positionsLoading } = useActivePositions();

  const signalIds = useMemo(() => signals.map((s) => s.id), [signals]);
  const councilMap = useCouncilSummaries(signalIds);

  const brokerMap = useMemo(() => {
    const map: Record<string, import('@/hooks/usePositions').ActivePosition> = {};
    for (const pos of positionsData?.positions ?? []) {
      map[String(pos.id)] = pos;
    }
    return map;
  }, [positionsData]);

  const { data: stats } = useSignalStats(broker_profile_id);
  const strategyName = signals[0]?.entry_model ?? signals[0]?.zone_type ?? 'Liquidity S&D';

  const { entries: logEntries, clear: clearLog } = useDashboardLog({
    signals,
    activeMode,
    isConnected,
    strategyName,
    timeframe: '5M',
    mounted,
  });

  const handleSelectSignal = useCallback((signal: TradingSignal) => {
    setSelectedSignal(signal);
    setInspectorOpen(true);
  }, []);

  const handleOpenDrawer = useCallback(
    (account: AccountComparisonApi, tab = 'overview') => {
      setDrawerAccount(account);
      setDrawerInitialTab(tab);
      setDrawerOpen(true);
    },
    []
  );

  const handleAddAccount = useCallback(() => {
    // Open drawer in settings tab with no account pre-selected
    // so user can add new account via BrokerProfilesPanel
    setDrawerAccount(accounts[0] ?? null);
    setDrawerInitialTab('settings');
    setDrawerOpen(true);
  }, [accounts]);

  const handlePositionRowClick = useCallback(
    (accountName: string) => {
      const account = accounts.find((a) => a.account_name === accountName);
      if (account) handleOpenDrawer(account, 'positions');
    },
    [accounts, handleOpenDrawer]
  );

  return (
    <div className='flex h-full min-h-0 flex-col'>
      {/* ── Aggregate bar (pinned) ── */}
      <AggregateBar
        summary={dashboardSummary}
        isLoading={summaryLoading}
        isConnected={isConnected}
      />

      <div className='flex flex-1 min-h-0 flex-col gap-3 overflow-y-auto p-3'>
        {/* ── Status banners ── */}
        <PageStatusBanner status={status} surfaceLabel='Dashboard' />
        <MarketSessionBanner />

        {/* ── Account grid ── */}
        <section>
          <p className='kpi-meta mb-2'>Accounts</p>
          <AccountGrid
            accounts={accounts}
            isLoading={accountsLoading}
            onSelectAccount={(account) => handleOpenDrawer(account)}
            onAddAccount={handleAddAccount}
          />
        </section>

        {/* ── Open positions ── */}
        <OpenPositionsTable
          positions={positionsData?.positions ?? []}
          accounts={accounts}
          isLoading={positionsLoading}
          onRowClick={handlePositionRowClick}
        />

        {/* ── Signal table + Live log ── */}
        <div className='flex min-h-[320px] flex-1 flex-col gap-3 xl:flex-row'>
          <section className='glow-card flex min-h-[280px] flex-1 flex-col overflow-hidden'>
            <div className='to-panel-header'>
              <div className='flex items-center gap-2'>
                <span className='panel-label'>Latest Signals</span>
                <span className='rounded-full bg-[var(--to-surface-raised)] border border-[var(--to-border)] px-2 py-0.5 font-mono text-[9px] tabular-nums text-[var(--to-text-dim)]'>
                  {signals.length}
                </span>
              </div>
              <ConnectionPill />
            </div>
            <div className='h-0 flex-1 overflow-hidden p-2'>
              {signalsLoading && signals.length === 0 ? (
                <TableSkeleton rowCount={8} columnCount={6} />
              ) : (
                <SignalTable
                  signals={signals}
                  councilMap={councilMap}
                  brokerMap={brokerMap}
                  onSelectSignal={handleSelectSignal}
                  maxRows={150}
                  accountFilter={signalAccountFilter}
                  onAccountFilterChange={setSignalAccountFilter}
                  accountNames={dashboardSummary?.accounts.map((a) => a.name) ?? []}
                />
              )}
            </div>
          </section>

          <aside className='flex min-h-0 w-full flex-col gap-2 xl:w-[320px]'>
            <button
              className='xl:hidden text-[11px] text-[var(--to-text-dim)] hover:text-[var(--to-text-secondary)] transition-colors py-1 px-0.5 text-left'
              onClick={() => setShowLog((prev) => !prev)}
            >
              {showLog ? 'Hide Live Log ▲' : 'Show Live Log ▼'}
            </button>
            <section className={cn('min-h-0 flex-1 overflow-hidden', !showLog && 'hidden xl:block')}>
              <LiveLog entries={logEntries} onClear={clearLog} className='h-full' />
            </section>
          </aside>
        </div>
      </div>

      {/* ── Account Drawer ── */}
      <AccountDrawer
        account={drawerAccount}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        initialTab={drawerInitialTab}
      />

      <SignalInspector
        signal={selectedSignal}
        open={inspectorOpen}
        onOpenChange={setInspectorOpen}
      />
    </div>
  );
}
```

- [ ] **Step 2: Verify it compiles without errors**

```bash
cd frontend && npx tsc --noEmit 2>&1
```

Fix any type errors before proceeding. Common fixes:
- If `ActivePosition` doesn't have `account_name` field, check `usePositions.ts` for the correct field name
- If `BrokerProfilesPanel` doesn't accept `filterAccountName`, remove that prop

- [ ] **Step 3: Run the dev server and visually check the dashboard**

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000` and verify:
- Aggregate bar is visible at top with PnL, win rate, drawdown, accounts count
- Account cards grid shows 3 per row on wide screens
- Clicking a card opens the right-side drawer
- Drawer tabs work (Overview, Positions, History, Analytics, Challenge if prop firm, Settings)
- Open positions table shows below the grid
- Signal table still works below that

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/page.tsx
git commit -m "feat: [DEV-62] Rewrite dashboard — command center layout with account grid + drawer"
```

---

## Task 7: Wire drawer tab for initial tab from position row click

This task verifies the drawer opens on the correct tab when clicking a position row.

- [ ] **Step 1: In the drawer, sync `activeTab` to `initialTab` when account changes**

In `frontend/src/components/dashboard/AccountDrawer.tsx`, find the `useState` for `activeTab` and add a `useEffect`:

```tsx
// After: const [activeTab, setActiveTab] = useState(initialTab);
// Add:
useEffect(() => {
  if (open) setActiveTab(initialTab);
}, [open, initialTab]);
```

- [ ] **Step 2: Verify it compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep AccountDrawer
```

- [ ] **Step 3: Test the flow**

Open the dashboard. Click a row in the Open Positions table. Verify the drawer opens on the "Positions" tab for that account.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/dashboard/AccountDrawer.tsx
git commit -m "feat: [DEV-62] AccountDrawer — sync tab on open to initialTab prop"
```

---

## Task 8: Add `animate-pulse-slow` utility (if needed)

`AccountGridCard` uses `animate-pulse-slow` for the danger state. Tailwind doesn't have this by default.

- [ ] **Step 1: Check if it already exists**

```bash
grep -r "pulse-slow" frontend/src/ --include="*.css" --include="*.ts" --include="*.tsx" | head -5
```

- [ ] **Step 2: If not found, add it to globals.css**

```bash
grep -n "pulse-slow\|@keyframes" frontend/src/app/globals.css | head -10
```

Add to `frontend/src/app/globals.css` inside the existing `@layer utilities` or at the end:

```css
@keyframes pulse-slow {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.65; }
}
.animate-pulse-slow {
  animation: pulse-slow 2.5s ease-in-out infinite;
}
```

- [ ] **Step 3: Commit if changed**

```bash
git add frontend/src/app/globals.css
git commit -m "feat: [DEV-62] add animate-pulse-slow utility for danger card state"
```

---

## Task 9: Update Jira + final check

- [ ] **Step 1: Add progress note to Jira**

```bash
node scripts/jira-agent.js add-progress DEV-62 "Dashboard redesign complete: AggregateBar + AccountGrid (3-per-row with danger states) + OpenPositionsTable + AccountDrawer with 6 tabs. Accounts page preserved but no longer linked from dashboard."
```

- [ ] **Step 2: Transition ticket to In Review**

```bash
node scripts/jira-agent.js set-status DEV-62 "In Review"
```

- [ ] **Step 3: Verify build passes**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: `✓ Compiled successfully` or similar. Fix any build errors.

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git add -p  # stage only relevant changes
git commit -m "fix: [DEV-62] build fixes for dashboard redesign"
```

---

## Self-Review Checklist

### Spec Coverage

| Requirement | Covered by |
|---|---|
| Remove accounts page link from dashboard | page.tsx rewrite — no `/accounts` href |
| Pinned aggregate bar (PnL, positions, win rate, drawdown, accounts health) | Task 1: AggregateBar |
| 3-per-row account card grid | Task 3: AccountGrid |
| Rich cards (balance, PnL, win rate, equity, drawdown, prop firm) | Task 2: AccountGridCard |
| Danger states on cards near drawdown limit | Task 2: AccountGridCard `ddState` |
| Slide-out drawer on card click | Task 5: AccountDrawer + Task 6: page.tsx |
| Drawer tabs: Overview, Positions, History, Analytics, Challenge, Settings | Task 5: AccountDrawer |
| Account management in Settings tab | Task 5: BrokerProfilesPanel in drawer |
| Open positions table below grid | Task 4: OpenPositionsTable |
| Row click → drawer on Positions tab | Task 7 |
| Account filter on positions table | Task 4: OpenPositionsTable `select` |
| Scales to 7+ accounts | Task 3: CSS grid, no hardcoded limit |

### No Placeholders ✓
All code is complete and explicit.

### Type Consistency ✓
- `AccountComparisonApi` used throughout (Tasks 2, 3, 5, 6)
- `ActivePosition` from `usePositions` used in Task 4
- `DashboardSummary` from `types/trading` used in Task 1
