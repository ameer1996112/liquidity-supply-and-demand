# Phase 5: Pre-filter Hardening & EV Score - Research

**Researched:** 2026-03-26
**Domain:** Python backend - worker.py guard pipeline, news filter singleton, EV scoring
**Confidence:** HIGH

## Summary

Phase 5 is a backend-only change to `src/worker.py` that adds 4 hard vetoes to the existing pre-filter pipeline. The good news: **3 of the 4 vetoes are already implemented** in `_validate_pine_filters()` (lines 790-815). The Sydney session veto, Friday 14:00 UTC cutoff, and news proximity veto are already working. The daily drawdown veto is also already implemented in `_run_account_guards()` (lines 1008-1039). What remains is: (a) verifying the existing implementations match the CONTEXT.md spec exactly, (b) adding `premium_discount` and `kill_zone` payload parsing, (c) adding the EV score formula and logging, (d) adding `RUBRIC_COUNCIL_GATE`, `RUBRIC_EXEC_GATE`, and `DEFAULT_ESTIMATED_RR` to settings.py, and (e) ensuring the test file `tests/test_pine_filters_phase1.py` passes (it already exists with 4 tests).

**Primary recommendation:** Verify existing veto implementations against CONTEXT.md spec, add the missing pieces (EV score, new payload fields, new settings), and ensure the existing test suite passes. This is primarily a wiring and enhancement phase, not a greenfield build.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Hard Veto 1: Sydney Session -- Block when `session == 0`, location: per-account loop in worker.py (~line 878), NOT `_validate_pine_filters`. Fail-closed, log WARNING, no Discord.
- Hard Veto 2: Friday Close -- Block when `day_of_week == 4` AND `hour >= 14` (UTC). Same location: per-account loop.
- Hard Veto 3: News Proximity -- Block when `news_minutes_to_next < 30`. Use `NewsFilter` singleton. Fail-closed for prop firm, fail-open for personal. Per-account loop, after session/day vetoes.
- Hard Veto 4: Daily Drawdown -- Block when `daily_drawdown_used_pct > 0.80`. Per-account. Supabase unavailability: fail-closed + Discord alert via `send_discord_async()`.
- EV Score: `ev_score = (composite_score / 100) * estimated_rr * (1 - daily_drawdown_used_pct)`. Informational only, logged.
- `premium_discount` (float 0-1, clamp) and `kill_zone` (int 0/1/2) parsed from Pine payload. If absent: None, log WARNING, do NOT veto.
- `RUBRIC_COUNCIL_GATE` (default 70) and `RUBRIC_EXEC_GATE` (default 78) added to settings.py but NOT wired.
- DO NOT remove `_validate_pine_filters` floor check in Phase 5.
- Phase 5 vetoes are additive; no changes to existing scoring logic.

### Claude's Discretion
- Exact placement of vetoes within the per-account loop (order matters: cheapest first)
- How to surface ev_score in existing logging (log level, format)
- Whether to add ev_score to the signal record in DB (if schema allows without migration)
- Implementation of `DEFAULT_ESTIMATED_RR` config pattern

### Deferred Ideas (OUT OF SCOPE)
- `rubric_engine.py` (Phase 6)
- Composite score gating of LLM council (Phase 6)
- JSONB rubric_score column in signals table (Phase 6)
- Remove `return_strength` floor check from `_validate_pine_filters` (Phase 6)
- RUBRIC_GATE_ENABLED feature flag with shadow scoring mode (Phase 6)
- Stage 2 monitoring (Pine approach-zone second alert) (Phase 6)
</user_constraints>

## Critical Finding: Location Mismatch

**The CONTEXT.md specifies all 4 vetoes go in the per-account loop (`_run_account_guards`), NOT in `_validate_pine_filters`.** However, the current codebase already has the Sydney, Friday, and news vetoes implemented inside `_validate_pine_filters()` (lines 790-815), which is a GLOBAL filter (runs once, not per-account).

The CONTEXT.md reasoning is: "drawdown lookup is per-account; vetoes that need account context belong here." The session/Friday/news vetoes do NOT need account context. The drawdown veto already IS in the per-account loop.

**Decision for planner:** The CONTEXT.md says to put them in the per-account loop. The existing code already has them in `_validate_pine_filters`. The planner must decide whether to:
1. **Move** the 3 vetoes from `_validate_pine_filters` to `_run_account_guards` (matches CONTEXT.md letter)
2. **Keep** them in `_validate_pine_filters` where they already work (pragmatic -- no account context needed for session/Friday/news)
3. **Duplicate** -- add per-account versions for prop-firm-specific fail behavior (news veto: fail-closed for prop firm vs fail-open for personal)

