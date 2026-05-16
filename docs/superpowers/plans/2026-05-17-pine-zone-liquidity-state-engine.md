# Pine Zone Liquidity State Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the Pine strategy into a deterministic broad-zone, strict-entry engine with explicit candidate, liquidity, BOS, return, and invalidation states.

**Architecture:** Keep the current single Pine strategy file for now to avoid import/library churn and TradingView publish friction. Add canonical reason/state helpers first, then move detector, liquidity proof, return/mitigation, and visuals onto those helpers. Entry/risk/SL/TP/webhook/order code remains unchanged until the state engine is verified.

**Tech Stack:** Pine Script v6, static Python contract tests under `scripts/pinescript/tests/`.

---

## Files

- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`
- Add/modify tests:
  - `scripts/pinescript/tests/test_snd_state_machine_contract_static.py`
  - `scripts/pinescript/tests/test_snd_liquidity_anchor_mitigation_static.py`
  - `scripts/pinescript/tests/test_snd_zone_inspector_static.py`
  - `scripts/pinescript/tests/test_snd_replay_determinism_static.py`

## Task 1: Canonical State And Reason Contract

- [ ] Add static test requiring all state/reason constants in `SND_Strategy.pine`.

Run:
```bash
python3 scripts/pinescript/tests/test_snd_state_machine_contract_static.py
```

Expected first run: FAIL until constants/helpers exist.

- [ ] Add constants:
```pine
const string ZSTATE_CANDIDATE = "Candidate"
const string ZSTATE_ACTIVE = "Active"
const string ZSTATE_LEFT_ZONE = "LeftZone"
const string ZSTATE_LIQ_FOUND = "LiquidityFound"
const string ZSTATE_LIQ_VALID = "LiquidityValid"
const string ZSTATE_LIQ_SWEPT = "LiquiditySwept"
const string ZSTATE_TARGET_BOS = "TargetBOSSwept"
const string ZSTATE_READY = "ReadyForMitigation"
const string ZSTATE_USED = "MitigatedUsed"
const string ZSTATE_INVALID = "Invalid"
const string ZSTATE_EXPIRED = "Expired"

const string REASON_CREATED = "CREATED"
const string REASON_REJECTED_NO_DISPLACEMENT = "REJECTED_NO_DISPLACEMENT"
const string REASON_REJECTED_CHOPPY_BASE = "REJECTED_CHOPPY_BASE"
const string REASON_REJECTED_CONTAMINATED_ORIGIN = "REJECTED_CONTAMINATED_ORIGIN"
const string REASON_REJECTED_DUPLICATE = "REJECTED_DUPLICATE"
const string REASON_LIQ_FOUND = "LIQ_FOUND"
const string REASON_LIQ_VALID = "LIQ_VALID"
const string REASON_LIQ_INVALID_INSIDE_ZONE = "LIQ_INVALID_INSIDE_ZONE"
const string REASON_LIQ_INVALID_TOO_FAR = "LIQ_INVALID_TOO_FAR"
const string REASON_LIQ_INVALID_NOT_STRONG = "LIQ_INVALID_NOT_STRONG"
const string REASON_INDUCEMENT_SWEPT = "INDUCEMENT_SWEPT"
const string REASON_TARGET_BOS_SWEPT = "TARGET_BOS_SWEPT"
const string REASON_READY_FOR_MITIGATION = "READY_FOR_MITIGATION"
const string REASON_INVALID_RETURN_BEFORE_PROOF = "INVALID_RETURN_BEFORE_PROOF"
const string REASON_INVALID_CLOSE_INSIDE_ZONE = "INVALID_CLOSE_INSIDE_ZONE"
const string REASON_INVALID_DISTAL_CLOSE = "INVALID_DISTAL_CLOSE"
const string REASON_INVALID_EARLY_RETURN = "INVALID_EARLY_RETURN"
const string REASON_MITIGATED_USED_FOR_ENTRY = "MITIGATED_USED_FOR_ENTRY"
const string REASON_EXPIRED = "EXPIRED"
const string REASON_PRUNED = "PRUNED"
```

- [ ] Add helper functions:
```pine
zone_state(Core.Zone z) =>
    if z.mitigated or not na(z.lastEntryBar)
        ZSTATE_USED
    else if not z.active and zone_inactive_reason(z) == REASON_EXPIRED
        ZSTATE_EXPIRED
    else if not z.active
        ZSTATE_INVALID
    else if z.targetSwept
        ZSTATE_READY
    else if z.liquiditySwept
        ZSTATE_LIQ_SWEPT
    else if z.liquidityValid
        ZSTATE_LIQ_VALID
    else if not na(z.liquidityPrice) or not na(z.liqLowPrice) or not na(z.liqHighPrice)
        ZSTATE_LIQ_FOUND
    else if z.leftZone
        ZSTATE_LEFT_ZONE
    else
        ZSTATE_ACTIVE
