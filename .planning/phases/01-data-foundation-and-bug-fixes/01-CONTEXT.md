# Phase 1: Data Foundation and Bug Fixes - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

The backend produces correct prop firm metrics for FTMO accounts — firm auto-detected from server name, rules in DB, all six known calculation bugs fixed
</domain>

<decisions>
## Implementation Decisions

### Firm Auto-Detection Strategy
- Matching strategy for server names? **Prefix matching** (`FTMO-Server` matches `FTMO-Server3`) — robust to new servers
- Case sensitivity? **Case-insensitive** — avoids capitalization bugs

### Rules Database Architecture
- Rule storage format? **Flat columns** — easier to query and update
- Timezone handling for daily reset (NY midnight)? **Store standard timezone string** (`America/New_York`) — handles DST automatically

### Challenge Account Differentiation
- Initial challenge type state for new accounts? `null` / unconfigured — forces explicit user selection via API
- Drawdown denominator basis for Phase 1/2? **Initial balance** — required by FTMO rules

### API Design
- Unrecognized server response? **200 OK with `firm_detected: false`** — allows graceful UI fallback ("Unknown firm")

### Claude's Discretion
None.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `api_funding.py` — existing prop firm page endpoints can serve as a base for `/challenge-status`
- `prop_firm_tracker.py` — existing calculations tracking daily loss and drawdown (contains the bugs to fix)

### Established Patterns
- Database interaction via Supabase Python client `adapters.supabase` using Pydantic schemas for data validation
- Error handling with logging and graceful fallback via `try/except` returning default empty values

### Integration Points
- Backend worker loops and logic engine (`logic.py`), specifically the `prop_guard.py` or where FTMO rules are evaluated
- Database migrations schema (`migrations/*.sql`) for adding new tables `prop_firm_rules` and `prop_firm_server_mappings`
</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches
</specifics>

<deferred>
## Deferred Ideas

- Other prop firms at launch (The5ers, FundedNext, E8) — deferred; architecture supports them, data not seeded yet
- Prop firm API integration (FTMO MetriX) — APIs not stable/public; rules in internal DB is more reliable
</deferred>
