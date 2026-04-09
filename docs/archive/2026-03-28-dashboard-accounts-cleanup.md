# Dashboard & Accounts Page Cleanup Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Replace the crowded dashboard AccountGrid+Drawer with a compact AccountStrip, and enrich the Accounts page with proper per-account overview cards.

**Architecture:** Three-level navigation: Dashboard (live monitor) → Accounts (overview cards) → Account Detail (6-tab deep dive). The AccountDrawer is deleted entirely — no more duplicate detail paths. Both the new AccountStrip and AccountOverviewList consume the existing `useAccountsComparison()` hook, so no API changes needed.

**Tech Stack:** Next.js App Router, React, TypeScript, `@tanstack/react-query`, `lucide-react`, existing CSS design tokens (`var(--to-*)`)

---

## Task 1: Create Jira Ticket

**Step 1: Create the ticket**

```bash
curl -s -X POST http://localhost:8000/api/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "title": "[Feature] Simplify dashboard account section and enrich accounts page",
    "problem": "The main dashboard AccountGrid renders full cards with sparklines, drawdown, and a slide-out AccountDrawer that duplicates the entire /accounts/[name] detail page (6 identical tabs). The Accounts page shows only the BrokerProfilesPanel credential manager with no account performance overview. This creates two redundant paths to account details and makes the dashboard crowded and hard to scan.",
    "solution": "1. Replace AccountGrid+AccountDrawer on dashboard with a compact AccountStrip (name, connection status, balance, click to navigate). 2. Enrich the Accounts page with AccountOverviewList (per-account rich cards: balance, equity, daily P&L, positions count, type badge). 3. Delete AccountDrawer component entirely.",
    "acceptance_criteria": [
      "Dashboard shows a compact strip with account name, connection indicator, status label, balance per row",
      "Clicking an account row navigates to /accounts/[name]",
      "AccountDrawer is deleted and all its wiring removed from page.tsx",
      "Accounts page shows rich per-account cards with balance, equity, daily P&L, connection status",
      "BrokerProfilesPanel is accessible from the Accounts page (collapsible section or modal)",
      "No TypeScript errors, no broken imports"
    ],
    "assignee": "5e77682c79f5ad0c34f09c9c",
    "type": "feature",
    "priority": "medium"
  }'
```

Save the returned `id` as `TICKET_ID`. Ask the user to create the Jira branch and wait for the branch name. Then:

```bash
git fetch origin
git checkout <branch-name-from-jira>
```

---

## Task 2: Create AccountStrip Component

**Files:**
- Create: `frontend/src/components/dashboard/AccountStrip.tsx`

**What it does:** A compact, table-like list of trading accounts. Each row: coloured dot + status, account name, balance. Clicking navigates to `/accounts/[name]`. Uses `AccountComparisonApi` type from `@/lib/api`.

**Step 1: Create the file**

