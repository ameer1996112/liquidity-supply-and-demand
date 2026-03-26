---
phase: 05-pre-filter-hardening-ev-score
plan: 01
subsystem: api
tags: [pydantic, settings, news-filter, ev-score, rubric, worker, testing]

# Dependency graph
requires: []
provides:
  - RUBRIC_COUNCIL_GATE, RUBRIC_EXEC_GATE, DEFAULT_ESTIMATED_RR settings with env aliases and startup validation
  - NewsFilter blocks Medium AND High impact events (not just High)
  - premium_discount parsed from payload, clamped to [0.0, 1.0], None if absent
  - kill_zone parsed from payload, validated to {0, 1, 2}, None if absent
  - EV score computed after per-account drawdown check, logged at INFO, stored in payload._ev_score
affects: [06-rubric-engine, any phase using rubric/EV scoring]

# Tech tracking
tech-stack:
  added: [pydantic model_validator]
  patterns: [Field + validation_alias for env-var settings, model_validator for cross-field validation, payload._underscore prefix for internal metadata]

key-files:
  created:
    - tests/test_pine_filters_phase1.py (6 new tests appended, total 10)
  modified:
    - config/settings.py
    - src/core/news_filter.py
    - src/worker.py
    - tests/test_pine_filters_phase1.py

key-decisions:
  - "EV score is informational only (logged, stored in payload._ev_score) — does NOT gate execution. Gating reserved for Phase 6."
  - "premium_discount and kill_zone parsed with debug log (not warning) when absent — these fields expected missing until Pine is updated."
  - "news filter changed from impact != High to impact not in (High, Medium) per CONTEXT.md decision."
  - "rubric_exec_gate >= rubric_council_gate enforced via model_validator at startup."

patterns-established:
  - "payload._underscore prefix = internal metadata not from webhook (consistent with _risk_multiplier_* pattern)"
  - "EV formula: (composite_proxy/100) * estimated_rr * (1 - dd_pct)"
  - "model_validator(mode='after') for cross-field settings validation"

requirements-completed: [RUBRIC-01, RUBRIC-02, RUBRIC-03]

# Metrics
duration: 25min
completed: 2026-03-26
---

# Phase 05 Plan 01: Pre-filter Hardening & EV Score Summary

**Three new rubric settings (RUBRIC_COUNCIL_GATE=70, RUBRIC_EXEC_GATE=78, DEFAULT_ESTIMATED_RR=2.0), Medium-impact news blocking, premium_discount/kill_zone payload parsing, and informational EV score formula — 10 tests all GREEN**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-03-26T12:25:00Z
- **Completed:** 2026-03-26T12:50:00Z
- **Tasks:** 5 (Task 0: Jira, Task 1: settings, Task 2: news_filter, Task 3: worker, Task 4: tests)
- **Files modified:** 4

## Accomplishments
- Added 3 rubric/EV score settings to `config/settings.py` with pydantic `model_validator` enforcing exec >= council gate
- Upgraded `NewsFilter.is_news_imminent` to block both Medium and High impact events (was High-only)
- Added `premium_discount` and `kill_zone` parsing in `_validate_pine_filters` with clamping/validation
- Added EV score computation in `_run_account_guards` — informational logging only, no execution gating
- Expanded test suite from 4 to 10 tests; all 356 tests in broader suite pass

## Task Commits

Each task was committed atomically:

1. **Task 0: Create Jira ticket** - Jira DEV-53 created, branch `feature/DEV-53-phase-5-prefilter-hardening-ev-score`
2. **Task 1: Add rubric settings** - `cf8ae74` (feat: [DEV-53] add RUBRIC_COUNCIL_GATE, RUBRIC_EXEC_GATE, DEFAULT_ESTIMATED_RR)
3. **Task 2: Upgrade NewsFilter** - `3d5d870` (feat: [DEV-53] upgrade NewsFilter to block Medium AND High impact events)
4. **Task 3: Parse payload fields + EV score** - `b6c8cb9` (feat: [DEV-53] parse premium_discount/kill_zone and compute EV score)
5. **Task 4: Add 6 new tests** - `ca3402b` (test: [DEV-53] add 6 new tests for rubric settings, payload parsing, EV score)

## Files Created/Modified
- `config/settings.py` - 3 new rubric/EV settings fields + model_validator for gate order validation
- `src/core/news_filter.py` - Medium impact now blocks (was High-only), log message uses impact variable
- `src/worker.py` - premium_discount/kill_zone parsing in _validate_pine_filters; EV score block in _run_account_guards
- `tests/test_pine_filters_phase1.py` - 6 new tests added (tests 5-10), import datetime added at top

## Decisions Made
- EV score does NOT gate execution — follows plan and CONTEXT.md. Phase 6 will wire this to rubric engine.
- Used `logger.debug` (not WARNING) for absent `premium_discount`/`kill_zone` fields — these are optional fields that won't exist until Pine is updated; WARNING would spam logs on every signal.
- EV formula uses `payload.get("score", 0) * 100` to convert Pine's 0-1 score to 0-100 composite proxy.
- Floating-point precision in EV test assertion fixed using `abs(ev_value - 1.6) < 0.01` instead of string matching.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] EV test assertion needed floating-point tolerance**
- **Found during:** Task 4 (test_ev_score_formula)
- **Issue:** String matching `"1.6" in ev_msg` failed because Python repr of `1.5999999999999646` doesn't contain `"1.6"` as a substring
- **Fix:** Changed assertion to extract numeric value from logger call args and use `abs(val - 1.6) < 0.01`
- **Files modified:** tests/test_pine_filters_phase1.py
- **Verification:** Test passes with correct EV value 1.5999... ≈ 1.6
- **Committed in:** ca3402b (Task 4 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test assertion)
**Impact on plan:** Necessary for test correctness. No scope creep.

## Issues Encountered
- EV test assertion floating-point precision — fixed inline (see deviations above)

## User Setup Required
None - no external service configuration required. New settings are optional with correct defaults.

## Next Phase Readiness
- Phase 6 (rubric engine) can read `s.rubric_council_gate`, `s.rubric_exec_gate`, `s.default_estimated_rr` immediately
- `payload["_ev_score"]` is populated after drawdown check, available to downstream logic
- `payload["premium_discount"]` and `payload["kill_zone"]` are parsed and validated, ready for rubric weighting
- News filter now correctly blocks Medium impact events

## Self-Check: PASSED

All files found:
- FOUND: config/settings.py
- FOUND: src/core/news_filter.py
- FOUND: src/worker.py
- FOUND: tests/test_pine_filters_phase1.py
- FOUND: 05-01-SUMMARY.md

All commits present: cf8ae74, 3d5d870, b6c8cb9, ca3402b

---
*Phase: 05-pre-filter-hardening-ev-score*
*Completed: 2026-03-26*
