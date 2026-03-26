# Phase 5: Pre-filter Hardening & EV Score — Context

**Gathered:** 2026-03-26
**Status:** Ready for planning
**Source:** PRD Express Path (~/.gstack/projects/ameer1996112-liquidity-supply-and-demand/ameeramer-main-design-20260325-231026.md + CEO plan + Eng review)

<domain>
## Phase Boundary

Phase 5 implements **Approach A** from the approved design: rule-based hard vetoes in the pre-filter stack plus EV-adjusted score output. This is the minimal patch that ships this week.

**Delivers:**
- 4 hard vetoes added to `worker.py` per-account guard loop (~line 878)
- NewsFilter singleton wired from `src/core/news_filter.py` (already built — just wire it)
- EV score formula (`ev_score = (composite/100) * estimated_rr * (1 - dd_pct)`) as informational output
- `premium_discount` and `kill_zone` fields parsed from Pine webhook payloads (new fields expected but not yet sent — graceful handling of missing values required)
- Test suite: `tests/test_pine_filters_phase1.py` (4 tests)

**Does NOT include:**
- `rubric_engine.py` (Phase 6)
- Composite score gating of LLM council (Phase 6)
- DB schema changes / JSONB rubric_score column (Phase 6)
- Pine Script changes (manual, user-driven, not automated)

</domain>

<decisions>
## Implementation Decisions

### Hard Veto 1: Sydney Session
- Block when `session == 0` (Sydney session)
- Location: per-account loop in `worker.py` (~line 878), NOT `_validate_pine_filters`
- Reason (from Eng Review): drawdown lookup is per-account; vetoes that need account context belong here
- Behavior: fail-closed (block trade), log as WARNING, no Discord alert needed

### Hard Veto 2: Friday Close
- Block when `day_of_week == 4` AND `hour >= 14` (UTC)
- Same location: per-account loop in `worker.py`
- `day_of_week` and `hour` already exist in Pine payload — use existing fields

### Hard Veto 3: News Proximity
- Block when `news_minutes_to_next < 30` (minutes to next high-impact news for traded pair)
- Use `NewsFilter` singleton from `src/core/news_filter.py` — **do not rebuild**, wire as singleton
- Cache: Redis, TTL=60 minutes, key=`ff_calendar:{week_iso}`
- API: `https://nfs.faireconomy.media/ff_calendar_thisweek.json` (public JSON)
- Filter: events where `impact >= "medium"` AND `currency` matches base or quote of instrument
- Fail behavior: **fail-closed for prop firm accounts**, fail-open for personal accounts
- Location: per-account loop, called after session/day vetoes (cheap vetoes first)

### Hard Veto 4: Daily Drawdown
- Block when `daily_drawdown_used_pct > 0.80`
- Computed as: `account.daily_loss_used / account.daily_loss_limit` from Supabase
- **Per-account** (not global) — account A blocked does NOT block account B
- Supabase unavailability: fail-closed + Discord alert via `send_discord_async()`
- Location: per-account loop, after session/day/news vetoes