```tsx
// frontend/src/components/dashboard/AccountStrip.tsx
'use client';

import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import type { AccountComparisonApi } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';

interface AccountStripProps {
  accounts: AccountComparisonApi[];
  isLoading?: boolean;
}

function ConnectionDot({ status }: { status: string }) {
  const cls = {
    connected: 'bg-[var(--to-long)]',
    disconnected: 'bg-[var(--to-warning)]',
    error: 'bg-[var(--to-short)]',
  }[status] ?? 'bg-[var(--to-text-dim)]';

  const label = {
    connected: 'Connected',
    disconnected: 'Disconnected',
    error: 'Error',
  }[status] ?? 'Unknown';

  return (
    <span className='flex items-center gap-1.5'>
      <span className={cn('h-1.5 w-1.5 rounded-full flex-shrink-0', cls)} />
      <span className={cn(
        'text-[10px] font-mono',
        status === 'connected' ? 'text-[var(--to-long)]' :
        status === 'error' ? 'text-[var(--to-short)]' :
        'text-[var(--to-warning)]'
      )}>
        {label}
      </span>
    </span>
  );
}

export function AccountStrip({ accounts, isLoading }: AccountStripProps) {
  const router = useRouter();

  if (isLoading) {
    return (
      <div className='space-y-1'>
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className='h-8 w-full rounded-lg bg-[var(--to-surface-raised)]/60' />
        ))}
      </div>
    );
  }

  if (!accounts.length) {
    return (
      <div className='rounded-lg border border-dashed border-[var(--to-border)] py-4 text-center'>
        <p className='text-xs text-[var(--to-text-dim)]'>No accounts configured</p>
      </div>
    );
  }

  return (
    <div className='rounded-xl border border-[var(--to-border)] overflow-hidden'>
      {accounts.map((account, idx) => (
        <button
          key={account.account_name}
          id={`account-strip-row-${account.account_name.replace(/\s+/g, '-').toLowerCase()}`}
          onClick={() => router.push(`/accounts/${encodeURIComponent(account.account_name)}`)}
          className={cn(
            'w-full flex items-center justify-between px-3 py-2 text-left transition-colors',
            'hover:bg-[var(--to-surface-raised)] group',
            idx !== accounts.length - 1 && 'border-b border-[var(--to-border)]'
          )}
        >
          <div className='flex items-center gap-3 min-w-0'>
            <ConnectionDot status={account.connection_status || 'unknown'} />
            <span className='font-mono text-xs font-semibold text-[var(--to-text-primary)] truncate'>
              {account.account_name}
            </span>
            {account.account_type && (
              <span className='hidden sm:inline text-[9px] text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] border border-[var(--to-border)] rounded px-1.5 py-0.5 font-mono'>
                {account.account_type}
              </span>
            )}
          </div>
          <div className='flex items-center gap-4 flex-shrink-0'>
            <span className='font-mono text-xs text-[var(--to-text-secondary)]'>
              ${account.balance?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? '—'}
            </span>
            <span className='text-[var(--to-text-dim)] group-hover:text-[var(--to-text-secondary)] transition-colors text-[10px]'>→</span>
          </div>
        </button>
      ))}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/dashboard/AccountStrip.tsx
git commit -m "feat: add AccountStrip compact account row list for dashboard"
```

---

## Task 3: Update Main Dashboard page.tsx

**Files:**
- Modify: `frontend/src/app/page.tsx`

**What changes:**
1. Remove imports: `AccountGrid`, `AccountDrawer`
2. Remove state: `drawerAccount`, `drawerOpen`, `drawerInitialTab`
3. Remove handlers: `handleOpenDrawer`, `handleAddAccount`
4. Remove `AccountGrid` render (replace with `AccountStrip`)
5. Remove `AccountDrawer` render at bottom
6. Add import for `AccountStrip`
7. Strip `onSelectAccount` callback (now navigates directly inside AccountStrip)

**Step 1: Apply changes to `frontend/src/app/page.tsx`**

Remove these imports:
```tsx
// REMOVE:
import { AccountGrid } from '@/components/dashboard/AccountGrid';
import { AccountDrawer } from '@/components/dashboard/AccountDrawer';
```

Add this import:
```tsx
import { AccountStrip } from '@/components/dashboard/AccountStrip';
```

Remove these state declarations (lines ~37-39):
```tsx
// REMOVE:
const [drawerAccount, setDrawerAccount] = useState<AccountComparisonApi | null>(null);
const [drawerOpen, setDrawerOpen] = useState(false);
const [drawerInitialTab, setDrawerInitialTab] = useState('overview');
```

Remove these handlers (lines ~81-97):
```tsx
// REMOVE:
const handleOpenDrawer = useCallback(
  (account: AccountComparisonApi, tab = 'overview') => {
    setDrawerAccount(account);
    setDrawerInitialTab(tab);
    setDrawerOpen(true);
  },
  []
);

const handleAddAccount = useCallback(() => {
  if (accounts.length > 0) {
    setDrawerAccount(accounts[0]);
  }
  setDrawerInitialTab('settings');
  setDrawerOpen(true);
}, [accounts]);
```

Replace the AccountGrid section (lines ~113-122):
```tsx
// REMOVE:
<section>
  <p className='kpi-meta mb-2'>Accounts</p>
  <AccountGrid
    accounts={accounts}
    isLoading={accountsLoading}
    onSelectAccount={(account) => handleOpenDrawer(account)}
    onAddAccount={handleAddAccount}
  />
</section>

// REPLACE WITH:
<section>
  <p className='kpi-meta mb-2'>Accounts</p>
  <AccountStrip accounts={accounts} isLoading={accountsLoading} />
</section>
```

