# Multi-Account Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the main dashboard to aggregate data across all broker accounts, with an account summary strip, filter pills on the signals table, and a unified live P&L ticker.

**Architecture:** Add a new backend `/api/v1/dashboard/summary` endpoint returning aggregated + per-account stats in one call. The frontend gains a new `useDashboardSummary` hook and `AccountSummaryStrip` component. `ActiveAccountProvider` stays unchanged — per-account pages continue working as before.

**Design System:** Sovereign Terminal aesthetic — `#080A0F` base, gold accent `#C4992A`, Space Grotesk labels, JetBrains Mono numbers, account type color borders (gold=funded, blue=eval, steel=personal).

**Tech Stack:** FastAPI (Python), React, TypeScript, Tailwind CSS, Supabase, TanStack Query

**Jira:** DEV-61

---

## File Map

**Create:**
- `src/api_dashboard.py` — aggregated dashboard summary endpoint
- `frontend/src/hooks/useDashboardSummary.ts` — TanStack Query hook for summary data
- `frontend/src/components/dashboard/AccountSummaryStrip.tsx` — account cards strip component
- `frontend/src/styles/sovereign-terminal.css` — design system CSS variables + fonts

**Modify:**
- `src/api.py` — register dashboard router
- `frontend/src/types/trading.ts` — add DashboardSummary and AccountSummaryItem types
- `frontend/src/components/dashboard/SignalTable.tsx` — add filter pills + account badge per row
- `frontend/src/components/dashboard/LivePnlTicker.tsx` — all-accounts mode + LIVE-only toggle
- `frontend/src/app/page.tsx` — use useDashboardSummary, render AccountSummaryStrip, wire filters
- `frontend/src/app/layout.tsx` — import sovereign-terminal.css

---

## Task 1: Backend — Dashboard Summary Endpoint

**Files:**
- Create: `src/api_dashboard.py`

- [ ] **Step 1: Create `src/api_dashboard.py`**

```python
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from config.settings import get_settings
from datetime import datetime, timedelta, date

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
settings = get_settings()


class AccountSummaryItem(BaseModel):
    id: int
    name: str
    account_type: str
    run_mode: str
    connection_status: str
    pnl_today: float
    pnl_total: float
    positions_count: int
    win_rate: float
    trades_today: int


class DashboardSummary(BaseModel):
    total_pnl_today: float
    total_pnl_all_time: float
    total_win_rate: float
    total_active_positions: int
    total_trades_today: int
    max_drawdown_pct: float
    accounts: List[AccountSummaryItem]


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary():
    sb = settings.supabase_client

    # 1. Fetch all broker profiles
    profiles_resp = sb.table("broker_profiles").select(
        "id, name, account_type, run_mode, connection_status"
    ).execute()
    profiles = profiles_resp.data or []

    # 2. Fetch closed signals for PnL stats (last 90 days)
    since = (datetime.utcnow() - timedelta(days=90)).isoformat()
    signals_resp = sb.table("trading_signals").select(
        "broker_profile_id, status, pnl, created_at"
    ).gte("created_at", since).in_(
        "status", ["closed", "CLOSED", "executed", "EXECUTED"]
    ).execute()
    signals = signals_resp.data or []

    # 3. Fetch open positions count
    open_resp = sb.table("trading_signals").select(
        "broker_profile_id"
    ).in_("status", ["active", "ACTIVE", "open", "OPEN"]).execute()
    open_signals = open_resp.data or []

    today_str = date.today().isoformat()
    account_items = []
    total_pnl_today = 0.0
    total_pnl_all_time = 0.0
    total_wins = 0
    total_closed = 0
    total_trades_today = 0

    for profile in profiles:
        pid = profile["id"]
        acct_signals = [s for s in signals if s.get("broker_profile_id") == pid]
        acct_open = [s for s in open_signals if s.get("broker_profile_id") == pid]

        pnl_total = sum(s.get("pnl") or 0 for s in acct_signals)
        pnl_today = sum(
            s.get("pnl") or 0 for s in acct_signals
            if (s.get("created_at") or "").startswith(today_str)
        )
        trades_today = sum(
            1 for s in acct_signals
            if (s.get("created_at") or "").startswith(today_str)
        )
        wins = sum(1 for s in acct_signals if (s.get("pnl") or 0) > 0)
        win_rate = round((wins / len(acct_signals) * 100), 1) if acct_signals else 0.0

        total_pnl_today += pnl_today
        total_pnl_all_time += pnl_total
        total_wins += wins
        total_closed += len(acct_signals)
        total_trades_today += trades_today

        account_items.append(AccountSummaryItem(
            id=pid,
            name=profile["name"],
            account_type=profile.get("account_type", "personal"),
            run_mode=profile.get("run_mode", "PAPER"),
            connection_status=profile.get("connection_status", "unknown"),
            pnl_today=round(pnl_today, 2),
            pnl_total=round(pnl_total, 2),
            positions_count=len(acct_open),
            win_rate=win_rate,
            trades_today=trades_today,
        ))

    overall_win_rate = round((total_wins / total_closed * 100), 1) if total_closed else 0.0

    # Max drawdown — best-effort from daily_stats
    max_drawdown_pct = 0.0
    try:
        dd_resp = sb.table("daily_stats").select("max_drawdown_pct").order(
            "date", desc=True
        ).limit(1).execute()
        if dd_resp.data:
            max_drawdown_pct = dd_resp.data[0].get("max_drawdown_pct") or 0.0
    except Exception:
        pass

    return DashboardSummary(
        total_pnl_today=round(total_pnl_today, 2),
        total_pnl_all_time=round(total_pnl_all_time, 2),
        total_win_rate=overall_win_rate,
        total_active_positions=len(open_signals),
        total_trades_today=total_trades_today,
        max_drawdown_pct=round(max_drawdown_pct, 2),
        accounts=account_items,
    )
```

