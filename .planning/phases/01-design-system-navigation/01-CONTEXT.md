# Phase 1: Design System & Navigation - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish the visual foundation of the trading bot dashboard redesign: Tailwind design tokens, shared component primitives (cards, skeletons, badges), typography rules, sidebar navigation, and global CSS resets. Everything downstream (Phases 2–7) builds on what Phase 1 creates. No page-level content — only the system and shell.

</domain>

<decisions>
## Implementation Decisions

### Color Palette & Tokens
- Base background: `#0a0b0d` (body), `#0f1117` (page surface), `#161b22` (card surface)
- Accent: `#00d2ff` (primary), `#3a7bd5` (secondary/hover)
- Profit green: `#2ed573`, Loss red: `#ff4757`, Warning amber: `#ffa502`
- Text: `#e8eaf0` (primary), `#8b949e` (muted), `#ffffff` (emphasis)
- Border: `rgba(255,255,255,0.08)` default, `rgba(255,255,255,0.16)` hover/focus
- All tokens defined in `tailwind.config.ts` as a `colors.terminal.*` palette extension

### Typography
- Font: Inter (loaded via `next/font/google`) — applied as CSS variable to `<html>`
- Monospace numbers: `font-variant-numeric: tabular-nums` + `font-family: 'JetBrains Mono', monospace` for all price/PnL/stat values
- Scale: `text-xs` (11px metadata), `text-sm` (13px body), `text-base` (15px default), `text-lg/xl` (headers)

### Card Component
- Style: `bg-terminal-card border border-white/8 rounded-xl backdrop-blur-sm`
- Hover: `border-white/16 shadow-lg shadow-black/20` transition
- Padding: `p-4` (compact), `p-6` (standard), `p-8` (featured)
- Export as `<Card>`, `<CardHeader>`, `<CardContent>`, `<CardFooter>` variants in `components/ui/card.tsx` (extend existing shadcn card)

### Skeleton Loading
- Color: `bg-white/6` with shimmer animation (`animate-pulse` or custom shimmer keyframe)
- Shape variants: `SkeletonText`, `SkeletonRect`, `SkeletonCircle`, `SkeletonTable`
- Usage pattern: wrap every async component in a skeleton that matches its final layout

### Sidebar Navigation
- Position: Fixed left, `w-64` expanded / `w-16` collapsed — toggle persisted in localStorage
- Structure: Logo/brand at top, nav items with icon + label, status indicator at bottom
- Active state: Left border accent (`border-l-2 border-terminal-accent`) + accent text color
- Status indicators: Green dot (bot active), Redis status, last heartbeat time
- Nav items: Dashboard, Positions, Risk, Analytics, Execution Quality, Prop Firm, Accounts, Alerts, Strategies, Settings
- Collapse: Icon-only mode, tooltip on hover showing label
- Mobile: Hidden on mobile (desktop-only app)

### Micro-Animations
- Number updates: `transition-colors duration-300` on P&L values (green/red flash on change)
- Status change: `transition-all duration-200` on badge/indicator transitions
- Page transitions: Next.js default — no custom page transition library (keep it simple)
- Sidebar collapse: `transition-all duration-200 ease-in-out`
- No Framer Motion unless already in the dependency tree (avoid new deps)

### Claude's Discretion
- Exact sidebar icon set (use Lucide icons already in shadcn)
- Exact scrollbar styling for the main content area
- Whether to use CSS variables or Tailwind config for the color tokens (prefer both — CSS vars first, Tailwind config references them)
- Exact shimmer keyframe implementation (CSS or Tailwind plugin)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/app/globals.css` (25KB) — existing global styles, will be restructured
- shadcn/ui components already in `components/ui/` — extend, don't replace
- Lucide icons already available via shadcn dependency
- `next/font` already used for font loading (check existing layout.tsx)
- `frontend/src/app/layout.tsx` — root layout where sidebar and font vars are injected

### Established Patterns
- Tailwind CSS for all styling — no CSS modules or styled-components
- shadcn/ui component pattern: `cn()` utility for class merging (`lib/utils.ts`)
- Dark mode: Already dark-themed (needs refinement, not a new direction)
- `frontend/src/providers/` — global providers (Auth, Query, etc.) mounted in layout

### Integration Points
- `frontend/src/app/layout.tsx` — sidebar wraps all pages here
- `frontend/tailwind.config.ts` — add `terminal.*` color palette extension here
- `frontend/src/app/globals.css` — CSS custom properties and base styles
- All pages in `frontend/src/app/**/page.tsx` will receive updated styles automatically via layout

</code_context>

<specifics>
## Specific Ideas

- Aesthetic direction: "dark pro trading terminal" — Bloomberg/TradingView feel, NOT a consumer app
- User gave full creative control — "do what you think is best"
- JetBrains Mono is preferred for numbers/prices (industry standard for trading terminals)
- Glass-morphism on cards subtle, not overdone — `backdrop-blur-sm` not heavy blur
- No external animation library — Tailwind transitions only to keep bundle lean

</specifics>

<deferred>
## Deferred Ideas

- Keyboard shortcuts for navigation — v2 requirement
- Dark/light toggle — v2 requirement
- Notification center panel in sidebar — v2 requirement
- Mobile responsive layout — out of scope this milestone

</deferred>
