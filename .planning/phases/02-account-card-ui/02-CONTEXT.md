# Phase 2: Account Card UI - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Embed real-time prop firm challenge tracking directly into the existing account cards (EnhancedAccountCard). This includes progress bars, trading days counter, warning banners, and a challenge type selector component without leaving the accounts page.
</domain>

<decisions>
## Implementation Decisions

### Layout style
- Integration: Append PropFirmSection UI below base account details inside EnhancedAccountCard.

### Warning Pattern
- Visuals: Use standard destructive/warning colors embedded as alert banners within the card matching 80% thresholds.

### Unknown Firm Handling
- Fallback: Clearly display "Unknown Firm" using raw server name string without crashing UI.

### Claude's Discretion
- Progress bar styling (Tailwind variants) and exact component composition (e.g. separating `PropFirmSection.tsx`) are up to the planner/executor as long as it fits the existing UI.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Foundational Specs
- `.planning/ROADMAP.md` — Phase 2 Success Criteria
- `.planning/phases/01-data-foundation-and-bug-fixes/01-RESEARCH.md` — Prop firm metrics math and context
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `EnhancedAccountCard.tsx`: The primary wrapper for presenting account data where the new section will live.
- Existing standard UI components in `frontend/src/components/ui/` (e.g., Progress, Badge, Alert) should be leveraged.

### Integration Points
- `usePropFirmChallenge` hook (to be created) will integrate data fetching from `/api/v1/prop-firm/challenge-status/...`.
</code_context>

<specifics>
## Specific Ideas
- Polling via SWR/React Query or standard useEffect interval (10s polling mentioned in roadmap).

</specifics>

<deferred>
## Deferred Ideas
None — discussion stayed within phase scope.
</deferred>
