# Architecture Patterns: Prop Firm Challenge Tracker Integration

**Domain:** Prop firm challenge tracking embedded in existing trading bot accounts page
**Researched:** 2026-03-18
**Context:** Integrating into FastAPI + React + Supabase system that already has partial prop firm infrastructure

---

## Recommended Architecture

### Component Boundary Map

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (React / Next.js)                                      │
│                                                                  │
│  accounts/page.tsx                                               │
│    └─ EnhancedAccountCard (existing)                             │
│         └─ PropFirmBadge (NEW — server_name → firm label)        │
│         └─ ChallengeProgressPanel (NEW — 4 progress bars)        │
│                                                                  │
│  accounts/[account_name]/page.tsx                                │
│    └─ ChallengeTab (EXISTING — already has phase switcher,       │
│         edit form, preset buttons; needs live metric overlay)    │
│                                                                  │
│  hooks/usePropFirmChallenge.ts (NEW)                             │
│    └─ polls GET /api/v1/prop-firm/challenge/{account_name}       │
│       every 5 seconds (matches positions page pattern)           │
└──────────────────────────────────────────────────────────────────┘
         │ HTTP polling 5s
         ▼
┌──────────────────────────────────────────────────────────────────┐
│  Backend (FastAPI)                                               │
│                                                                  │
│  api_prop_firm.py (NEW router)                                   │
│    GET /api/v1/prop-firm/challenge/{account_name}                │
│      ├─ Calls PropFirmDetector.detect(server_name)               │
│      ├─ Reads account_prop_firm_config (challenge_type)         │
│      ├─ Loads rules from prop_firm_rules table                   │
│      ├─ Calls PropFirmMetricsService.compute(account, rules)     │
│      └─ Returns ChallengeResponse                                │
│                                                                  │
│    PUT /api/v1/prop-firm/challenge/{account_name}/config         │
│      └─ Saves challenge_type to account_prop_firm_config         │
│                                                                  │
│  services/prop_firm_detector.py (NEW — thin, pure)              │
│    PropFirmDetector.detect(server_name: str) → str | None        │
│    Uses prop_firm_server_mappings table (NOT hardcoded)          │
│                                                                  │
│  services/prop_firm_metrics_service.py (NEW — wraps existing)   │
│    Adapts existing PropFirmTracker + portfolio_snapshots data    │
│    into the new ChallengeResponse shape                          │
│                                                                  │
│  (existing) services/prop_firm_tracker.py — kept untouched      │
│  (existing) api_funding.py — kept untouched (legacy page)        │
└──────────────────────────────────────────────────────────────────┘
         │ SQL queries (Supabase)
         ▼
