# Phase 1: Data Foundation and Bug Fixes - Research

**Researched:** 2026-03-18
**Domain:** Python backend — prop firm metrics, Supabase migrations, FastAPI routing, timezone handling
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BUG-01 | Daily drawdown reset boundary uses NY midnight (EST/EDT), not UTC midnight | `pytz` already in requirements.txt; `zoneinfo` available in Python 3.9+; `America/New_York` handles DST automatically |
| BUG-02 | Daily drawdown baseline uses equity at day start, not balance — FTMO measures from equity (includes floating PnL at reset) | `MTMGuardian.get_real_time_equity()` returns current equity; `perform_daily_reset()` correctly uses `current_equity` but reset trigger uses UTC midnight |
| BUG-03 | Max drawdown denominator uses initial account balance for Phase 1/2, not trailing HWM — Funded accounts use HWM (two branches required) | `prop_firm_tracker.py` line 154 uses `max_historical_equity` as denominator for all phases — Phase 1/2 branch must use `starting_balance` from `broker_profiles` |
| BUG-04 | `trades_today` counter hardcoded to 0 in `prop_firm_tracker.py` | `save_snapshot()` line 255 has `"trades_today": 0,  # TODO` — must query `trading_signals` with today's NY-midnight boundary |
| BUG-05 | Silent exception swallowing removed from `prop_firm_tracker.py` — errors must surface to logs | `save_snapshot()` catches all exceptions, logs error but does not re-raise; must `raise` or surface to caller |
| BUG-06 | JPY pip value calculation corrected in floating PnL computation (94x error) | `mtm_guardian.py` lines 167-168: `pip_value_per_lot = 1000.0` hardcoded for JPY — must use dynamic formula: `(pip_size / entry_price) * 100000` (same fix as `risk_engine.py`) |
| DATA-01 | Migration creates `prop_firm_server_mappings` table | New migration after 046; prefix-based lookup (e.g. "FTMO" matches "FTMO-Server3") |
| DATA-02 | Migration creates `prop_firm_rules` table | firm_id + challenge_type composite key; stores all rule values including reset_tz |
| DATA-03 | FTMO Phase 1, Phase 2, and Funded rules seeded | daily 5%, total 10%, profit_target 10%/5%/0%, min_trading_days 4, reset_tz America/New_York |
| DATA-04 | `prop_firm_detector.py` maps server name to firm_id via prefix lookup in DB | Unknown firms return null gracefully; no crash |
| API-01 | `GET /api/v1/prop-firm/challenge-status/{account_id}` — returns pre-computed metrics | New endpoint; account_id maps to broker_profile_id; reads rules from DB via detector |
| API-02 | `PATCH /api/v1/prop-firm/challenge-config/{account_id}` — saves challenge_type per account | Updates `challenge_type` field on broker_profiles or new config table; idempotent |
| API-03 | Returns `firm_detected: false` with empty metrics for unknown server names | PropFirmDetector returns None → endpoint returns structured empty response |
</phase_requirements>

---

## Summary

Phase 1 is entirely backend Python work: two SQL migrations, fixes to two existing services (`prop_firm_tracker.py` and `mtm_guardian.py`), one new service (`prop_firm_detector.py`), and two new FastAPI endpoints under a new `/api/v1/prop-firm/` router prefix.

The existing `api_prop_firm.py` uses the old `/api/prop-firm/` prefix and account-name-based routing. The new requirements target `/api/v1/prop-firm/` with account_id-based routing and pull rules from DB instead of from settings. These are additive — the old endpoints can coexist, and the new router should be a separate file (e.g. `api_prop_firm_v1.py`) registered with prefix `/api/v1`.

Six confirmed bugs exist in currently deployed code. Four are in `prop_firm_tracker.py`, one in `mtm_guardian.py`. All are surgical one-to-five line fixes. The most consequential is BUG-06 (JPY 94x error) which produces wildly wrong floating PnL in drawdown calculations for JPY pairs. The fix pattern already exists in `risk_engine.py` and must be replicated to `mtm_guardian.py`.

