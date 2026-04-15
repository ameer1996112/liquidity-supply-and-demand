# Pass Evaluation Risk Mode

## Summary
Add a dedicated pass-evaluation risk mode focused on maximizing survival and consistency during prop-firm evaluations. The goal is not to guarantee a pass, but to make the system much harder to fail by reducing risk dynamically when pair performance weakens, when a pair trades too frequently during the day, and when account-level drawdown pressure increases.

This mode keeps the backend as the single source of truth for risk assignment and lot sizing. It layers conservative dynamic controls on top of each pair’s approved base risk.

## Goals
- Add a backend risk mode optimized for prop-firm evaluations.
- Make per-trade risk adapt to pair performance, same-day trade frequency, and account safety state.
- Keep approved pair rules as the base starting point for risk.
- Reduce the probability of failing evaluations through overtrading and uncontrolled drawdown.
- Keep the logic transparent enough for operators to understand and tune.

## Non-Goals
- Guaranteeing a 100% pass rate.
- Replacing the optimizer or alert-generation workflow.
- Changing strategy logic or entry logic.
- Creating a fully autonomous “black box” risk model that operators cannot understand.

## Approved Decisions
- The design target is “hard to fail,” not “maximum profit.”
- Dynamic logic can reduce risk aggressively, but should increase risk only slightly or not at all in evaluation mode.
- Same-day repeated trades from the same pair must reduce risk.
- Account safety logic must only reduce risk, never increase it.
- Hard floors and ceilings remain in place for every trade.

## Problems Being Solved

### 1. Static per-pair risk is too blunt for evaluation conditions
Even strong optimized pairs can go cold temporarily. Fixed risk makes the system slow to adapt.

### 2. High intraday trade frequency can compound losses
If one of the four active pairs fires many trades in a day, losses can stack too quickly even if the pair is normally good.

### 3. Passing evaluations requires consistency more than aggression
Prop-firm evaluations reward capital preservation and smooth progress more than large risk swings.

## Design Overview
The pass-evaluation mode adds five layers:

1. Base pair risk from approved active rules.
2. Pair-performance multiplier.
3. Same-day frequency multiplier.
4. Account-safety multiplier.
5. Hard per-trade and per-day caps.

Final trade risk is derived from all of them and then clamped.

## Core Formula

### Final Risk
For each trade:

`final_risk_pct = clamp(base_pair_risk × pair_performance_multiplier × frequency_multiplier × account_safety_multiplier, min_risk_pct, max_risk_pct)`

### Design Intent
- `base_pair_risk` comes from the active approved rule.
- `pair_performance_multiplier` reflects how the pair has behaved recently.
- `frequency_multiplier` reflects how many trades that same pair has already taken today.
- `account_safety_multiplier` reflects current account protection state.
- `clamp` enforces hard risk boundaries.

## Layer 1: Base Pair Risk

### Source
Base risk starts from active `symbol_risk_rules.risk_percent`.

Examples:
- `EURUSD = 0.50%`
- `XAUUSD = 0.25%`
- `GBPJPY = 0.50%`

### Evaluation Recommendation
For pass-evaluation mode, recommended starting base risks are conservative:
- normal forex pair: `0.25%` to `0.50%`
- high-volatility pair: `0.25%`
- no pair should start above the evaluation mode cap

## Layer 2: Pair Performance Multiplier

### Inputs
Use recent live pair performance, not just optimizer history.

Recommended metrics:
- recent win rate
- recent profit factor
- recent drawdown contribution
- recent expectancy or net pnl over last N trades

### Behavior
In evaluation mode, this multiplier should be conservative:
- strong pair performance: small lift or no lift
- weak pair performance: meaningful reduction

Recommended band:
- strong: `1.00` to `1.05`
- neutral: `1.00`
- weak: `0.75`
- very weak: `0.50`

### Recommendation
Allow only small upside in evaluation mode. The main purpose of this layer is to cut risk when a pair degrades.

## Layer 3: Same-Day Frequency Multiplier

### Purpose
Control repeated same-day signals from the same pair.

### Inputs
Use the count of executed or accepted trades for that pair during the current day.