Remove AccountDrawer render (lines ~179-185):
```tsx
// REMOVE:
<AccountDrawer
  account={drawerAccount}
  open={drawerOpen}
  onOpenChange={setDrawerOpen}
  initialTab={drawerInitialTab}
/>
```

Also remove unused imports at top of file:
```tsx
// REMOVE (no longer needed):
import type { AccountComparisonApi } from '@/lib/api';
```
(Only remove this if `AccountComparisonApi` is no longer referenced anywhere in the file after the changes above.)

**Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -40
```

Expected: zero new errors (there may be pre-existing ones — compare against baseline).

**Step 3: Commit**

```bash
git add frontend/src/app/page.tsx
git commit -m "feat: replace AccountGrid+Drawer with compact AccountStrip on dashboard"
```

---

## Task 4: Delete AccountDrawer

**Files:**
- Delete: `frontend/src/components/dashboard/AccountDrawer.tsx`

**Step 1: Confirm no other imports**

```bash
grep -r "AccountDrawer" frontend/src --include="*.tsx" --include="*.ts"
```

Expected: zero results (we already removed it from page.tsx in Task 3).

**Step 2: Delete the file**

```bash
rm frontend/src/components/dashboard/AccountDrawer.tsx
```

**Step 3: Commit**

```bash
git add -A
git commit -m "chore: delete AccountDrawer (replaced by /accounts/[name] navigation)"
```

---

## Task 5: Create AccountOverviewList Component

**Files:**
- Create: `frontend/src/components/accounts/AccountOverviewList.tsx`

**What it does:** A list of rich per-account cards. Each card shows: account name, type badge, connection status, balance, equity, daily P&L (coloured), open positions count (from the comparison data's `open_positions` field if available, else hidden). Clicking navigates to `/accounts/[name]`.

**Step 1: Create the file**

```tsx
// frontend/src/components/accounts/AccountOverviewList.tsx
'use client';

import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import type { AccountComparisonApi } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';
import { TrendingUp, TrendingDown, Wifi, WifiOff, AlertTriangle } from 'lucide-react';

interface AccountOverviewListProps {
  accounts: AccountComparisonApi[];
  isLoading?: boolean;
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'connected') {
    return (
      <span className='flex items-center gap-1 text-[10px] text-[var(--to-long)]'>
        <Wifi className='h-3 w-3' /> Connected
      </span>
    );
  }
  if (status === 'error') {
    return (
      <span className='flex items-center gap-1 text-[10px] text-[var(--to-short)]'>
        <AlertTriangle className='h-3 w-3' /> Error
      </span>
    );
  }
  return (
    <span className='flex items-center gap-1 text-[10px] text-[var(--to-warning)]'>
      <WifiOff className='h-3 w-3' /> Disconnected
    </span>
  );
}

function TypeBadge({ type }: { type?: string }) {
  if (!type) return null;
  const cls = {
    Funded: 'text-[var(--to-long)] bg-[var(--to-long)]/10 border-[var(--to-long)]/20',
    Eval: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    Personal: 'text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] border-[var(--to-border)]',
  }[type] ?? 'text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] border-[var(--to-border)]';

  return (
    <span className={cn('px-1.5 py-0.5 text-[9px] font-mono font-bold rounded uppercase tracking-wider border', cls)}>
      {type}
    </span>
  );
}

function PnlBadge({ value, pct }: { value: number; pct: number }) {
  const isPositive = value >= 0;
  return (
    <div className={cn('flex items-center gap-1 font-mono text-xs font-semibold', isPositive ? 'text-[var(--to-long)]' : 'text-[var(--to-short)]')}>
      {isPositive ? <TrendingUp className='h-3 w-3' /> : <TrendingDown className='h-3 w-3' />}
      <span>{isPositive ? '+' : ''}${value.toFixed(2)}</span>
      <span className='text-[10px] opacity-75'>({isPositive ? '+' : ''}{pct.toFixed(2)}%)</span>
    </div>
  );
}