Option 3 is strongest because: the news veto has per-account behavior (fail-closed for prop firm, fail-open for personal), which requires account context. Session and Friday vetoes don't need account context, so keeping them global is fine. The drawdown veto is already per-account.

**Recommendation:** Keep Sydney/Friday/news in `_validate_pine_filters` as global guards (they already work). Add a per-account news override in `_run_account_guards` for prop-firm fail-closed behavior. The drawdown veto is already in the right place.

## Architecture Patterns

### Current Guard Pipeline (worker.py)

```
process_trade(payload)                    # Line 1173
  |
  +-- Exit events bypass guards          # Line 1175
  +-- Global guards (run once):
  |     - Kill switch                    # ~Line 1200
  |     - Max lot size                   # ~Line 1220
  |     - Staleness guard               # ~Line 1330
  |     - _validate_pine_filters()       # Line 1354  <-- Sydney/Friday/news vetoes HERE
  |     - AI ensemble (RF + LLM)         # ~Line 1365+
  |
  +-- Per-account loop (_execute_for_profile):  # Line 1089
        - Idempotency check              # Line 1105
        - _run_account_guards()          # Line 1115
        |   - Kill switch (Redis+MTM)    # Line 911
        |   - Circuit breaker            # Line 944
        |   - Adaptive trade limit       # Line 952
        |   - PropGuard                  # Line 992
        |   - Daily drawdown veto        # Line 1008  <-- DD veto HERE
        |   - Correlation guard          # Line 1041
        |   - Consistency analyzer       # Line 1057
        +-- Execute trade                # Line 1148
```

### Existing Implementations Already In Place

| Veto | Implemented? | Location | Line | Match CONTEXT.md? |
|------|-------------|----------|------|-------------------|
| Sydney (session=0) | YES | `_validate_pine_filters` | 790-797 | Location differs (global vs per-account) |
| Friday 14:00 UTC | YES | `_validate_pine_filters` | 799-805 | Location differs; uses `_get_now_utc()` not payload fields |
| News proximity | YES | `_validate_pine_filters` | 807-814 | Location differs; no prop-firm differentiation |
| Daily drawdown >80% | YES | `_run_account_guards` | 1008-1039 | YES -- correct location, per-account |

### Key Function Signatures

```python
# Global filter (runs once per signal)
def _validate_pine_filters(payload: Dict[str, Any]) -> Optional[str]:
    """Returns None if pass, rejection reason string if blocked."""

# Per-account guard (runs per broker profile)
def _run_account_guards(
    payload: Dict[str, Any],
    profile: Optional[Dict[str, Any]],
    s,               # Settings object
    current_equity_global: float,
) -> Optional[str]:
    """Returns rejection reason or None if all pass."""
```

### NewsFilter Interface (HIGH confidence)

```python
# src/core/news_filter.py
class NewsFilter:
    def __init__(self, block_minutes_before=30, block_minutes_after=30):
        ...

    def is_news_imminent(self, symbol: str) -> bool:
        """Returns True if trading should be BLOCKED."""
        # Fetches from https://nfs.faireconomy.media/ff_calendar_thisweek.json
        # Caches for 3600 seconds (1 hour) via time.time() comparison
        # Filters: impact == 'High', currency matches symbol
        # Currently fail-open (returns False on error)
```

**Singleton already exists at module level (line 56):**
```python
_NEWS_FILTER = NewsFilter(block_minutes_before=30, block_minutes_after=30)
```

**Note:** The NewsFilter currently uses in-memory caching only (`self.cache` dict + `self.last_fetch` timestamp). The CONTEXT.md mentions Redis caching with TTL=60min and key=`ff_calendar:{week_iso}`. The existing implementation uses `time.time()` + 3600s memory cache instead. The existing approach works fine for Phase 5. Redis caching can be deferred.

**Note 2:** The CONTEXT.md says filter by `impact >= "medium"`, but the existing code only filters `impact == 'High'`. Phase 5 should update to include "Medium" impact events per spec.

### send_discord_async Pattern