### Recommended Decay
Example evaluation schedule:
- trade 1 of the day for that pair: `1.00`
- trade 2: `0.85`
- trade 3: `0.70`
- trade 4: `0.50`
- trade 5+: `0.25` or blocked entirely

### Recommendation
This layer should only reduce risk. It should never increase it.

## Layer 4: Account Safety Multiplier

### Purpose
Protect the evaluation account when the overall session quality deteriorates.

### Inputs
Recommended signals:
- daily realized loss utilization
- current drawdown utilization
- losing streak length
- number of failed trades in current session

### Recommended States
- normal: `1.00`
- caution: `0.75`
- defensive: `0.50`
- survival: `0.25`
- lockout: `0.00`

### Recommendation
This multiplier must only reduce risk. It acts as the final defensive layer before hard stops.

## Layer 5: Hard Caps

### Per-Trade Caps
Evaluation mode should enforce:
- `min_risk_pct`: `0.10%` or `0.25%`
- `max_risk_pct`: `0.50%` or `0.75%`

### Daily Caps
Recommended:
- per-pair daily risk budget
- total daily account risk budget
- optional max trades per pair per day

### Hard Stops
When daily loss utilization or drawdown utilization reaches danger levels:
- force account safety multiplier to `0.00`
- no new trades for the day

## Example

### Scenario
- base pair risk: `0.50%`
- pair performance multiplier: `0.90`
- same-day frequency multiplier: `0.70`
- account safety multiplier: `0.80`

Calculation:

`0.50 × 0.90 × 0.70 × 0.80 = 0.252%`

If min risk is `0.25%`, final risk becomes approximately `0.25%`.

This is exactly the type of behavior we want: the pair is still tradable, but risk is compressed because conditions are less favorable.

## Backend Architecture

### Rule Ownership
- active `symbol_risk_rules` remain the base approved config
- pass-evaluation mode lives in backend logic, not in the frontend only

### Dynamic Inputs
Add or derive:
- recent pair performance state
- daily trade count per pair
- account safety state

### Output
Before final lot sizing:
- compute `effective_risk_percent`
- pass that into the existing lot-sizing path

Execution remains backend-owned.

## Frontend Design

### Page Role
The Risk Rules or Prop Firm page should surface:
- base pair risk
- current effective risk
- current frequency state
- current account safety state
- current evaluation mode state

### Operator Visibility
Operators should be able to see why risk changed:
- pair weak -> reduced
- too many trades today -> reduced
- account in defensive mode -> reduced

This is important so the system stays understandable and trusted.

## Mode Configuration

### Evaluation Mode Toggle
Add a dedicated backend-controlled mode such as:
- `NORMAL`
- `PASS_EVAL`

### Pass-Eval Defaults
Suggested defaults:
- conservative base risk
- aggressive risk decay for repeated same-day trades
- strong account-safety reductions
- minimal or zero risk boosting from pair performance

## Testing Strategy

### Backend
- test final risk calculation under neutral conditions
- test pair-performance reductions
- test frequency-based decay
- test account-safety reductions
- test hard caps and lockout behavior

### Regression
- verify existing lot sizing still works with static rules
- verify evaluation mode affects risk percent before lot sizing, not after
- verify disabled symbols and minimum lot logic still apply

## Risks and Mitigations

### Risk: system becomes too conservative and grows too slowly
Mitigation: start conservative, measure results, and tune upward gradually rather than failing the evaluation early.

### Risk: too many multipliers create a black box
Mitigation: expose effective risk and multiplier reasons in the UI.

### Risk: performance-based boosts increase drawdown
Mitigation: keep upside tiny in pass-eval mode; most dynamic behavior should be downward only.

## Acceptance Criteria
- Each trade’s risk percent is computed dynamically from base pair risk plus conservative evaluation multipliers.
- Same-day repeated trades from the same pair reduce risk progressively.
- Account safety state can reduce risk sharply or lock trading entirely.
- Final lot sizing still happens in the backend using the effective risk percent.
- Operators can understand why current trade risk is higher or lower than base risk.
