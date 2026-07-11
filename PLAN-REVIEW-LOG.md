# Plan Review Log: Match RD Forex 5-Minute Zone Detection
Act 1 (grill) complete — plan locked with the user. MAX_ROUNDS=5.

## Round 1 — Codex

Findings:

1. `PLAN.md` had an impossible acceptance bar: “zero missed zones, zero extra zones” against manually labeled screenshots from a protected indicator. That could block implementation indefinitely and confuse label noise with code defects. Fix: define tolerances, adjudication rules, and a second-pass label review process.
2. `SND_Raw_RD_Forex_LAB.pine` sends every lifecycle event through `alert()`, while the plan said only confirmed trade-eligible PROD zones should alert. `ZONE_CREATED`, `LIQUIDITY_LINKED`, `LIQUIDITY_SWEPT`, `TARGET_SWEPT`, `ZONE_TOUCHED`, and `ZONE_INVALIDATED` can reach the webhook path. Fix: separate visual/debug events from executable alerts or enforce an event contract that the backend rejects unless it is a trade signal.
3. `src/core/signal.py` requires executable fields such as `strategy_id`, `side`, `entry`, `sl`, `tp`, and `size`; the Pine lifecycle payload lacks them. The plan did not cover the backend contract boundary. Fix: use a separate non-execution endpoint/schema or keep lifecycle alerts off `/webhook` until executable payloads exist.
4. `src/api.py` can override incoming `run_mode` with system configuration and default toward live when system mode is live. “Live execution remains blocked” was not enforced by the alert path. Fix: require a backend execution gate that rejects this strategy/version unless validation flags explicitly allow it.
5. `SND_Raw_RD_Forex_LAB.pine` hard-gates displacement on ATR/body thresholds, while the plan wanted to remove them without defining the replacement predicate. Fix: specify exact standard and accuracy rules for wick-only, close-only, doji, gap, and equal-high/low cases.
6. LAB suppresses accuracy bounds for XAU/XAG/XPT/XPD, while the plan includes XAUUSD and XPTUSD. Fix: state whether metals intentionally use standard bounds, or remove suppression and add labeled metal cases.
7. LAB sets `createdBar := bar_index`, not `confirmationBar`; historical suppressed-symbol creation can create old-origin zones on the current bar. Fix: distinguish detection, confirmation, and visual backfill timing.
8. Invalidation starts after confirmation, but the touch flag can be set for any overlap after `originBar`, including formation/departure candles. Fix: evaluate touches from `invalidationStartBar` or an explicit return-tap start.
9. The plan said the three indicator files may drift but only proposed comparing them before promotion. Fix: require a documented promotion step or a mandatory diff checklist.
10. The plan lacked an observability format, artifact location, replay procedure, and machine-readable mismatch report. Fix: define a CSV/JSON fixture schema and deterministic diff output.

### Claude's response

Accepted all ten findings. The plan now defines a reviewed fixture set with one-tick adjudication, exact close-based standard/accuracy predicates, separate origin/detection/confirmation timestamps, departure-exempt touch evaluation, metal accuracy behavior, a documented LAB-to-PROD diff gate, a machine-readable event schema, and a fail-closed boundary that prevents lifecycle/debug events from reaching the executable webhook. The zero-mismatch requirement remains, but only for adjudicated, same-feed examples and zero unresolved discrepancies.

## Round 2 — Codex

Findings:

1. Liquidity selection remained underspecified: the plan did not define which candle owns liquidity, equal-level handling, separation limits, competing candidates, or inducement versus target selection. Fix: add deterministic side-mirrored liquidity ownership, clustering, search-window, and tie-break rules.
2. The plan prohibited lifecycle events from `/webhook`, but chart-local logging is not a persisted two-week audit channel. Fix: choose a dedicated non-execution endpoint/schema or a retained export workflow.
3. The plan required fixtures and a mismatch report without defining how actual Pine output is extracted deterministically from TradingView replay. Fix: define run IDs, alert/export collection, replay procedure, and comparator inputs/outputs.
4. The backend gate was a safety dependency with no owned phase while production alert contracts were out of scope. Fix: make the backend gate and debug schema an explicit Phase 0 prerequisite, or block executable work until a separate ticket lands.
5. Excluding ambiguous or feed-mismatched examples could make the dataset artificially easy. Fix: cap exclusions, categorize them, and require minimum coverage per instrument/model.
6. LAB must retain candidates, rejected states, labels, liquidity, and historical diagnostics, but Pine object/runtime limits were not addressed. Fix: add bounded object budgets, deterministic pruning, and overflow-free validation criteria.
7. Confirmation timing and trade eligibility were easy to conflate. Fix: name `ZONE_CONFIRMED_NON_EXECUTABLE` and `TRADE_ELIGIBLE_EXECUTABLE` separately and define allowed destinations.

