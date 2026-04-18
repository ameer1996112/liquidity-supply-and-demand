# DEV-138 Prop-Firm Survival Optimizer Design

## Summary

Upgrade the current optimizer from a single-pass parameter searcher into a prop-firm survival optimizer that selects pair configurations and portfolio weights based on recent unseen performance, execution realism, and combined multi-pair drawdown. The upgraded system must also expose a richer analyst UI so operators can understand not only which pairs were approved, but why.

The design target is not perfect prediction. The design target is to make evaluation failure materially harder by preferring strategies and pair combinations that survive current conditions, realistic execution friction, and portfolio-level stress.

## Goals

- Optimize for passing prop-firm evaluation conditions, not maximum backtest profit.
- Promote the latest unseen forward window to the highest-priority approval gate.
- Enforce pair-level and portfolio-level internal drawdown limits tighter than the prop-firm hard limits.
- Add execution realism through spread and slippage stress tests.
- Add market-context awareness through trend and news modes.
- Save all optimizer outputs so they can be queried, compared, reused, and re-ranked later.
- Upgrade the optimizer UI into an analyst workspace with drill-downs, comparisons, and portfolio reasoning.

## Non-Goals

- Guaranteeing a 100 percent pass rate.
- Changing strategy entry logic directly.
- Replacing the optimizer runner architecture in one step.
- Requiring paid market-data or news services for the first implementation.

## Product Principles

- Survival first, profit second.
- Recent unseen data matters more than historical fit.
- Portfolio safety matters more than any single pair score.
- Stress-tested results matter more than clean backtest winners.
- Explainability matters; every optimizer decision should have a visible reason.

## Current Problems

### 1. The optimizer over-values historical winners

The current Bayesian flow can find parameter sets that perform well on the data used during optimization but degrade on newer data. This is dangerous for prop-firm evaluation where recent drawdown behavior matters more than historical peak profit.

### 2. Pair-level results are insufficient

Even if each pair looks safe on its own, a combined portfolio can still violate drawdown limits when correlated losses cluster in the same session, news event, or volatility regime.

### 3. Execution assumptions are too clean

Results are currently too vulnerable to spread expansion, slippage, and poor fills. That makes the optimizer optimistic relative to live evaluation conditions.

### 4. The UI does not support analyst-style decision making

Operators need a workspace that shows approval reasons, stress outcomes, and portfolio tradeoffs. A thin run-status UI is not enough for this workflow.

## Proposed System

The upgraded optimizer will become a staged approval pipeline:

1. Bayesian candidate search per pair on train data.
2. Validation on unseen data without re-tuning.
3. Forward approval on the latest unseen data without re-tuning.
4. Stress testing for execution, trend mode, and news mode.
5. Portfolio simulation across approved survivors on a shared timeline.
6. Weight allocation to keep the combined portfolio under internal risk caps.
7. Final pair classification into `PASS`, `REDUCE_RISK`, or `REJECT`.

## Internal Risk Targets

The prop-firm hard limits remain external constraints. The optimizer will use stricter internal safety buffers.

### Prop-Firm Hard Limits

- total drawdown: typically `8%` to `10%`
- daily drawdown: `5%`

### Optimizer Internal Limits

Use tighter gates for approval:

- pair max drawdown: `5%` if optimizing for an `8%` firm, `6%` if optimizing for a `10%` firm
- pair max daily drawdown: `2.5%` to `3%`
- portfolio max drawdown: `6%`
- portfolio max daily drawdown: `3%`

These are the approval thresholds, not just score inputs.

## Time Windows

### Initial Split

The first implementation should use a strict three-way chronological split:

- `train`: oldest `60%`
- `validation`: next `20%`
- `forward`: latest `20%`

No re-optimization is allowed on validation or forward windows.

### Future Upgrade

After the first version is stable, add rolling walk-forward windows. The initial release should keep the implementation simpler and reliable.

## Candidate Search

### Search Method

Keep Bayesian optimization as the primary search method.

### Search Scope

The search must cover:

- strategy parameters already supported by the optimizer
- trend mode candidate
- news mode candidate
- execution stress profile selection only if performance is acceptable under the normal profile first

### Trend Candidates

Use these initial modes:

- `none`
- `ema200_aligned`
- `ema200_soft_bias`

EMA200 is preferred over SMA200 for the first implementation because it reacts faster and better suits evaluation protection.

## Hard Approval Gates

Every candidate must pass these gates on the latest `forward` window:

- `max_drawdown_pct <= configured_pair_dd_limit`
- `max_daily_loss_pct <= configured_pair_daily_dd_limit`
- `net_profit > 0`
- `profit_factor >= 1.10`
- `total_trades >= 15`

If any gate fails, the candidate is rejected before any ranking.

## Stress Tests

Surviving candidates must be re-tested under multiple adverse conditions.

