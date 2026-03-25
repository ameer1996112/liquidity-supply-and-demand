# Multi-Account Dashboard Upgrade Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a unified multi-account interface by allowing the main Dashboard to filter by account, and reusing the Dashboard layout on individual Account detail pages.

**Architecture:** The dashboard currently fetches data globally directly from Supabase. We will modify `fetchSignals`, `fetchSignalStats`, and other relevant Supabase queries to accept an `accountName` parameter. Then we extract the inner grid of `page.tsx` into a reusable `<DashboardView>` component that passes this `accountName` query parameter down to the React Query hooks.

**Tech Stack:** Next.js, React Query, Supabase JS Client

---

## Chunk 1: Update Supabase API Fetchers

**Files:**
- Modify: `frontend/src/lib/supabase.ts`

- [ ] **Step 1: Update `fetchSignals` parameter**
Modify `fetchSignals` to accept `accountName?: string` inside its `options` object, and append `.eq('account_name', accountName)` if provided.

- [ ] **Step 2: Update `fetchSignalStats` parameter**
Modify `fetchSignalStats(accountName?: string)` to accept an account name. 
Add `.eq('account_name', accountName)` to the 24h signals query.
Add `.eq('account_name', accountName)` to the closed signals query.
For snapshot queries, filter `account_strategies` appropriately.

- [ ] **Step 3: Commit**
```bash
git add frontend/src/lib/supabase.ts
git commit -m "feat(api): add accountName filtering to Supabase data fetchers"
```

## Chunk 2: Update React Query Hooks

**Files:**
- Modify: `frontend/src/hooks/useTradingSignals.ts`
- Modify: `frontend/src/hooks/useDashboardLog.ts`

- [ ] **Step 1: Update `useTradingSignals`**
Accept `accountName?: string` as a second parameter. Pass it to `fetchSignals` in the `queryFn`.
Update the query cache keys to include `accountName`.

- [ ] **Step 2: Update `useSignalStats`**
Accept `accountName` parameter. Pass to `fetchSignalStats`. Update query keys.

- [ ] **Step 3: Update `useDashboardLog` (if necessary)**
Ensure log merging correctly handles specific account contexts if logs are filtered.

- [ ] **Step 4: Commit**
```bash
git add frontend/src/hooks/
git commit -m "feat(hooks): forward account name to data fetching hooks"
```

## Chunk 3: Extract `<DashboardView>` Component

**Files:**
- Create: `frontend/src/components/dashboard/DashboardView.tsx`
- Modify: `frontend/src/app/page.tsx`

- [ ] **Step 1: Create `<DashboardView>`**
Move all the layout grids, `StatCard`s, `SignalTable`, and `<LiveLog>` from `page.tsx` into `DashboardView.tsx`.
It should accept `props: { accountName?: string, activeMode: TradingMode }`.
It should invoke the updated hooks using `props.accountName`.

- [ ] **Step 2: Refactor `page.tsx`**
Replace the mass of code with `<DashboardView accountName={selectedAccount} />`.
Add a "Quick-Switch Tabs" navigation bar at the top with "Global" and tabs for active accounts (fetched via `useAccountsComparison` or similar).

- [ ] **Step 3: Test rendering**
Run `npm run dev` and navigate to `localhost:3000`. Ensure the Dashboard loads successfully with the "Global" tab.

- [ ] **Step 4: Commit**
```bash
git add frontend/src/components/dashboard/DashboardView.tsx frontend/src/app/page.tsx
git commit -m "refactor(ui): extract DashboardView component and add account tabs"
```

## Chunk 4: Update Account Detail Page

**Files:**
- Modify: `frontend/src/app/accounts/[account_name]/page.tsx`

- [ ] **Step 1: Replace Overview Tab**
Import `<DashboardView>`. Under `activeTab === 'overview'`, replace the existing stub with `<DashboardView accountName={accountName} activeMode={"LIVE"} />`.

- [ ] **Step 2: Test rendering**
Navigate to `localhost:3000/accounts` and click on an account. The Overview tab should proudly display the scoped dashboard.

- [ ] **Step 3: Commit**
```bash
git add frontend/src/app/accounts/
git commit -m "feat(ui): embed DashboardView into Account detail page overview"
```
