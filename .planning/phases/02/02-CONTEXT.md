# Phase 2: Backend Stability & Bug Fixes - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Attain zero `ruff` warnings, maintain 100% backend test passage, resolve MetaAPI background timeouts (5s), and fix `yfinance` HTTP 404 errors.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices for standardizing the backend via ruff formatters, API tweaks for MetaAPI timeouts, and data-fetching fixes are left to Claude.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ruff` linter and `pytest` are available for validation.
- `meta_api_adapter.py` identified as the host of the timeout bug.
- `market_data.py` or similar is the likely yfinance failure point.

</code_context>

<specifics>
## Specific Ideas
- Target the 5-second `Read timed out` by separating execution paths or strictly elevating background task timeout parameters to >5s.
- Isolate the GBPJPY 404 issue in the `yfinance` call.

</specifics>

<deferred>
## Deferred Ideas
None
</deferred>
