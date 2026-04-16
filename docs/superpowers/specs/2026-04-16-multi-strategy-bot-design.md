# Multi-Strategy Bot Design

Date: 2026-04-16
Status: Approved for planning

## Summary

Upgrade the trading system from a single globally active strategy model to a multi-strategy architecture where every alert, guard decision, trade, optimization run, notification, and UI view is strategy-aware.

The system will keep a single webhook channel from TradingView, but every Pine alert must include `strategy_id` and `strategy_version`. The backend will resolve strategy configuration from that identity, reject unknown or inactive strategies, and keep strategy context attached all the way through risk, execution, analytics, and UI rendering.

The product direction is strategy-first automation with isolated observability. A strategy should be measurable, promotable, and reversible without mixing its identity or results with any other strategy.

## Goals

- Support multiple mechanical strategies in one system without losing attribution.
- Keep one shared TradingView alert/webhook channel while making every alert strategy-aware.
- Resolve risk, routing, notifications, analytics, and pages per strategy.
- Reject unknown, inactive, or malformed strategy alerts instead of falling back to a default.
- Keep strategy versions traceable so optimizer results and live trades can be compared honestly.
- Allow one live primary strategy while newer strategies remain paper or shadow-only.

## Non-Goals

- Building a portfolio allocator or capital scheduler in the first version.
- Letting the backend infer strategy identity from symbols, sessions, or setup shape.
- Auto-promoting optimizer results directly into live trading.
- Merging multiple new strategies into one real account before each proves itself independently.
- Rewriting core trade execution logic beyond what is required to pass strategy context through the system.

## Product Direction

The system should treat strategy identity as a first-class concept, not an optional label.

This means:

- Strategy identity is mandatory at signal ingestion.
- Strategy configuration is loaded explicitly from alert identity, not from a global active strategy.
- Risk decisions are evaluated in two layers:
  - strategy-level rules
  - account-level or global protections
- Notifications and UI always show which strategy and version produced a result.
- Optimizer and backtest outputs never mix results across strategies.

The intent is to let the operator become a bot supervisor rather than a discretionary trader. The operator should be able to answer:

- Which strategy generated this alert?
- Which strategy version was live?
- Which strategy is profitable over time?
- Which strategy caused drawdown?
- Which strategy is still only in paper or shadow mode?

## Strategy Identity Model

Every TradingView alert on the shared webhook channel must include:

- `strategy_id`
- `strategy_version`
- `symbol`
- `side`
- `entry`
- `sl`
- `tp`
- `size`

Existing optional fields such as `rr_ratio`, `zone_id`, `signal_time`, `bar_time`, and `run_mode` remain supported.

Recommended payload shape:

```json
{
  "strategy_id": "liq_sd_v1",
  "strategy_version": "2026-04-16",
  "symbol": "EURUSD",
  "side": "buy",
  "entry": 1.0825,
  "sl": 1.0790,
  "tp": 1.0895,
  "size": 1.0,
  "rr_ratio": 2.1
}
```

Rules:

- `strategy_id` is required for all entry alerts.
- `strategy_version` is required for all entry alerts.
- Unknown `strategy_id` is hard rejected.
- Inactive strategy is hard rejected.
- Missing version is hard rejected.
- There is no fallback to a globally active strategy.

## Strategy Entity

Each strategy should exist as its own first-class record with:

- stable `strategy_id` or slug
- human-readable name
- integer or semantic version
- active or inactive state
- description
- config blob
- signal filters
- risk preset
- execution routing rules
- notification preferences
- metadata about promotion state such as paper, shadow, or live

The current `strategy-as-data` model in `src/services/strategy_config.py` is the right foundation, but it must evolve from "single active strategy" into "explicitly resolved strategy by id."

## Alert Ingestion And Validation

The webhook/API path should:

1. Validate alert shape, including `strategy_id` and `strategy_version`.
2. Load the matching strategy record by `strategy_id`.
3. Reject if the strategy is missing, inactive, or version-mismatched.
4. Stamp strategy context onto the saved signal payload.

Strategy context that should be carried forward:

- `strategy_id`
- `strategy_version`
- strategy name
- strategy config id or config snapshot reference
- strategy routing mode

This guarantees that downstream services do not need to guess strategy identity later.

## Execution And Risk Flow

The worker path should become strategy-aware instead of depending on one global active strategy.

Recommended flow:

1. Signal arrives with `strategy_id` and `strategy_version`.
2. Backend resolves the matching strategy configuration.
3. Signal is validated against that strategy's symbol and session filters.
4. Worker runs strategy-level guard checks using strategy-specific settings.
5. Worker also runs account-level and global protections shared across the account.
6. If both layers pass, execution routing uses the strategy's routing rules.
7. Every guard decision, execution result, and failure is saved with strategy identity attached.

Risk should be evaluated in two layers:

### Strategy-Level Risk

Per strategy:

- allowed symbols
- allowed sessions
- minimum RR
- risk percent
- daily trade limits
- evaluation mode settings
- notification preferences
- paper or live routing

### Account-Level Or Global Risk

Shared protections:

- max total positions
- kill switch
- daily loss protection
- correlation limits
- hard evaluation safety rules

Every trade must pass both the strategy-level checks and the account-level protections.

## Routing Model

Each strategy should declare its own execution routing rules.

Examples:

- `liq_sd_v1` routes to live Alpha evaluation account
- `breakout_v1` routes to paper only
- `mean_reversion_v1` routes to shadow mode and never executes

This lets the system support:

- one primary live strategy
- additional paper or shadow strategies
- later promotion without changing the alert channel

The first version should support one strategy per account or profile for live trading. Shared-capital portfolio coordination should wait until each strategy proves itself independently.

