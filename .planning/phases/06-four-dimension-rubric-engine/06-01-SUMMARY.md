---
phase: 06-four-dimension-rubric-engine
plan: 01
subsystem: rubric-engine
tags: [rubric, scoring, trading-council, pre-gate, ev-score, phase6]
dependency_graph:
  requires: [phase-05-prefilter-hardening]
  provides: [four-dimension-rubric-engine, score-trade-api, council-pre-gate]
  affects: [src/worker.py, src/rubric_engine.py, config/settings.py]
tech_stack:
  added: []
  patterns: [feature-flag, hard-veto, composite-scoring, linear-decay]
key_files:
  created:
    - migrations/060_add_rubric_score_column.sql
  modified:
    - src/rubric_engine.py
    - config/settings.py
    - src/worker.py
    - tests/test_rubric_engine.py
decisions:
  - "score_trade replaces score_signal as public API; score_signal kept as backward-compat shim"
  - "get_settings imported at module level (not inside functions) to allow test patching"
  - "env score 15 pts at dd=0 means empty payload scores 15 not 0 — tests account for this"
  - "Hard veto boundary: dd > 0.80 (strict greater-than), dd == 0.80 allowed through"
metrics:
  duration: "~25 minutes"
  completed: "2026-03-26"
  tasks: 5
  files: 5
---

# Phase 06 Plan 01: Four-Dimension Rubric Engine Summary

Replaced the interim `score_signal(payload)` API with the production `score_trade(payload, account_state)` function using four weighted scoring dimensions and four hard vetoes as the LLM council pre-gate.

## What Was Built

**New public API:** `score_trade(payload, account_state) -> RubricResult`

Four dimensions replacing the old 4-dimension approach:
- **Liquidity Context (max 35 pts):** departure_strength * 0.25 + kill_zone lookup (0/5/10)
- **Zone Quality (max 25 pts):** return_strength inverted * 0.15 + candles_to_return lookup (10/6/3/0)
- **Structural Alignment (max 25 pts):** premium_discount directional alignment (BUY in discount, SELL in premium)
- **Account & Environment (max 15 pts):** linear decay from 15 pts at 0% DD to 0 pts at 80% DD

Four hard vetoes (composite=0, proceed=False):
1. `sweep_candle_close=True`
2. `session=0` (Sydney)
3. `daily_drawdown_pct > 0.80`
4. `news_block=True` or `time_to_news_minutes < 30`

Gate status thresholds (from settings):
- `blocked` — composite < 70 (rubric_council_gate)
- `shadow` — 70 <= composite < 78 (rubric_exec_gate)
- `execute` — composite >= 78
- `disabled` — RUBRIC_ENGINE_ENABLED=False

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Add rubric_engine_enabled to settings.py | 1ab2138 |
| 2 | Rewrite src/rubric_engine.py with 4-dimension engine | 1ab2138 |
| 3 | Wire score_trade before Trading Council in worker.py | 1ab2138 |
| 4 | Create migration 060_add_rubric_score_column.sql | 1ab2138 |
| 5 | Rewrite tests/test_rubric_engine.py (42 tests) | 1ab2138 |

## Test Results

- `tests/test_rubric_engine.py`: **42 passed, 0 failed**
- `tests/test_pine_filters_phase1.py`: **10 passed, 0 failed** (no regressions)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Module-level import required for get_settings**
- **Found during:** Task 5 (test_rubric_engine_disabled_bypasses_all_logic)
- **Issue:** Plan showed `from config.settings import get_settings` inside functions; `patch("src.rubric_engine.get_settings")` failed because the name wasn't in the module namespace
- **Fix:** Moved `from config.settings import get_settings` to module-level import in rubric_engine.py; removed local function imports
- **Files modified:** src/rubric_engine.py
- **Commit:** 1ab2138

**2. [Rule 1 - Bug] Empty payload test expectation corrected**
- **Found during:** Task 5 (test_composite_empty_payload)
- **Issue:** Empty payload with dd=0 still scores 15 pts from account_environment. Plan test description said "composite=0" but that's only achievable with dd=0.8 in account_state
- **Fix:** Updated test to pass account with daily_drawdown_pct=0.80 (at the cap, no veto) so env=0 and composite=0
- **Files modified:** tests/test_rubric_engine.py
- **Commit:** 1ab2138

## Known Stubs

None — all dimensions are fully wired with real payload fields.

## Self-Check: PASSED

Files exist:
- FOUND: /Users/ameeramer/dev/projects/galilsoftware/sources/trading/src/rubric_engine.py
- FOUND: /Users/ameeramer/dev/projects/galilsoftware/sources/trading/config/settings.py
- FOUND: /Users/ameeramer/dev/projects/galilsoftware/sources/trading/src/worker.py
- FOUND: /Users/ameeramer/dev/projects/galilsoftware/sources/trading/migrations/060_add_rubric_score_column.sql
- FOUND: /Users/ameeramer/dev/projects/galilsoftware/sources/trading/tests/test_rubric_engine.py

Commit exists: 1ab2138 — feat: [DEV-53] implement four-dimension rubric engine (Phase 6)
