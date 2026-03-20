# Phase 3: Navigation Redesign - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Redesign the desktop sidebar and create a mobile bottom navigation bar. Polish the existing collapsible sidebar behavior with premium active state indicators and glass treatment. Add a frosted-glass mobile bottom nav (≤768px) with overflow drawer. Apply fade-in-up page transition on route change. No new routes or features — navigation UX and visual quality only.

</domain>

<decisions>
## Implementation Decisions

### Desktop Sidebar Layout & Behavior
- Keep collapsible sidebar — polish existing `useSidebar()` expand/collapse rather than remove it
- Active nav item: left accent glow bar — 3px left border + gold glow fill (`--to-surface-raised` tint + `--glow-amber`)
- Section group labels hidden when collapsed — tooltips fill the gap; reduces noise in minimized state
- Sidebar glass treatment: `glass-panel` class — consistent with Phase 2 elevated surface decision

### Mobile Bottom Navigation
- 5 items: Dashboard, Positions, Risk, Prop Firm, More (overflow)
- "More" opens a slide-up drawer (sheet) with remaining nav items
- Bottom nav appearance: frosted glass bar (`glass-panel` with `backdrop-filter: blur`), floats 8px above bottom safe area
- Active state: icon glow (`--glow-amber` drop-shadow) + label bold

### Page Transitions & Active State Animations
- Page transition: fade-in-up — matches animation already defined in globals.css (Phase 1)
- Transition trigger: on route change via layout.tsx wrapper with CSS animation class on mount
- Active glow on sidebar: static (no pulse) — continuous pulse is distracting in trading context
- Sidebar collapse animation: CSS `transition: width 250ms ease` — consistent with existing behavior

### Claude's Discretion
- Exact pixel values for bottom nav height and safe-area padding
- Tooltip delay and styling for collapsed sidebar items
- Drawer animation easing and height for mobile "More" sheet

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Sidebar.tsx` — existing sidebar with `useSidebar()` collapse, `NAV_GROUPS` (Overview, Trading, Monitoring, Analysis, Tools, System), Lucide icons, `ConnectionPill` at bottom
- `AppShell.tsx` — layout wrapper, integration point for new mobile nav
- `TopBar.tsx` — existing top bar for mobile header
- `glass-panel` CSS class — defined in globals.css, backdrop-filter + border
- `glow-amber`, `--glow-amber` — existing glow utility for active indicator
- `fade-in-up` — animation defined in globals.css from Phase 1
- `cn()` utility at `@/lib/utils`
- Lucide icons already imported in Sidebar.tsx
- `useSidebar()` hook from `@/providers/SidebarProvider`
- `usePathname()` — Next.js hook for active state detection

### Established Patterns
- Token naming: `--to-*` prefix
- `glass-panel` for elevated surfaces (Phase 2 decision)
- `--glow-amber` for primary accent glow (Phase 2: primary button glow)
- Static glow preferred over pulse in trading UI
- Section divider format: `/* ── Label ─────────────────────────── */`
- CSS transitions for sidebar width (no JS layout engine)

### Integration Points
- `Sidebar.tsx` — primary file to update for desktop nav redesign
- `AppShell.tsx` — add `MobileNav` component render, hide below 768px
- `globals.css` — add any new animation/transition utilities if needed
- New file: `MobileNav.tsx` in `frontend/src/components/layout/` for mobile bottom nav + drawer

</code_context>

<specifics>
## Specific Ideas

- Mobile bottom nav floats 8px above safe area for a premium feel
- Slide-up drawer for overflow items (not a separate page)
- Active state is purely visual — static amber glow bar on desktop, glow + bold label on mobile

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
