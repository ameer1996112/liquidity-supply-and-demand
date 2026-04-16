# Guards Tab Multi-Account Design

## Summary

The current Guards tab is a global configuration screen backed by `/api/v1/guards/config`. That no longer matches runtime behavior: the trading pipeline executes a mixed model where some guards are system-wide and many important protections run per account/profile.

This design introduces a clear split inside the Guards experience:

- `Global`
- `Per Account`

The goal is to make guard scope explicit, reduce risky misconfiguration, and align the UI/API with the actual multi-account execution model.

## Problem

Today:

- the frontend loads one global guard payload
- updates write to one global settings surface
- the page has no account selector or scope labels

But in the worker:

- global guards run once before account fan-out
- per-account guards run separately for each matched broker profile

This creates a product mismatch. Users can reasonably assume a setting applies to one account when it actually applies to all accounts, or assume a control exists per account when the UI only exposes a shared value.

## Goals

- Make guard scope obvious at a glance
- Separate truly global controls from account-scoped controls
- Reuse the current visual language where possible
- Add the smallest backend surface needed to support per-account reads and writes safely
- Preserve current global guard behavior during rollout

## Non-Goals

- Rebuilding the whole Risk & Rules page
- Changing live guard logic semantics in the worker as part of this pass
- Migrating every guard immediately if its true scope is still ambiguous

## Recommended UX

Inside the existing `Guards` tab, add a second-level split:

- `Global`
- `Per Account`

### Global

This sub-tab shows only controls that are intentionally shared across the whole system.

Examples:

- global emergency kill switch
- staleness guard
- holiday / market schedule filters
- AI / signal-quality filters that run before account fan-out

Each row should include a subtle `Global` scope pill.

### Per Account

This sub-tab starts with an account selector tied to broker profiles.

Behavior:

- default to the first active broker profile
- switching accounts reloads that account’s guard config
- every row includes a scope pill like `Account: ACG-DEMO-2`

This section should include controls that are account-scoped in runtime behavior.

Examples:

- daily loss limit
- max drawdown
- max positions
- prop firm scaling
- real-time balance check
- per-account kill switch
- circuit-breaker protections

## Information Architecture

### Top level

- Risk & Rules
  - Monitor
  - Guards
  - Risk Rules
  - Strategy

### Guards

- Global
- Per Account

This keeps the current page intact and limits the change to the Guards experience only.

## Backend Design

### Existing surface

Keep the current global API for system-wide guards:

- `GET /api/v1/guards/config`
- `PATCH /api/v1/guards/config/{guard_id}`

These remain the backing endpoints for the `Global` sub-tab.

### New surface

Add account-scoped endpoints for broker-profile guard settings:

- `GET /api/v1/guards/accounts`
  - returns active broker profiles for selection
- `GET /api/v1/guards/config/account/{account_id}`
  - returns per-account guard config in the same general shape as the global response
- `PATCH /api/v1/guards/config/account/{account_id}/{guard_id}`
  - updates one account-scoped guard

The response shape should stay as close as possible to the current `GuardsConfigResponse` so the frontend can reuse most rendering logic.

## Data Model

### Global guards

Continue to use the current dynamic settings source.

### Per-account guards

Store account-scoped values against the broker profile / account record, not the global system config table.

Recommended model:

- one per-account guard settings record per broker profile
- sparse storage is acceptable
- unset account-level values fall back to global defaults where appropriate

Important rule:

- the API must always return the effective value plus its scope source if useful for debugging

Example:

- `source = "account"`
- `source = "global_default"`

This can be omitted from the initial UI if it adds noise, but the backend should be designed with this in mind.

## Frontend Design

### Hooks

Split the current guard hooks into:

- `useGlobalGuardsConfig`
- `useUpdateGlobalGuard`
- `useGuardAccounts`
- `useAccountGuardsConfig(accountId)`
- `useUpdateAccountGuard`

### Components

Refactor the current panel into reusable pieces:

- `GuardsPanel`
  - owns the `Global / Per Account` switch
- `GuardGroupList`
  - shared grouped rendering
- `GlobalGuardsView`
- `AccountGuardsView`

`AccountGuardsView` owns:

- account selector
- account metadata strip
- grouped guard cards

### Guard cards

Keep the current card style, but add:

- scope label
- selected account context on the per-account view

## Error Handling

- If active accounts cannot be loaded, keep `Global` usable and show a focused error in `Per Account`
- If one account’s guard config fails to load, do not break the whole page
- PATCH requests must include explicit scope in the route so writes cannot silently hit the wrong settings surface

## Testing

### Backend

- global endpoints still behave exactly as they do today
- account list endpoint returns active broker profiles
- account guard config endpoint returns only per-account guards
- account-scoped updates do not mutate global settings

### Frontend

- Guards tab renders `Global` by default
- switching to `Per Account` loads accounts and account-specific config
- changing account refreshes the view
- updating a per-account guard invalidates only the relevant account query
- scope labels render correctly

## Rollout Plan

### Phase 1

- Add `Global / Per Account` split in UI
- Keep current global implementation intact
- Add read-only per-account fetch if necessary

### Phase 2

- Enable per-account guard editing
- Add account-scoped backend update endpoints

### Phase 3

- Review every existing guard and classify it explicitly:
  - global
  - per-account
  - mixed / not yet supported

## Open Decisions

- Which current guards should remain global versus move to per-account on day one
- Whether per-account fallback to global values is shown in the UI or kept backend-only

## Recommendation

Implement the `Global / Per Account` split first, then wire account-scoped APIs and storage for the clearly account-level protections. This is the safest path because it improves product clarity immediately without forcing a risky all-at-once migration of every guard.