**Primary recommendation:** Execute the work in the three plans already defined in ROADMAP.md — DB migration first, then bug fixes, then the detector service and API endpoints. The migration must precede everything else as the detector and API read from the new tables.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.109.0 | API routing and response models | Already in use project-wide |
| Pydantic | (bundled with FastAPI) | Request/response schemas | Already used for all API models |
| supabase-py | 2.10.0 | Database reads/writes | Already in use; pinned version |
| pytz | >=2023.3 | Timezone handling (America/New_York) | Already in requirements.txt |
| pytest | (in dev deps) | Unit tests | Test infrastructure already in `/tests/` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| zoneinfo | stdlib (Python 3.9+) | Alternative to pytz for timezone handling | Acceptable alternative but pytz is already present |
| Python datetime | stdlib | Date/time arithmetic | For all boundary calculations |

**Installation:** No new packages required. All dependencies already in requirements.txt.

---

## Architecture Patterns

### Recommended Project Structure

New files for Phase 1:

```
src/
├── api_prop_firm_v1.py          # New: /api/v1/prop-firm/ endpoints (challenge-status, challenge-config)
├── services/
│   └── prop_firm_detector.py   # New: server_name → firm_id + rules lookup
migrations/
└── 047_prop_firm_data_foundation.sql  # New: server_mappings + rules tables + FTMO seed data
```

Existing files modified:
```
src/services/prop_firm_tracker.py   # BUG-01, BUG-02, BUG-03, BUG-04, BUG-05
src/services/mtm_guardian.py        # BUG-06
src/api.py                          # Register new api_prop_firm_v1 router
```

### Pattern 1: NY Midnight Boundary (BUG-01)

**What:** Replace UTC midnight reset boundary with NY midnight (handles EST = UTC-5 in winter, EDT = UTC-4 in summer).

**Current code (broken):**
```python
# prop_firm_tracker.py line 104 — uses UTC midnight
today_start = datetime.now(timezone.utc).replace(
    hour=0, minute=0, second=0, microsecond=0
).isoformat()
```

**Correct pattern:**
```python
import pytz

NY_TZ = pytz.timezone("America/New_York")

def get_ny_midnight_utc() -> datetime:
    """Return today's NY midnight as a UTC datetime."""
    now_ny = datetime.now(NY_TZ)
    midnight_ny = now_ny.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight_ny.astimezone(timezone.utc)
```

This single helper replaces all four occurrences of the UTC midnight pattern in `prop_firm_tracker.py` and one occurrence in `mtm_guardian.py`. The `reset_tz` column in `prop_firm_rules` stores `"America/New_York"` and this is loaded at runtime.

### Pattern 2: Drawdown Denominator Branch (BUG-03)

**What:** Phase 1/2 use `starting_balance` (fixed initial balance) as total DD denominator. Funded accounts use trailing HWM.

**Current code (broken):** Uses `max_historical_equity` as denominator for all phases.

**Correct pattern:**
```python
# In get_current_metrics(), replace line 154
if evaluation_phase == "funded":
    # Funded: trailing HWM denominator
    total_dd_pct = (
        (max_historical_equity - current_equity) / max_historical_equity * 100
        if max_historical_equity > 0 else 0
    )
else:
    # Phase 1 / Phase 2: initial starting balance denominator
    total_dd_pct = (
        (starting_balance - current_equity) / starting_balance * 100
        if starting_balance > 0 else 0
    )
```

`starting_balance` comes from `broker_profiles.starting_balance` (already exists, seeded as $50,000).

### Pattern 3: PropFirmDetector Service (DATA-04)

**What:** Stateless service that resolves a MetaAPI server name string to a firm + rules record.

```python
class PropFirmDetector:
    def __init__(self, supabase_client):
        self.supabase = supabase_client

    def detect(self, server_name: str) -> Optional[dict]:
        """
        Returns firm_id, firm_display_name, and rules dict, or None if unknown.
        Uses prefix matching: 'FTMO-Server3' matches prefix 'FTMO'.
        """
        if not server_name:
            return None
        result = self.supabase.table("prop_firm_server_mappings") \
            .select("firm_id, firm_display_name") \
            .execute()
        for row in (result.data or []):
            if server_name.startswith(row["firm_id"]):
                return row
        return None
```

Prefix matching is intentional: FTMO uses servers named `FTMO-Server3`, `FTMO-Server4`, etc. A simple `startswith("FTMO")` covers all of them without a wildcard table.