```

- [ ] Run:
```bash
python3 scripts/pinescript/tests/test_snd_state_machine_contract_static.py
```

Expected: PASS.

## Task 2: Candidate Detector And Rejection Reasons

- [ ] Extend static test to require `mark_zone_rejected(reason)` usage for duplicate, no displacement, choppy base, contaminated origin, and oversized base rejection.
- [ ] Update `createZone()` and `maybeCreateDetectedZone()` so candidates can be rejected with canonical reasons before creation.
- [ ] Preserve base-time duplicate guard and replay rescan order.
- [ ] Run:
```bash
python3 scripts/pinescript/tests/test_snd_state_machine_contract_static.py
python3 scripts/pinescript/tests/test_snd_replay_determinism_static.py
python3 scripts/pinescript/tests/test_snd_continuation_zones_static.py
```

Expected: all PASS.

## Task 3: Zone Lab Candidate Visibility

- [ ] Add Zone Lab table/visual rows for `State`, `Reason`, `Candidate/Active/Invalid`, `Inducement`, `Target`, `Return`.
- [ ] Clean mode must show only `zone_is_live(z) and not zone_is_invalid_or_rejected(z) and not z.mitigated and na(z.lastEntryBar)`.
- [ ] Zone Lab must show candidates/rejections when `show_candidate_zones` or `show_invalid_zones` is enabled.
- [ ] Run:
```bash
python3 scripts/pinescript/tests/test_snd_zone_inspector_static.py
python3 scripts/pinescript/tests/test_snd_state_machine_contract_static.py
```

Expected: all PASS.

## Task 4: Liquidity Proof Engine

- [ ] Replace old `WAITING_*` and `REJECT_LIQ_*` strings with canonical `LIQ_*` reasons.
- [ ] Demand liquidity must only accept `pLow > z.top`.
- [ ] Supply liquidity must only accept `pHigh < z.bottom`.
- [ ] Choose closest valid liquidity; tie goes to more recent pivot.
- [ ] Target/BOS sweep cannot be set before inducement sweep.
- [ ] Run:
```bash
python3 scripts/pinescript/tests/test_snd_liquidity_anchor_mitigation_static.py
python3 scripts/pinescript/tests/test_snd_state_machine_contract_static.py
```

Expected: all PASS.

## Task 5: Return And Mitigation Engine

- [ ] Demand ready return requires wick/touch demand and close above demand top.
- [ ] Supply ready return requires wick/touch supply and close below supply bottom.
- [ ] Return before liquidity proof sets `INVALID_RETURN_BEFORE_PROOF`.
- [ ] Close inside zone sets `INVALID_CLOSE_INSIDE_ZONE`.
- [ ] Close through distal side sets `INVALID_DISTAL_CLOSE`.
- [ ] Used zones set `MITIGATED_USED_FOR_ENTRY` and cannot trade again.
- [ ] Run:
```bash
python3 scripts/pinescript/tests/test_snd_zone_rules_static.py
python3 scripts/pinescript/tests/test_snd_state_machine_contract_static.py
```

Expected: all PASS.

## Task 6: Entry Reconnection Check

- [ ] Do not edit risk, SL/TP, webhooks, alerts, or order execution blocks.
- [ ] Only replace entry preconditions with the state-machine readiness predicate.
- [ ] Run all Pine static tests:
```bash
for t in scripts/pinescript/tests/test_snd_*_static.py; do python3 "$t"; done
git diff --check -- scripts/pinescript/strategies/SND_Strategy.pine scripts/pinescript/tests
```

Expected: all PASS.

## Self-Review

- Spec coverage: tasks cover detector, Zone Lab, liquidity proof, return/mitigation, replay, duplicate base time, and entry reconnection.
- Deliberate non-goal: no risk, SL/TP, webhook, alert, or order execution changes.
- Known limitation: TradingView compilation/runtime must be verified in TradingView after static tests because Pine limits are not locally executable.