## Optimizer And Backtest Model

Optimizer and backtest results must be isolated per strategy and per version.

Each optimization run should store:

- `strategy_id`
- `strategy_version`
- date range
- tested symbols
- tested sessions
- candidate parameters
- summary metrics
- recommendation state

Each backtest should be versioned. If rules change materially, it becomes a new strategy version rather than an overwrite of the previous result set.

The optimizer should produce candidate configurations, not silent production updates.

Recommended promotion flow:

1. optimize candidate for one strategy
2. compare candidate to current live version
3. paper or shadow test candidate
4. explicitly promote candidate to a new active version

This keeps the live bot stable and prevents optimizer churn from turning into emotion by code.

## Metrics And Analytics

The system should track at minimum per strategy and per version:

- total trades
- win rate
- average win
- average loss
- expectancy
- profit factor
- max drawdown
- longest losing streak
- pnl by pair
- pnl by session
- rejected signal count
- guard rejection reasons

Analytics should support:

- all strategies
- one strategy
- one strategy version
- compare multiple strategies
- compare versions of the same strategy

This is required to answer whether the strategy is working and whether a pair is working inside that strategy.

## Notifications

All alerts can stay in one channel, but every notification must include strategy identity.

Each signal, trade, rejection, and operational alert should show:

- `strategy_id`
- `strategy_version`
- symbol
- side
- account or profile
- status
- reason if blocked

Examples:

- `[liq_sd_v1@2026-04-16] EURUSD BUY accepted`
- `[breakout_v1@2026-05-01] NAS100 rejected: RR below minimum`

Notification event types should include:

- signal received
- trade accepted
- trade rejected
- execution failed
- guard blocked
- kill switch triggered

The one shared channel remains operationally simple while still preserving strategy attribution.

## UI And Pages

Existing pages should become strategy-aware rather than creating a separate app surface.

At minimum, the following pages need strategy columns and filters:

- signals
- trades or positions
- analytics
- risk or monitoring
- strategy management

Recommended UI behaviors:

- strategy filter on every trading page
- strategy and version columns wherever signals or trades are listed
- strategy detail page with version history
- compare strategies inside analytics
- compare versions within one strategy
- blocked trades and guard reasons grouped by strategy

The UI should avoid showing only a blended "system performance" view without strategy segmentation.

## Notification And UI Principles

- one alert channel
- one shared application
- strategy identity visible everywhere
- all pages filterable by strategy
- every result attributable to one strategy and one version

## Rollout Plan

### Phase 1: Strategy Identity

- add `strategy_id` and `strategy_version` to Pine alerts
- add validation for these fields in webhook ingestion
- persist strategy identity on signals and trades

### Phase 2: Strategy Resolution

- resolve strategy config from `strategy_id`
- reject unknown or inactive strategies
- remove fallback to one global active strategy for signal processing

### Phase 3: Strategy-Specific Routing And Risk

- make routing, filters, and risk use resolved strategy config
- keep account-level protections as a second layer

### Phase 4: Notifications And Pages

- add strategy context to notifications
- add strategy columns and filters to the existing app pages

### Phase 5: Optimizer And Backtest Separation

- store optimizer runs per strategy and version
- store backtest results per strategy and version
- support manual promotion to a new active version

### Phase 6: Shadow Strategy Support

- allow new strategies to run in alert-only, paper-only, or shadow mode
- promote only after evidence

## Safety Rules

The first version should enforce these safety rules:

- unknown strategy = reject
- inactive strategy = reject
- missing version = reject
- no fallback to default strategy
- every trade must pass both strategy-level and account-level protections
- new strategy starts in paper or shadow mode only
- each strategy version change is explicit and traceable
- optimizer output never auto-promotes to live
- multiple new strategies do not share real capital at first

## Testing Requirements

Implementation should verify these cases:

1. A signal with valid `strategy_id` and `strategy_version` resolves the right strategy config.
2. A signal with unknown `strategy_id` is rejected.
3. A signal for an inactive strategy is rejected.
4. Strategy-specific symbol and session filters are enforced.
5. Strategy-specific routing can send one strategy to live and another to paper.
6. Notifications include strategy identity for accepted and rejected trades.
7. UI pages can filter and compare by strategy and version.
8. Optimizer runs are isolated per strategy and version.
9. Historical trades retain strategy identity after config changes.

## Risks

- If TradingView alerts omit strategy identity, valid trading opportunities will be rejected by design.
- If versioning is handled loosely, analytics can become misleading even with `strategy_id` present.
- If the UI shows only blended totals, operators may draw the wrong conclusions.
- If multiple strategies are allowed to share real capital too early, attribution and drawdown diagnosis become difficult.
- If optimizer outputs are allowed to mutate live configs automatically, the operator will lose trust in the bot.

## Recommended Implementation Scope

The implementation should stay focused on making strategy identity first-class across the existing system.

Recommended scope:

- require `strategy_id` and `strategy_version` in alert ingestion
- resolve strategy config by id instead of relying on one active strategy
- propagate strategy identity through worker, guards, execution, analytics, and notifications
- add strategy and version columns and filters to core UI pages
- isolate optimizer and backtest data by strategy and version

Deferred scope:

- portfolio allocator
- cross-strategy capital scheduler
- automatic promotion engine
- strategy inference in the backend

## Decision

Proceed with a strategy-first multi-strategy architecture:

- one shared webhook channel
- Pine supplies `strategy_id` and `strategy_version`
- backend resolves and validates the strategy explicitly
- risk, routing, analytics, notifications, and pages become strategy-aware
- optimizer and backtests remain isolated by strategy and version
- one primary live strategy is supported first, with additional strategies in paper or shadow mode until proven