### Pattern 4: New API Router (API-01, API-02, API-03)

**What:** Separate router file under `/api/v1/` prefix, account_id-based, reads from DB.

```python
router = APIRouter(prefix="/api/v1/prop-firm", tags=["Prop Firm v1"])

@router.get("/challenge-status/{account_id}")
async def get_challenge_status(account_id: int):
    ...

@router.patch("/challenge-config/{account_id}")
async def patch_challenge_config(account_id: int, body: ChallengeConfigUpdate):
    ...
```

Register in `api.py`:
```python
from src.api_prop_firm_v1 import router as prop_firm_v1_router
app.include_router(prop_firm_v1_router)
```

The existing `api_prop_firm.py` with prefix `/api/prop-firm/` is untouched (backward compatibility).

### Anti-Patterns to Avoid

- **Hardcoding FTMO rules in Python code:** All rule values (5%, 10%, etc.) must come from the `prop_firm_rules` table. Do not embed them in the endpoint handler.
- **Reusing the old `/api/prop-firm/` router prefix for new endpoints:** The old router uses `account_name` strings; new endpoints use integer `account_id`. Register separately.
- **UTC midnight for reset boundary:** Every `datetime.now(timezone.utc).replace(hour=0...)` in prop firm code is wrong and must be replaced with NY midnight.
- **Broad exception swallowing:** `except Exception as e: logger.error(...)` with no re-raise hides failures. Follow CLAUDE.md rule: "No silent failures."

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DST-aware timezone arithmetic | Custom offset math | `pytz.timezone("America/New_York")` | DST transitions are complex; pytz handles them with IANA database |
| Prefix matching for firm detection | Regex/LIKE query | Python `str.startswith()` on fetched rows | Table is small (< 20 rows); fetch all, match in Python avoids SQL complexity |
| Challenge type persistence | New table | Add `challenge_type` column to existing `broker_profiles` | broker_profiles already has `evaluation_phase` — this is the same concept under a new name; one PATCH updates it |

**Key insight:** The `broker_profiles` table already stores `evaluation_phase` with a CHECK constraint for `('phase1', 'phase2', 'funded')`. API-02 is a PATCH to that existing field. No new table is needed for challenge_type config — but check whether renaming `evaluation_phase` → `challenge_type` breaks anything first (safe to add a separate `challenge_type` column if needed to avoid breaking existing code).

---

## Common Pitfalls

### Pitfall 1: UTC Midnight Reset in Multiple Places
**What goes wrong:** The NY midnight fix is applied in `get_current_metrics()` but the same pattern exists in `get_daily_reset_needed()` (line 301) and `mtm_guardian.py` — those still use UTC midnight.
**Why it happens:** The bug is copy-pasted across three locations in the same file and one more in mtm_guardian.
**How to avoid:** Extract `get_ny_midnight_utc()` as a module-level function, call it from all four sites.
**Warning signs:** Drawdown resets 5-6 hours early in winter (UTC midnight vs NY midnight).

### Pitfall 2: `broker_profiles.evaluation_phase` vs `challenge_type`
**What goes wrong:** API-02 spec uses the term "challenge_type" but the DB column is "evaluation_phase". If a new `challenge_type` column is added alongside `evaluation_phase`, both must be kept in sync or one must be deprecated.
**Why it happens:** Naming divergence between REQUIREMENTS.md (challenge_type) and existing DB schema (evaluation_phase).
**How to avoid:** Either: (a) treat `challenge_type` as an alias for `evaluation_phase` in the API response, updating `evaluation_phase` on PATCH, or (b) add a new `challenge_type` column and deprecate `evaluation_phase` in a future migration. Option (a) is the minimal safe patch.

### Pitfall 3: `save_snapshot` Swallows Errors (BUG-05)
**What goes wrong:** `save_snapshot()` in `prop_firm_tracker.py` catches all exceptions and only logs. If Supabase is unreachable or the schema changed, snapshots silently stop saving.
**Why it happens:** Original author prioritized non-blocking behavior.
**How to avoid:** Re-raise after logging, or return a success boolean that the caller checks. Align with CLAUDE.md: "No silent failures."