- [ ] **Step 2: Verify syntax**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
python3 -c "import ast; ast.parse(open('src/api_dashboard.py').read()); print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/api_dashboard.py
git commit -m "feat: [DEV-61] add /api/v1/dashboard/summary aggregation endpoint"
```

---

## Task 2: Backend — Register Router

**Files:**
- Modify: `src/api.py`

- [ ] **Step 1: Add import to `src/api.py`**

Find the block of router imports (search for `from src.api_` lines) and add alongside them:
```python
from src.api_dashboard import router as dashboard_router
```

- [ ] **Step 2: Register the router**

Find the block of `app.include_router(...)` calls and add:
```python
app.include_router(dashboard_router)
```

- [ ] **Step 3: Verify import resolves**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
python3 -c "from src.api import app; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/api.py
git commit -m "feat: [DEV-61] register dashboard summary router"
```

---

## Task 3: Frontend Types

**Files:**
- Modify: `frontend/src/types/trading.ts`

- [ ] **Step 1: Append new types at end of `frontend/src/types/trading.ts`**

```typescript
export interface AccountSummaryItem {
  id: number
  name: string
  account_type: 'funded' | 'evaluation' | 'personal'
  run_mode: 'LIVE' | 'PAPER'
  connection_status: 'connected' | 'error' | 'unknown'
  pnl_today: number
  pnl_total: number
  positions_count: number
  win_rate: number
  trades_today: number
}

export interface DashboardSummary {
  total_pnl_today: number
  total_pnl_all_time: number
  total_win_rate: number
  total_active_positions: number
  total_trades_today: number
  max_drawdown_pct: number
  accounts: AccountSummaryItem[]
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading/frontend
npx tsc --noEmit 2>&1 | head -20
```
Expected: no new errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/trading.ts
git commit -m "feat: [DEV-61] add DashboardSummary and AccountSummaryItem types"
```

---

## Task 4: Frontend Hook — `useDashboardSummary`

**Files:**
- Create: `frontend/src/hooks/useDashboardSummary.ts`

- [ ] **Step 1: Create `frontend/src/hooks/useDashboardSummary.ts`**

```typescript
import { useQuery } from '@tanstack/react-query'
import type { DashboardSummary } from '@/types/trading'

