# Phase 3: Navigation Redesign — Research

**Researched:** 2026-03-20
**Status:** Complete

## Executive Summary

Phase 3 is a targeted polish pass on existing navigation infrastructure plus one new component (MobileNav). Most of the heavy lifting is already in place — `sidebar-glass`, amber glow active states, collapsible behavior, and page transitions via `animate-fade-in-up` are all done. The phase adds:

1. **Left-border active indicator** — 3px amber left bar on active sidebar items (replaces/augments current background-only active state)
2. **MobileNav.tsx** — New fixed-bottom frosted-glass nav with 5 items + slide-up Sheet overflow drawer
3. **AppShell.tsx integration** — Inject MobileNav, adjust content margins on mobile to avoid overlap

## Existing Code Analysis

### Sidebar.tsx (`.../components/layout/Sidebar.tsx`)

**Current state:**
- Uses `NAV_GROUPS` (6 groups: Overview, Trading, Monitoring, Analytics, Strategy, Ops)
- `useSidebar()` → `isCollapsed`, `toggleCollapse` — already works
- `usePathname()` for active route detection — already works
- Active state: `bg-[var(--to-warning)]/10 text-[var(--to-warning)] border border-[var(--to-warning)]/20` — amber background + border ✓
- `nav-active-glow` span rendered inside active links — CSS utility exists
- `sidebar-glass` class on `<aside>` — frosted glass ✓
- Section group labels: centered separator with `--to-text-dim` uppercase mono text — already implemented
- Tooltips via TooltipProvider on collapsed items — already implemented
- `transition-all duration-200 ease-in-out` on width change — already implemented

**What's missing:**
- No explicit **left border bar** (3px amber line on left edge of active items) — current active state uses `border` on all sides, not left-only accent bar
- Section labels are **shown** even when collapsed (they're wrapped in `{!isCollapsed && ...}`) — actually fine, this is already correct

**What to add:**
- Replace or augment active border with a left-only accent: `border-l-[3px] border-l-[var(--to-warning)] border-y-0 border-r-0` + `pl-[calc(0.625rem-3px)]` to compensate for border thickness. This creates the premium "left glow bar" look while keeping amber background.

### AppShell.tsx (`.../components/layout/AppShell.tsx`)

**Current state:**
- Page transitions: `key={pathname}` + `animate-fade-in-up` on main content div — **already complete** (NAV-03 ✓ out of the box)
- Sidebar margin: `ml-56` / `ml-14` for expanded/collapsed — desktop only, no mobile handling
- No `MobileNav` rendered anywhere yet
- `<main>` has `p-3 sm:p-4` padding — needs `pb-20 md:pb-3` on mobile to clear bottom nav

**Integration points:**
- Add `<MobileNav />` import + render inside the shell (after `<Sidebar />`)
- Add `pb-safe` / `pb-20` to `<main>` element for mobile safe-area clearance
- Remove `ml-56`/`ml-14` on mobile (add `md:ml-56` / `md:ml-14` responsive prefix)

### globals.css — Animations

```css
/* Already defined: */
@keyframes fade-in-up { ... }
.animate-fade-in-up { animation: fade-in-up 0.25s ease-out forwards; }
```

Page transitions are **already complete**. No new animation tokens needed for Phase 3.

### shadcn/ui Sheet

`frontend/src/components/ui/sheet.tsx` — present (used in existing components). The `Sheet` with `side="bottom"` is the standard approach for the mobile overflow drawer. Already imported in the project.

## Implementation Approach

### Plan A: Desktop Sidebar Polish (small change)

Modify the active link `className` in Sidebar.tsx:
- Change `border border-[var(--to-warning)]/20` → `border-l-[3px] border-l-[var(--to-warning)]/60 border-t-0 border-r-0 border-b-0`
- Adjust left padding to compensate: `px-2.5` → `pl-[8px] pr-2.5` (10px - 3px border = 7px visual, ~same as before)
- Keep `bg-[var(--to-warning)]/10` — subtle amber fill remains
- Keep `nav-active-glow` span — existing glow pseudo-element

### Plan B: New MobileNav.tsx Component

```
File: frontend/src/components/layout/MobileNav.tsx
```

**Structure:**
```tsx
// Fixed bottom bar, visible only <768px (hidden md:hidden)
// 5 items: Dashboard, Positions, Risk, Prop Firm, More
// Active: icon glow + bold label
// "More" opens shadcn Sheet (side="bottom") with remaining nav items
```

**Nav items for bottom bar (5):**
1. Dashboard → `/` (LayoutDashboard)
2. Positions → `/positions` (Crosshair)  
3. Risk → `/risk` (Gauge)
4. Prop Firm → `/prop-firm` (Trophy)
5. More → opens Sheet (MoreHorizontal icon)

**Sheet contents (overflow):**
- Accounts, Exec Quality, Scanner, Alerts, Analytics, Backtest, Strategies, Rules, Journal, Board, Settings

**Styling:**
- `fixed bottom-0 left-0 right-0 z-50 md:hidden`
- `glass-panel border-t border-[var(--to-border)]`
- `safe-area-inset-bottom` padding (`pb-[env(safe-area-inset-bottom,8px)]`)
- Height: `h-16` (64px)
- Active state: `text-[var(--to-warning)]` + `filter: drop-shadow(var(--glow-amber))`

### Plan C: AppShell Integration

1. `import { MobileNav } from './MobileNav'`
2. Render `<MobileNav />` inside the shell (after `<Sidebar />`)
3. Change `ml-56`/`ml-14` → `md:ml-56`/`md:ml-14` (no margin on mobile)
4. Add `pb-20 md:pb-0` to `<main>` to clear bottom nav on mobile

## Files to Modify

| File | Change | Scope |
|------|--------|-------|
| `frontend/src/components/layout/Sidebar.tsx` | Left border active indicator | Small — 2 className changes |
| `frontend/src/components/layout/AppShell.tsx` | Add MobileNav, responsive margins, mobile padding | Medium — 4 changes |
| `frontend/src/components/layout/MobileNav.tsx` | **NEW** — Mobile bottom nav + Sheet drawer | New file ~120 lines |

## Validation Architecture

### NAV-01: Desktop Sidebar Active State
- `grep -r "border-l-\[3px\]" frontend/src/components/layout/Sidebar.tsx` → must match
- Visual: 3px amber left bar visible on active route

### NAV-02: Mobile Bottom Nav
- `test -f frontend/src/components/layout/MobileNav.tsx` → true
- `grep -c "Sheet" frontend/src/components/layout/MobileNav.tsx` → ≥1 (drawer exists)
- `grep "md:hidden" frontend/src/components/layout/MobileNav.tsx` → must match
- `grep '"/positions\|/risk\|/prop-firm"' frontend/src/components/layout/MobileNav.tsx` → items present

### NAV-03: Page Transitions
- `grep "animate-fade-in-up" frontend/src/components/layout/AppShell.tsx` → already passes
- `grep 'key={pathname}' frontend/src/components/layout/AppShell.tsx` → already passes

### AppShell Integration
- `grep "MobileNav" frontend/src/components/layout/AppShell.tsx` → must match
- `grep "md:ml-56" frontend/src/components/layout/AppShell.tsx` → must match
- `grep "pb-20" frontend/src/components/layout/AppShell.tsx` → must match

## RESEARCH COMPLETE