### Pitfall 4: JPY pip value in MTM vs Risk Engine
**What goes wrong:** BUG-06 fix is made only in `mtm_guardian.py`, but the static `pip_value_per_lot = 1000.0` fallback remains elsewhere. The `risk_engine.py` already has the correct dynamic formula — reuse it.
**Why it happens:** `mtm_guardian.py` duplicates the pip-value lookup instead of calling into `risk_engine`.
**How to avoid:** Extract the pip-value calculation into a shared utility function in `src/core/risk_engine.py` or `src/utils/`. Both `risk_engine.py` and `mtm_guardian.py` call the shared function.

### Pitfall 5: Migration Numbering Conflict
**What goes wrong:** Migrations 026 already has three variants (`026_clean_state_model.sql`, `026_clean_state_model_safe.sql`, `026_add_missing_jpy_pairs.sql`). The next safe number requires inspection.
**Why it happens:** Multiple developers created migrations on the same day without coordinating.
**How to avoid:** Check highest-numbered migration before naming. Current highest is `046_be_trigger.sql` — new migration should be `047_prop_firm_data_foundation.sql`.

### Pitfall 6: server_name Not Always Available
**What goes wrong:** `server_name` comes from MetaAPI's `get_account_information()` response. If MetaAPI is unreachable or the adapter doesn't expose `get_account_information`, `server_name` will be `None`.
**Why it happens:** `account_orchestrator.py` already handles this gracefully (returns `None`), but the challenge-status endpoint must also handle it — returning `firm_detected: false` rather than raising 500.
**How to avoid:** PropFirmDetector's `detect(None)` must return `None` safely. The API endpoint must never raise 500 for missing server name.

---

## Code Examples

### Correct JPY pip value (BUG-06 fix in mtm_guardian.py)
```python
# Replace lines 167-168 in mtm_guardian.py
if "JPY" in symbol:
    pip_size = 0.01
    # Dynamic pip value — same formula as risk_engine.py
    if entry > 0:
        pip_value_per_lot = (pip_size / entry) * 100000
    else:
        pip_value_per_lot = 1000.0  # fallback only (logs warning)
        logger.warning("MTM: JPY fallback pip_value for %s (no entry price)", symbol)
```

### trades_today fix (BUG-04)
```python
# In save_snapshot(), replace hardcoded 0 with:
ny_midnight = get_ny_midnight_utc()
trades_result = self.supabase.table("trading_signals") \
    .select("id") \
    .in_("status", ["closed", "CLOSED", "executed", "EXECUTED"]) \
    .gte("closed_at", ny_midnight.isoformat()) \
    .execute()
trades_today = len(trades_result.data) if trades_result.data else 0
```

### prop_firm_server_mappings table (DATA-01)
```sql
CREATE TABLE IF NOT EXISTS public.prop_firm_server_mappings (
    id          bigserial PRIMARY KEY,
    server_prefix  text NOT NULL UNIQUE,  -- e.g. 'FTMO'
    firm_id        text NOT NULL,          -- e.g. 'ftmo'
    firm_display_name text NOT NULL,       -- e.g. 'FTMO'
    created_at  timestamptz DEFAULT now()
);
```

### prop_firm_rules table (DATA-02)
```sql
CREATE TABLE IF NOT EXISTS public.prop_firm_rules (
    id                  bigserial PRIMARY KEY,
    firm_id             text NOT NULL,          -- e.g. 'ftmo'
    challenge_type      text NOT NULL           -- 'phase_1' | 'phase_2' | 'funded'
        CHECK (challenge_type IN ('phase_1', 'phase_2', 'funded')),
    daily_dd_pct        real NOT NULL,          -- 5.0
    total_dd_pct        real NOT NULL,          -- 10.0
    profit_target_pct   real,                   -- NULL for funded
    min_trading_days    int NOT NULL DEFAULT 4,
    reset_tz            text NOT NULL DEFAULT 'America/New_York',
    drawdown_reference  text NOT NULL DEFAULT 'starting_balance'
        CHECK (drawdown_reference IN ('starting_balance', 'high_water_mark')),
    UNIQUE (firm_id, challenge_type)
);
```

