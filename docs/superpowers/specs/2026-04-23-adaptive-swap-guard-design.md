# DEV-201 Adaptive Swap Guard Recovery Design

## Summary

Replace the current timer-only post-rollover behavior with an adaptive swap guard that keeps symbols blocked after rollover until live broker spread data shows market conditions have normalized. The guard should still block before swap, still support pre-swap position closing, and remain fail-safe when quote data is unavailable.

## Goals

- Keep the existing pre-swap blackout behavior.
- Prevent symbols from reopening immediately after a fixed post-swap timer expires.
- Reopen symbols only after their own spread recovers to a safe level.
- Track recovery per symbol so one unhealthy market does not block all instruments.
- Fail safe when quote data is missing or unreliable.
- Preserve clear audit and UI reasons for each swap-related rejection state.

## Non-Goals

- No changes to core trading strategy or setup selection logic.
- No redesign of the worker pipeline outside the swap-guard path.
- No dependency on true order-book depth or Level 2 liquidity for the first rollout.
- No requirement to build a streaming quote cache in this change.
- No changes to `src/logic.py` trading-path behavior.

## Existing Context

The current implementation lives in:

1. `src/core/guard_rails/swap_guard.py`
2. `src/worker.py`
3. `tests/test_swap_guard.py`

Today the guard blocks signals during a fixed blackout window:

- start: `swap_time - swap_close_before_min`
- end: `swap_time + swap_block_after_min`

Once the fixed window ends, new entries are allowed again. This is simple, but it assumes rollover conditions recover on schedule. In practice, spreads can remain distorted beyond the configured timer, especially on symbols such as gold or around broker-specific rollover conditions.

The worker also initializes a `SwapScheduler` that closes open positions during the pre-swap close window. That scheduler should remain focused on position-closing behavior and should not be the source of truth for when entry blocking ends.

## Problem Statement

The danger around rollover is not the clock alone. The real risk is abnormal spread and weak tradability after swap. A fixed post-swap timer can reopen trading while spreads are still too wide, which makes the guard feel safe in configuration but unsafe in live behavior.

## Recommended Approach

Use `time floor + spread recovery + hard max cap`.

The guard should continue to enter blackout before swap, remain blocked for a minimum post-swap floor, then switch to a recovery phase where each symbol is checked against live spread thresholds. A symbol should reopen only after it records enough consecutive healthy spread checks within a bounded recovery window. If quote data is missing or never recovers, the guard should stay fail-safe until a hard maximum block cap is reached.

This is preferred over:

- `longer fixed timer`, because it is still a guess
- `block until next day`, because it is safe but overly blunt and likely to discard valid setups after rollover settles

## Proposed System Shape

Keep `SwapGuard` as the policy owner and extend it to manage three phases:

1. `pre_swap_blackout`
2. `post_swap_min_floor`
3. `spread_recovery_check`

Keep `SwapScheduler` for pre-swap closing only.

Suggested guard responsibilities:

- calculate whether the system is before swap, inside the minimum post-swap floor, or inside the adaptive recovery phase
- fetch or receive live spread data for the signal symbol
- maintain in-memory per-symbol recovery state
- decide whether to reject or allow the signal
- emit explicit reason codes for logging, audit, and UI

Suggested per-symbol recovery state:

- `blocked_since`
- `last_spread`
- `healthy_check_count`
- `last_healthy_at`
- `last_reason`
- `released_at`

This state should live in memory in the worker process for the first rollout. Persistence is not required because the recovery problem is intraday and bounded around rollover.

## Data Source Strategy

### Spread

Use the existing broker adapter capability to read live bid/ask and compute spread from MetaApi. This is already closer to the real failure mode than a timer.

### Liquidity

Do not require true depth or Level 2 liquidity for v1. The current codebase has a `liquidity_scorer`, but it uses contextual proxies such as session and RVOL rather than broker depth. For this feature, spread is the primary operational signal for market recovery.

### Quote Freshness

For the first rollout, a successful live spread fetch is the freshness signal. Missing quotes after swap should keep the symbol blocked until either healthy quotes return or the hard max cap is reached.

## Decision Flow

For each incoming signal:

