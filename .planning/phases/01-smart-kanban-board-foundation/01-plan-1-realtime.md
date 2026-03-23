# Phase 1 Plan 1: Supabase Realtime Subscription

## Goal
Replace manual poll-on-load with Supabase realtime subscription so the Kanban board updates automatically when tickets are created, updated, or deleted from any source (gsd-autonomous, backend API, trading events, other sessions).

## Requirements
- UI-01: Kanban board auto-populates tickets in real-time

## Implementation

### File: `jira/src/app/(app)/board/page.tsx`

Add a `useEffect` that sets up a Supabase realtime channel after initial load:

```typescript
// After the existing load useEffect:
useEffect(() => {
  const sb = getSupabase();
  const channel = sb
    .channel('board-issues')
    .on(
      'postgres_changes',
      { event: '*', schema: 'public', table: 'project_tickets' },
      (payload) => {
        if (payload.eventType === 'INSERT') {
          setIssues((prev) => {
            if (prev.find((i) => i.id === (payload.new as Issue).id)) return prev;
            return [payload.new as Issue, ...prev];
          });
        } else if (payload.eventType === 'UPDATE') {
          setIssues((prev) =>
            prev.map((i) => i.id === (payload.new as Issue).id ? payload.new as Issue : i)
          );
        } else if (payload.eventType === 'DELETE') {
          setIssues((prev) => prev.filter((i) => i.id !== (payload.old as Issue).id));
        }
      }
    )
    .subscribe();

  return () => { sb.removeChannel(channel); };
}, []);
```

Also import `getSupabase` from `@/lib/supabase`.

## Verification
- Open board in browser
- Create a ticket via `POST /api/tickets` (curl or Postman)
- Ticket appears on board without manual refresh within 2 seconds