### FTMO seed data (DATA-03)
```sql
INSERT INTO public.prop_firm_server_mappings (server_prefix, firm_id, firm_display_name)
VALUES ('FTMO', 'ftmo', 'FTMO')
ON CONFLICT (server_prefix) DO NOTHING;

INSERT INTO public.prop_firm_rules
    (firm_id, challenge_type, daily_dd_pct, total_dd_pct, profit_target_pct, min_trading_days, reset_tz, drawdown_reference)
VALUES
    ('ftmo', 'phase_1', 5.0, 10.0, 10.0, 4, 'America/New_York', 'starting_balance'),
    ('ftmo', 'phase_2', 5.0, 10.0, 5.0, 4, 'America/New_York', 'starting_balance'),
    ('ftmo', 'funded',  5.0, 10.0, NULL, 4, 'America/New_York', 'high_water_mark')
ON CONFLICT (firm_id, challenge_type) DO NOTHING;
```

### challenge-status response shape (API-01)
```python
class ChallengeStatusResponse(BaseModel):
    account_id: int
    firm_id: Optional[str]
    firm_name: Optional[str]
    challenge_type: Optional[str]       # 'phase_1' | 'phase_2' | 'funded'
    detected: bool
    # Metrics — all None when detected=False
    daily_dd_pct: Optional[float]
    daily_dd_limit_pct: Optional[float]
    total_dd_pct: Optional[float]
    total_dd_limit_pct: Optional[float]
    profit_pct: Optional[float]
    profit_target_pct: Optional[float]
    trades_today: Optional[int]
    min_trading_days: Optional[int]
    trading_days_count: Optional[int]
    warnings: List[str]                 # metrics at >=80% of limit
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| UTC midnight reset | NY midnight (America/New_York via pytz) | Phase 1 | 5-6 hour correctness gap in winter eliminated |
| Static JPY pip value (1000.0) | Dynamic: `(0.01 / entry_price) * 100000` | Phase 1 | 94x calculation error eliminated for floating PnL |
| HWM denominator for all phases | Split: starting_balance for P1/P2, HWM for funded | Phase 1 | FTMO-compliant drawdown calculation |
| `trades_today` hardcoded 0 | DB query scoped to NY trading day | Phase 1 | Accurate trading days counter |
| Rules in settings.py | Rules in `prop_firm_rules` DB table | Phase 1 | Multi-firm support without code deploys |
| Firm identity manual / from settings | Auto-detected from MetaAPI server name | Phase 1 | Zero-config for traders |

---

## Open Questions

1. **FTMO reset time verification**
   - What we know: STATE.md explicitly flags: "FTMO's exact reset timezone assumed to be New York midnight — must verify against current FTMO FAQ before seeding `reset_tz` in rules DB"
   - What's unclear: Whether FTMO uses New York midnight or a different boundary (e.g. Central European Time or London close)
   - Recommendation: Seed `America/New_York` as specified in REQUIREMENTS.md (DATA-03) since that is the confirmed decision; flag in code comment that this was the stated requirement. Planner should note this as a post-deployment verification step.

2. **challenge_type naming vs evaluation_phase column**
   - What we know: `broker_profiles` has `evaluation_phase TEXT CHECK (IN ('phase1', 'phase2', 'funded'))`. REQUIREMENTS.md uses `challenge_type` with values `'phase_1'`, `'phase_2'`, `'funded'` (underscore variant).
   - What's unclear: Whether to reuse `evaluation_phase` column or add a separate `challenge_type` column.
   - Recommendation: Add a new `challenge_type` column to `broker_profiles` in the migration with the new enum values (`phase_1`, `phase_2`, `funded` with underscore). Keep `evaluation_phase` untouched to avoid breaking the existing prop firm code. The new API reads `challenge_type`; old code reads `evaluation_phase`.

3. **server_name storage**
   - What we know: `server_name` is fetched live from MetaAPI in `account_orchestrator.py` but is NOT persisted to `broker_profiles`. It appears in `account_status_snapshots.server_name`.
   - What's unclear: Whether the challenge-status endpoint should query `account_status_snapshots` to retrieve the cached server_name, or call MetaAPI live.
   - Recommendation: Read `server_name` from the most recent `account_status_snapshots` row for the given `broker_profile_id`. This avoids a live MetaAPI call on every polling request and is already populated by `AccountSyncService`.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already installed, conftest.py exists) |
| Config file | `tests/conftest.py` |
| Quick run command | `pytest tests/test_prop_firm_phase1.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BUG-01 | NY midnight returns correct UTC offset in winter (UTC-5) and summer (UTC-4) | unit | `pytest tests/test_prop_firm_phase1.py::test_ny_midnight_winter -x` | Wave 0 |
| BUG-02 | Daily start baseline uses equity (including floating PnL) not just balance | unit | `pytest tests/test_prop_firm_phase1.py::test_equity_baseline -x` | Wave 0 |
| BUG-03 | Phase1/2 drawdown denominator is starting_balance; funded uses HWM | unit | `pytest tests/test_prop_firm_phase1.py::test_drawdown_denominator -x` | Wave 0 |
| BUG-04 | trades_today reflects actual closed trades since NY midnight | unit | `pytest tests/test_prop_firm_phase1.py::test_trades_today -x` | Wave 0 |
| BUG-05 | Exceptions in save_snapshot surface to caller rather than being silently swallowed | unit | `pytest tests/test_prop_firm_phase1.py::test_save_snapshot_error_propagation -x` | Wave 0 |
| BUG-06 | JPY floating PnL uses dynamic pip value (not hardcoded 1000.0) | unit | `pytest tests/test_prop_firm_phase1.py::test_jpy_pip_value_dynamic -x` | Wave 0 |
| DATA-04 | PropFirmDetector returns firm_id for 'FTMO-Server3'; returns None for 'Unknown-Broker' | unit | `pytest tests/test_prop_firm_phase1.py::test_firm_detector -x` | Wave 0 |
| API-01 | challenge-status returns correct fields for known account | integration | `pytest tests/test_prop_firm_phase1.py::test_challenge_status_endpoint -x` | Wave 0 |
| API-02 | challenge-config PATCH is idempotent; second call with same value returns 200 | integration | `pytest tests/test_prop_firm_phase1.py::test_challenge_config_patch -x` | Wave 0 |
| API-03 | challenge-status returns `detected: false` and empty metrics for unknown server name | integration | `pytest tests/test_prop_firm_phase1.py::test_challenge_status_unknown_firm -x` | Wave 0 |
| DATA-01/02/03 | Migration SQL syntax valid; seed data present | manual-only | Run migration in Supabase SQL editor and verify row counts | N/A |

