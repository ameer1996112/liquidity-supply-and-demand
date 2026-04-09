# Dashboard Account-Aware Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the main dashboard show data scoped to the currently active broker account (`selected_for_trading=true`) instead of blending data across all accounts.

**Architecture:** A new `ActiveAccountProvider` React context reads the active broker profile from the existing `/api/broker-profiles` endpoint and exposes `broker_profile_id` globally. The `fetchSignals` and `fetchSignalStats` Supabase helpers gain an optional `broker_profile_id` filter. The dashboard reads the active account from context and passes it to signal/stat hooks. Positions and account status endpoints already respect the active account on the backend — no backend changes needed.

**Tech Stack:** React Context API, TanStack Query (useQuery), Supabase JS client, Next.js App Router, TypeScript

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| **Create** | `frontend/src/providers/ActiveAccountProvider.tsx` | New context — fetches broker profiles, exposes active one |
| **Modify** | `frontend/src/lib/supabase.ts` | Add `broker_profile_id` param to `fetchSignals` and `fetchSignalStats` |
| **Modify** | `frontend/src/hooks/useTradingSignals.ts` | Pass `broker_profile_id` through to Supabase helpers; update query keys |
| **Modify** | `frontend/src/app/providers.tsx` (or equivalent root provider file) | Wrap app with `ActiveAccountProvider` |
| **Modify** | `frontend/src/app/page.tsx` | Consume `useActiveAccount()`, pass `broker_profile_id` to hooks; show account badge |

---

## Task 1: Create `ActiveAccountProvider`

**Files:**
- Create: `frontend/src/providers/ActiveAccountProvider.tsx`

- [ ] **Step 1: Write the file**

```tsx
'use client';

import { createContext, useContext, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');

interface ActiveBrokerProfile {
  id: number;
  name: string;
  selected_for_trading: boolean;
  run_mode: string;
  account_type: 'personal' | 'evaluation' | 'funded';
  prop_firm_name?: string | null;
}

interface ActiveAccountContextValue {
  activeProfile: ActiveBrokerProfile | null;
  broker_profile_id: number | null;
  isLoading: boolean;
}

const ActiveAccountContext = createContext<ActiveAccountContextValue>({
  activeProfile: null,
  broker_profile_id: null,
  isLoading: true,
});

async function fetchBrokerProfiles(): Promise<ActiveBrokerProfile[]> {
  const r = await fetch(`${API_BASE}/api/broker-profiles`);
  if (!r.ok) throw new Error('Failed to load broker profiles');
  return r.json();
}

export function ActiveAccountProvider({ children }: { children: ReactNode }) {
  const { data: profiles, isLoading } = useQuery({
    queryKey: ['broker-profiles'],
    queryFn: fetchBrokerProfiles,
    refetchInterval: 30_000,
    staleTime: 20_000,
  });

  const activeProfile = profiles?.find((p) => p.selected_for_trading) ?? null;

  return (
    <ActiveAccountContext.Provider
      value={{
        activeProfile,
        broker_profile_id: activeProfile?.id ?? null,
        isLoading,
      }}
    >
      {children}
    </ActiveAccountContext.Provider>
  );
}

export function useActiveAccount(): ActiveAccountContextValue {
  return useContext(ActiveAccountContext);
}
```

- [ ] **Step 2: Verify file compiles — no test needed for a context file, just check TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep ActiveAccount
```

Expected: no output (no errors)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/providers/ActiveAccountProvider.tsx
git commit -m "feat: [DEV-XX] add ActiveAccountProvider context for active broker profile"
```

---

## Task 2: Register `ActiveAccountProvider` in the app

**Files:**
- Modify: find the root providers file — run `grep -rn "TradingModeProvider" frontend/src/app/ | head -5` to locate it

- [ ] **Step 1: Find the root providers file**

```bash
grep -rn "TradingModeProvider" frontend/src/app/ | head -5
```

Expected output: a file like `frontend/src/app/providers.tsx` or `frontend/src/app/layout.tsx`

- [ ] **Step 2: Add `ActiveAccountProvider` import and wrapping**

Open the file found above. Add the import at the top:

```tsx
import { ActiveAccountProvider } from '@/providers/ActiveAccountProvider';
```

Then wrap the children **inside** `QueryProvider` (needs React Query available) and **outside** `TradingModeProvider`:

```tsx
// Before
<QueryProvider>
  <TradingModeProvider>
    {children}
  </TradingModeProvider>
</QueryProvider>

// After
<QueryProvider>
  <ActiveAccountProvider>
    <TradingModeProvider>
      {children}
    </TradingModeProvider>
  </ActiveAccountProvider>
</QueryProvider>
```

