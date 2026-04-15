# Per-Account Guard Monitor Design

## Summary
The system already executes most live guard enforcement on a per-account basis, but the operator-facing guard and risk pages still expose several single-account style metrics. This creates a mismatch between what the backend is protecting and what the UI appears to be protecting.

This design keeps per-account guard enforcement as the source of truth and adds a backend monitor shape that reports both:
- a combined summary across active trading accounts
- separate per-account guard cards with identity and live risk state

The goal is to make the UI reflect the real multi-account behavior of the system and prevent operators from reading one account’s drawdown or balance as if it represented the whole fleet.

## Goals
- Verify that guard enforcement runs per account across the active execution path.
- Fix monitor and guard reporting so it reflects each trading account independently.
- Add a combined summary at the top of the page for fleet-level visibility.
- Add separate per-account cards that show identity plus live guard state.
- Remove dependence on `settings.account_balance` for per-account display metrics where real account-specific data exists.

## Non-Goals
- Rewriting the full guard system.
- Changing trade strategy logic or optimizer logic.
- Replacing existing account-level guard implementations with a new framework.
- Building a full historical analytics dashboard for every account in this pass.

## Problems Being Solved

### 1. Guard enforcement and reporting are misaligned
The pipeline already scopes many live checks by `account_name` or `broker_profile_id`, but the reporting layer still exposes global-style metrics in places.

### 2. The current guard page can look like it represents only one account
Metrics such as drawdown and account balance can still be derived from `settings.account_balance`, which makes the page look like a single-account monitor even when multiple accounts are active.

### 3. Operators need both fleet-level and account-level visibility
When managing multiple evaluation or funded accounts, operators need a fast combined overview and a clear per-account breakdown.

## Current State

### Enforcement Path
The current per-account enforcement path in `src/pipeline/account_guards.py` already scopes most key checks correctly:
- Redis kill switch
- MTM Guardian
- MetaAPI circuit breaker
- adaptive trade limit
- PropGuard
- correlation guard
- consistency analyzer

These guards run with `account_name`, `broker_profile_id`, or account-scoped trade queries.

### Reporting Path
The current reporting layer in `src/api_risk_monitor.py` still includes single-account style assumptions:
- daily PnL is aggregated without a per-account card structure
- open positions and trades today are global counts
- drawdown is derived from `settings.account_balance`
- active settings expose one shared balance

The current `src/api_guards.py` endpoint is mainly configuration and rejection-stat reporting, not live per-account guard state.

## Recommended Approach

### Chosen Approach
Add a dedicated backend monitor response that returns:
- one combined summary section
- one array of per-account guard cards

Keep enforcement in the existing guard pipeline and make the monitor/reporting layer match it.

### Why This Approach
- It fixes the user-facing problem without destabilizing live execution logic.
- It preserves current guard ownership boundaries.
- It makes the UI truthful about multi-account state.
- It creates a clean contract for frontend cards without needing a full backend rewrite.

## Data Model

### Combined Summary
The monitor response should include a fleet-level summary:
- `total_accounts`
- `active_accounts`
- `total_equity_usd`
- `total_starting_balance_usd`
- `total_daily_pnl_usd`
- `total_open_positions`
- `accounts_in_warning`
- `accounts_blocked`
- `global_kill_switch_active`

This summary is for top-level awareness only. It is not a substitute for per-account status.

### Per-Account Card
Each account card should include a light identity header plus live risk status.

Identity fields:
- `account_name`
- `broker_profile_id`
- `account_type`
- `evaluation_phase`
- `prop_firm_name`
- `run_mode`
- `connection_status`

Financial state:
- `starting_balance_usd`
- `current_equity_usd`
- `daily_pnl_usd`
- `daily_pnl_pct`
- `peak_equity_usd`

Guard and risk state:
- `current_drawdown_pct`
- `max_drawdown_allowed_pct`
- `drawdown_utilization_pct`
- `daily_loss_used_usd`
- `daily_loss_limit_usd`
- `open_positions`
- `max_positions`
- `trades_today`
- `max_trades_today`
- `risk_multiplier`
- `risk_label`
- `effective_risk_pct`
- `base_risk_pct`
- `kill_switch_active`
- `blocked`
- `guard_rails[]`