### Sampling Rate
- **Per task commit:** `pytest tests/test_prop_firm_phase1.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_prop_firm_phase1.py` — all unit + integration tests for Phase 1 requirements (create in Plan 01-02 or 01-03)
- [ ] Supabase mocking pattern: follow `tests/conftest.py` — mock `self.supabase.table(...)` with `MagicMock` returning controlled `.data`

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `src/services/prop_firm_tracker.py` — confirmed BUG-01 through BUG-05 locations with line numbers
- Direct codebase inspection: `src/services/mtm_guardian.py` lines 167-168 — confirmed BUG-06 (hardcoded JPY pip value)
- Direct codebase inspection: `src/core/risk_engine.py` lines 95-112 — confirmed correct dynamic JPY formula already exists
- Direct codebase inspection: `migrations/021_per_account_evaluation.sql` — confirmed `broker_profiles` schema, existing `evaluation_phase` column
- Direct codebase inspection: `migrations/046_be_trigger.sql` — confirmed highest existing migration number

### Secondary (MEDIUM confidence)
- `.planning/STATE.md` — documented blocker: FTMO reset timezone assumed NY midnight, unverified against FTMO FAQ
- `.planning/REQUIREMENTS.md` — authoritative requirements document; DATA-03 specifies exact FTMO rule values

### Tertiary (LOW confidence)
- None — all findings are from direct source code inspection.

---

## Metadata

**Confidence breakdown:**
- Bug locations: HIGH — directly inspected source files with line numbers confirmed
- Bug fixes: HIGH — fix patterns are either already present in adjacent code (risk_engine.py) or are straightforward one-line changes
- Migration schema: HIGH — follows established patterns from existing migrations
- FTMO rules (DATA-03): MEDIUM — values (5%, 10%, 4 days, NY midnight) are specified in REQUIREMENTS.md; whether they match current FTMO documentation is flagged as an open question
- API shape: HIGH — follows existing FastAPI patterns in the codebase

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable domain — Python, Supabase, FTMO rules do not change frequently)