```python
# Used in _run_account_guards (line 1029-1037)
from src.adapters.discord import send_discord_async
send_discord_async(
    {"symbol": ..., "side": ..., "size": 0, "entry": 0,
     "account_balance": acct_balance, "run_mode": ...,
     "_guard_reason": _fail_msg, "_guard_blocked": True},
    alert_id=0, mode="guard_blocked",
)
```

### Payload Structure (HIGH confidence)

Payload is a plain `Dict[str, Any]` -- NOT a Pydantic model, NOT a dataclass. All access is via `payload.get("key")` or `payload["key"]`.

**Known payload fields relevant to Phase 5:**
- `session` -- int (0=Sydney, 1=London, 2=NY, etc.) -- already parsed from Pine webhook
- `score` -- float/int, zone quality score from Pine
- `symbol` -- string, e.g. "EURUSD"
- `side` -- "buy" or "sell"
- `entry`, `sl`, `tp` -- float prices
- `size` -- float lots
- `rr_ratio` -- float
- `run_mode` -- "DRY_RUN", "PAPER", "LIVE"
- `account_balance` -- float

**Fields NOT in payload currently (need to be parsed):**
- `premium_discount` -- new from Pine, float 0-1
- `kill_zone` -- new from Pine, int 0/1/2
- `day_of_week` -- NOT in payload; Friday check uses `_get_now_utc().weekday()` instead
- `hour` -- NOT in payload; Friday check uses `_get_now_utc().hour` instead

**Important finding about day_of_week/hour:** CONTEXT.md says "day_of_week and hour already exist in Pine payload -- use existing fields." However, grep shows `day_of_week` is NEVER referenced in worker.py. The existing Friday check (line 800-805) uses `_get_now_utc().weekday()` to get the current UTC weekday. This is actually more reliable than trusting the Pine payload timestamp.

### Settings Pattern (HIGH confidence)

`config/settings.py` uses Pydantic `BaseSettings` with `Field()` declarations. Pattern for adding new settings:

```python
# In class Settings(BaseSettings):
rubric_council_gate: float = Field(
    default=70.0,
    ge=0.0,
    le=100.0,
    description="Composite score threshold for LLM council to fire. Phase 6.",
    validation_alias=AliasChoices("RUBRIC_COUNCIL_GATE", "rubric_council_gate"),
)
rubric_exec_gate: float = Field(
    default=78.0,
    ge=0.0,
    le=100.0,
    description="Composite score threshold for execution. Phase 6.",
    validation_alias=AliasChoices("RUBRIC_EXEC_GATE", "rubric_exec_gate"),
)
default_estimated_rr: float = Field(
    default=2.0,
    ge=0.5,
    le=10.0,
    description="Default R:R when TP not present in payload. Used for EV score.",
    validation_alias=AliasChoices("DEFAULT_ESTIMATED_RR", "default_estimated_rr"),
)
```

### Test Patterns (HIGH confidence)

**Existing test infrastructure:**
- Framework: pytest
- Config: `tests/conftest.py` -- sets dummy env vars, mocks Redis globally
- Mocking: `unittest.mock.patch` and `unittest.mock.MagicMock`
- Pattern: patch `src.worker.get_settings` with `FakeSettings`, patch module-level singletons like `_NEWS_FILTER`

**Existing test file:** `tests/test_pine_filters_phase1.py` -- already has 4 tests:
1. `test_sydney_session_veto_blocks_signal()` -- patches `_validate_pine_filters` with session=0
2. `test_friday_cutoff_blocks_signal()` -- patches `_get_now_utc` to return a Friday 14:00
3. `test_news_proximity_veto_blocks_signal()` -- patches `_NEWS_FILTER.is_news_imminent` to return True
4. `test_drawdown_veto_blocks_one_account_not_other()` -- tests `_run_account_guards` with two profiles

**Key mocking patterns used:**
```python
with patch("src.worker.get_settings", return_value=_get_fake_settings()), \
     patch("src.worker._NEWS_FILTER") as mock_nf:
    mock_nf.is_news_imminent.return_value = False
    from src.worker import _validate_pine_filters
    result = _validate_pine_filters(payload)

# For per-account guards:
with patch("src.worker.supabase", new=MagicMock()), \
     patch("src.worker._get_account_positions_from_db", return_value=[]), \
     patch("src.worker._get_account_daily_pnl") as mock_daily_pnl:
    from src.worker import _run_account_guards
    result = _run_account_guards(payload, profile, settings, equity)
```

### Recommended Project Structure (no changes needed)

