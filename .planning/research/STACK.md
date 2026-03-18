# Technology Stack — Prop Firm Challenge Dashboard

**Project:** Prop firm challenge tracker embedded in Accounts page
**Milestone:** Subsequent — existing trading bot stack is unchanged
**Researched:** 2026-03-18
**Overall confidence:** HIGH (all findings drawn directly from codebase inspection)

---

## Scope

This document covers only the incremental stack for the prop firm challenge dashboard
feature. The base trading stack (FastAPI, Supabase, Next.js 16, TanStack Query, MetaAPI
REST adapter) is already documented in `.planning/codebase/STACK.md` and must not be
duplicated or changed.

---

## MetaAPI: Fields for Firm Detection

**Confidence: HIGH** — Confirmed in `src/adapters/execution/meta_api_adapter.py` and
`src/services/account_sync_service.py`. The `server` field is already fetched, stored,
and surfaced to the backend.

### How the `server` field reaches the system

The `get_account_status()` method in `MetaApiAdapter` calls two MetaAPI endpoints and
merges them:

1. `GET /users/current/accounts/{id}/account-information` — balance, equity, margin
2. `GET /users/current/accounts/{id}` — **`server`**, `platform`, `state`, `connectionStatus`

The merged dict is written to `account_status_snapshots.server_name` (VARCHAR 100) by
`AccountSyncService.sync_account_status()`. The value arrives as a string like
`FTMO-Server2`, `FTMO-Server3`, or `Real 3` (for non-prop accounts).

### Fields available from MetaAPI account object

| Field | MetaAPI key | Example | Available? |
|-------|-------------|---------|-----------|
| Broker server name | `server` | `FTMO-Server3` | YES — already stored |
| Platform | `platform` | `mt5` | YES — stored |
| Account state | `state` | `DEPLOYED` | YES — merged |
| Connection status | `connectionStatus` | `CONNECTED` | YES — stored |
| Balance | `balance` | `50403.56` | YES |
| Equity | `equity` | `50250.12` | YES |
| Margin | `margin` | `120.50` | YES |
| Free margin | `freeMargin` | `50129.62` | YES |
| Leverage | `leverage` | `100` | YES — stored |

The `account_strategies` table also stores `server_name` (synced by `account_sync_service`).
The `broker_profiles` table also has `server_name` populated at connection time
(line 225 of `account_orchestrator.py`).

### Server-name to firm detection mapping

Use a pure Python dict lookup. No regex needed for FTMO (all known servers follow
`FTMO-Server{N}` exactly). The lookup should live in a new module, e.g.
`src/services/prop_firm_detector.py`.

```python
FIRM_SERVER_PREFIXES = {
    "FTMO-Server": "ftmo",
    "FTMO-Demo":   "ftmo",
    # Future firms added here without schema change
}

def detect_firm(server_name: str) -> str:
    """Returns lowercase firm slug or 'unknown'."""
    if not server_name:
        return "unknown"
    server_upper = server_name.upper()
    for prefix, slug in FIRM_SERVER_PREFIXES.items():
        if server_upper.startswith(prefix.upper()):
            return slug
    return "unknown"
```

**Confidence: HIGH** — server string `FTMO-Server2` is already confirmed in the codebase
(logs and doc strings reference it). Detection via prefix match is the standard pattern
used by commercial prop-firm dashboards.

Unknown servers must return `"unknown"` and the account card must render gracefully
(no prop firm section shown) — this is an explicit constraint in `PROJECT.md`.

---

## Supabase: `prop_firm_rules` Table Design

**Confidence: HIGH** — Based on direct inspection of existing migration patterns
(migrations 015, 021, 028) and the `broker_profiles` evaluation columns.

### Why a new table (not just columns on `broker_profiles`)

`broker_profiles` already carries the per-account evaluation config
(`max_daily_loss_pct`, `max_drawdown_pct`, `profit_target`, etc.) — these are the
user's *configured* limits for a specific account. The new `prop_firm_rules` table is
a *read-only reference catalogue* of standard firm rules, keyed by `(firm_slug,
challenge_type)`. This separation means:

- Rules for FTMO Phase 1 are stored once and shared across all FTMO accounts
- Adding a new firm (The5ers, FundedNext) requires only an INSERT, not ALTER TABLE
- Rule lookups are a simple key-value fetch at challenge setup time

### Recommended schema

