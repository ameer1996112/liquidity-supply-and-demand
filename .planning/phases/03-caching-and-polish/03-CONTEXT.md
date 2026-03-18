# Phase 3: Caching and Polish - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement Redis caching to offload repetitive Prop Firm metrics recalculations from the Supabase database. This boundary includes modifying the background worker to continuously compute and cache these metrics independently from client polling, and updating the API endpoint to read from Redis with a database fallback.
</domain>

<decisions>
## Implementation Decisions

### Cache Layer
- Data Store: Redis (running locally on port 6379 natively required by worker/API).
- Key Format: `prop_firm:metrics:{account_name}`
- TTL: 30 seconds to provide grace period before expiration without stale data issues.

### Computation Loop
- Worker implementation: A scheduled background task or async polling loop in `src/worker.py` (or a dedicated task) scanning `broker_profiles` every 20 seconds.
- Storage payload: Serialized JSON object matching the `ChallengeStatusResponse` output format but wrapped internally or matching the metrics dictionary.

### API Adaptation
- Backend: Update `src/api_prop_firm_v1.py` `get_challenge_status` to query Redis first. Only if the key is missing or stale does it invoke `PropFirmDetector.get_account_status()` and cache the result immediately.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Foundational Specs
- `.planning/ROADMAP.md` — Phase 3 Success Criteria
- AGENTS.md — Required infrastructure states Redis must be running on `localhost:6379`.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/api_prop_firm_v1.py`: Contains API endpoints fetching metrics using `PropFirmDetector.get_account_status()`.
- `src.worker`: Existing worker infrastructure. We can either add to the main worker loop or create a subprocess loop for metrics compilation.
</code_context>

<specifics>
## Specific Ideas
- Background worker writing prop_firm metrics to Redis every 20s.
- `fastapi` dependency injection or global redis client setup in backend to fetch Redis keys.

</specifics>

<deferred>
## Deferred Ideas
- Expanding cache logic to other endpoints besides `challenge-status`.
</deferred>