1. If current time is before swap inside the pre-swap blackout window, reject with `SWAP_PRE_BLACKOUT`.
2. If current time is after swap but still within the minimum post-swap floor, reject with `SWAP_POST_MIN_FLOOR`.
3. If current time is in the adaptive recovery phase:
   - fetch spread for the signal symbol
   - if spread fetch fails, reject with `SWAP_QUOTES_UNAVAILABLE`
   - if spread is above threshold, reject with `SWAP_SPREAD_STILL_WIDE` and reset the healthy counter as needed
   - if spread is at or below threshold, increment the healthy counter
4. Allow the symbol only after it records the configured number of healthy checks within the configured recovery window.
5. If the hard max cap is reached, release the block with a loud warning and record `SWAP_MAX_CAP_RELEASE`.

The recovery decision should be per symbol, not global. `GBPUSD` may recover earlier than `XAUUSD`, and the guard should reflect that.

## Configuration

Keep:

- `swap_time`
- `swap_timezone`
- `swap_close_before_min`

Replace the fixed post-swap unblock model with:

- `swap_min_block_after_min`
- `swap_max_block_after_min`
- `swap_recovery_consecutive_checks`
- `swap_recovery_window_seconds`

Add spread-threshold configuration as asset-class defaults plus optional symbol overrides. The concrete settings shape should support both:

1. asset-class default thresholds
2. exact symbol overrides that take precedence

This keeps configuration manageable while allowing stricter thresholds for symbols like `XAUUSD`.

## Threshold Strategy

Thresholds should be explicit and conservative for the first rollout.

Recommended order of precedence:

1. exact symbol override
2. asset-class default
3. guarded fallback default

Suggested asset classes:

- FX majors
- JPY pairs
- gold
- indices if needed later

The threshold unit should be defined clearly in configuration and logs. The implementation may store thresholds in price terms if that matches the adapter output most directly, but the user-facing description should remain understandable.

## Failure Handling

After swap, missing quote data must not silently reopen trading.

Behavior:

- quote fetch failure: keep symbol blocked
- malformed quote or negative spread: keep symbol blocked and log warning
- recovery window timeout after partial healthy checks: reset healthy counter
- hard max cap reached with no usable quotes: release block, log warning, and emit explicit release reason

This design intentionally favors false negatives over false positives around rollover.

## Integration Points

Primary change points:

- `src/core/guard_rails/swap_guard.py`
  - extend guard phases
  - add per-symbol recovery state
  - integrate spread-aware release logic
- `src/worker.py`
  - pass adapter access needed for spread checks
  - preserve pre-swap scheduler behavior
  - avoid using scheduler state to control post-swap reopening
- `config/settings.py`
  - replace fixed post-swap timer configuration with adaptive recovery settings
- `tests/test_swap_guard.py`
  - expand test coverage for the new decision flow

No changes should be made to `src/logic.py` or core strategy logic.

## Testing

Add or update tests for:

- pre-swap rejection
- minimum post-swap floor rejection
- symbol-specific recovery progression
- healthy spread counted across consecutive checks
- healthy counter reset after a bad spread
- recovery window expiration resetting partial progress
- quote fetch failure fail-safe behavior
- hard max cap release behavior
- independent recovery between two symbols

Where practical, keep time behavior deterministic by overriding the guard clock in tests.

## Rollout Defaults

Recommended initial defaults:

- `swap_close_before_min=15`
- `swap_min_block_after_min=45`
- `swap_max_block_after_min=240`
- `swap_recovery_consecutive_checks=3`
- `swap_recovery_window_seconds=300`

Threshold defaults should be conservative and tuned separately for:

- major FX
- JPY pairs
- gold

## Observability

Use explicit reason codes so operators can distinguish between:

- `SWAP_PRE_BLACKOUT`
- `SWAP_POST_MIN_FLOOR`
- `SWAP_QUOTES_UNAVAILABLE`
- `SWAP_SPREAD_STILL_WIDE`
- `SWAP_RECOVERED`
- `SWAP_MAX_CAP_RELEASE`

These reasons should be visible in logs and any existing guard/audit paths that currently surface `swap_rejected`.

## Future Improvement

If polling spread from the broker becomes noisy or expensive, add a lightweight quote cache fed by the existing MetaApi streaming path or another small market-data cache. That should be a follow-up optimization, not a requirement for the first safe rollout.
