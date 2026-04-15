# Optimizer Risk Rule Suggestions

## Summary
Add a hybrid approval workflow between the optimizer and the Risk Rules page. Optimizer output should no longer be treated as an implicit source of live risk configuration. Instead, optimizer runs produce backend-owned per-symbol suggestions, while live execution continues to read only the active `symbol_risk_rules` configuration.

This keeps the backend as the single source of truth for execution-time sizing and adds an explicit operator approval step before optimizer results affect live rules.

## Goals
- Let optimizer runs publish per-symbol risk rule suggestions.
- Keep active `symbol_risk_rules` unchanged until an operator approves a suggestion.
- Show both active and suggested values on the Risk Rules page.
- Make approval update only optimizer-owned fields by default.
- Preserve prop-firm-safe operator control over manual safety fields.

## Non-Goals
- Auto-applying optimizer results directly into live rules.
- Replacing the current `symbol_risk_rules` table as the active execution source.
- Rebuilding the optimizer scoring logic or output format.
- Adding account-level or strategy-level inheritance in this iteration.

## Approved Decisions
- The flow is hybrid, not automatic.
- Optimizer results become pending suggestions, not live rules.
- Active rules remain the only inputs used by the worker and risk engine at execution time.
- Approval updates only optimizer-owned fields:
  - `risk_percent`
  - `max_lot_size`
  - `pip_size`
  - `pip_value_per_lot`
- Manual safety fields stay operator-owned by default:
  - `min_lot_size`
  - `lot_step`
  - `stop_loss_buffer_pips`
  - `max_positions`
  - `enabled`

## Problems Being Solved

### 1. Optimizer output is useful but not safe to auto-apply
Optimizer runs can discover strong per-pair values, but directly turning those into live execution rules is too risky for prop-firm trading.

### 2. Operators need a review gate
The trading system needs a clear difference between a candidate rule and an approved live rule.

### 3. Risk ownership needs separation
Some fields should be optimizer-owned, while others should remain manual safety controls managed by the operator.

## Design Overview
The feature adds four pieces:

1. A new backend suggestion model for optimizer-produced symbol rule candidates.
2. A backend read model that combines active rules with latest suggestions.
3. Approval actions that selectively copy optimizer-owned fields into active rules.
4. A Risk Rules UI that displays active and suggested values side by side.

## Architecture

### Active Execution Path
The worker and risk engine continue to read only active rows from `symbol_risk_rules`.

Execution path remains:

`Risk Rules page -> backend API -> symbol_risk_rules -> worker/risk engine`

### Suggestion Path
Optimizer runs write suggestion rows into a separate backend-owned store.

Suggestion path becomes:

`optimizer run -> backend suggestion store -> Risk Rules review UI -> operator approval -> symbol_risk_rules`

### Separation of Concerns
- `symbol_risk_rules`: live active rules used in execution
- `symbol_risk_rule_suggestions`: candidate values from optimizer runs
- approval API: controlled copy from suggestion to active rule

This keeps execution deterministic and lets optimizer keep learning without silently changing production behavior.

## Data Model

### Active Rules
Keep the current `symbol_risk_rules` model as the live source of truth.

### Suggestions
Add a new table or equivalent backend persistence model named `symbol_risk_rule_suggestions`.

Recommended fields:
- `id`
- `symbol`
- `optimizer_run_id`
- `suggested_risk_percent`
- `suggested_max_lot_size`
- `suggested_pip_size`
- `suggested_pip_value_per_lot`
- `status` with values such as `pending`, `approved`, `rejected`, `superseded`
- `created_at`
- `approved_at`
- `approved_by`
- `source_payload` for raw optimizer metrics or metadata

### Status Meaning
- `pending`: latest optimizer candidate awaiting review
- `approved`: candidate was accepted into active rules
- `rejected`: candidate was reviewed and declined
- `superseded`: a newer suggestion exists for the same symbol

## Ownership Model

