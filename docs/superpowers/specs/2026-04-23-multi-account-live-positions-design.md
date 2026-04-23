# Multi-Account Live Positions Design

Date: 2026-04-23
Ticket: DEV-213

## Problem

The dashboard `Open Positions` panel is currently driven by a single-account backend path in `src/api_positions.py`.
That path assumes one primary broker adapter, which breaks when live trading spans multiple accounts or multiple venues.

In production this creates two user-facing failures:

1. The account overview can show connected accounts with open positions while `/positions/active` fails or returns incomplete data.
2. The dashboard falls back to signal rows, which do not reliably contain real live position data.

The desired user experience is one clean live positions panel that shows true open positions, grouped by account name, regardless of whether the account is backed by MetaAPI or cTrader.

## Goals

- Show real live open positions across all active live accounts in one unified dashboard panel.
- Support both MetaAPI-backed and cTrader-backed accounts.
- Keep the UI clean: one `LIVE` experience, one unified list, grouped by account name.
- Return partial results if one account or venue fails, instead of failing the whole panel.
- Preserve reconciliation metadata so stale or orphaned records can still be diagnosed.

## Non-Goals

- Changing trading logic or execution routing.
- Adding new venue-specific UI controls or surfacing venue complexity in the dashboard.
- Reworking the signal table beyond removing its need to act as the primary live positions source.

## Approaches Considered

### 1. Unified backend aggregator

Aggregate positions across all active live-capable broker profiles in `/positions/active`, normalize them into one response shape, and let the frontend render a single flat list.

Pros:
- Cleanest user experience.
- Keeps the frontend simple.
- Makes the backend the single source of truth for live positions.

Cons:
- Requires per-venue normalization and partial-failure handling.

### 2. Per-venue backend endpoints plus merge layer

Keep separate venue fetch flows and merge them inside a higher-level positions service or endpoint.

Pros:
- Internals can stay more explicitly separated by venue.

Cons:
- More plumbing with little user-facing benefit.
- Still needs a final normalization layer.

### 3. Frontend merge

Fetch live positions separately per venue or account and merge them in the dashboard.

Pros:
- Minimal backend restructuring.

Cons:
- Pushes source-of-truth logic into the UI.
- Harder to keep clean and correct.
- Makes failure handling and reconciliation more fragile.

## Decision

Use approach 1: a unified backend aggregator for live positions.

This keeps the dashboard clean while supporting multiple accounts and multiple venues. Internally, the implementation may use smaller venue-specific helpers, but the public contract should remain one aggregated live positions response.

## Architecture

### Position sources

`/positions/active` and `/positions/account` should stop depending on a single primary adapter.
Instead they should:

1. Load all active broker profiles eligible for live position aggregation.
2. Resolve the correct adapter per profile.
3. Fetch live account information and open positions per profile.
4. Normalize all venue responses into a shared internal position shape.
5. Reconcile those live positions against `trading_signals`.
6. Return one aggregated response to the dashboard.

### Eligible accounts

Eligible accounts are broker profiles that:

- are active
- are selected for trading when that concept is used for live trading visibility
- are in live mode or otherwise part of the current live operating set
- have sufficient credentials for their venue adapter

Profiles without valid venue credentials must be skipped and reported as degraded, not treated as fatal for the entire endpoint.

### Normalized live position shape

Each venue-specific position must normalize into a common structure that can be mapped to the existing `ActivePosition` response:

- `broker_profile_id`
- `account_name`
- `symbol`
- `side`
- `size`
- `entry`
- `sl`
- `tp`
- `current_price`
- `live_pnl`
- `broker_order_id`
- `broker_position_id`
- `opened_at` or equivalent live-open timestamp when available

This normalized representation is internal. The API can continue returning the current `ActivePosition` shape, extended only if needed for reconciliation.

## Data Flow

### `/positions/active`

1. Query candidate broker profiles.
2. For each eligible profile:
   - resolve the adapter
   - fetch open positions
   - fetch account info or prices if needed for live PnL enrichment
3. Build a merged live broker position index keyed by profile and broker ids.
4. Query `trading_signals` for rows that could represent open positions.
5. Match DB rows to broker positions using `broker_profile_id` and broker ids.
6. Return:
   - merged live positions
   - DB-backed metadata like `zone_id`, `entry_model`, and `rr_ratio` when matched
   - reconciliation summary including stale and missing counts

If a live broker position exists without a matching DB row, it should still contribute to reconciliation data and may optionally be surfaced as a broker-only row later. For this change, reconciliation visibility is enough.

### `/positions/account`

Aggregate account information across all eligible live profiles rather than reading a single adapter:

- total balance
- total equity
- total free margin
- total margin used
- aggregated active positions count

If one profile fails, the endpoint should still return totals from the healthy profiles and include degraded status in logs or metadata.

## Frontend Behavior

The dashboard should keep one `Open Positions` table.

It should:

- render the aggregated live positions list
- group rows by `account_name`
- show real position data instead of signal-derived placeholders
- avoid venue-specific clutter in the UI

The existing signal fallback should no longer be treated as normal live behavior.
It may remain as an emergency fallback, but the dashboard should be able to distinguish:

- no open positions
- degraded live data
- temporary fallback mode

The fallback mapping must use the actual DB size field when fallback is used:

- `signal.position_size ?? signal.size ?? 0`

## Failure Handling

The aggregation must support partial success.

Required behavior:

- one failing profile must not fail the whole endpoint
- one unsupported venue must not fail the whole endpoint
- one healthy account with open positions must still appear in the dashboard even if another account is unhealthy

Operational expectations:

- log failures per `broker_profile_id`
- preserve a reconciliation summary for observability
- return an empty positions list only when there are truly no visible live positions or every eligible source failed

## Testing

Add or update tests for:

1. Multiple active MetaAPI profiles returning merged live positions.
2. Mixed MetaAPI and cTrader profiles returning one aggregated list.
3. Partial failure where one profile errors and another still returns positions.
4. Reconciliation matching DB rows by `broker_profile_id` and broker ids.
5. `/positions/account` aggregating values across multiple profiles.
6. Frontend fallback using `signal.size` when `position_size` is absent.

## Risks

- `src/api_positions.py` is currently shaped around one adapter, so the refactor should extract helpers instead of extending the current inline flow further.
- Venue adapters may not expose identical fields, so normalization rules must be explicit.
- Reconciliation bugs can create ghost or duplicate positions if profile-aware matching is not enforced.

## Minimal Implementation Direction

1. Introduce a helper that resolves all eligible live broker profiles and adapters.
2. Introduce a helper that fetches and normalizes live positions per profile.
3. Refactor `/positions/active` to aggregate normalized live positions across profiles.
4. Refactor `/positions/account` to aggregate balances across profiles.
5. Tighten the frontend so live positions prefer aggregated endpoint data and fallback remains clearly degraded.

## Success Criteria

- The dashboard shows one clean live positions list across MetaAPI and cTrader accounts.
- Every row includes account name and real position data.
- A single venue outage does not blank the panel.
- The panel no longer depends on signal fallback for ordinary live trading.
