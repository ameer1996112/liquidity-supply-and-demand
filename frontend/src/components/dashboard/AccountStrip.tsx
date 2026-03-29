'use client';

import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import type { AccountComparisonApi } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';
import { ExternalLink } from 'lucide-react';

interface AccountStripProps {
  accounts: AccountComparisonApi[];
  isLoading?: boolean;
  /** Which account is currently selected (filters signal table below) */
  activeAccount?: string | undefined;
  /** Called when user clicks a card body — pass account_name to filter, or undefined to clear */
  onAccountSelect?: (accountName: string | undefined) => void;
  /** Signal counts per account_name — shown as badge on each card */
  signalCounts?: Record<string, number>;
}

// ─── sub-components ──────────────────────────────────────────────────────────

/** Left-edge connection rail color */
function connectionRail(status: string): string {
  if (status === 'connected') return '#0ecb81';
  if (status === 'error') return '#f6465d';
  return '#f0b90b';
}

/** Dot + text status indicator */
function StatusPill({ status }: { status: string }) {
  const color =
    status === 'connected'
      ? 'var(--to-long)'
      : status === 'error'
      ? 'var(--to-short)'
      : 'var(--to-warning)';
  const label =
    status === 'connected' ? 'Live' : status === 'error' ? 'Error' : 'Offline';

  return (
    <span
      className="inline-flex items-center gap-1"
      style={{ color }}
    >
      <span
        className="block rounded-full"
        style={{
          width: 5,
          height: 5,
          backgroundColor: color,
          boxShadow: `0 0 5px ${color}`,
          animation: status === 'connected' ? 'as-pulse 2s ease-in-out infinite' : undefined,
        }}
      />
      <span className="font-mono text-[9px] uppercase tracking-widest">{label}</span>
    </span>
  );
}

/** Tiny account-type badge */
function TypeChip({ type }: { type?: string }) {
  if (!type) return null;
  const styles: Record<string, { color: string; bg: string }> = {
    Funded: { color: '#f0b90b', bg: 'rgba(240,185,11,0.1)' },
    Eval: { color: '#3b82f6', bg: 'rgba(59,130,246,0.1)' },
    Personal: { color: '#8b95a5', bg: 'rgba(139,149,165,0.1)' },
  };
  const s = styles[type] ?? { color: '#8b95a5', bg: 'rgba(139,149,165,0.1)' };
  return (
    <span
      className="font-mono text-[8px] uppercase tracking-widest rounded px-1.5 py-0.5"
      style={{ color: s.color, backgroundColor: s.bg, border: `1px solid ${s.color}30` }}
    >
      {type}
    </span>
  );
}

/** Equity vs balance drift — a thin progress-bar style stat */
function EquityBar({ balance, equity }: { balance: number | null; equity: number | null }) {
  if (!balance || !equity) return null;
  const pct = Math.min(Math.max((equity / balance) * 100, 0), 200);
  const above = equity >= balance;
  return (
    <div className="mt-2 overflow-hidden rounded-full" style={{ height: 2, backgroundColor: 'var(--to-border)' }}>
      <div
        style={{
          height: '100%',
          width: `${Math.min(pct, 100)}%`,
          backgroundColor: above ? 'var(--to-long)' : 'var(--to-short)',
          borderRadius: 9999,
          transition: 'width 0.5s ease',
        }}
      />
    </div>
  );
}

// ─── main card ───────────────────────────────────────────────────────────────

