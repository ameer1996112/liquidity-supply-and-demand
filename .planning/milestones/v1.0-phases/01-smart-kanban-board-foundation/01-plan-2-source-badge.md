# Phase 1 Plan 2: Source Badge on IssueCard + Assignee Avatar

## Goal
Add a "source" badge and assignee initials avatar to IssueCard so users can immediately see where a ticket came from (GSD phase, trading event, AI, or manually created).

## Requirements
- UI-03: Rich ticket metadata visible on cards

## Implementation

### File: `jira/src/components/IssueCard.tsx`

Add source derivation function and render badge + assignee avatar:

**Source derivation (above component):**
```typescript
function getSourceBadge(issue: Issue): { label: string; color: string } | null {
  if (issue.title?.startsWith('Phase ') && issue.title?.includes(':')) {
    return { label: 'GSD', color: '#a78bfa' }; // violet
  }
  if (issue.signal_id != null) {
    return { label: 'SIG', color: '#38bdf8' }; // sky blue
  }
  return null;
}

function getAssigneeColor(name: string): string {
  const colors = ['#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#ef4444', '#f97316'];
  const idx = name.charCodeAt(0) % colors.length;
  return colors[idx];
}
```

**In JSX top row (next to existing AI badge):**
```tsx
{/* Source badge */}
{(() => {
  const src = getSourceBadge(issue);
  return src ? (
    <span
      className="text-[8px] font-mono border rounded px-1"
      style={{ color: src.color, borderColor: src.color + '40', background: src.color + '15' }}
    >
      {src.label}
    </span>
  ) : null;
})()}

{/* Assignee avatar */}
{issue.assignee && (
  <span
    className="flex h-4 w-4 items-center justify-center rounded-full text-[7px] font-bold text-white"
    style={{ background: getAssigneeColor(issue.assignee) }}
    title={issue.assignee}
  >
    {issue.assignee.charAt(0).toUpperCase()}
  </span>
)}
```

## Verification
- A ticket with title "Phase 1: Smart Kanban" shows violet "GSD" badge
- A ticket with `signal_id` set shows sky "SIG" badge
- A ticket with `assignee` shows a colored initial circle