### Execution Stress

Run at least:

- baseline spread
- `+25%` spread
- `+50%` spread
- spread plus slippage

If a candidate breaks internal drawdown limits under stress, it cannot be promoted to `PASS`.

### News Stress

Use Trading Economics as the initial non-paid news source and cache events locally.

The initial news mode should support:

- `none`
- `high_impact_blackout_30m`

The blackout mode blocks entries `30 minutes before` and `30 minutes after` high-impact events relevant to the pair currencies.

### Trend Stress

Compare the chosen candidate against all supported trend modes so the system can prove that the selected trend behavior actually improves survival rather than looking good by chance.

### Regime and Session Reporting

The first version should report regime and session breakdowns even if they do not become hard gates yet:

- London
- New York
- overlap
- low-liquidity hours
- trending periods
- ranging periods
- high-volatility periods
- low-volatility periods

This gives operators decision context and prepares the next upgrade path.

## Robustness Test

The optimizer must prefer parameter neighborhoods, not magic single points.

For the first implementation:

- retain the top candidate plus nearby parameter variants
- score how much performance collapses when parameters move slightly
- penalize candidates where neighbors fail badly

This feeds a `robustness_score` rather than acting as a hard gate in v1.

## Scoring Model

Scoring only applies to candidates that already passed the forward gates.

### Pair Score

```text
pair_score =
  0.35 * forward_score
+ 0.20 * validation_score
+ 0.15 * stress_score
+ 0.15 * robustness_score
+ 0.15 * execution_score
```

### Score Intent

- `forward_score`: newest unseen survival quality, highest importance
- `validation_score`: confirms the result was not a one-window fluke
- `stress_score`: resilience to spread, slippage, news, and trend-mode differences
- `robustness_score`: nearby parameters also behave acceptably
- `execution_score`: smoothness metrics such as lower worst-day loss and more stable drawdown

Profit remains meaningful, but only after survival and stability are satisfied.

## Pair Decision Outcomes

Each pair receives one final state:

- `PASS`
- `REDUCE_RISK`
- `REJECT`

### PASS

Use when the candidate:

- passes forward hard gates
- remains within stress tolerances
- does not threaten portfolio caps at its assigned weight

### REDUCE_RISK

Use when the candidate:

- passes forward gates
- remains tradable
- but approaches drawdown thresholds under stress or portfolio aggregation

### REJECT

Use when the candidate:

- fails forward gates
- fails stress
- or cannot fit safely inside the portfolio risk budget

## Portfolio Construction

### Why It Exists

The optimizer must evaluate the full pair set together because correlation can cause evaluation failure even when single-pair results look acceptable.

### Portfolio Simulation Inputs

For the approved survivors, build a shared timeline and compute:

- combined equity curve
- combined max drawdown
- combined daily drawdown
- worst day
- losing streak clusters
- session overlap risk
- correlated stress around news windows

### Weighting Strategy

Start with these default weights:

- `PASS`: `1.0`
- `REDUCE_RISK`: `0.5`
- `REJECT`: `0.0`

Then iteratively reduce or remove pairs until:

- combined max drawdown is within the internal portfolio limit
- combined daily drawdown is within the internal portfolio limit

This first version can use a greedy risk allocator:

1. sort surviving pairs by safety-first rank
2. add them one by one
3. reduce weight when a pair pushes portfolio risk too high
4. remove the pair if a reduced weight still breaks portfolio limits

## Data Sources

### News Source Recommendation

Use Trading Economics for v1 because it provides an official economic calendar API and documented guest-style access examples. Cache all fetched data locally to avoid runtime dependency during optimizer scoring.

Relevant docs:

- https://docs.tradingeconomics.com/economic_calendar/snapshot/
- https://docs.tradingeconomics.com/economic_calendar/
- https://docs.tradingeconomics.com/economic_calendar/country/

### Spread Source Recommendation

Do not block the feature on perfect broker-grade spread history.

For v1:

- store a baseline spread per symbol
- create stressed variants at `1.25x` and `1.50x`
- add a fixed slippage penalty per side where appropriate

For later versions:

- ingest sampled spread history by broker, symbol, and session

## Persistence and Reuse

The optimizer must save all meaningful outputs, not only the final winner.

### Source of Truth

Use Supabase as the primary structured store.

### Artifacts

Keep JSON snapshots on disk as portable run artifacts and debugging backups.

### Data to Save

- run metadata
- pair summaries
- all Bayesian trials
- stress-test outputs
- portfolio results
- approval reasons
- selected weights
- news and spread assumptions used during the run

## Proposed Data Model

The current `optimizer_runs` and `optimizer_run_results` remain, but they need richer usage and companion tables.

### Existing Tables

- `optimizer_runs`
- `optimizer_run_results`
- `optimizer_run_events`

### New Tables

