# Phase 1: Smart Kanban Board Foundation - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Upgrade the `jira/` Kanban board to be fully real-time and add a rich text editor for ticket descriptions. The core board mechanics (dnd-kit drag-and-drop, sprint tabs, issue cards, issue drawer) already work well — this phase adds the missing live data layer and richer editing experience. Scope: Supabase realtime subscription replacing manual polling, rich text editor (markdown) in IssueDrawer, and a "source" badge on cards indicating whether a ticket came from GSD/event/manual.

</domain>

<decisions>
## Implementation Decisions

### Realtime Strategy
- Use Supabase `channel().on('postgres_changes', ...)` on the `project_tickets` table
- Handle INSERT (add card), UPDATE (update card in place), DELETE (remove card) events
- Keep the existing `load()` on mount as initial fetch, realtime handles changes after
- Subscribe in `useEffect` on `BoardPage`, unsubscribe on unmount
- No polling interval — purely realtime after initial load

### Rich Text Editor
- Use `@uiw/react-md-editor` (lightweight, no prosemirror complexity) OR a simple `<textarea>` with markdown preview toggle
- Decision: **plain textarea with markdown preview toggle** — zero new deps, matches the codebase's minimal-dependency approach
- Edit mode: raw markdown textarea; Preview mode: render via `dangerouslySetInnerHTML` with basic CSS
- Auto-save on blur (300ms debounce) — same pattern used for other inline edits in IssueDrawer

### Source Tag
- Add `source` field to display on IssueCard: derive from `ai_changelog` presence (AI-touched) and `signal_id` presence (trading signal)
- "GSD" badge: tickets with title starting "Phase " (naming convention from gsd-autonomous)
- "EVENT" badge: tickets with `signal_id` set
- "AI" badge: tickets with `ai_changelog.length > 0` (already shown)
- "MANUAL" badge: none of the above — show nothing (default)

### Card Metadata Display
- Story points: already shown (bottom-left)
- Sprint name: not shown on card — too verbose, visible in column context
- Assignee: show initials avatar (top-right) if `assignee` is set
- Epic: not implemented in this phase — deferred to Phase 4

### Claude's Discretion
- Realtime subscription error handling — reconnect silently, log to console
- Markdown preview CSS styling — match dark theme with inline styles

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `IssueCard.tsx` — already has dnd-kit `useSortable`, priority dot, type icon, labels, story_points, ai badge
- `IssueDrawer.tsx` (12KB) — full-featured drawer with inline editing for all fields; description is currently a plain `<textarea>`
- `supabase.ts` — `getSupabase()` already configures realtime client with `eventsPerSecond: 10`
- `board/page.tsx` (293 lines) — complete board with DndContext, SortableContext, DragOverlay, sprint tabs, issue modal

### Established Patterns
- State management: plain `useState` + `useCallback` (no Zustand, no React Query)
- Data fetching: async functions in `supabase.ts` called directly from components
- Styling: Tailwind CSS with hardcoded dark theme hex colors (`#13161e`, `#1f2335`, etc.)
- Edit pattern in IssueDrawer: `editingField` state + click-to-edit inline fields with `onBlur` save

### Integration Points
- Realtime subscription goes in `board/page.tsx` `useEffect` — attach on mount, detach on unmount
- Description editor goes inside `IssueDrawer.tsx` — replace the existing `<textarea>` block
- Source badge goes inside `IssueCard.tsx` — add to top row next to AI badge

</code_context>

<specifics>
## Specific Ideas

- Source badges should use the same tiny monospace style as the existing AI badge (`text-[8px] font-mono ... border rounded px-1`)
- Realtime should feel instantaneous — tickets created by gsd-autonomous or trading events should appear without any refresh button click
- Assignee initials should be a small colored circle (pick color from first char hash) in the top-right of IssueCard

</specifics>

<deferred>
## Deferred Ideas

- Epic field on tickets — deferred to Phase 4 (AI Command Center)
- Velocity charts / burndown — deferred to Phase 4
- Roadmap timeline — deferred to Phase 4
- GSD↔Jira automation hooks — Phase 2
- Trading event triggers — Phase 3

</deferred>