### Claude's response

Accepted all seven findings. The plan now specifies side-mirrored liquidity ownership and tie-breaks, a dedicated persisted debug collection path, run IDs and a deterministic fixture comparator, Phase 0 ownership of the fail-closed backend boundary, capped/adjudicated validation exclusions with per-instrument coverage, bounded Pine object budgets, and explicit non-executable versus executable event names.

## Round 3 — Codex

Prior findings are largely addressed. The revised plan explicitly covers dedicated event names, `TRADE_ELIGIBLE_EXECUTABLE` as the only executable event, Phase 0 ownership for backend fail-closed gating and the non-execution debug schema, persisted debug collection, deterministic fixtures and comparator flow, exclusion caps and instrument coverage, Pine object/runtime caps, closed-bar confirmation, and LAB/PROD drift control.

Remaining non-blocking tightening: the liquidity tie-break wording says “prefer closest qualifying candidate, then earliest pivot, then smallest price distance,” where “closest” and “smallest price distance” may overlap unless “closest” is defined as nearest in time or nearest to the zone edge. This will be made explicit during implementation; it does not block the plan because Phase 0 and fixture comparison catch divergence.

VERDICT: APPROVED

## Act 3 — Build Report (Codex, 2026-07-11)

Implemented Phase 0 safety boundary and the first LAB detector alignment pass.

Changed:
- `scripts/pinescript/indicators/SND_Raw_RD_Forex_LAB.pine`
  - Disabled continuation-zone creation for the core normal/accuracy validation phase.
  - Removed metal/index accuracy suppression by making accuracy bounds available for all symbols.
  - Changed directional candle checks so dojis do not confirm zones.
  - Replaced ATR/body displacement hard gates with strict closed-bar confirmation beyond the full origin boundary or selected accuracy boundary.
  - Renamed official confirmation lifecycle event to `ZONE_CONFIRMED_NON_EXECUTABLE`.
  - Expanded debug payload fields with `run_id`, strategy/version, feed/timeframe, model, detection/confirmation fields, liquidity, tap, and invalidation fields.
  - Kept Pine `alert()` fail-closed: only `TRADE_ELIGIBLE_EXECUTABLE` can call `alert()`. LAB currently emits no executable event.
  - Moved touch marking to confirmation/invalidation window so formation/departure wicks do not count as return taps.
  - Implemented the reviewed liquidity tie-break interpretation as closest to the zone edge, then earliest pivot, then price distance. In code this is represented by `bestDist` first and `isEarlierPivot` on equal distance.
- `src/core/signal.py`
  - Added non-execution RD Forex debug schema.
  - Rejected RD Forex lifecycle/debug events from executable webhook validation.
- `src/api.py`
  - Added `/webhook/rd-forex/debug`, which validates lifecycle/debug events and does not persist or enqueue them.
  - Added fail-closed `/webhook` gate for RD Forex executable alerts.
- `config/settings.py`
  - Added `RD_FOREX_EXECUTABLE_ENABLED`, default `false`.
- `scripts/pinescript/tests/test_snd_raw_rd_demand_liquidity_near_edge_static.py`
  - Kept baseline/PROD old ranking assertions and added LAB-specific earliest-pivot tie-break assertions.
- `scripts/pinescript/tests/test_snd_raw_rd_origin_high_reference_fallback_static.py`
  - Updated retracement tie-break assertion for LAB only.
- `tests/test_signal_transport.py`
  - Added schema coverage for executable rejection and debug payload acceptance.

Validation:
- Jira ticket creation attempted with `node scripts/jira/jira-sync.js --no-branch "Implement RD Forex LAB zone detection validation gates"` and failed because Atlassian returned `Jira 404: {"errorMessage":"Site temporarily unavailable","errorCode":"OTHER"}`.
- `source ./venv/bin/activate && PYTHONPATH=. pytest -q tests/test_signal_transport.py scripts/pinescript/tests` passed: `50 passed in 0.43s`.
- `source ./venv/bin/activate && python -m py_compile src/core/signal.py src/api.py config/settings.py` passed.
- `git diff --check` passed.
- Required `PYTHONPATH=. pytest -q` was run with system Python and failed during collection because `playwright` was not installed and `scripts.optimizer.optimizer` called `sys.exit(1)`.
- Required full-suite command was rerun through `./venv`; it progressed past 60% with several failures already printed, then produced no further output for repeated polls and was terminated to avoid leaving a background test run. Full-suite pass/fail remains unresolved in this environment.

