---
plan: 04-02
phase: 4
status: complete
completed: 2026-03-20
---

# Plan 04-02 Summary: Dashboard Page — Bento Grid, Signal Animations, Mobile Stack

## What Was Built
- Imported `cn` from `@/lib/utils` and `ConnectionPill` into `page.tsx`
- Added `ConnectionPill` to the dashboard header (between `SessionRing` and `tf-badge`)
- Upgraded `Today PnL` StatCard with `hero={true}` and `className='col-span-1 xl:col-span-2 animate-fade-in-up'` — creates bento hero span at xl breakpoint
- `WaitingBanner` container upgraded from `to-panel` to `glass-panel border-[var(--to-warning)]/30 p-4` for premium frosted glass treatment
- Status check dots in `WaitingBanner` changed from text `●` to `<span className='h-2 w-2 rounded-full inline-block ...'/>` — proper green/red dots
- Added `showLog` state + mobile log toggle button (`xl:hidden`) + conditional `hidden xl:block` on LiveLog section
- `SignalTable` row accent: changed `rowAccentColor()` from status-based to side-based (BUY/LONG→green, SELL/SHORT→red)
- `SignalTable` row accent: added `animate-slide-in-right` class to the accent span element
- `SignalTable` timestamp: swapped primary/secondary — relative time "Xm ago" is now primary with `title` attr for absolute time tooltip; HH:MM is now secondary dim text

## Key Files
### key-files:
modified:
  - frontend/src/app/page.tsx
  - frontend/src/components/dashboard/SignalTable.tsx

## Deviations
- Slide-in animation applied to `row_accent` span rather than the full `<tr>` (DataTable doesn't expose `rowClassName` prop) — visual effect is equivalent for the colored indicator

## Self-Check
- [x] ConnectionPill imported and rendered in header
- [x] hero StatCard with xl:col-span-2 in page.tsx
- [x] WaitingBanner glass-panel treatment with amber border
- [x] showLog state and mobile toggle button
- [x] SignalTable side-based accent (to-long / to-short)
- [x] animate-slide-in-right on signal accent spans
- [x] Relative timestamp as primary, absolute as title tooltip
- [x] TypeScript: zero errors
- [x] Commit: dd498a2