function AccountCard({ account }: { account: AccountComparisonApi }) {
  const router = useRouter();

  return (
    <button
      id={`account-overview-card-${account.account_name.replace(/\s+/g, '-').toLowerCase()}`}
      onClick={() => router.push(`/accounts/${encodeURIComponent(account.account_name)}`)}
      className={cn(
        'w-full text-left rounded-xl border p-4 transition-all duration-150 group',
        'hover:shadow-[0_0_16px_rgba(0,0,0,0.2)] hover:border-[var(--to-border-hover,var(--to-border))]',
        account.connection_status === 'connected'
          ? 'border-[var(--to-border)] bg-[var(--to-surface)]'
          : 'border-[var(--to-border)] bg-[var(--to-surface)] opacity-80'
      )}
    >
      {/* Header row */}
      <div className='flex items-start justify-between gap-2 mb-3'>
        <div className='min-w-0'>
          <div className='flex items-center gap-2 flex-wrap'>
            <span className='font-mono font-bold text-sm text-[var(--to-text-primary)] truncate'>
              {account.account_name}
            </span>
            <TypeBadge type={account.account_type} />
            {account.prop_firm_name && (
              <span className='text-[9px] text-[var(--to-text-dim)] bg-[var(--to-surface-raised)] border border-[var(--to-border)] rounded px-1.5 py-0.5 font-mono'>
                {account.prop_firm_name}
              </span>
            )}
          </div>
          <div className='mt-1'>
            <StatusBadge status={account.connection_status || 'unknown'} />
          </div>
        </div>
        <span className='text-[var(--to-text-dim)] group-hover:text-[var(--to-text-secondary)] transition-colors text-sm flex-shrink-0'>→</span>
      </div>

      {/* Metrics row */}
      <div className='grid grid-cols-3 gap-3'>
        <div>
          <p className='text-[9px] uppercase tracking-wider text-[var(--to-text-dim)] mb-0.5'>Balance</p>
          <p className='font-mono text-xs font-semibold text-[var(--to-text-primary)]'>
            ${account.balance?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? '—'}
          </p>
        </div>
        <div>
          <p className='text-[9px] uppercase tracking-wider text-[var(--to-text-dim)] mb-0.5'>Equity</p>
          <p className='font-mono text-xs font-semibold text-[var(--to-text-primary)]'>
            ${account.equity?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? '—'}
          </p>
        </div>
        <div>
          <p className='text-[9px] uppercase tracking-wider text-[var(--to-text-dim)] mb-0.5'>Today</p>
          {typeof account.daily_pnl === 'number' ? (
            <PnlBadge value={account.daily_pnl} pct={account.daily_pnl_pct ?? 0} />
          ) : (
            <p className='font-mono text-xs text-[var(--to-text-dim)]'>—</p>
          )}
        </div>
      </div>
    </button>
  );
}