┌──────────────────────────────────────────────────────────────────┐
│  Database (Supabase / PostgreSQL)                                │
│                                                                  │
│  NEW tables (additive, zero existing-table changes):             │
│    prop_firm_server_mappings   — server_name → firm slug         │
│    prop_firm_rules             — firm + challenge_type → limits  │
│    account_prop_firm_config    — per-account: firm + phase       │
│                                                                  │
│  EXISTING tables (read-only for this feature):                   │
│    account_status_snapshots    — server_name, balance, equity    │
│    prop_firm_metrics           — daily snapshots (already used)  │
│    broker_profiles             — evaluation_phase, limits        │
│    portfolio_snapshots         — daily PnL source                │
└──────────────────────────────────────────────────────────────────┘
```

---

## DB Schema (New Tables Only)

All three tables are purely additive — no `ALTER TABLE` on existing tables required.

### Table: `prop_firm_server_mappings`

Maps MetaAPI `server_name` strings to internal firm slugs. Lives in DB (not config, not hardcoded) so new firms are added by inserting a row, no deploy needed.

```sql
-- Migration 047_prop_firm_server_mappings.sql
CREATE TABLE IF NOT EXISTS public.prop_firm_server_mappings (
    id              BIGSERIAL PRIMARY KEY,
    -- Exact MetaAPI server name substring (matched with ILIKE '%pattern%')
    -- Examples: 'FTMO-Server', 'FTMO', 'ACG-MT5', 'MFF'
    server_pattern  VARCHAR(100) NOT NULL UNIQUE,
    -- Canonical slug used everywhere in code
    -- Examples: 'FTMO', 'ACG', 'MyFundedFX'
    firm_slug       VARCHAR(64)  NOT NULL,
    -- Human-readable display name for UI
    firm_display_name VARCHAR(128) NOT NULL,
    active          BOOLEAN      NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pfm_firm_slug
    ON public.prop_firm_server_mappings (firm_slug);

-- Seed: FTMO at launch
INSERT INTO public.prop_firm_server_mappings
    (server_pattern, firm_slug, firm_display_name)
VALUES
    ('FTMO',     'FTMO',       'FTMO'),
    ('FTMO-Server', 'FTMO',   'FTMO')
ON CONFLICT (server_pattern) DO NOTHING;
```

**Design rationale:** pattern matching (`ILIKE '%pattern%'`) is sufficient because MetaAPI server names are stable strings like `FTMO-Server3`. The backend iterates rows ordered by `LENGTH(server_pattern) DESC` to give longer/more-specific patterns priority.

---

### Table: `prop_firm_rules`

Canonical rules per (firm, challenge_type) pair. These are the **firm's official limits** — not the bot's conservative kill thresholds. The UI displays these to give the trader the full picture; the guard rail in `prop_guard.py` continues to use `broker_profiles.max_daily_loss_pct` (which is set below firm limits as a safety buffer).

```sql
-- Part of migration 047
CREATE TABLE IF NOT EXISTS public.prop_firm_rules (
    id              BIGSERIAL PRIMARY KEY,
    firm_slug       VARCHAR(64)  NOT NULL,
    -- 'phase1' | 'phase2' | 'funded'
    challenge_type  VARCHAR(32)  NOT NULL,
    -- Dollar amount of challenge (50000, 100000, 200000)
    -- NULL = applies to all sizes (use most specific match first)
    account_size_usd INTEGER,

    -- Official firm limits (percentages of starting balance)
    daily_loss_limit_pct    REAL NOT NULL,
    total_drawdown_limit_pct REAL NOT NULL,
    profit_target_pct       REAL NOT NULL DEFAULT 0,
    min_trading_days        INTEGER NOT NULL DEFAULT 0,
    consistency_limit_pct   REAL,           -- NULL if firm has no consistency rule
    -- Maximum duration allowed (NULL if no time limit)
    max_duration_days       INTEGER,

    -- Metadata
    effective_from  DATE         NOT NULL DEFAULT CURRENT_DATE,
    notes           TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT uq_firm_challenge_size
        UNIQUE (firm_slug, challenge_type, account_size_usd)
);

CREATE INDEX IF NOT EXISTS idx_pfr_firm_type
    ON public.prop_firm_rules (firm_slug, challenge_type);

-- Seed: FTMO $50k challenge rules (official firm limits)
INSERT INTO public.prop_firm_rules
    (firm_slug, challenge_type, account_size_usd,
     daily_loss_limit_pct, total_drawdown_limit_pct,
     profit_target_pct, min_trading_days,
     consistency_limit_pct, max_duration_days)
VALUES
    ('FTMO', 'phase1', 50000,  5.0, 10.0, 10.0, 4, 40.0, 30),
    ('FTMO', 'phase2', 50000,  5.0, 10.0,  5.0, 4, 40.0, 60),
    ('FTMO', 'funded', 50000,  5.0, 10.0,  0.0, 0, 40.0, NULL),
    ('FTMO', 'phase1', 100000, 5.0, 10.0, 10.0, 4, 40.0, 30),
    ('FTMO', 'phase2', 100000, 5.0, 10.0,  5.0, 4, 40.0, 60),
    ('FTMO', 'funded', 100000, 5.0, 10.0,  0.0, 0, 40.0, NULL)
ON CONFLICT (firm_slug, challenge_type, account_size_usd) DO NOTHING;
```

---

### Table: `account_prop_firm_config`

One row per account. Stores the trader's one-time challenge setup: which firm, which phase. Written on first account-detail visit; never asked again once set. Foreign-key-free to avoid migration ordering issues.

```sql
-- Part of migration 047
CREATE TABLE IF NOT EXISTS public.account_prop_firm_config (
    id              BIGSERIAL PRIMARY KEY,
    -- Matches accounts.account_id or account_status_snapshots.account_name
    account_name    VARCHAR(255) NOT NULL UNIQUE,
    -- NULL when server is unrecognized
    firm_slug       VARCHAR(64),
    -- 'phase1' | 'phase2' | 'funded' | NULL when not configured yet
    challenge_type  VARCHAR(32),
    -- Starting balance for this challenge run
    starting_balance_usd REAL,
    -- Date trader started this challenge run (for min_trading_days counter)
    challenge_start_date DATE,
    -- ISO timestamp of last user update
    configured_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION public.set_apfc_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$;

DROP TRIGGER IF EXISTS trg_apfc_updated ON public.account_prop_firm_config;
CREATE TRIGGER trg_apfc_updated
    BEFORE UPDATE ON public.account_prop_firm_config
    FOR EACH ROW EXECUTE FUNCTION public.set_apfc_updated_at();
```

---

## API Endpoint Design

### GET `/api/v1/prop-firm/challenge/{account_name}`

The primary read endpoint. Called by the account card every 5 seconds. Embeds everything the UI needs in a single response — no cascading fetches from the frontend.

**Response shape:**

```python
class ChallengeResponse(BaseModel):
    account_name: str
    # Detected firm info
    firm_slug: Optional[str]          # 'FTMO' | None if unrecognized
    firm_display_name: Optional[str]  # 'FTMO' | None
    server_name: Optional[str]        # Raw MetaAPI server string
    # Challenge config (null when not yet configured)
    challenge_type: Optional[str]     # 'phase1' | 'phase2' | 'funded'
    challenge_configured: bool        # False = show setup prompt
    # Official firm limits (from prop_firm_rules)
    rules: Optional[ChallengeRules]
    # Live metrics (from existing prop_firm_tracker / portfolio_snapshots)
    metrics: Optional[ChallengeMetrics]
    # Alert flags
    alerts: List[ChallengeAlert]      # [] when safe

class ChallengeRules(BaseModel):
    daily_loss_limit_pct: float
    total_drawdown_limit_pct: float
    profit_target_pct: float
    min_trading_days: int
    consistency_limit_pct: Optional[float]
    max_duration_days: Optional[int]

class ChallengeMetrics(BaseModel):
    # Drawdown
    daily_drawdown_pct: float
    total_drawdown_pct: float
    # Profit progress
    current_profit_usd: float
    profit_target_usd: float
    profit_progress_pct: float        # 0–100
    # Trading days
    trading_days_completed: int
    min_trading_days_required: int
    # Raw equity
    current_equity: float
    starting_balance: float
    daily_start_balance: float

class ChallengeAlert(BaseModel):
    metric: str   # 'daily_drawdown' | 'total_drawdown' | 'profit_target' | 'trading_days'
    severity: str # 'warning' (>=80%) | 'critical' (>=95%)
    message: str
```

**Backend computation sequence:**

```
1. Fetch latest account_status_snapshots row for account_name
   → get server_name, equity, balance
2. PropFirmDetector.detect(server_name)
   → SELECT from prop_firm_server_mappings WHERE server_name ILIKE '%pattern%'
   → Returns firm_slug or None
3. SELECT from account_prop_firm_config WHERE account_name = ?
   → Get challenge_type, starting_balance, challenge_start_date
   → If no row: return challenge_configured=False, rules=None, metrics=None
4. SELECT from prop_firm_rules WHERE firm_slug = ? AND challenge_type = ?
   → Match closest account_size_usd (NULL row as fallback)
5. PropFirmMetricsService.compute(account_name, rules, starting_balance)
   → Reads portfolio_snapshots for daily PnL breakdown
   → Reads prop_firm_metrics for daily_start_balance, daily_high_water_mark
   → Counts distinct trading days from portfolio_snapshots since challenge_start_date
   → Computes drawdown and profit progress
6. Evaluate 80% alert thresholds
7. Return ChallengeResponse
```

**Complexity note:** All computation happens in the backend service. The frontend receives pre-computed percentages and renders them directly. No metric math in React.

---

### PUT `/api/v1/prop-firm/challenge/{account_name}/config`

Called once when the trader picks their challenge type.

```python
class ChallengeConfigRequest(BaseModel):
    challenge_type: Literal['phase1', 'phase2', 'funded']
    starting_balance_usd: float
    challenge_start_date: Optional[str]  # ISO date string, defaults to today
```

Upserts `account_prop_firm_config`. Returns the full `ChallengeResponse` so the frontend doesn't need a second fetch.

---

### Existing endpoints: no changes

`GET /api/accounts` — unchanged. `AccountResponse` is not modified.

The accounts page already polls `fetchAccountsComparison` every 30 seconds for balance/PnL data. Prop firm data comes from a separate `usePropFirmChallenge(accountName)` hook polling the new endpoint every 5 seconds. These are decoupled by design — prop firm metrics need more frequent refresh; account comparison data does not.

---

## Where Each Piece of Logic Lives

### Server-name-to-firm mapping: DB table, not config or hardcode

**Decision:** `prop_firm_server_mappings` table in Supabase.

Rationale:
- Config file would require a redeploy to add a new firm.
- Hardcoding creates a code change for what is really a data change.
- DB allows adding firms (The5ers, FundedNext, E8) by `INSERT` without touching any Python or TypeScript.
- The existing pattern in this codebase (`symbol_risk_rules`, `guard_rails_config`) already stores domain data in DB tables for the same reason.

**Not a settings.py field.** Settings are for secrets and tuning parameters. Firm identity is reference data.

---

### Rules: DB table with seed data

**Decision:** `prop_firm_rules` table, seeded at migration time.

Rationale:
- FTMO rules are documented and stable (they change infrequently, typically yearly).
- Storing in DB allows the operator to correct a rule by `UPDATE` without a deploy.
- Architecture already does this for `symbol_risk_rules`.
- The `ChallengeTab` frontend component already has `PROVIDER_PRESETS` hardcoded as a fallback — these will be replaced by the DB-backed endpoint response.

---

### Metric computation: backend service, not frontend

**Decision:** `PropFirmMetricsService` in `src/services/`, computed on each API request.

Rationale:
- Frontend should receive `daily_drawdown_pct = 3.2` and `daily_loss_limit_pct = 5.0`, not raw PnL arrays it has to process.
- Existing `PropFirmTracker` already does the core calculation. `PropFirmMetricsService` is a thin adapter that reshapes its output to `ChallengeMetrics`.
- React's job is rendering, not domain calculations. Keeping calculations in the backend also means the same logic feeds both the UI and the existing `prop_guard.py` guard rail without duplication.
- Trading day counting (distinct calendar days with a closed trade since `challenge_start_date`) is a SQL aggregation that belongs in the backend.

---

### Integration with `/api/accounts`: embedding, not merging

**Decision:** The challenge data is fetched via a separate `usePropFirmChallenge` hook, not embedded in `AccountResponse`.

Rationale:
- `AccountResponse` from `/api/accounts` is currently stable and used by `AccountsTable`, `EnhancedAccountCard`, and capital allocator — changing its shape would require updates to all three plus their TypeScript types.
- Challenge data needs 5s polling; account comparison data is fine at 30s. Separate hooks allow independent refresh cadences.
- When `challenge_configured = false` (new account never set up), the card shows a "Configure challenge" CTA rather than empty progress bars. This state is orthogonal to the account itself.

---

## Component Boundaries

| Component | Layer | Responsibility | Inputs | Does Not Do |
|-----------|-------|---------------|--------|-------------|
| `PropFirmDetector` | `src/services/` | `server_name → firm_slug` via DB lookup | `server_name: str` | Compute metrics, read broker API |
| `PropFirmMetricsService` | `src/services/` | Compute `ChallengeMetrics` from existing data | `account_name`, `rules`, `starting_balance` | Detect firm, write to DB |
| `api_prop_firm.py` | `src/` router | Orchestrate detection + metrics + rules into `ChallengeResponse` | HTTP request | Business logic (delegates to services) |
| `usePropFirmChallenge` | `frontend/hooks/` | Fetch and cache challenge data per account | `accountName: string` | Render, compute metrics |
| `ChallengeProgressPanel` | `frontend/components/accounts/` | Render 4 progress bars + alert banner | `ChallengeResponse` | Fetch, compute |
| `PropFirmBadge` | `frontend/components/accounts/` | Render firm name badge on account card | `firm_display_name: string \| null` | Nothing else |

---

## Data Flow Direction

```
MetaAPI broker
  → account_status_snapshots.server_name (existing write path, unchanged)
  → backend: SELECT latest snapshot WHERE account_name = ?
  → PropFirmDetector: SELECT prop_firm_server_mappings WHERE ILIKE match
  → account_prop_firm_config: SELECT challenge_type (set by user once)
  → prop_firm_rules: SELECT limits for (firm_slug, challenge_type)
  → PropFirmMetricsService: SELECT portfolio_snapshots + prop_firm_metrics
  → ChallengeResponse assembled in api_prop_firm.py
  → Frontend: usePropFirmChallenge polls every 5s
  → ChallengeProgressPanel renders progress bars
  → EnhancedAccountCard renders PropFirmBadge + inline panel
```

All computation flows left-to-right. The frontend is a pure rendering layer.

---

## Migration Strategy

### Principle: additive only

Every migration adds new tables or columns. No existing tables are altered. No existing endpoints change shape. The production system stays fully operational throughout rollout.

### Migration sequence

```
Migration 047_prop_firm_server_mappings.sql
  CREATE TABLE prop_firm_server_mappings
  CREATE TABLE prop_firm_rules
  CREATE TABLE account_prop_firm_config
  (all in one file to keep atomic; split only if migration runner requires it)

Migration 048_prop_firm_min_trading_days.sql  [if needed]
  (placeholder for future rule adjustments — not needed at launch)
```

Latest existing migration is `046_be_trigger.sql`, so `047` is the next number.

### Zero-downtime rollout order

1. Apply migration 047 (new tables, zero impact on existing queries)
2. Deploy backend with `api_prop_firm.py` and new services (new endpoints, no existing endpoint changes)
3. Deploy frontend with `usePropFirmChallenge` hook and new card components (graceful degradation: if backend unavailable, challenge panel shows skeleton)
4. No environment variable changes required

---

## Build Order (What Must Come Before What)

```
Step 1 — DB migration (047)
  Creates prop_firm_server_mappings, prop_firm_rules, account_prop_firm_config
  Seeds FTMO server patterns and rules
  DEPENDENCY: Nothing. Run immediately.

Step 2 — PropFirmDetector service
  Reads prop_firm_server_mappings
  DEPENDENCY: Step 1 (table must exist)

Step 3 — PropFirmMetricsService
  Reads portfolio_snapshots, prop_firm_metrics, account_status_snapshots
  DEPENDENCY: None (these tables already exist)
  Can be built in parallel with Step 2

Step 4 — api_prop_firm.py router
  Calls PropFirmDetector + PropFirmMetricsService
  Registered in api.py (one include_router line)
  DEPENDENCY: Steps 2 and 3

Step 5 — Frontend usePropFirmChallenge hook
  Calls GET /api/v1/prop-firm/challenge/{account_name}
  DEPENDENCY: Step 4 (endpoint must exist)

Step 6 — PropFirmBadge + ChallengeProgressPanel components
  Consume hook output
  DEPENDENCY: Step 5

Step 7 — Wire into EnhancedAccountCard
  Embed panel below existing balance/PnL section
  DEPENDENCY: Step 6

Step 8 — Wire into ChallengeTab (account detail page)
  Show live metrics alongside existing edit form
  DEPENDENCY: Step 6
  (ChallengeTab already exists; this adds the live metric overlay)
```

Steps 2 and 3 can be developed in parallel. Steps 5–8 are frontend-only and can be done as one unit.

---

## Existing Code Reuse (No Duplication)

| Existing file | How this feature uses it |
|---------------|--------------------------|
| `src/services/prop_firm_tracker.py` | `PropFirmMetricsService` calls `PropFirmTracker.get_current_metrics()` to get drawdown data rather than reimplementing it |
| `src/core/guard_rails/prop_guard.py` | No change; continues to use `broker_profiles` limits for trade blocking. The new feature is display-only. |
| `src/api_funding.py` | No change; remains the legacy prop firm page backend |
| `migrations/018_prop_firm_metrics.sql` | `prop_firm_metrics` table is read by `PropFirmMetricsService` for `daily_start_balance` and `daily_high_water_mark` |
| `migrations/021_per_account_evaluation.sql` | `broker_profiles` evaluation columns remain the source of truth for the guard rail. The new `account_prop_firm_config` stores display-facing config only. |
| `frontend/src/components/accounts/detail/ChallengeTab.tsx` | Existing component keeps its edit form and preset buttons; new code adds a live metrics panel above the edit section |
| `frontend/src/app/accounts/[account_name]/page.tsx` | No change to page structure; ChallengeTab receives live data via the new hook |

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Computing metrics in the frontend

**What it looks like:** Passing raw `portfolio_snapshots` JSON to React and computing `daily_drawdown_pct` in a `useMemo`.

**Why bad:** React re-renders cannot guarantee numerical consistency with the guard rail (which also computes drawdown in Python). Users could see 4.9% in the UI while the guard fires at 5.0% due to floating-point differences in JavaScript vs Python. The backend is the single source of computation truth.

**Instead:** Backend returns pre-computed percentages. Frontend renders them.

---

### Anti-Pattern 2: Hardcoding server-name patterns in Python

**What it looks like:** `if 'FTMO' in server_name: firm = 'FTMO'` in a service file.

**Why bad:** Adding The5ers requires a code change + redeploy. Breaks the "add firm by INSERT" promise. Also means tests must mock code paths rather than data.

**Instead:** `SELECT firm_slug FROM prop_firm_server_mappings WHERE server_name ILIKE '%' || server_pattern || '%'`.

---

### Anti-Pattern 3: Embedding challenge data in `AccountResponse`

**What it looks like:** Adding `prop_firm: PropFirmData | null` to `GET /api/accounts` response.

**Why bad:** Forces all consumers of `/api/accounts` (table view, capital allocator, copy configurator) to receive prop firm data they don't use. Also forces the slower prop-firm query (which hits multiple tables) onto every accounts page load, increasing latency for users who have no prop firm accounts.

**Instead:** Separate endpoint, separate hook, composed in the card component.

---

### Anti-Pattern 4: Altering `broker_profiles` for display config

**What it looks like:** Adding `firm_slug` and `challenge_type` columns to `broker_profiles`.

**Why bad:** `broker_profiles` is a sensitive table — it's read by the live trade guard rail (`prop_guard.py`). Schema changes to it require careful testing against the execution pipeline. Challenge display config is orthogonal to trade execution config.

**Instead:** New `account_prop_firm_config` table with no foreign keys into the execution path.

---

## Scalability Considerations

| Concern | Current (1-3 accounts) | At 10+ accounts |
|---------|----------------------|-----------------|
| Polling frequency | 5s per account, all cards visible simultaneously | Each card polls independently; consider debouncing to a single batch endpoint |
| Metrics computation | Real-time on each request | Cache `ChallengeMetrics` in Redis with 10s TTL (same pattern as balance cache in `logic.py`) |
| Historical trading day count | `COUNT(DISTINCT date)` from `portfolio_snapshots` | Index on `(account_name, created_at)` already exists; no action needed |
| Adding new firms | `INSERT` into two tables + optional seed data | No architectural change |

---

## Sources

- Existing codebase: `src/services/prop_firm_tracker.py`, `src/core/guard_rails/prop_guard.py`, `src/api_funding.py`, `src/api_accounts.py`
- Existing migrations: `015_account_status_snapshots.sql`, `018_prop_firm_metrics.sql`, `021_per_account_evaluation.sql`, `028_accounts.sql`
- Existing frontend: `frontend/src/components/accounts/detail/ChallengeTab.tsx`, `frontend/src/app/accounts/page.tsx`
- Project requirements: `.planning/PROJECT.md`
- Codebase patterns: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`
- Confidence: HIGH — architecture derived entirely from direct inspection of existing production code and migrations, not assumptions.
