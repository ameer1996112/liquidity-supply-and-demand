# Phase 7: Multi-Account Execution - Context
**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary
Migrate the singleton Python `worker.py` and Config dependencies from executing against a single MetaAPI account to executing concurrently across an infinite array of configured tokens mapping to individual risk contexts.
</domain>

<decisions>
## Implementation Decisions
### Configuration Parsing
We will migrate to a composite `.env` string like `META_API_ACCOUNTS="token|id, token2|id2"` to handle unlimited prop firm definitions.
### Concurrency
Execute natively using `asyncio.gather()` inside the Worker loop to hit all accounts concurrently without systemic slippage.
### Redis Isolation
All state-driven guardrails (Daily Limits, Streaks, Correlation) will dynamically append the `{account_id}` to their Redis key schemas.
</decisions>