async function fetchDashboardSummary(): Promise<DashboardSummary> {
  const res = await fetch('/api/v1/dashboard/summary')
  if (!res.ok) throw new Error('Failed to fetch dashboard summary')
  return res.json()
}

export function useDashboardSummary() {
  return useQuery<DashboardSummary>({
    queryKey: ['dashboard-summary'],
    queryFn: fetchDashboardSummary,
    refetchInterval: 30_000,
    staleTime: 15_000,
  })
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading/frontend
npx tsc --noEmit 2>&1 | head -20
```
Expected: no new errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useDashboardSummary.ts
git commit -m "feat: [DEV-61] add useDashboardSummary hook"
```

---

## Task 5: Design System CSS

**Files:**
- Create: `frontend/src/styles/sovereign-terminal.css`
- Modify: `frontend/src/app/layout.tsx`

- [ ] **Step 1: Create `frontend/src/styles/sovereign-terminal.css`**

```css
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Outfit:wght@300;400;500&display=swap');

:root {
  --bg-base: #080A0F;
  --bg-surface: #0D1117;
  --bg-card: #111827;
  --bg-card-hover: #161F2E;
  --border: #1E2A3A;
  --border-subtle: #141C28;
  --accent-gold: #C4992A;
  --accent-gold-dim: rgba(196, 153, 42, 0.15);
  --accent-gold-glow: rgba(196, 153, 42, 0.25);
  --text-primary: #E8EAF0;
  --text-secondary: #8892A4;
  --text-muted: #4B5A72;
  --positive: #2ECC8A;
  --positive-dim: rgba(46, 204, 138, 0.12);
  --negative: #E05555;
  --negative-dim: rgba(224, 85, 85, 0.12);
  --live-blue: #3B82F6;
  --live-blue-dim: rgba(59, 130, 246, 0.15);

  /* Account type accent colors */
  --acct-funded: #C4992A;
  --acct-evaluation: #3B82F6;
  --acct-personal: #6B7A99;

  /* Typography */
  --font-display: 'Space Grotesk', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  --font-body: 'Outfit', sans-serif;
}

body {
  font-family: var(--font-body);
  background-color: var(--bg-base);
  color: var(--text-primary);
}

.st-font-mono {
  font-family: var(--font-mono) !important;
  font-variant-numeric: tabular-nums;
}

.st-font-display {
  font-family: var(--font-display) !important;
}
```

- [ ] **Step 2: Read `frontend/src/app/layout.tsx` then add the import**

Read the file, find the last import line, and add after it:
```typescript
import '@/styles/sovereign-terminal.css'
```

- [ ] **Step 3: Verify Next.js builds**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading/frontend
npx next build 2>&1 | tail -10
```
Expected: build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/styles/sovereign-terminal.css frontend/src/app/layout.tsx
git commit -m "feat: [DEV-61] add Sovereign Terminal design system — fonts, CSS variables"
```

---

## Task 6: AccountSummaryStrip Component

**Files:**
- Create: `frontend/src/components/dashboard/AccountSummaryStrip.tsx`

- [ ] **Step 1: Create `frontend/src/components/dashboard/AccountSummaryStrip.tsx`**

```tsx
'use client'

import { useRouter } from 'next/navigation'
import type { AccountSummaryItem } from '@/types/trading'

interface Props {
  accounts: AccountSummaryItem[]
  isLoading: boolean
}

const ACCOUNT_TYPE_COLORS: Record<string, string> = {
  funded: 'var(--acct-funded)',
  evaluation: 'var(--acct-evaluation)',
  personal: 'var(--acct-personal)',
}

const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  funded: 'Funded',
  evaluation: 'Eval',
  personal: 'Personal',
}

function LiveDot({ status, runMode }: { status: string; runMode: string }) {
  const isLive = runMode === 'LIVE' && status === 'connected'
  return (
    <span
      style={{
        display: 'inline-block',
        width: 7,
        height: 7,
        borderRadius: '50%',
        backgroundColor: isLive
          ? 'var(--live-blue)'
          : status === 'error'
          ? 'var(--negative)'
          : 'var(--text-muted)',
        boxShadow: isLive ? '0 0 6px var(--live-blue)' : 'none',
        animation: isLive ? 'st-pulse 2s ease-in-out infinite' : 'none',
        flexShrink: 0,
      }}
    />
  )
}

function AccountCard({ account }: { account: AccountSummaryItem }) {
  const router = useRouter()
  const accentColor = ACCOUNT_TYPE_COLORS[account.account_type] || 'var(--acct-personal)'
  const pnlColor = account.pnl_today >= 0 ? 'var(--positive)' : 'var(--negative)'
  const pnlSign = account.pnl_today >= 0 ? '+' : ''

  return (
    <div
      onClick={() => router.push(`/accounts/${encodeURIComponent(account.name)}`)}
      style={{
        position: 'relative',
        minWidth: 200,
        maxWidth: 220,
        padding: '14px 16px',
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderLeft: `3px solid ${accentColor}`,
        borderRadius: 8,
        cursor: 'pointer',
        transition: 'transform 120ms ease, box-shadow 120ms ease, background 120ms ease',
        flexShrink: 0,
      }}
      onMouseEnter={e => {
        const el = e.currentTarget
        el.style.transform = 'translateY(-2px)'
        el.style.boxShadow = `0 4px 20px rgba(0,0,0,0.4), 0 0 0 1px ${accentColor}40`
        el.style.background = 'var(--bg-card-hover)'
      }}
      onMouseLeave={e => {
        const el = e.currentTarget
        el.style.transform = 'translateY(0)'
        el.style.boxShadow = 'none'
        el.style.background = 'var(--bg-card)'
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
        <LiveDot status={account.connection_status} runMode={account.run_mode} />
        <span
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--text-primary)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            flex: 1,
          }}
        >
          {account.name}
        </span>
        <span
          style={{
            fontSize: 9,
            fontWeight: 600,
            color: accentColor,
            background: `${accentColor}18`,
            padding: '2px 5px',
            borderRadius: 3,
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
            flexShrink: 0,
          }}
        >
          {ACCOUNT_TYPE_LABELS[account.account_type] || account.account_type}
        </span>
      </div>

      {/* PnL Today */}
      <div style={{ marginBottom: 8 }}>
        <div
          style={{
            fontSize: 10,
            color: 'var(--text-muted)',
            marginBottom: 2,
            fontFamily: 'var(--font-display)',
          }}
        >
          Today
        </div>
        <div
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 18,
            fontWeight: 600,
            color: pnlColor,
            letterSpacing: '-0.02em',
          }}
        >
          {pnlSign}${Math.abs(account.pnl_today).toFixed(2)}
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: 'flex', gap: 12 }}>
        <div>
          <div
            style={{
              fontSize: 9,
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-display)',
            }}
          >
            Positions
          </div>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 13,
              fontWeight: 500,
              color: 'var(--text-secondary)',
            }}
          >
            {account.positions_count}
          </div>
        </div>
        <div>
          <div
            style={{
              fontSize: 9,
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-display)',
            }}
          >
            Win Rate
          </div>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 13,
              fontWeight: 500,
              color: 'var(--text-secondary)',
            }}
          >
            {account.win_rate}%
          </div>
        </div>
        <div>
          <div
            style={{
              fontSize: 9,
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-display)',
            }}
          >
            Mode
          </div>
          <div
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              fontWeight: 600,
              color:
                account.run_mode === 'LIVE' ? 'var(--live-blue)' : 'var(--text-muted)',
            }}
          >
            {account.run_mode}
          </div>
        </div>
      </div>
    </div>
  )
}

function SkeletonCard() {
  return (
    <div
      style={{
        minWidth: 200,
        height: 130,
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderLeft: '3px solid var(--border)',
        borderRadius: 8,
        flexShrink: 0,
        animation: 'st-shimmer 1.5s ease-in-out infinite',
      }}
    />
  )
}

export function AccountSummaryStrip({ accounts, isLoading }: Props) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 12,
        overflowX: 'auto',
        paddingBottom: 4,
        scrollbarWidth: 'thin',
        scrollbarColor: 'var(--border) transparent',
      }}
    >
      <style>{`
        @keyframes st-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.35; }
        }
        @keyframes st-shimmer {
          0%, 100% { opacity: 0.35; }
          50% { opacity: 0.6; }
        }
      `}</style>

      {isLoading ? (
        <>
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </>
      ) : (
        <>
          {accounts.map(account => (
            <AccountCard key={account.id} account={account} />
          ))}
          <div
            onClick={() => (window.location.href = '/accounts')}
            style={{
              minWidth: 48,
              height: 130,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'var(--bg-card)',
              border: '1px dashed var(--border)',
              borderRadius: 8,
              cursor: 'pointer',
              color: 'var(--text-muted)',
              fontSize: 20,
              flexShrink: 0,
              transition: 'border-color 120ms ease, color 120ms ease',
            }}
            onMouseEnter={e => {
              const el = e.currentTarget
              el.style.borderColor = 'var(--accent-gold)'
              el.style.color = 'var(--accent-gold)'
            }}
            onMouseLeave={e => {
              const el = e.currentTarget
              el.style.borderColor = 'var(--border)'
              el.style.color = 'var(--text-muted)'
            }}
            title="Manage accounts"
          >
            +
          </div>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading/frontend
npx tsc --noEmit 2>&1 | head -20
```
Expected: no new errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/dashboard/AccountSummaryStrip.tsx
git commit -m "feat: [DEV-61] AccountSummaryStrip — Sovereign Terminal account cards with type borders"
```

---

## Task 7: Update SignalTable — Filter Pills + Account Badge

**Files:**
- Modify: `frontend/src/components/dashboard/SignalTable.tsx`

- [ ] **Step 1: Read the current props interface**

```bash
head -80 frontend/src/components/dashboard/SignalTable.tsx
```

- [ ] **Step 2: Add three new props to the component's props interface**

Find the existing props interface/type (search for `interface.*Props` or `type.*Props`) and add these three fields:

```typescript
accountFilter?: string
onAccountFilterChange?: (name: string | undefined) => void
accountNames?: string[]
```

- [ ] **Step 3: Add filter pills block above the signals table header**

Find where the table/list begins rendering (look for the outermost wrapping `<div>` or `<table>` of the signals section) and insert before it:

```tsx
{/* Account Filter Pills */}
{accountNames && accountNames.length > 0 && (
  <div style={{ display: 'flex', gap: 6, padding: '10px 0', flexWrap: 'wrap' }}>
    <button
      onClick={() => onAccountFilterChange?.(undefined)}
      style={{
        padding: '4px 12px',
        borderRadius: 20,
        border: '1px solid',
        borderColor: !accountFilter ? 'var(--accent-gold)' : 'var(--border)',
        background: !accountFilter ? 'var(--accent-gold-dim)' : 'transparent',
        color: !accountFilter ? 'var(--accent-gold)' : 'var(--text-muted)',
        fontSize: 11,
        fontFamily: 'var(--font-display)',
        fontWeight: 600,
        cursor: 'pointer',
        transition: 'all 120ms ease',
        letterSpacing: '0.04em',
      }}
    >
      ALL
    </button>
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
        }}
      >
        {name.toUpperCase()}
      </button>
    ))}
  </div>
)}
```

- [ ] **Step 4: Apply filter to displayed signals**

Find the `.map()` call over signals. Just before it, add:

```typescript
const displayedSignals = accountFilter
  ? signals.filter(s => s.account_name === accountFilter)
  : signals