- `optimizer_run_trials`
  Stores every Bayesian trial per pair.
- `optimizer_run_stress_tests`
  Stores spread, slippage, news, and trend stress outcomes.
- `optimizer_portfolio_results`
  Stores combined portfolio simulation outputs.
- `news_events`
  Stores cached normalized economic calendar events.
- `spread_profiles`
  Stores baseline and stressed spread settings by symbol and broker.

### Optional Derived Table

- `optimizer_pair_approvals`
  Stores reusable approved pair configurations across runs.

## Backend Architecture

### Core Responsibilities

- runner orchestrates staged evaluation
- scoring service computes survival and rank signals
- stress service evaluates execution, trend, and news scenarios
- portfolio service simulates combined pair behavior and suggests risk weights
- persistence layer stores all artifacts and summaries

### Initial File Targets

The first implementation should start in these existing files:

- `scripts/optimizer/optimizer.py`
  Add staged evaluation flow, hard gates, and richer candidate outcomes.
- `src/services/optimizer_run_service.py`
  Persist trials, stress outputs, and portfolio summaries.
- `src/api_optimizer_runs.py`
  Expose richer run results to the frontend.

New supporting modules will likely be needed for:

- news ingestion
- spread profiles
- scoring
- portfolio simulation
- trial persistence

## UI Design

The optimizer UI must become an analyst workspace rather than a thin run launcher.

### UX Direction

Choose an advanced analyst UI with strong top-level summaries and deep drill-down details on the same workspace.

### Layout Zones

#### 1. Run Config

Controls for:

- selected pairs
- optimizer mode
- pair internal drawdown cap
- portfolio internal drawdown cap
- train / validation / forward split
- spread stress mode
- slippage mode
- trend mode candidates
- news mode

#### 2. Portfolio Overview

High-importance summary area showing:

- combined max drawdown
- combined daily drawdown
- worst day
- approved pair count
- reduced-risk pair count
- rejected pair count
- recommended portfolio weights
- combined equity curve

#### 3. Pair Analysis Grid

Sortable main workspace grid showing:

- pair
- status
- risk weight
- forward profit
- forward max drawdown
- forward daily drawdown
- stress drawdown
- profit factor
- chosen trend mode
- chosen news mode
- primary reason

#### 4. Pair Drill-Down

Selected pair panel showing:

- chosen parameters
- validation vs forward comparison
- spread and slippage stress results
- trend mode comparison
- news mode comparison
- robustness analysis
- approval explanation

#### 5. Run Comparison

Historical comparisons between saved runs showing:

- differences in approved pairs
- metric changes
- changed weights
- degradation or improvement signals

### UI Feel

The interface should feel like a serious analysis workstation:

- clear status colors
- dense but readable metrics
- fast sorting and filtering
- charts where they aid judgment
- explanations beside decisions rather than buried in logs

## API Requirements

The optimizer API must expose:

- run summaries
- per-pair final outcomes
- raw and aggregated stress results
- portfolio summary
- drill-down detail for a selected pair
- run comparison endpoints or client-queryable history

## Testing Strategy

### Backend

- test forward hard-gate rejection logic
- test stress downgrade logic
- test portfolio allocator behavior
- test persistence of trials, stress outputs, and portfolio results
- test news-event mapping from currencies to symbols
- test baseline and stressed spread application

### Frontend

- test analyst workspace rendering for populated runs
- test status colors and decision explanations
- test pair drill-down state handling
- test history comparisons

### Regression

- preserve existing optimizer-run lifecycle behavior
- preserve current run queueing, status transitions, and event streaming

## Rollout Plan

### Phase 1

- add persistence for trials, stress tests, and portfolio summaries
- add forward-gated pair decisions
- add spread stress and news blackout support
- add portfolio weighting with internal caps

### Phase 2

- add richer analyst UI
- add pair drill-down and run comparison
- expose historical saved results and reusable approvals

### Phase 3

- add rolling walk-forward windows
- add broker-specific spread history
- add deeper regime-aware hard gating if the data quality supports it

## Risks

### 1. The design can become too complex too quickly

Mitigation:

- stage the rollout
- keep v1 to the highest-value protections

### 2. Free news data may be rate-limited or incomplete

Mitigation:

- cache aggressively
- normalize into local storage
- design the pipeline so missing news data degrades safely

### 3. Portfolio simulation quality depends on result alignment

Mitigation:

- standardize timestamps and symbol timelines early
- keep aggregation logic deterministic and well-tested

## Final Recommendation

Build the optimizer as a prop-firm survival engine with portfolio awareness and analyst-grade visibility. Use Bayesian search, strict forward gating, execution stress, EMA200 trend modes, cached Trading Economics news events, and portfolio-level risk weighting. Save every run in Supabase and in JSON snapshots so results can be compared and reused over time.
