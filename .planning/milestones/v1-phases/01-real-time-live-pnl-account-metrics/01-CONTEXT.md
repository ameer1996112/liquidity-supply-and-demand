# Phase 1: Real-time Live PnL & Account Metrics - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Dashboard accurately displays Live PnL and overall account metrics (Balance, Margin, Drawdown). Fix Live PnL showing `0.00`.
</domain>

<decisions>
## Implementation Decisions

### Data Sync Strategy
- Use Subscriptions or WebSocket streaming from the backend to Next.js or direct from Supabase to ensure live PnL updates continuously without polling.

### Calculation Source of Truth
- Rely strictly on MetaTrader/MetaApi's reported equity and PnL fields for active trades instead of calculating manually in the Next.js frontend to avoid precision loss or missing hidden fees.

### Claude's Discretion
- All implementation choices and specific Supabase table structures are at Claude's discretion.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- Supabase realtime hooks in Next.js frontend or standard Supabase client.
- `api.py` and `worker.py` already handling MetaApi connections.

### Established Patterns
- Pydantic models in FastAPI for validation.
- Redis queues for passing data between MetaApi and backend.

### Integration Points
- Connecting the MetaApi live account updates to Supabase dashboard tables.
</code_context>

<specifics>
## Specific Ideas

The Live PnL currently shows `0.00` which must be fixed. Ensure sync includes Account Balance, Margin, and Daily Drawdown perfectly matched to MT4/MT5.
</specifics>

<deferred>
## Deferred Ideas

Historical PnL retroactive fixes (Deferred to Phase 2/3).
</deferred>