```sql
-- Migration 047_prop_firm_rules.sql
CREATE TABLE IF NOT EXISTS public.prop_firm_rules (
    id               BIGSERIAL PRIMARY KEY,

    -- Firm identification
    firm_slug        VARCHAR(64) NOT NULL,   -- 'ftmo', 'the5ers', 'funded_next'
    firm_display     VARCHAR(128) NOT NULL,  -- 'FTMO', 'The5ers', 'FundedNext'

    -- Challenge type
    challenge_type   VARCHAR(32) NOT NULL    -- 'phase1', 'phase2', 'funded'
                     CHECK (challenge_type IN ('phase1', 'phase2', 'funded')),

    -- Account size tier (NULL = applies to all sizes)
    account_size_usd INTEGER,               -- 10000, 25000, 50000, 100000, 200000

    -- Core rules
    daily_dd_pct     REAL NOT NULL,         -- 5.0  (max daily loss % of starting balance)
    total_dd_pct     REAL NOT NULL,         -- 10.0 (max drawdown % — trailing or absolute)
    total_dd_type    VARCHAR(16) NOT NULL   -- 'trailing' | 'balance_based'
                     DEFAULT 'balance_based'
                     CHECK (total_dd_type IN ('trailing', 'balance_based')),
    profit_target_pct REAL NOT NULL,        -- 10.0 (% of starting balance to reach)
    min_trading_days  INTEGER NOT NULL,     -- 4 (min distinct calendar days with a trade)
    max_trading_days  INTEGER,              -- 30 (NULL = unlimited, e.g. funded)
    consistency_rule_pct REAL,             -- 40.0 (best day <= X% of total profit; NULL = no rule)

    -- Metadata
    notes            TEXT,                  -- Human-readable notes (e.g. "No news trading rule")
    source_url       TEXT,                  -- https://ftmo.com/en/trading-rules/
    effective_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_prop_firm_rules_lookup
    ON public.prop_firm_rules (firm_slug, challenge_type, COALESCE(account_size_usd, 0));

-- FTMO seed data (confirmed from broker_profiles defaults already in migration 021)
INSERT INTO public.prop_firm_rules
    (firm_slug, firm_display, challenge_type, account_size_usd,
     daily_dd_pct, total_dd_pct, total_dd_type,
     profit_target_pct, min_trading_days, max_trading_days,
     consistency_rule_pct, source_url)
VALUES
    -- FTMO Phase 1 (all sizes share same %)
    ('ftmo', 'FTMO', 'phase1', NULL,
     5.0, 10.0, 'balance_based',
     10.0, 4, 30,
     40.0, 'https://ftmo.com/en/trading-rules/'),

    -- FTMO Phase 2
    ('ftmo', 'FTMO', 'phase2', NULL,
     5.0, 10.0, 'balance_based',
     5.0, 4, 60,
     40.0, 'https://ftmo.com/en/trading-rules/'),

    -- FTMO Funded
    ('ftmo', 'FTMO', 'funded', NULL,
     5.0, 10.0, 'trailing',
     0.0, 0, NULL,
     40.0, 'https://ftmo.com/en/trading-rules/')
ON CONFLICT DO NOTHING;
```

### How challenge setup interacts with this table

On challenge type selection (one-time setup per account):
1. UI shows dropdown populated from `SELECT DISTINCT firm_slug, challenge_type FROM prop_firm_rules`
2. On selection, copy `daily_dd_pct`, `total_dd_pct`, `profit_target_pct`, `min_trading_days`
   into `broker_profiles` evaluation columns (already have these columns from migration 021)
3. Flag `broker_profiles.evaluation_mode = true`

The per-account columns in `broker_profiles` are the live working copy.
`prop_firm_rules` is the catalogue. This avoids re-querying the rules table on every
metrics refresh — the backend reads only from `broker_profiles`.

### Migration numbering

Next migration is `047_prop_firm_rules.sql` (after the existing `046_be_trigger.sql`).

---

## Backend: New API Endpoint

**Confidence: HIGH** — Follows the pattern in `src/api_prop_firm.py` and
`src/api_portfolio_control.py`.

### New endpoint: `GET /api/v1/prop-firm/challenge-status/{account_name}`

This is the single endpoint the account card polls. It returns everything the card
needs in one round trip.

```python
class ChallengeStatusResponse(BaseModel):
    account_name: str
    firm_slug: str           # 'ftmo' | 'unknown'
    firm_display: str        # 'FTMO' | 'Unknown'
    challenge_type: str      # 'phase1' | 'phase2' | 'funded'
    # Real-time metrics
    daily_dd_pct: float      # current daily drawdown %
    daily_dd_limit: float    # from broker_profiles
    total_dd_pct: float      # current trailing/balance drawdown %
    total_dd_limit: float    # from broker_profiles
    profit_pct: float        # current profit as % of starting balance
    profit_target_pct: float # from broker_profiles
    trading_days: int        # distinct days with at least one closed trade
    min_trading_days: int    # from broker_profiles
    # Alert flags
    daily_dd_warn: bool      # daily_dd_pct >= daily_dd_limit * 0.8
    total_dd_warn: bool
    profit_near_target: bool  # profit_pct >= profit_target_pct * 0.8
    any_breach: bool
    # Source
    server_name: str | None
    last_updated: str        # ISO timestamp
```

