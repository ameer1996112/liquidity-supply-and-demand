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