Deviations / limitations:
- No visual parity claim is made. Protected-reference screenshots/fixtures and comparator artifacts were not provided in this repo state.
- No production promotion was made; baseline and PROD were compared at the header/shape level and left unchanged.
- Pine cannot be compiled locally here; validation is static tests plus review.
- LAB debug events are schema-ready but not persisted to JSONL/CSV by the API yet; the endpoint is non-execution and log-only.
- Candidate/rejected events remain visual/internal in this slice; confirmed/liquidity/touch/invalidation payload shape is prepared, but `sendEvent()` suppresses all non-executable alerts to keep fail-closed behavior.
- Object peak counts were not measured because TradingView runtime/replay execution was not available.

### Fix Round 1 (Codex, 2026-07-11)

Addressed verification findings without redesigning the approved plan:
- `SND_Raw_RD_Forex_LAB.pine` now sends only allowlisted non-executable debug events through TradingView `alert()`: `ZONE_CANDIDATE`, `ZONE_CONFIRMED_NON_EXECUTABLE`, `LIQUIDITY_LINKED`, `LIQUIDITY_SWEPT`, `TARGET_SWEPT`, `ZONE_TOUCHED`, and `ZONE_INVALIDATED`.
- LAB no longer contains or emits `TRADE_ELIGIBLE_EXECUTABLE`; executable routing remains backend-gated by `/webhook`, schema validation, and `RD_FOREX_EXECUTABLE_ENABLED`.
- `ZONE_CONFIRMED_NON_EXECUTABLE` is only alerted when `confirmationBar == bar_index`; historical/backfilled zones may still render but do not emit a current confirmation debug event.
- Added focused Pine static tests for the debug-event allowlist, no LAB executable event, and current-bar confirmation alert guard.
- Added backend schema coverage proving debug payloads reject `TRADE_ELIGIBLE_EXECUTABLE`.

Proof:
- `source ./venv/bin/activate && PYTHONPATH=. pytest -q tests/test_signal_transport.py scripts/pinescript/tests`
  - `53 passed in 0.50s`
- `source ./venv/bin/activate && python -m py_compile src/core/signal.py src/api.py config/settings.py`
  - passed with no output
- `git diff --check`
  - passed with no output

### Claude's verdict — comparator and artifact continuation

Independent verification completed. The continuation slice passes `61` focused tests, `3` webhook-ingress tests, Python compilation, and `git diff --check`. The debug endpoint now persists validated non-executable LAB events to per-run JSONL and CSV artifacts, and the comparator preserves duplicate-event multiplicity while reporting missing, extra, boundary, timestamp, lifecycle, repaint, and fixture-key discrepancies.

The full `PYTHONPATH=. pytest -q` suite remains unresolved from the prior bounded run, and no new full-suite pass is claimed. TradingView compilation, protected-reference visual parity, real labeled fixture coverage, and runtime object-peak measurements remain unverified. The checked-in fixture is schema-only; this slice is therefore validation infrastructure and a tested safety boundary, not evidence that zone detection is 100% accurate or approval for PROD promotion/live execution.

### Claude's verdict

Independent review completed. The focused Pine/backend suite passes (`53 passed in 0.50s`), the webhook-ingress proof passes (`30 passed in 4.05s`), Python compilation passes, and `git diff --check` passes. The fix closes the material debug-stream gap: LAB emits only allowlisted non-executable lifecycle events, the executable event is absent from LAB, and historical confirmation alerts are limited to the current confirmation bar.

The full `PYTHONPATH=. pytest -q` suite remains unresolved: it reproduced multiple failures and stopped yielding output before the bounded run was terminated. TradingView compilation, protected-reference visual parity, the JSONL/CSV comparator artifacts, and object-peak measurements remain unverified. This build is therefore an implemented and tested alignment slice, not approval for PROD promotion or live execution.

### Fix Round 2 (Codex, 2026-07-11)

Addressed the comparator multiplicity verification finding:
- `scripts/pinescript/validation/rd_forex_compare.py` no longer collapses fixture or actual rows into one row per key. It groups rows by deterministic comparison key, matches rows in input order within each key, reports unmatched expected rows as missing, and reports unmatched confirmed actual rows as extra.
- Duplicate fixture keys now produce a deterministic `duplicate_fixture_key` fixture error instead of silently overwriting an earlier reference row.
- Duplicate actual confirmed events beyond the fixture count are preserved as extra events and summarized in `duplicate_actuals`.
- `tests/test_rd_forex_debug_validation.py` now includes regressions proving duplicate actual confirmed events are reported as extras and duplicate fixture keys are diagnosed.

Proof:
- `source ./venv/bin/activate && PYTHONPATH=. pytest -q tests/test_rd_forex_debug_validation.py tests/test_signal_transport.py scripts/pinescript/tests`
  - `61 passed in 0.42s`
- `source ./venv/bin/activate && python -m py_compile src/api.py src/core/signal.py config/settings.py src/services/rd_forex_debug_collector.py scripts/pinescript/validation/rd_forex_compare.py tests/test_rd_forex_debug_validation.py`
  - passed with no output
- `git diff --check`
  - passed with no output