### Optimizer-Owned Fields
These fields may be updated from suggestions when approved:
- `risk_percent`
- `max_lot_size`
- `pip_size`
- `pip_value_per_lot`

### Operator-Owned Fields
These fields remain manual by default:
- `min_lot_size`
- `lot_step`
- `stop_loss_buffer_pips`
- `max_positions`
- `enabled`

This ownership split reduces the chance that an optimizer run accidentally weakens manual prop-firm controls.

## Backend API Contract

### Read API
Add an API that returns active rules plus the latest suggestion per symbol.

Recommended response shape per symbol:
- `symbol`
- `active_rule`
- `latest_suggestion`
- `suggestion_status`
- `has_pending_changes`

### Approval API
Add an approval endpoint such as:

`POST /api/rules/symbols/{symbol}/approve-suggestion`

Behavior:
- loads latest pending suggestion for the symbol
- loads active rule for the symbol
- copies optimizer-owned fields into the active rule
- keeps operator-owned safety fields unchanged
- marks the suggestion as approved
- marks older pending suggestions for that symbol as superseded if needed

### Reject API
Add:

`POST /api/rules/symbols/{symbol}/reject-suggestion`

Behavior:
- marks the current pending suggestion as rejected
- active rule remains unchanged

## Frontend Design

### Page Changes
The Risk Rules page becomes both:
- an editor for active rules
- a review queue for optimizer suggestions

### Per-Symbol Presentation
For each symbol, show:
- active values
- suggested values when present
- a clear pending/review badge
- actions:
  - `Approve`
  - `Reject`
  - `Edit Active`

### Diff-Oriented UX
Highlight only the fields that differ between active and suggested values. This keeps review fast and reduces noise when some values are identical.

### Safety Messaging
UI copy should explain:
- backend uses only active rules for execution
- suggestions are candidates from optimizer runs
- approval is required before live behavior changes

## Optimizer Integration

### Write Behavior
When an optimizer run finishes, backend logic should persist a suggestion row per symbol instead of mutating `symbol_risk_rules`.

### Idempotency and Freshness
If the optimizer writes multiple results for the same symbol:
- latest result becomes the primary pending suggestion
- older pending rows may be marked `superseded`

### Traceability
Every suggestion should point back to the optimizer run that produced it so the operator can understand where it came from.

## Error Handling

### No Active Rule Yet
If a suggestion exists for a symbol without an active rule:
- allow approval to create a new active rule
- initialize operator-owned safety fields from backend defaults or current operator defaults

### Stale Suggestion
If an operator is reviewing an older suggestion and a newer one already exists:
- block approval of the stale one or require explicit override
- default behavior should prefer the latest suggestion

### Partial Optimizer Data
If a suggestion is missing required optimizer-owned fields:
- do not allow approval
- surface a clear backend validation error

## Testing Strategy

### Backend
- test optimizer suggestion persistence
- test latest-suggestion lookup per symbol
- test approve action updates only optimizer-owned fields
- test reject action leaves active rule unchanged
- test stale suggestion handling

### Frontend
- test combined active-plus-suggestion rendering
- test approve and reject actions
- test field-diff highlighting
- test symbols with active rule only, suggestion only, and both

### Regression
- verify worker and risk engine still use only active `symbol_risk_rules`
- verify existing Risk Rules editing continues to work when no suggestions exist

## Risks and Mitigations

### Risk: operators confuse suggested values with active values
Mitigation: visually separate the two and label live execution as active-only.

### Risk: approval overwrites manual safety settings
Mitigation: copy only optimizer-owned fields by default.

### Risk: suggestion table becomes noisy across repeated runs
Mitigation: mark old rows as superseded and show only the latest pending candidate by default.

## Acceptance Criteria
- Optimizer output is stored as suggestions, not auto-applied live rules.
- Risk Rules page shows both active and suggested per-symbol values.
- Operators can approve or reject suggestions.
- Approval updates only optimizer-owned fields by default.
- Worker and risk engine continue to read only active rules at execution time.