function AccountCard({
  account,
  isActive,
  isArchived,
  sigCount,
  onFilter,
  onNavigate,
}: {
  account: AccountComparisonApi;
  isActive: boolean;
  isArchived: boolean;
  sigCount: number;
  onFilter: () => void;
  onNavigate: () => void;
}) {
  const rail = connectionRail(account.connection_status || 'unknown');
  const balanceStr = account.balance != null
    ? `$${account.balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : '—';

  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-xl transition-all duration-200 select-none',
        isActive
          ? 'ring-1 ring-[var(--to-long)] shadow-[0_0_16px_rgba(14,203,129,0.12)]'
          : 'ring-1 ring-[var(--to-border)] hover:ring-[var(--to-border-glow)] hover:shadow-[0_0_12px_rgba(0,0,0,0.3)]',
        isArchived && 'opacity-50',
      )}
      style={{ backgroundColor: 'var(--to-surface)' }}
    >
      {/* Left connection rail */}
      <div
        className="absolute left-0 top-0 bottom-0 w-[3px] rounded-l-xl"
        style={{
          backgroundColor: rail,
          opacity: isArchived ? 0.3 : isActive ? 1 : 0.5,
          boxShadow: isActive ? `0 0 8px ${rail}` : undefined,
          transition: 'opacity 0.2s, box-shadow 0.2s',
        }}
      />

      {/* Card body — click to filter */}
      <button
        id={`account-strip-filter-${account.account_name.replace(/\s+/g, '-').toLowerCase()}`}
        onClick={onFilter}
        className="w-full pl-4 pr-3 pt-3 pb-2 text-left focus:outline-none"
      >
        {/* Row 1: name + chips */}
        <div className="flex items-start justify-between gap-2 mb-1">
          <span
            className={cn(
              'font-mono text-[11px] font-semibold leading-tight truncate transition-colors',
              isActive ? 'text-[var(--to-text-primary)]' : 'text-[var(--to-text-secondary)]',
            )}
          >
            {account.account_name}
          </span>
          <div className="flex items-center gap-1 flex-shrink-0">
            {sigCount > 0 && (
              <span
                className={cn(
                  'font-mono text-[8px] px-1.5 py-0.5 rounded-full border tabular-nums',
                  isActive
                    ? 'bg-[var(--to-long)]/15 border-[var(--to-long)]/30 text-[var(--to-long)]'
                    : 'bg-[var(--to-surface-raised)] border-[var(--to-border)] text-[var(--to-text-dim)]',
                )}
              >
                {sigCount}
              </span>
            )}
            {isArchived ? (
              <span
                className="font-mono text-[8px] px-1.5 py-0.5 rounded border italic"
                style={{ color: 'var(--to-text-dim)', backgroundColor: 'var(--to-surface-raised)', borderColor: 'var(--to-border)' }}
              >
                archived
              </span>
            ) : (
              <TypeChip type={account.account_type} />
            )}
          </div>
        </div>

        {/* Row 2: status pill */}
        {!isArchived && <StatusPill status={account.connection_status || 'unknown'} />}

        {/* Row 3: balance (big number) */}
        {!isArchived && (
          <p
            className="font-mono tabular-nums mt-1.5 leading-none transition-colors"
            style={{
              fontSize: 15,
              fontWeight: 600,
              color: isActive ? 'var(--to-text-primary)' : 'var(--to-text-secondary)',
              letterSpacing: '-0.02em',
            }}
          >
            {balanceStr}
          </p>
        )}

        {/* Row 4: equity drift bar */}
        {!isArchived && <EquityBar balance={account.balance} equity={account.equity} />}
      </button>

      {/* Navigate arrow — bottom-right corner */}
      {!isArchived && (
        <button
          id={`account-strip-nav-${account.account_name.replace(/\s+/g, '-').toLowerCase()}`}
          onClick={onNavigate}
          title={`Go to ${account.account_name} details`}
          className={cn(
            'absolute bottom-2 right-2 p-1 rounded transition-all',
            'text-[var(--to-text-dim)] hover:text-[var(--to-text-primary)] hover:bg-[var(--to-surface-raised)]',
          )}
        >
          <ExternalLink size={10} />
        </button>
      )}
    </div>
  );
}

// ─── loading skeletons ────────────────────────────────────────────────────────

function CardSkeleton() {
  return (
    <div className="rounded-xl ring-1 ring-[var(--to-border)] overflow-hidden" style={{ backgroundColor: 'var(--to-surface)' }}>
      <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-[var(--to-border)] rounded-l-xl" />
      <div className="pl-4 pr-3 pt-3 pb-3 space-y-2">
        <Skeleton className="h-3 w-24 rounded bg-[var(--to-surface-raised)]" />
        <Skeleton className="h-2 w-12 rounded bg-[var(--to-surface-raised)]" />
        <Skeleton className="h-4 w-20 rounded bg-[var(--to-surface-raised)]" />
        <Skeleton className="h-0.5 w-full rounded-full bg-[var(--to-surface-raised)]" />
      </div>
    </div>
  );
}

// ─── exported component ───────────────────────────────────────────────────────

export function AccountStrip({
  accounts,
  isLoading,
  activeAccount,
  onAccountSelect,
  signalCounts = {},
}: AccountStripProps) {
  const router = useRouter();

  if (isLoading) {
    return (
      <>
        <style>{`
          @keyframes as-pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
          }
        `}</style>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-2 relative">
          {[1, 2, 3].map((i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      </>
    );
  }

  if (!accounts.length) {
    return (
      <div
        className="rounded-xl ring-1 ring-dashed ring-[var(--to-border)] py-5 text-center"
        style={{ backgroundColor: 'var(--to-surface)' }}
      >
        <p className="text-[11px] text-[var(--to-text-dim)]">No accounts configured</p>
      </div>
    );
  }

  return (
    <>
      {/* Pulse animation for live dots */}
      <style>{`
        @keyframes as-pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(0.85); }
        }
      `}</style>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-2">
        {accounts.map((account) => {
          const isActive = activeAccount === account.account_name;
          const isArchived =
            account.connection_status === 'disconnected' && account.balance == null;
          const sigCount = signalCounts[account.account_name] ?? 0;

          return (
            <AccountCard
              key={account.account_name}
              account={account}
              isActive={isActive}
              isArchived={isArchived}
              sigCount={sigCount}
              onFilter={() => onAccountSelect?.(isActive ? undefined : account.account_name)}
              onNavigate={() =>
                router.push(`/accounts/${encodeURIComponent(account.account_name)}`)
              }
            />
          );
        })}
      </div>
    </>
  );
}
