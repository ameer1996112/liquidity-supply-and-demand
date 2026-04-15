# Backend-Driven Per-Pair Risk Rules

## Summary
Move the Risk & Rules page from static, frontend-owned symbol inputs to a backend-driven risk configuration system. The page becomes the operator control surface for per-pair risk rules, while the backend becomes the single source of truth for prop-firm-safe risk validation and position sizing.

This design keeps live trade logic centralized in backend services instead of letting the UI define sizing behavior. Operators can tune each pair from the page, but execution always recalculates the final position size from live account state, stop-loss distance, and saved risk rules.

## Goals
- Make the Risk & Rules page manage per-pair risk rules from the backend.
- Remove direct frontend writes to `symbol_risk_rules`.
- Make backend APIs the only write path for symbol risk configuration.
- Ensure the backend computes final position size dynamically at execution time.
- Add rule fields needed for prop firm evaluations and safer sizing.
- Preserve compatibility with the current optimizer workflow so optimized pair results can feed this page.

## Non-Goals
- Changing strategy logic or signal generation logic.
- Changing trade execution behavior in `src/logic.py`.
- Reworking the full prop firm rules product into a multi-layer policy engine in this iteration.
- Replacing existing global account-level risk checks already handled elsewhere.

## Approved Decisions
- Source of truth: backend API plus backend risk engine.
- UI responsibility: edit and display risk rules, not calculate final lot size.
- Execution responsibility: derive final lot size from saved rules and live trade context.
- Storage model: extend the existing `symbol_risk_rules` model instead of introducing a brand-new policy hierarchy.
- Scope: symbol-level rules first, with validation designed to support future account/global layering.

## Problems Being Solved

### 1. The UI currently owns rule persistence
The current `RiskRulesPanel` reads and writes `symbol_risk_rules` directly through Supabase from the browser. This bypasses backend validation, duplicates data access patterns, and makes risk control harder to evolve safely.

### 2. Trade sizing is still too static
The current table exposes static fields like pip size and pip value, but the system goal is dynamic sizing. Position size should be recalculated by the backend from account balance, rule limits, live stop distance, and broker or symbol metadata.

### 3. Prop firm compliance needs stronger per-pair controls
Passing prop firm evaluations requires tighter guards than a simple max lot plus risk percent table. We need clear per-symbol limits for lot boundaries, concurrency, and safety buffers, all enforced centrally by the backend.

## Design Overview
The feature adds four coordinated changes:

1. Extend the backend symbol risk rule model to include execution-safe sizing constraints.
2. Move all Risk Rules page CRUD traffic to backend endpoints in `src/api_rules.py`.
3. Make the frontend consume backend DTOs instead of direct Supabase rows.
4. Make the worker and risk engine use backend-managed per-symbol rules as the execution-time source of truth.

## Architecture

### Current Flow
The browser loads `symbol_risk_rules` directly from Supabase, edits rows locally, and persists updates without backend validation. The backend risk engine can consume symbol overrides, but the product surface is not designed around backend ownership.

### Proposed Flow
Frontend requests symbol risk rules:

`GET /api/rules/symbols`

Frontend edits or creates rules:

- `POST /api/rules/symbols`
- `PUT /api/rules/symbols/{symbol}`
- `DELETE /api/rules/symbols/{symbol}`

Backend validates and stores rules, invalidates cache, and returns normalized rows.

At execution time:
- worker loads symbol overrides
- risk engine derives final lot size from live payload plus saved rules
- guard rails and position sizing use the same backend-owned symbol config

### Ownership Boundaries
- `frontend/src/app/risk/page.tsx` and `frontend/src/components/rules/RiskRulesPanel.tsx`: view and edit only
- `src/api_rules.py`: transport, validation entrypoint, DTO shaping
- `src/core/risk_engine.py`: final position sizing and risk math
- `src/worker.py`: symbol-rule fetch and application during execution

This keeps the live trade path backend-owned while still giving operators a clear editing surface.

## Data Model

### Existing Table
The current `symbol_risk_rules` table already stores:
- `symbol`
- `max_lot_size`
- `risk_percent`
- `pip_size`
- `pip_value_per_lot`
- `max_positions`
- `enabled`

### Proposed Fields
Keep the existing fields and add backend-focused execution constraints:
- `min_lot_size` numeric
- `lot_step` numeric
- `stop_loss_buffer_pips` numeric

Optional future-ready fields that may remain out of the UI for now:
- `notes` text
- `source` text such as `manual` or `optimizer`
- `requires_manual_review` boolean

### Field Intent
- `risk_percent`: maximum allowed risk allocation for that pair
- `max_lot_size`: hard cap on final lot size
- `min_lot_size`: smallest tradable lot allowed for that pair
- `lot_step`: broker-compatible size increment for rounding
- `pip_size`: symbol movement granularity
- `pip_value_per_lot`: backend override when dynamic contract data is unavailable
- `max_positions`: max concurrent positions for that pair
- `stop_loss_buffer_pips`: extra safety margin added around stop calculations
- `enabled`: whether the pair may be traded

## Backend API Contract

### `GET /api/rules/symbols`
Returns normalized symbol rules for the page.

Response shape should be backend-friendly and frontend-stable:
- `symbol`
- `max_lot_size`
- `min_lot_size`
- `lot_step`
- `risk_percent`
- `pip_size`
- `pip_value_per_lot`
- `stop_loss_buffer_pips`
- `max_positions`
- `enabled`
- timestamps if available

### `POST /api/rules/symbols`
Creates a new symbol rule and normalizes the symbol key to uppercase.

Validation:
- reject duplicate symbol
- reject zero or negative lot boundaries
- reject `min_lot_size > max_lot_size`
- reject invalid `lot_step`
- reject negative risk or position values