The endpoint delegates to the existing `EvaluationTracker` / `PropFirmTracker` services
for metric computation, adding only the firm detection logic at the top.

### Firm detection integration point

```python
# In the endpoint handler:
server_name = (
    sb.table("account_status_snapshots")
      .select("server_name")
      .eq("account_name", account_name)
      .order("snapshot_time", desc=True)
      .limit(1)
      .execute()
      .data or [{}]
)[0].get("server_name")

firm_slug = detect_firm(server_name or "")
```

If `firm_slug == "unknown"`, return the response with metrics computed from
`broker_profiles` evaluation columns (user may have manually configured them) but
set `firm_display = "Unknown"`. Never error out.

---

## React: Polling Pattern and Progress Bar Implementation

**Confidence: HIGH** — Directly confirmed from `usePositions.ts` (5s interval) and
`useEvaluationStats.ts` (10s interval) in the codebase.

### Polling vs WebSocket decision

**Use polling at 10s interval. Do not introduce WebSocket infrastructure.**

Rationale specific to this feature:
- Prop firm metrics change only when a trade closes or MTM moves significantly — a 10s
  delay is imperceptible to the trader
- The existing `usePropFirmMetrics` hook already polls at 10s (`refetchInterval: 10_000`)
  for the standalone prop firm page. The account card should match this
- MetaAPI itself is polled (no push callbacks implemented per `INTEGRATIONS.md`), so
  faster polling than 10s only adds backend load without fresher data
- Adding Supabase Realtime subscriptions for this use case would introduce a new
  dependency class (`@supabase/supabase-js` realtime channels) without meaningful UX benefit
- The `@supabase/supabase-js` client (`2.93.3`) already supports Realtime subscriptions
  in the frontend, but none of the existing data flows use them — adopting it for a
  progress bar is not worth the surface area

**Polling interval table:**

| Metric type | Interval | Reasoning |
|-------------|----------|-----------|
| Challenge status (progress bars) | 10s | Matches EvaluationStats, acceptable staleness |
| Account balance on card header | 15s | Matches `useLiveBrokerBalance` already in codebase |
| Firm rules from DB | `staleTime: 300_000` / no `refetchInterval` | Rules are static, fetched once |

### TanStack Query hook pattern

Follow `usePropFirmMetrics` exactly (already exists in `src/hooks/usePropFirm.ts`).
The new hook for the embedded card:

```typescript
// src/hooks/useChallengeStatus.ts
export function useChallengeStatus(accountName: string) {
  return useQuery({
    queryKey: ['challenge-status', accountName],
    queryFn: () => fetchChallengeStatus(accountName),
    refetchInterval: 10_000,
    staleTime: 5_000,
    retry: 1,
    enabled: !!accountName,
  });
}
```

The `retry: 1` (not the default 3) is consistent with all existing live-data hooks
(`useActivePositions`, `useEvaluationStats`, `usePropFirmMetrics`) — prevents cascading
retries when the backend is briefly unavailable.

### Progress bar component

`<Progress>` already exists at `frontend/src/components/ui/progress.tsx` with:
- `value` / `max` props
- `indicatorClassName` for color override
- CSS transition via `transition-all duration-300`

No new UI library needed. The `EvaluationDashboard` component already demonstrates
the three-color pattern (green → amber → red) based on percentage consumed:

```typescript
// Confirmed pattern from EvaluationDashboard.tsx
const indicatorColor = (consumed: number, limit: number) => {
  const pct = (consumed / limit) * 100;
  if (pct >= 100) return 'bg-[var(--to-short)]';        // breach
  if (pct >= 80)  return 'bg-[var(--to-warning)]';      // 80% warn
  return 'bg-[var(--to-long)]';                         // safe
};
```

This pattern is already used for daily loss, total drawdown, and consistency bars in
`EvaluationDashboard.tsx`. The account card embed should reuse it identically.

### Component architecture for the embed

The prop firm section in the account card must be a self-contained sub-component
(not inlined into `EnhancedAccountCard.tsx`):

```
EnhancedAccountCard.tsx
  └── PropFirmSection.tsx      ← new, self-contained
        └── Progress (existing)
        └── Badge (existing)
        └── ChallengeSetupPrompt.tsx ← one-time setup if firm detected but no challenge_type set
```

`PropFirmSection` accepts `accountName: string` and calls `useChallengeStatus(accountName)`
internally. This keeps the account card's prop interface stable — no new props are added
to `EnhancedAccountCard`.