### EV Score
- Formula: `ev_score = (composite_score / 100) * estimated_rr * (1 - daily_drawdown_used_pct)`
- `estimated_rr = (tp - entry) / abs(entry - sl)` when tp present; default `DEFAULT_ESTIMATED_RR=2.0` when absent
- `composite_score` for Phase 1 is a simplified placeholder (not the full 4-dimension score — that's Phase 6)
- Output: informational only, logged alongside existing scores; does NOT gate execution in Phase 1
- `RUBRIC_COUNCIL_GATE` and `RUBRIC_EXEC_GATE` env vars added to settings.py (default 70/78) but NOT wired into execution flow yet — reserved for Phase 6

### premium_discount and kill_zone Parsing
- Add both fields to Pine webhook payload parser in `worker.py` or the signal intake handler
- `premium_discount`: float 0–1 (0=deep discount, 1=deep premium); clamp to [0,1] if out of range
- `kill_zone`: int (1=London KZ, 2=NY KZ, 0=outside)
- If field absent (Pine not yet updated): treat as None, log WARNING, do NOT veto
- These are parsed/stored but not yet used for scoring in Phase 5

### return_strength Floor Check
- DO NOT remove `_validate_pine_filters` floor check in Phase 5 (that's a Phase 6 prerequisite)
- Phase 5 vetoes are additive; no changes to existing scoring logic

### Test Strategy
- `tests/test_pine_filters_phase1.py`:
  1. Sydney session → blocked
  2. Friday after 14:00 UTC → blocked
  3. News < 30 min → blocked (mock NewsFilter)
  4. Drawdown > 80% → blocked per-account (account A blocked, account B not blocked)
- Tests should mock account state — no real Supabase calls in unit tests

### Claude's Discretion
- Exact placement of vetoes within the per-account loop (order matters: cheapest first)
- How to surface ev_score in existing logging (log level, format)
- Whether to add ev_score to the signal record in DB (if schema allows without migration)
- Implementation of `DEFAULT_ESTIMATED_RR` config pattern (consistent with existing settings.py pattern)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Authority
- `~/.gstack/projects/ameer1996112-liquidity-supply-and-demand/ameeramer-main-design-20260325-231026.md` — Full rubric design, all 4 dimensions, grading criteria, open questions, success criteria
- `~/.gstack/projects/ameer1996112-liquidity-supply-and-demand/ceo-plans/2026-03-25-trade-evaluation-rubric.md` — CEO plan: scope decisions, architectural decisions, fail behavior, threshold tunability
- `~/.gstack/projects/ameer1996112-liquidity-supply-and-demand/ameeramer-main-eng-review-test-plan-20260325-235436.md` — Eng review test plan: 35-path test plan, Phase 1 + Phase 2 key interactions

### Key Implementation Files (read before touching)
- `src/worker.py` — Pre-filter stack + per-account guard loop (~line 878); all 4 vetoes go here
- `src/core/news_filter.py` — NewsFilter already built; wire as singleton, do NOT rebuild
- `config/settings.py` — All threshold env vars pattern (add RUBRIC_COUNCIL_GATE, RUBRIC_EXEC_GATE, DEFAULT_ESTIMATED_RR)
- `src/ai/trading_council.py` — LLM council entry point (read-only in Phase 5; gated in Phase 6)
- `src/adapters/jira.py` — Jira automation (per CLAUDE.md rules)

### Project Instructions
- `CLAUDE.md` — Jira workflow enforcement, board rules, tracking rules
- `.claude/CLAUDE.md` — Production trading system rules: API contract integrity, minimal safe patches

</canonical_refs>

<specifics>
## Specific Implementation Notes

### NewsFilter wiring
`src/core/news_filter.py` exists. Create module-level singleton (not per-call):
```python
# In worker.py or a shared module
from src.core.news_filter import NewsFilter
_news_filter = NewsFilter()  # singleton
```
Second call must use cached calendar — no second HTTP request. Covered by test.

### Fail-closed behavior (Supabase unavailability)
When Supabase is unreachable for the drawdown check:
```python
try:
    dd_pct = get_account_drawdown_pct(account_id)
except Exception:
    await send_discord_async(f"[TRADE BLOCKED] Supabase unavailable for account {account_id} — fail-closed")
    return  # block trade
```
This is the explicit pattern from the Eng Review decision.

### Veto order (cheapest first)
1. Session check (no I/O)
2. Day/hour check (no I/O)
3. News check (Redis cache → HTTP on miss)
4. Drawdown check (Supabase query)

### EV score for Phase 5 (simplified)
Phase 5 does not have a composite_score from the full rubric yet. Use existing Pine `score` field as a proxy:
```python
composite_proxy = payload.get("score", 0) * 100  # normalize 0-1 → 0-100
ev_score = (composite_proxy / 100) * estimated_rr * (1 - dd_pct)
```
Log it. Don't gate on it. Phase 6 replaces composite_proxy with the real rubric score.

</specifics>

<deferred>
## Deferred to Phase 6

- `rubric_engine.py` — full 4-dimension scoring
- Composite score gate for LLM council (≥70 threshold)
- JSONB rubric_score column in signals table (DB migration)
- Remove `return_strength` floor check from `_validate_pine_filters`
- RUBRIC_GATE_ENABLED feature flag with shadow scoring mode
- Stage 2 monitoring (Pine approach-zone second alert)

</deferred>

---

*Phase: 05-pre-filter-hardening-ev-score*
*Context gathered: 2026-03-26 via PRD Express Path*