```

Replace `signals.map(` with `displayedSignals.map(`

- [ ] **Step 5: Add account badge to each signal row**

In the signal row render, find where `symbol` and `side` are displayed. After them, add:

```tsx
{signal.account_name && (
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
    {signal.account_name}
  </span>
)}
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading/frontend
npx tsc --noEmit 2>&1 | head -20
```
Expected: no new errors

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/dashboard/SignalTable.tsx
git commit -m "feat: [DEV-61] SignalTable — filter pills per account + account badge per row"
```

---

## Task 8: Update LivePnlTicker — All Accounts + LIVE Filter

**Files:**
- Modify: `frontend/src/components/dashboard/LivePnlTicker.tsx`

- [ ] **Step 1: Read the current component**

```bash
cat frontend/src/components/dashboard/LivePnlTicker.tsx
```

- [ ] **Step 2: Add `liveOnly` prop to the props interface**

Find the existing props interface and add:
```typescript
liveOnly?: boolean   // default true — only show positions from LIVE-mode accounts
```

- [ ] **Step 3: Add `includePaper` state inside the component**

Add near the top of the component function body (after existing useState/useEffect calls):
```typescript
const [includePaper, setIncludePaper] = useState(!(liveOnly ?? true))
```

- [ ] **Step 4: Add LIVE-only toggle button**

Find where the component renders its header or title section, and add the toggle alongside it:

```tsx
<button
  onClick={() => setIncludePaper(p => !p)}
  style={{
    padding: '2px 8px',
    borderRadius: 10,
    border: '1px solid',
    borderColor: includePaper ? 'var(--accent-gold)' : 'var(--border)',
    background: includePaper ? 'var(--accent-gold-dim)' : 'transparent',
    color: includePaper ? 'var(--accent-gold)' : 'var(--text-muted)',
    fontSize: 9,
    fontFamily: 'var(--font-display)',
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'all 120ms ease',
    letterSpacing: '0.04em',
  }}
>
  {includePaper ? 'LIVE + PAPER' : 'LIVE ONLY ●'}
</button>
```

- [ ] **Step 5: Filter positions by run_mode**

Find where positions are mapped to rendered items. Just before the `.map()`, add:

```typescript
const displayedPositions = includePaper
  ? positions
  : positions.filter(p => (p.run_mode || p.runMode) === 'LIVE')
```

Replace `positions.map(` with `displayedPositions.map(`

- [ ] **Step 6: Add account label to each ticker item**

In the position row render, find where `symbol` is displayed and add after it:

```tsx
{position.account_name && (
  <span
    style={{
      fontSize: 9,
      color: 'var(--text-muted)',
      fontFamily: 'var(--font-mono)',
    }}
  >
    · {position.account_name}
  </span>
)}
```

- [ ] **Step 7: Verify TypeScript compiles**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading/frontend
npx tsc --noEmit 2>&1 | head -20
```
Expected: no new errors

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/dashboard/LivePnlTicker.tsx
git commit -m "feat: [DEV-61] LivePnlTicker — all-accounts mode, LIVE-only default, account labels"
```

---

## Task 9: Wire Everything Into `page.tsx`

**Files:**
- Modify: `frontend/src/app/page.tsx`

- [ ] **Step 1: Add imports at top of `page.tsx`**

After existing imports, add:
```typescript
import { useDashboardSummary } from '@/hooks/useDashboardSummary'
import { AccountSummaryStrip } from '@/components/dashboard/AccountSummaryStrip'
```

- [ ] **Step 2: Add hook call after existing hooks (around line 180)**

```typescript
const { data: dashboardSummary, isLoading: summaryLoading } = useDashboardSummary()
```

- [ ] **Step 3: Derive aggregated KPI values**

After the hook call, add:
```typescript
const totalPnlToday = dashboardSummary?.total_pnl_today ?? stats?.daily_pnl ?? 0
const totalWinRate = dashboardSummary?.total_win_rate ?? stats?.win_rate ?? 0
const totalActivePositions = dashboardSummary?.total_active_positions ?? stats?.active_trades ?? 0
const totalDrawdown = dashboardSummary?.max_drawdown_pct ?? stats?.daily_drawdown_pct ?? 0
```

- [ ] **Step 4: Update the 4 top-level StatCards to use derived values**

Find the StatCard instances for Total PnL, Win Rate, Active Positions, and Drawdown. Update their `value` props to use the derived variables from Step 3:

- Total PnL card: `value={totalPnlToday}`
- Win Rate card: `value={totalWinRate}`
- Active Positions card: `value={totalActivePositions}`
- Drawdown card: `value={totalDrawdown}`

(Leave the remaining 4 StatCards — Trades Today, Daily Drawdown, Risk, etc. — unchanged as they are per-account detail stats)

- [ ] **Step 5: Add AccountSummaryStrip between KPI row and main content**

Find where the KPI cards section ends (look for the closing of the grid/flex container holding StatCards) and insert after it:

```tsx
{/* Account Summary Strip */}
<div style={{ marginBottom: 24 }}>
  <div
    style={{
      fontFamily: 'var(--font-display)',
      fontSize: 10,
      fontWeight: 600,
      color: 'var(--text-muted)',
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      marginBottom: 10,
    }}
  >
    Accounts
  </div>
  <AccountSummaryStrip
    accounts={dashboardSummary?.accounts ?? []}
    isLoading={summaryLoading}
  />
</div>
```

- [ ] **Step 6: Add account filter state**

Near the top of the component (after existing useState calls), add:
```typescript
const [signalAccountFilter, setSignalAccountFilter] = useState<string | undefined>(undefined)
```

- [ ] **Step 7: Pass filter props to SignalTable**

Find the `<SignalTable />` render and add the three new props:
```tsx
accountFilter={signalAccountFilter}
onAccountFilterChange={setSignalAccountFilter}
accountNames={dashboardSummary?.accounts.map(a => a.name) ?? []}
```

- [ ] **Step 8: Pass liveOnly to LivePnlTicker**

Find the `<LivePnlTicker />` render and add:
```tsx
liveOnly={true}
```

- [ ] **Step 9: Verify TypeScript compiles**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading/frontend
npx tsc --noEmit 2>&1 | head -20
```
Expected: no new errors

- [ ] **Step 10: Commit**

```bash
git add frontend/src/app/page.tsx
git commit -m "feat: [DEV-61] wire multi-account dashboard — summary hook, account strip, signal filters"
```

---

## Task 10: Final Jira Update + Build Verification

- [ ] **Step 1: Final build check**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading/frontend
npx next build 2>&1 | tail -15
```
Expected: build succeeds

- [ ] **Step 2: Add progress comment to Jira**

```bash
cd /Users/ameeramer/dev/projects/galilsoftware/sources/trading
node scripts/jira-agent.js add-progress DEV-61 "Multi-account dashboard complete: /api/v1/dashboard/summary endpoint, AccountSummaryStrip, SignalTable filter pills, LivePnlTicker all-accounts mode, Sovereign Terminal design system wired into page.tsx"
```

- [ ] **Step 3: Transition to In Review**

```bash
node scripts/jira-agent.js set-status DEV-61 "In Review"
```

---

## Self-Review

**Spec coverage:**
- ✅ Main dashboard aggregated KPIs → Task 9 Steps 3–4
- ✅ Account summary strip with per-account cards → Tasks 6, 9 Step 5
- ✅ Click account → navigate to `/accounts/[name]` → Task 6 Step 1
- ✅ Signals filter pills (All + per account) → Task 7 Steps 3–4
- ✅ Account badge per signal row → Task 7 Step 5
- ✅ LivePnlTicker LIVE-only default + Paper toggle → Task 8 Steps 3–5
- ✅ Account label per ticker item → Task 8 Step 6
- ✅ Sovereign Terminal design system → Task 5
- ✅ Account type color borders (funded/eval/personal) → Task 6 Step 1
- ✅ Backend aggregation endpoint → Tasks 1–2
- ✅ Frontend types → Task 3
- ✅ TanStack Query hook → Task 4
- ✅ Jira DEV-61 tracking → Task 10

**Type consistency:**
- `AccountSummaryItem` — defined Task 3, used Tasks 6 and 9 ✅
- `DashboardSummary` — defined Task 3, used Task 4 hook return type and Task 9 ✅
- `useDashboardSummary` — defined Task 4, imported Task 9 ✅
- `AccountSummaryStrip` — defined Task 6, imported Task 9 ✅
- `liveOnly` prop on `LivePnlTicker` — added Task 8, passed Task 9 Step 8 ✅
- `accountFilter`, `onAccountFilterChange`, `accountNames` — added Task 7, passed Task 9 Step 7 ✅