```
src/
  worker.py              # Main guard pipeline -- add EV score calc, payload parsing
  core/
    news_filter.py       # NewsFilter singleton -- already built, no changes needed
config/
  settings.py            # Add 3 new settings fields
tests/
  test_pine_filters_phase1.py  # Already exists -- verify tests pass
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| News calendar fetching | Custom HTTP+parse | `NewsFilter` singleton (already built) | Handles caching, timezone conversion, impact filtering |
| Payload validation | Pydantic model for webhook | Continue using `dict.get()` pattern | Entire codebase uses dict access; Pydantic model would be a Phase 6+ concern |
| Friday/day detection | Parse `day_of_week` from Pine payload | `_get_now_utc().weekday()` (already implemented) | Server UTC time is authoritative; Pine payload may have stale timestamps |

## Common Pitfalls

### Pitfall 1: Location Confusion (Global vs Per-Account)
**What goes wrong:** CONTEXT.md says vetoes go in per-account loop, but 3 of 4 are already in `_validate_pine_filters` (global).
**Why it happens:** The spec was written before checking the actual codebase.
**How to avoid:** Do NOT move existing working vetoes. Add per-account overrides only where needed (news: prop-firm fail-closed).
**Warning signs:** Tests breaking because veto logic is duplicated.

### Pitfall 2: NewsFilter Impact Level Mismatch
**What goes wrong:** CONTEXT.md says filter `impact >= "medium"`, but existing code only checks `impact == 'High'`.
**Why it happens:** Original NewsFilter was more conservative.
**How to avoid:** Decide explicitly whether to include Medium impact events. Medium events are far more frequent and would block more trades.
**Warning signs:** Too many news blocks during London session if Medium is included.

### Pitfall 3: Drawdown Calculation Method
**What goes wrong:** CONTEXT.md says `daily_drawdown_used_pct > 0.80` computed as `account.daily_loss_used / account.daily_loss_limit`. Existing code computes it differently: `dd_pnl < (max_daily_loss * 0.80)` using PnL and account balance.
**Why it happens:** Two different formulations that should be equivalent but may not be if account limits are configured differently.
**How to avoid:** Use the existing `_run_account_guards` drawdown logic (lines 1008-1039) as-is. It already does 80% of daily loss limit check.
**Warning signs:** EV score formula needs `daily_drawdown_used_pct` as a 0-1 float. Must extract it from the existing drawdown computation.

### Pitfall 4: rubric_engine.py Already Exists
**What goes wrong:** `src/rubric_engine.py` already exists (Phase 6 file). It references `premium_discount`. Phase 5 must NOT modify or wire this file.
**Why it happens:** Phase 6 code was scaffolded early.
**How to avoid:** Phase 5 parsing of `premium_discount` goes in worker.py payload handling only. Do NOT import from rubric_engine.py.

### Pitfall 5: Test File Already Exists But May Need Updates
**What goes wrong:** `tests/test_pine_filters_phase1.py` exists but tests may not match the final implementation (e.g., test 1 calls `_validate_pine_filters` but CONTEXT.md says veto goes in `_run_account_guards`).
**Why it happens:** Tests were scaffolded alongside the CONTEXT.md which specified per-account location.
**How to avoid:** Run tests first, see what passes/fails, then adjust implementation or tests as needed.

## Code Examples

### EV Score Calculation (from CONTEXT.md spec)
```python
# In worker.py, after drawdown check in _run_account_guards or at execution time
entry = float(payload.get("entry", 0))
sl = float(payload.get("sl", 0))
tp = float(payload.get("tp", 0))

if tp > 0 and sl > 0 and entry > 0:
    estimated_rr = abs(tp - entry) / abs(entry - sl)
else:
    estimated_rr = s.default_estimated_rr  # default 2.0

composite_proxy = float(payload.get("score", 0))  # 0-100 from Pine
# dd_pct must be computed from existing drawdown logic
ev_score = (composite_proxy / 100) * estimated_rr * (1 - dd_pct)
logger.info("EV score: %.4f (composite=%s, rr=%.2f, dd_pct=%.4f)", ev_score, composite_proxy, estimated_rr, dd_pct)
```

### premium_discount and kill_zone Parsing
```python
# Add to payload parsing area or at start of _validate_pine_filters / _run_account_guards
raw_pd = payload.get("premium_discount")
if raw_pd is not None:
    try:
        pd_val = float(raw_pd)
        payload["premium_discount"] = max(0.0, min(1.0, pd_val))  # clamp [0,1]
    except (ValueError, TypeError):
        payload["premium_discount"] = None
        logger.warning("premium_discount parse failed: %r", raw_pd)