### `PUT /api/rules/symbols/{symbol}`
Updates an existing rule with the same validation rules.

### `DELETE /api/rules/symbols/{symbol}`
Deletes a symbol rule and invalidates the symbol rule cache.

## Backend Validation Rules
Validation must be centralized in the backend, not only in the browser.

Required checks:
- `symbol` must be non-empty after normalization
- `risk_percent` must be greater than 0 and within a safe upper bound
- `max_lot_size` must be positive
- `min_lot_size` must be positive
- `lot_step` must be positive
- `min_lot_size` must not exceed `max_lot_size`
- `max_positions` must be at least 1
- `pip_size` must be positive
- `pip_value_per_lot` must be positive
- `stop_loss_buffer_pips` must be zero or positive

Recommended safe upper bounds for v1:
- `risk_percent <= 2.0`
- `max_positions <= 10`

These bounds are product safety defaults, not strategy logic.

## Risk Engine Changes

### Core Principle
The browser should never be trusted to produce the final position size. The risk engine remains the single source of truth.

### Sizing Inputs
When sizing a trade, the risk engine should use:
- signal payload entry and stop loss
- account balance or equity
- backend symbol rule overrides
- risk multiplier from current guard logic
- broker spec when available

### Updated Position Sizing Behavior
The risk engine already supports `symbol_overrides`. Extend that behavior so it consistently consumes:
- `min_lot_size`
- `lot_step`
- `stop_loss_buffer_pips`

Existing fallback sizing stays in place for symbols without overrides, but configured rules should take precedence.

### Rejection Behavior
The engine should explicitly reject trades when:
- calculated size is below `min_lot_size`
- symbol rule is disabled
- symbol rule produces invalid sizing parameters
- concurrent position limits are exceeded elsewhere in the pipeline

Returned rejection details should stay machine-readable so the UI and audit logs can explain why a trade was blocked.

## Worker Integration
The worker already fetches per-symbol rules and caches them. This feature keeps that pattern but makes the page and API align with it more cleanly.

Execution path expectations:
- worker fetches rule map from backend storage
- selected symbol rule is passed into risk sizing helpers
- computed final lot size is written to execution payload
- no frontend-provided static lot size is trusted for execution sizing

## Frontend Design

### Page Role
The Risk Rules tab becomes a backend-driven risk policy table for symbols.

### UX Changes
- Replace direct Supabase reads and writes with fetches to backend endpoints.
- Keep the same table-oriented operator workflow to minimize disruption.
- Add inputs for:
  - `min_lot_size`
  - `lot_step`
  - `stop_loss_buffer_pips`
- Keep existing fields visible, but present `pip_size` and `pip_value_per_lot` as advanced execution fields instead of trade inputs.

### UX Messaging
The page should communicate the new ownership model:
- rules are saved to backend
- backend calculates final lot size during execution
- the table configures limits, not manual trade sizing

### Optimizer Relationship
This page should be the place where optimized pairs become approved operational rules. The optimizer can remain responsible for finding candidate values, while this page becomes the backend-managed final rule editor.

## Migration Strategy

### Backend First
Implement backend model and API changes first so the browser can switch over without a broken state.

### Frontend Switch
Update the panel to use backend endpoints only after the API is ready. Remove direct table access from the component.

### Data Compatibility
For existing rows:
- default `min_lot_size` to `0.01`
- default `lot_step` to `0.01`
- default `stop_loss_buffer_pips` to `1.0`

If the table migration is not part of this exact change set, the backend should still tolerate missing values and apply the same defaults until the migration lands.

## Testing Strategy

### Backend
- API tests for create, update, list, delete
- validation tests for invalid field combinations
- risk engine tests for min lot, lot step rounding, and stop-loss buffer
- worker-facing tests confirming configured overrides are consumed

### Frontend
- component tests for loading rules from API
- save and edit flows using backend endpoints
- rendering tests for the new fields and backend error states

### Regression Coverage
Verify existing rule rows still load and existing sizing fallbacks still work for symbols without explicit overrides.

## Risks and Mitigations

### Risk: inconsistent schema across frontend and backend
Mitigation: define one backend DTO shape and update the frontend type to match it.

### Risk: missing DB fields in older environments
Mitigation: backend applies safe defaults when optional rule fields are absent.

### Risk: operator confusion during transition
Mitigation: update copy on the page to explain that the backend now handles sizing dynamically.

### Risk: unexpected impact on execution sizing
Mitigation: keep fallback logic for symbols without overrides and add targeted tests before rollout.

## Implementation Units

### Unit 1: API and validation
Extend `src/api_rules.py` models and validation for backend-owned symbol risk rules.

### Unit 2: Risk engine consumption
Ensure `src/core/risk_engine.py` consistently consumes the expanded rule fields.

### Unit 3: Frontend integration
Refactor `frontend/src/components/rules/RiskRulesPanel.tsx` to call backend APIs instead of Supabase directly.

### Unit 4: Type and compatibility updates
Align frontend types and backend defaults so existing rows continue to work.

## Open Decisions Resolved
- The page is not the source of final position size.
- The backend will handle risk and position calculation.
- Per-pair rules remain editable from the Risk & Rules page.
- Existing static frontend trade inputs are replaced by backend-driven rule values.

## Acceptance Criteria
- Operators can create, edit, enable, disable, and delete per-pair rules from the Risk & Rules page.
- The page no longer talks directly to `symbol_risk_rules` from the browser.
- Backend validates rule input before persisting it.
- The risk engine uses backend symbol rules for execution-time sizing.
- New lot and stop-loss buffer controls are available for safer prop-firm-oriented operation.