Optional operator-explanation fields:
- `warning_message`
- `blocked_reason`

## Backend Design

### Source of Accounts
Use the same account universe already used by risk status and dashboard flows:
- active account strategies
- selected-for-trading active broker profiles

The monitor should build one unified account list and avoid double-counting accounts that appear in both places.

### Per-Account State Calculation
For each account, calculate metrics using account-scoped reads:
- daily PnL from account-scoped closed trades
- trades today from account-scoped rows
- active positions from account-scoped open trades
- balance or equity from account-specific snapshots where available
- starting balance from broker profile fallback where snapshot data is unavailable

Per-account drawdown must be based on that account’s own balance/equity, not the global settings fallback unless no account-specific data exists.

### Guard State Projection
The monitor should project the same logic the guard pipeline uses, but only for display:
- kill switch state
- PropGuard result
- circuit breaker state
- trade-limit state
- correlation occupancy
- consistency state when evaluation mode applies

This projection must be read-only and should not mutate guard state.

### Combined Summary Calculation
The summary row should aggregate only from the per-account card data, not from separate duplicate queries where possible. This keeps the summary consistent with the cards.

## API Shape

### Recommended Endpoint Strategy
Extend the risk-monitor API rather than inventing a disconnected guard endpoint.

Preferred options:
- add a new version of `/api/risk/monitor`
- or add a new endpoint like `/api/risk/monitor/accounts`

Recommended response shape:

```json
{
  "summary": {
    "total_accounts": 4,
    "active_accounts": 4,
    "total_equity_usd": 201340.25,
    "total_daily_pnl_usd": -420.0,
    "total_open_positions": 6,
    "accounts_in_warning": 1,
    "accounts_blocked": 0,
    "global_kill_switch_active": false
  },
  "accounts": [
    {
      "account_name": "FTMO Phase 1",
      "run_mode": "LIVE",
      "starting_balance_usd": 50000,
      "current_equity_usd": 49620,
      "daily_pnl_usd": -380,
      "current_drawdown_pct": 0.76,
      "risk_multiplier": 0.5,
      "guard_rails": []
    }
  ],
  "last_updated": "2026-04-16T00:00:00Z"
}
```

## Frontend Design

### Layout
The page should use:
1. one combined summary row at the top
2. separate per-account cards underneath

### Card Structure
Each card should have:
- account identity header
- high-signal metrics row
- guard rail status list
- blocked or warning banner when applicable

### Why This Layout
- the top row answers “how is the whole fleet doing?”
- the cards answer “which exact account is in trouble?”

This matches the operator need much better than a single shared drawdown block.

## Verification Plan

### Enforcement Verification
Before changing the page contract, verify that each account guard still scopes correctly in the live path:
- account-scoped kill switch
- account-scoped MTM checks
- account-scoped daily loss and trade count
- account-scoped open-position correlation
- account-scoped consistency checks

If any remaining guard uses shared state incorrectly, fix that in the same implementation.

### Reporting Verification
Add tests that prove:
- two accounts with different balances produce different drawdown cards
- combined summary totals match the sum of card-level metrics
- one account entering defensive mode does not incorrectly mark another account as defensive

## Error Handling
- If one account snapshot fails, the monitor should still return the other accounts.
- Each account card may include a degraded or partial-data flag if required.
- The combined summary should aggregate only successful account rows and expose a warning count if partial data exists.

## Testing Strategy

### Backend Tests
- test account list aggregation and de-duplication
- test per-account drawdown calculations
- test per-account daily pnl and trade counts
- test combined summary aggregation
- test partial failure behavior for one account

### Frontend Tests
- test summary row rendering
- test separate account cards rendering
- test warning and blocked styling by account
- test no fallback to a single shared balance block

## Rollout Recommendation
- Ship backend response first with compatibility preserved where possible.
- Update the guard page to consume the new response shape.
- Keep legacy single-summary sections only if needed during transition, then remove them.

## Final Recommendation
The right fix is not just a UI split. The right fix is a truthful multi-account monitor:
- keep guard enforcement per-account
- verify the live path is fully scoped
- expose a combined summary for fleet awareness
- expose separate per-account cards for real decision-making

This gives operators a page that matches how the system actually protects capital.
