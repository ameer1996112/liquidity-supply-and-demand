# Multi-Account Activation with cTrader Parity

Date: 2026-04-23
Jira: DEV-209
Status: Proposed

## Problem

The Accounts page currently presents `Activate` as if multiple accounts can be enabled at once, but the backend treats activation as exclusive by clearing `selected_for_trading` on every other profile whenever one account is activated.

At the same time, dashboard and portfolio-control data paths are still biased toward MetaAPI. This causes active cTrader accounts, such as FTMO, to fail broker-detail fetching or disappear from the same live account experience that MetaAPI accounts receive.

The result is confusing and operationally unsafe:

- only one activated account remains selected at a time
- activated cTrader accounts do not receive the same dashboard detail as MetaAPI accounts
- account detail fetches route some cTrader cards through MetaAPI-only logic
- one account’s broker failure can distort the visibility of other activated accounts

## Goal

Make `Activate` a true multi-select trading enablement control.

Any account activated from the Accounts page should:

- remain activated until explicitly deactivated
- appear on the dashboard alongside other activated accounts
- participate in execution routing independently of other activated accounts
- surface the same class of balance, equity, margin, leverage, and open-position detail regardless of whether the venue is MetaAPI or cTrader

## Non-Goals

- changing trading logic, strategy logic, or risk formulas
- introducing a new top-level account-selection concept beyond the existing broker profile model
- degrading MetaAPI behavior in order to support cTrader
- allowing one account failure to block successful execution on another account

## User-Facing Behavior

### Accounts Page

- Clicking `Activate` on one profile must not deactivate any other activated profile.
- `Deactivate` affects only the selected profile.
- Multiple cards may show the trading-enabled state at the same time.
- Copy should describe activation as parallel trading enablement, not primary account selection.

### Dashboard

- All activated broker profiles should appear together after refresh.
- cTrader accounts should show the same dashboard card structure as MetaAPI accounts.
- Live account details should be adapter-driven by venue instead of assuming MetaAPI.

### Execution

- A single signal should fan out to all activated accounts.
- Success or failure must be tracked per account.
- If one account rejects a trade, other activated accounts should still proceed.

## Proposed Approach

### 1. Activation Semantics

Keep `selected_for_trading` as the current enabled-for-trading flag, but remove the exclusivity behavior attached to it.

This is the least invasive path because it matches the current UI meaning, avoids schema churn, and preserves compatibility with existing rows. The backend must stop clearing other selected profiles during activation.

If the deployment has a database uniqueness rule that only allows one `selected_for_trading=true` row, that rule must be removed or replaced as part of rollout.

### 2. Venue-Aware Account Snapshot and Position Loading

All dashboard and portfolio-control fetches that currently instantiate `MetaApiAdapter` directly should move to the generic execution router, using each profile’s `venue` to resolve the correct adapter.

That router-driven path should be used consistently for:

- account information
- open positions
- broker connectivity status
- profile-specific live metadata such as server, leverage, and margin

This is required so FTMO cTrader profiles stop flowing through MetaAPI-only code paths.

### 3. Equal-Treatment Dashboard Aggregation

The account comparison/dashboard pipeline should treat all activated broker profiles as peers.

Activated profiles without `account_strategies` rows should still render through the standalone-profile path, but that path must use the correct adapter and expose equivalent fields across venues. cTrader accounts should no longer be omitted, downgraded, or shown with materially less live detail.

### 4. Per-Account Execution Isolation

Execution fan-out should remain multi-account, but failures must stay isolated to the affected profile.

For a single signal:

- one account may execute successfully
- another may reject for venue-specific reasons
- the successful execution must remain valid
- the failed execution must be recorded with account-level status and error detail

The overall signal should not collapse into a global failure if at least one target account succeeds.

## Implementation Areas

### [src/api_broker_profiles.py](/Users/ameeramer/dev/projects/galilsoftware/sources/trading/src/api_broker_profiles.py)

- remove the “clear everyone else first” activation behavior
- keep deactivation scoped to one profile
- update API comments and intent from exclusive primary selection to multi-select enablement

### [src/services/account_orchestrator.py](/Users/ameeramer/dev/projects/galilsoftware/sources/trading/src/services/account_orchestrator.py)

- ensure active broker profile snapshots use venue-aware adapters
- continue surfacing standalone active profiles for dashboard comparison
- preserve per-profile visibility even when another profile fails broker calls

### [src/api_portfolio_control.py](/Users/ameeramer/dev/projects/galilsoftware/sources/trading/src/api_portfolio_control.py)

- replace MetaAPI-only open-position fetching with adapter routing by venue
- keep reconciliation logic venue-neutral where possible
- return equivalent broker-position detail for cTrader and MetaAPI accounts

## Data and Migration Notes

- Existing activated accounts should remain activated.
- Existing connected cTrader profiles should not require reauthorization solely because activation semantics changed.
- If the database contains a uniqueness constraint on `selected_for_trading`, deployment must remove that constraint before or alongside the code rollout.
- No new top-level directories or new core account tables are required.

## Error Handling

- Broker detail fetch failures should be isolated to the affected account card.
- cTrader-specific errors should not be translated into MetaAPI-auth failures.
- Dashboard rendering should degrade gracefully per account instead of hiding the full account set.
- Activation should fail only for the selected profile being updated, not for unrelated activated accounts.

## Testing

### Functional

- Activate `ACG-DEMO-3`; verify it remains enabled.
- Activate cTrader FTMO; verify `ACG-DEMO-3` stays enabled.
- Refresh the dashboard; verify both cards appear together.
- Deactivate one account; verify the other remains enabled and visible.

### Venue Parity

- Confirm MetaAPI and cTrader cards both show live balance, equity, and open positions.
- Confirm portfolio-control queries do not attempt MetaAPI auth for cTrader accounts.
- Confirm cTrader FTMO detail uses the cTrader adapter path end to end.

### Execution Isolation

- Send one controlled signal to both activated accounts.
- Simulate one-account broker rejection.
- Verify the other account still executes.
- Verify stored results and UI statuses are account-specific.

## Risks

- Some deployments may still enforce single-selection at the database level.
- MetaAPI-centric assumptions may exist in additional read paths beyond the first known dashboard and portfolio-control surfaces.
- cTrader open-position payloads may not match MetaAPI fields exactly, so normalization must be explicit rather than assumed.

## Rollout

1. Remove activation exclusivity in the API layer.
2. Confirm database allows multiple `selected_for_trading=true` profiles.
3. Switch dashboard and portfolio-control broker data fetches to venue-aware adapters.
4. Verify both MetaAPI and cTrader accounts can stay activated and visible together.
5. Validate one successful and one failed account execution in the same signal flow.

## Success Criteria

- More than one account can remain activated from the Accounts page at the same time.
- Activated MetaAPI and cTrader accounts appear together on the dashboard.
- cTrader FTMO no longer hits MetaAPI-only fetch paths.
- A single failing account does not prevent the other activated accounts from executing.