else:
    logger.warning("premium_discount not in payload (Pine not updated yet)")

raw_kz = payload.get("kill_zone")
if raw_kz is not None:
    try:
        kz_val = int(raw_kz)
        payload["kill_zone"] = kz_val if kz_val in (0, 1, 2) else 0
    except (ValueError, TypeError):
        payload["kill_zone"] = None
        logger.warning("kill_zone parse failed: %r", raw_kz)
else:
    logger.warning("kill_zone not in payload (Pine not updated yet)")
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (no version file; standard Python stdlib mocking) |
| Config file | `tests/conftest.py` (sets dummy env vars, mocks Redis) |
| Quick run command | `python -m pytest tests/test_pine_filters_phase1.py -x -v` |
| Full suite command | `python -m pytest tests/ -x -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RUBRIC-01 | Sydney session (session=0) blocked | unit | `pytest tests/test_pine_filters_phase1.py::test_sydney_session_veto_blocks_signal -x` | YES |
| RUBRIC-01 | Friday after 14:00 UTC blocked | unit | `pytest tests/test_pine_filters_phase1.py::test_friday_cutoff_blocks_signal -x` | YES |
| RUBRIC-02 | News < 30 min blocked | unit | `pytest tests/test_pine_filters_phase1.py::test_news_proximity_veto_blocks_signal -x` | YES |
| RUBRIC-02 | Drawdown > 80% blocked per-account | unit | `pytest tests/test_pine_filters_phase1.py::test_drawdown_veto_blocks_one_account_not_other -x` | YES |
| RUBRIC-03 | EV score calculated and logged | unit | (new test needed) | NO - Wave 0 |
| RUBRIC-03 | premium_discount parsed/clamped | unit | (new test needed) | NO - Wave 0 |
| RUBRIC-03 | kill_zone parsed | unit | (new test needed) | NO - Wave 0 |
| RUBRIC-03 | Settings: RUBRIC_COUNCIL_GATE, RUBRIC_EXEC_GATE, DEFAULT_ESTIMATED_RR | unit | (new test needed) | NO - Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_pine_filters_phase1.py -x -v`
- **Per wave merge:** `python -m pytest tests/ -x -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] EV score calculation test (verify formula output)
- [ ] premium_discount/kill_zone parsing tests (absent field, out-of-range, valid)
- [ ] Settings fields existence test (verify defaults load correctly)

## Project Constraints (from CLAUDE.md)

- **Jira workflow:** Must create Jira ticket before any work. Ticket number in every git commit. Progress comment at every meaningful step.
- **API contract integrity:** Never change API payload shape without updating backend schema, frontend types, tests, docs.
- **Minimal safe patches:** Prefer minimal safe patches over rewrites. Phase 5 vetoes are additive.
- **Tracking:** Update docs/worklog.md, docs/bugs.md, docs/decisions.md as appropriate.
- **Board rules:** Create BUG tickets for any bugs discovered during implementation.
- **Smart Commit format:** `feat: [DEV-XX] Add pre-filter vetoes and EV score #time Xh`

## Sources

### Primary (HIGH confidence)
- `src/worker.py` lines 50-56 -- NewsFilter singleton instantiation
- `src/worker.py` lines 584-816 -- `_get_now_utc()`, `_validate_pine_filters()` with existing vetoes
- `src/worker.py` lines 893-1086 -- `_run_account_guards()` with existing drawdown veto
- `src/worker.py` lines 1173-1361 -- `process_trade()` guard pipeline flow
- `src/core/news_filter.py` -- Full NewsFilter class (142 lines)
- `config/settings.py` -- Pydantic BaseSettings pattern (483 lines)
- `tests/test_pine_filters_phase1.py` -- Existing 4-test suite (157 lines)
- `tests/conftest.py` -- Pytest config with dummy env vars and Redis mock

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all code is local, read directly
- Architecture: HIGH - guard pipeline fully traced from entry to execution
- Pitfalls: HIGH - identified 5 specific mismatches between CONTEXT.md and actual code
- Test patterns: HIGH - existing test file read and analyzed

**Research date:** 2026-03-26
**Valid until:** 2026-04-26 (stable backend, no external dependencies changing)