export function AccountOverviewList({ accounts, isLoading }: AccountOverviewListProps) {
  if (isLoading) {
    return (
      <div className='grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3'>
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className='h-28 w-full rounded-xl bg-[var(--to-surface-raised)]/60' />
        ))}
      </div>
    );
  }

  if (!accounts.length) {
    return (
      <div className='rounded-xl border border-dashed border-[var(--to-border)] py-12 text-center'>
        <p className='text-sm text-[var(--to-text-dim)]'>No accounts configured</p>
        <p className='text-[11px] text-[var(--to-text-dim)] mt-1'>Add an account below to get started</p>
      </div>
    );
  }

  return (
    <div className='grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3'>
      {accounts.map((account) => (
        <AccountCard key={account.account_name} account={account} />
      ))}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add frontend/src/components/accounts/AccountOverviewList.tsx
git commit -m "feat: add AccountOverviewList for enriched accounts page"
```

---

## Task 6: Update Accounts Page

**Files:**
- Modify: `frontend/src/app/accounts/page.tsx`

**What changes:** Replace the single `BrokerProfilesPanel` with:
1. `AccountOverviewList` at top (accounts with their metrics, navigate-to-detail)
2. A collapsible "Manage Credentials" section below containing `BrokerProfilesPanel`

**Step 1: Rewrite `frontend/src/app/accounts/page.tsx`**

```tsx
'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Settings2 } from 'lucide-react';
import { BrokerProfilesPanel } from '@/components/accounts/BrokerProfilesPanel';
import { AccountOverviewList } from '@/components/accounts/AccountOverviewList';
import { useAccountsComparison } from '@/hooks/useAccounts';

export default function AccountsPage() {
  const [credentialsOpen, setCredentialsOpen] = useState(false);
  const { data: accounts = [], isLoading } = useAccountsComparison();

  return (
    <div className='space-y-6'>
      {/* Page header */}
      <div>
        <h1 className='page-title text-lg font-semibold'>Accounts</h1>
        <p className='page-subtitle mt-0.5 text-xs'>
          Overview of all trading accounts. Click an account to view full details.
        </p>
      </div>

      {/* Account overview cards */}
      <AccountOverviewList accounts={accounts} isLoading={isLoading} />

      {/* Credentials management — collapsible */}
      <div className='rounded-xl border border-[var(--to-border)]'>
        <button
          id='credentials-toggle'
          onClick={() => setCredentialsOpen((v) => !v)}
          className='w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-[var(--to-text-secondary)] hover:text-[var(--to-text-primary)] transition-colors'
        >
          <span className='flex items-center gap-2'>
            <Settings2 className='h-4 w-4 text-[var(--to-warning)]' />
            Manage MetaAPI Credentials
          </span>
          {credentialsOpen ? (
            <ChevronUp className='h-4 w-4' />
          ) : (
            <ChevronDown className='h-4 w-4' />
          )}
        </button>

        {credentialsOpen && (
          <div className='border-t border-[var(--to-border)] p-4'>
            <BrokerProfilesPanel />
          </div>
        )}
      </div>
    </div>
  );
}
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -40
```

Expected: zero new errors.

**Step 3: Commit**

```bash
git add frontend/src/app/accounts/page.tsx
git commit -m "feat: replace accounts page with AccountOverviewList + collapsed credentials panel"
```

---

## Task 7: Check AccountGrid Usage & Clean Up

**Step 1: Verify AccountGrid is no longer imported anywhere**

```bash
grep -r "AccountGrid\|AccountGridCard" frontend/src --include="*.tsx" --include="*.ts"
```

**If zero results:** delete both files:

```bash
rm frontend/src/components/dashboard/AccountGrid.tsx
rm frontend/src/components/dashboard/AccountGridCard.tsx
```

**If still imported somewhere:** investigate before deleting.

**Step 2: Commit (only if deleted)**

```bash
git add -A
git commit -m "chore: delete AccountGrid and AccountGridCard (replaced by AccountStrip)"
```

---

## Task 8: Verify & Close Ticket

**Step 1: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -v "^$" | head -50
```

Expected: no new errors introduced by this change.

**Step 2: Run frontend lint**

```bash
cd frontend && npx eslint src/app/page.tsx src/app/accounts/page.tsx src/components/dashboard/AccountStrip.tsx src/components/accounts/AccountOverviewList.tsx 2>&1 | head -40
```

**Step 3: Spot check in browser**

Start the dev server:
```bash
cd frontend && npm run dev
```

Check:
- `http://localhost:3000/` — dashboard shows compact account strip, no drawer
- Click an account row → navigates to `/accounts/[name]`
- `http://localhost:3000/accounts` — shows rich account cards grid + collapsed credentials section
- Click "Manage MetaAPI Credentials" → credentials panel expands
- Click an account card → navigates to `/accounts/[name]` detail page

**Step 4: Close the Jira ticket**

```bash
curl -s -X POST "http://localhost:8000/api/tickets/$TICKET_ID/ai-update" \
  -H "Content-Type: application/json" \
  -d '{
    "new_status": "done",
    "summary_of_work": "Replaced AccountGrid+AccountDrawer on dashboard with compact AccountStrip (account name, connection status, balance, click-to-navigate). Enriched Accounts page with AccountOverviewList (per-account cards: balance, equity, daily P&L, type badge, connection status). Deleted AccountDrawer component entirely. BrokerProfilesPanel demoted to collapsible credentials section on Accounts page. No API changes required.",
    "agent": "antigravity"
  }'
```

**Step 5: Final commit**

```bash
git add -A
git commit -m "chore: verify + close DEV-XX dashboard accounts cleanup"
```