- [ ] **Step 3: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no new errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/providers.tsx  # or layout.tsx — use the file you found
git commit -m "feat: [DEV-XX] register ActiveAccountProvider in app provider tree"
```

---

## Task 3: Add `broker_profile_id` filter to Supabase helpers

**Files:**
- Modify: `frontend/src/lib/supabase.ts` — `fetchSignals()` and `fetchSignalStats()`

- [ ] **Step 1: Update `fetchSignals` to accept and apply `broker_profile_id`**

In `frontend/src/lib/supabase.ts`, find the `fetchSignals` function (around line 52). Update the options type and query:

```ts
// Before
export async function fetchSignals(
  options: {
    mode?: 'LIVE' | 'PAPER' | 'BACKTEST';
    limit?: number;
    offset?: number;
    runId?: string;
  } = {}
): Promise<TradingSignal[]> {
  // ...
  const { mode, limit = 50, offset = 0, runId } = options;

  let query = supabase
    .from('trading_signals')
    .select('*')
    .order('created_at', { ascending: false })
    .range(offset, offset + limit - 1);

  if (mode) {
    query = query.eq('run_mode', mode);
  }

  if (runId) {
    query = query.eq('run_id', runId);
  }
```

```ts
// After
export async function fetchSignals(
  options: {
    mode?: 'LIVE' | 'PAPER' | 'BACKTEST';
    limit?: number;
    offset?: number;
    runId?: string;
    broker_profile_id?: number | null;
  } = {}
): Promise<TradingSignal[]> {
  // ...
  const { mode, limit = 50, offset = 0, runId, broker_profile_id } = options;

  let query = supabase
    .from('trading_signals')
    .select('*')
    .order('created_at', { ascending: false })
    .range(offset, offset + limit - 1);

  if (mode) {
    query = query.eq('run_mode', mode);
  }

  if (runId) {
    query = query.eq('run_id', runId);
  }

  if (broker_profile_id) {
    query = query.eq('broker_profile_id', broker_profile_id);
  }
```

- [ ] **Step 2: Update `fetchSignalStats` to accept and apply `broker_profile_id`**

Find `fetchSignalStats` (around line 96). Update:

```ts
// Before
export async function fetchSignalStats(): Promise<SignalStats> {
  if (!supabase) {
    return getMockStats();
  }

  const twentyFourHoursAgo = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();

  const { data, error } = await supabase
    .from('trading_signals')
    .select('*')
    .gte('created_at', twentyFourHoursAgo);
```

```ts
// After
export async function fetchSignalStats(
  options: { broker_profile_id?: number | null } = {}
): Promise<SignalStats> {
  if (!supabase) {
    return getMockStats();
  }

  const twentyFourHoursAgo = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();

  let query = supabase
    .from('trading_signals')
    .select('*')
    .gte('created_at', twentyFourHoursAgo);

  if (options.broker_profile_id) {
    query = query.eq('broker_profile_id', options.broker_profile_id);
  }

  const { data, error } = await query;
```

> Note: Remove the old `const { data, error } = await supabase...` line — it is now replaced by the `let query` + `const { data, error } = await query` pattern above.

- [ ] **Step 3: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep supabase
```

Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/supabase.ts
git commit -m "feat: [DEV-XX] add broker_profile_id filter to fetchSignals and fetchSignalStats"
```

---

## Task 4: Update `useTradingSignals` and `useSignalStats` hooks

**Files:**
- Modify: `frontend/src/hooks/useTradingSignals.ts`

- [ ] **Step 1: Update `signalKeys` to include `broker_profile_id`**

Find the `signalKeys` object (around line 109):

```ts
// Before
export const signalKeys = {
  all: ['trading-signals'] as const,
  list: (mode?: TradingMode) => [...signalKeys.all, 'list', mode] as const,
  stats: ['trading-stats'] as const,
};
```

```ts
// After
export const signalKeys = {
  all: ['trading-signals'] as const,
  list: (mode?: TradingMode, broker_profile_id?: number | null) =>
    [...signalKeys.all, 'list', mode, broker_profile_id] as const,
  stats: (broker_profile_id?: number | null) =>
    ['trading-stats', broker_profile_id] as const,
};
```

- [ ] **Step 2: Update `useTradingSignals` signature and query**

Find the `useTradingSignals` function (around line 139):

```ts
// Before
export function useTradingSignals(mode?: TradingMode) {
  const queryClient = useQueryClient();
  // ...
  const query = useQuery({
    queryKey: signalKeys.list(mode),
    queryFn: async () => {
      const rawSignals = await fetchSignals({
        mode,
        limit: CONFIG.SIGNAL_LIMIT,
      });
```

```ts
// After
export function useTradingSignals(mode?: TradingMode, broker_profile_id?: number | null) {
  const queryClient = useQueryClient();
  // ...
  const query = useQuery({
    queryKey: signalKeys.list(mode, broker_profile_id),
    queryFn: async () => {
      const rawSignals = await fetchSignals({
        mode,
        limit: CONFIG.SIGNAL_LIMIT,
        broker_profile_id,
      });
```

- [ ] **Step 3: Update the realtime batch flush to use the new query key**

Inside `flushRealtimeBatch` (around line 164), update the `queryClient.setQueryData` call:

```ts
// Before
queryClient.setQueryData<TradingSignal[]>(
  signalKeys.list(mode),
```

```ts
// After
queryClient.setQueryData<TradingSignal[]>(
  signalKeys.list(mode, broker_profile_id),
```

- [ ] **Step 4: Update `useSignalStats` signature**

Find `useSignalStats` (around line 362):

```ts
// Before
export function useSignalStats() {
  return useQuery({
    queryKey: signalKeys.stats,
    queryFn: async () => {
      const stats = await fetchSignalStats();
```

```ts
// After
export function useSignalStats(broker_profile_id?: number | null) {
  return useQuery({
    queryKey: signalKeys.stats(broker_profile_id),
    queryFn: async () => {
      const stats = await fetchSignalStats({ broker_profile_id });
```

- [ ] **Step 5: Fix `signalKeys.stats` reference in `flushRealtimeBatch`**

Inside `flushRealtimeBatch`, find the invalidate call:

```ts
// Before
queryClient.invalidateQueries({ queryKey: signalKeys.stats });
```

```ts
// After
queryClient.invalidateQueries({ queryKey: signalKeys.stats(broker_profile_id) });
```

- [ ] **Step 6: Fix `useRefreshSignals` which also references `signalKeys.stats`**

Find `useRefreshSignals` (around line 397):

```ts
// Before
queryClient.invalidateQueries({ queryKey: signalKeys.stats });
```

```ts
// After
queryClient.invalidateQueries({ queryKey: ['trading-stats'] });
```

> Note: Using the base prefix `['trading-stats']` here invalidates ALL stat variants (all accounts) on manual refresh — which is the correct behavior for a "refresh everything" action.

- [ ] **Step 7: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep useTradingSignals
```

Expected: no errors

- [ ] **Step 8: Commit**

```bash
git add frontend/src/hooks/useTradingSignals.ts
git commit -m "feat: [DEV-XX] scope useTradingSignals and useSignalStats to broker_profile_id"
```

---

## Task 5: Update dashboard page to consume active account

**Files:**
- Modify: `frontend/src/app/page.tsx`

- [ ] **Step 1: Add `useActiveAccount` import**

At the top of `frontend/src/app/page.tsx`, add:

```tsx
import { useActiveAccount } from '@/providers/ActiveAccountProvider';
```

- [ ] **Step 2: Consume the context in the main dashboard component**

Find where `useTradingMode` is called inside the dashboard component. Add `useActiveAccount` next to it:

```tsx
// Before
const { mode: activeMode } = useTradingMode();
const { data: signals } = useTradingSignals(activeMode);
const { data: stats } = useSignalStats();
```

```tsx
// After
const { mode: activeMode } = useTradingMode();
const { broker_profile_id, activeProfile } = useActiveAccount();
const { data: signals } = useTradingSignals(activeMode, broker_profile_id);
const { data: stats } = useSignalStats(broker_profile_id);
```

- [ ] **Step 3: Add account name badge to the dashboard header**

Find the header area where `ModeBadge` is rendered. Add the account badge immediately after it:

```tsx
// Find this pattern (approximate — look for ModeBadge usage in JSX):
<ModeBadge mode={activeMode} />

// Add after it:
{activeProfile && (
  <a
    href="/accounts"
    className="inline-flex items-center gap-1.5 rounded border border-panel-border bg-surface px-2 py-0.5 text-xs text-text-secondary hover:text-text-primary transition-colors"
  >
    <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
    {activeProfile.name}
  </a>
)}
```

- [ ] **Step 4: Verify TypeScript**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/page.tsx
git commit -m "feat: [DEV-XX] dashboard now scoped to active broker profile"
```

---

## Task 6: Manual verification checklist

- [ ] **Step 1: Start dev server**

```bash
cd frontend && npm run dev
```

- [ ] **Step 2: Check React Query devtools**

Open browser devtools → React Query tab. Verify:
- `['broker-profiles']` query is present and has data
- `['trading-signals', 'list', 'LIVE', <id>]` query key includes your account's `broker_profile_id`
- `['trading-stats', <id>]` query key includes your account's `broker_profile_id`

- [ ] **Step 3: Check account badge renders**

The dashboard header should show a small green dot + account name (e.g. "FTMO-Demo-50K") next to the LIVE badge. Clicking it should navigate to `/accounts`.

- [ ] **Step 4: Switch accounts and verify dashboard updates**

1. Go to `/accounts`
2. Activate a different account
3. Return to dashboard
4. Wait up to 30 seconds (or hard refresh)
5. Verify: account badge name changes, signal/stat data re-fetches with new `broker_profile_id`

- [ ] **Step 5: Check null safety — no account selected**

In Supabase, temporarily set all `selected_for_trading = false`. Reload dashboard.
Expected: dashboard renders normally (account badge hidden, signals unfiltered as fallback)

- [ ] **Step 6: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: [DEV-XX] dashboard account-aware verification fixes"
```
