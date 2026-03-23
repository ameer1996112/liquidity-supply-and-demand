# Jira Board Sprint & Timestamp Upgrade — Design Spec

**Date:** 2026-03-23  
**Status:** Approved

## Overview

Upgrade the existing Jira kanban board from a simple status-based view to a full sprint-aware board with:
- Sprint tabs for filtering (all sprints + backlog)
- Sprint progress bar in header
- "Complete Sprint" with auto-migration of incomplete tickets
- Quick sprint creation from the board
- Timestamps ("Created X ago") on every card (already partially present)

No DB schema changes needed — `jira_sprints` and `project_tickets` tables already have all required columns.

---

## Decisions

| Feature | Decision |
|---|---|
| Sprint navigation | Tabs row (all sprints + Backlog tab) |
| Board filtering | Each tab filters board to that sprint's tickets |
| Timestamps | "Created X ago" — already rendered via `relativeTime()` |
| Complete Sprint | Auto-move all non-`done` tickets to next sprint |
| Sprint creation | Quick-create from board + full CRUD on `/sprints` page |

---

## Components

### 1. SprintTabs (new component)

**Location:** `src/components/SprintTabs.tsx`

A horizontal tab bar rendered below the board header. Displays:
- One tab per sprint, ordered by `created_at` desc, labelled with sprint name
- Active sprint gets an amber dot indicator
- "Backlog" tab at the end (shows tickets with `sprint_id = null`)
- "New Sprint" button (opens `NewSprintModal`)
- "Complete Sprint" button shown only on the active sprint tab

**Props:** `sprints`, `selectedSprintId`, `onSelect`, `onCompleteSprint`, `onSprintCreated`

### 2. NewSprintModal (new component)

**Location:** `src/components/NewSprintModal.tsx`

Modal with fields: name (required), goal, start\_date, end\_date. Reuses the same form already in `/sprints/page.tsx` — extract into shared component.

**On submit:** calls `createSprint()` from `supabase.ts`, calls `onSprintCreated(sprint)` callback.

### 3. Board page changes

**Location:** `src/app/(app)/board/page.tsx`

- Add `selectedSprintId: number | null | 'backlog'` state  
- Default to active sprint's ID on load  
- `byStatus(status)` filtered further by selected sprint:  
  - If `'backlog'`: `sprint_id === null`  
  - If `number`: `sprint_id === selectedSprintId`  
  - If `null` (no sprint selected): show all  
- Render `<SprintTabs>` below header  
- Sprint progress bar in header (done / total, % + days left)

### 4. Complete Sprint logic

**Location:** board page `handleCompleteSprint(sprint)`

```
1. Find or create next planned sprint
2. Bulk-update all non-done tickets in this sprint to next sprint's sprint_id
3. PATCH sprint status → 'completed'
4. Set selectedSprintId to next sprint (or activeSprint if newly activated)
```

Uses existing `updateIssue()` and `updateSprint()` from `supabase.ts`.  
Needs new helper `updateIssues(ids, payload)` for bulk update (or Promise.all of individual calls).

### 5. Sprints page — edit support

**Location:** `src/app/(app)/sprints/page.tsx`

Add inline edit for name/goal/dates on each sprint card (currently read-only after creation). Small "Edit" button → inline form or re-uses `NewSprintModal` in edit mode.

---

## Data Flow

```
Board loads → fetchSprints() + fetchIssues({ includeArchived: false })
                   ↓
SprintTabs renders sprint list
User selects sprint tab
                   ↓
byStatus() filters issues by status AND sprint_id
                   ↓
User clicks "Complete Sprint"
                   ↓
handleCompleteSprint():
  - bulk-update incomplete tickets → next sprint_id
  - updateSprint(id, { status: 'completed' })
  - reload
```

---

## Files Changed

| File | Change |
|---|---|
| `src/components/SprintTabs.tsx` | **NEW** — sprint tab bar + "New Sprint" + "Complete Sprint" |
| `src/components/NewSprintModal.tsx` | **NEW** — extracted from sprints/page.tsx, reusable |
| `src/app/(app)/board/page.tsx` | **MODIFY** — add sprint filtering + SprintTabs + progress bar |
| `src/app/(app)/sprints/page.tsx` | **MODIFY** — use NewSprintModal, add edit support |
| `src/lib/supabase.ts` | **MODIFY** — add `bulkUpdateIssues()` helper |

No DB migrations required.

---

## Verification

1. Board loads filtered to active sprint by default
2. Clicking tab changes board contents correctly
3. "Backlog" tab shows only unassigned tickets
4. "Complete Sprint" moves incomplete tickets to next sprint and marks sprint done
5. "New Sprint" from board creates sprint and selects it
6. Sprints page edit works end-to-end
7. All existing tests pass