The section renders nothing (zero height) when `firm_slug === "unknown"` and challenge
has not been manually configured, satisfying the graceful-handling constraint.

---

## Libraries Already Available

All required libraries for this feature are already installed. No new dependencies needed.

| Need | Library | Already in package.json |
|------|---------|------------------------|
| Data fetching + polling | `@tanstack/react-query 5.90+` | YES |
| Progress bars | Custom `<Progress>` component | YES (ui/progress.tsx) |
| Badges / status chips | `<Badge>` component | YES (ui/badge.tsx) |
| Alert banners | `<Alert>` component | YES (ui/alert.tsx) |
| Icons | `lucide-react 0.563+` | YES |
| Date formatting | `date-fns 4.1+` | YES |
| CSS utility merging | `tailwind-merge` | YES |
| Supabase client | `@supabase/supabase-js 2.93.3` | YES |

---

## Existing Code to Reuse (Not Rewrite)

**Confidence: HIGH** — Confirmed by direct code inspection.

| Existing artifact | Reuse for |
|------------------|-----------|
| `EvaluationDashboard.tsx` | Source the Progress + color pattern; do not duplicate |
| `useEvaluationStats.ts` | Model for `useChallengeStatus` hook (same shape) |
| `usePropFirmMetrics` / `usePropFirmHistory` | Existing hooks; consolidate or delegate from new endpoint |
| `PropFirmTracker` service (`src/services/prop_firm_tracker.py`) | Call from the new endpoint — do not rewrite |
| `EvaluationTracker` service | Same — delegate to it |
| `broker_profiles` evaluation columns (migration 021) | Already have `evaluation_mode`, `evaluation_phase`, `max_daily_loss_pct`, `max_drawdown_pct`, `profit_target`, `consistency_limit_pct` |
| `account_status_snapshots.server_name` | Use to look up firm without additional MetaAPI call |
| `api_portfolio_control.py` challenge endpoints | Existing `GET/PUT /accounts/{name}/challenge` for one-time setup |

---

## What Does NOT Exist Yet (Must Be Built)

| Component | What it is |
|-----------|-----------|
| `prop_firm_detector.py` | Server-name → firm slug mapping (pure dict lookup, ~20 lines) |
| `047_prop_firm_rules.sql` | New table + FTMO seed data |
| `GET /api/v1/prop-firm/challenge-status/{account_name}` | Unified endpoint for card polling |
| `PropFirmSection.tsx` | React sub-component embedded in `EnhancedAccountCard` |
| `useChallengeStatus` hook | TanStack Query hook for the above endpoint |
| `ChallengeSetupPrompt.tsx` | One-time inline prompt when firm is detected but type not set |

---

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| MetaAPI `server` field availability | HIGH | Confirmed in adapter code, stored in `account_status_snapshots` |
| Server-name detection pattern | HIGH | String prefix match confirmed from existing log strings |
| `prop_firm_rules` table design | HIGH | Derived from existing migration patterns and `broker_profiles` columns |
| React polling pattern | HIGH | Confirmed from `usePositions` (5s) and `useEvaluationStats` (10s) — 10s is right for this |
| WebSocket decision | HIGH | No existing WebSocket usage in frontend; cost-benefit clearly favors polling |
| FTMO rule values (5%/10%/10%/4 days) | MEDIUM | Hardcoded in existing `api_prop_firm.py` (line 91, 104) and `broker_profiles` defaults; not verified against FTMO website (web access denied) |
| Progress bar component | HIGH | `Progress` component exists and is already used for identical purpose in `EvaluationDashboard` |

---

## Known Gaps

1. **FTMO rule values should be externally verified.** The seeded values (5% daily DD,
   10% total DD, 10% profit target, 4 min trading days, 40% consistency) match existing
   hardcoded constants in `api_prop_firm.py` and `broker_profiles` defaults. However,
   FTMO rules can change without notice. The `source_url` and `effective_date` columns
   in `prop_firm_rules` exist precisely to flag when a manual re-check is due.

2. **FTMO trailing vs balance-based drawdown.** FTMO's funded account uses trailing
   drawdown (peak equity based), while Phase 1/2 use balance-based. The `total_dd_type`
   column captures this, but the computation logic in `PropFirmTracker` must be
   verified to implement both correctly.

3. **The challenge setup UX flow** (one-time prompt per account) needs frontend design
   decisions not resolvable from the stack research alone — specifically whether it
   appears inline in the card or in a modal. The `useChallengeSettings` /
   `useUpdateChallengeSettings` hooks already exist in `useChallenge.ts` for this.

---

*Research complete: 2026-03-18. No external searches performed (permissions denied).
All findings are HIGH confidence from direct codebase inspection.*
