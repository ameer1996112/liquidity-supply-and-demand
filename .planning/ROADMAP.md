# Roadmap: Trinity Trading System — UI Redesign

## v1.0: Premium Dark Trading Terminal

**Goal:** Complete UI overhaul — premium dark fintech aesthetic, mobile-first responsive layout, cohesive design system applied uniformly across all pages.

**Phases:** 8 | **Requirements:** 31

---

### Phase 1: Design System Foundation

**Goal:** Consolidate and formalize the design system — audit existing tokens, fill gaps in typography/spacing scales, and ensure every visual primitive is defined as a reusable CSS custom property.

**Requirements:** DSYS-01, DSYS-02, DSYS-03, DSYS-04

**Success Criteria:**
1. Complete color token set documented and defined as CSS custom properties (no hardcoded hex values remain in any component)
2. Typography scale with 6+ size steps, defined weights, and line-height ratios is usable via utility classes
3. Spacing scale (4px-based) defined and applied consistently across components
4. Glass, glow, and gradient tokens are consolidated and documented as reusable utility classes

**Plans:** 2 plans

Plans:
- [x] 01-01-PLAN.md — Color tokens (semantic status) + typography scale + font weights (DSYS-01, DSYS-02)
- [x] 01-02-PLAN.md — Spacing scale + radius aliases + glass variants + gradient tokens + TOKEN-AUDIT.md (DSYS-03, DSYS-04)

| Plans | Progress |
|-------|----------|
| 2 | 2/2 complete — Phase 1 DONE |

---

### Phase 2: Core Component Library

**Goal:** Restyle all base UI components (buttons, cards, tables, badges, inputs, loaders) to use design system tokens exclusively, ensuring consistency across the entire application.

**Requirements:** COMP-01, COMP-02, COMP-03, COMP-04, COMP-05, COMP-06

**Success Criteria:**
1. Every button variant (primary, secondary, ghost, destructive) renders with token-based colors, consistent padding, and hover states
2. Card/panel components consistently use glass-panel or to-panel styling depending on elevation
3. All tables use consistent header/row styling with hover highlight and dense mode option
4. Badge styling is uniform (live/paper, long/short, trigger types)
5. All form inputs render with dark-theme styling using design tokens
6. Skeleton/shimmer loading pattern is implemented and used on at least 3 pages

| Plans | Progress |
|-------|----------|
| — | Not started |

---

### Phase 3: Navigation Redesign

**Goal:** Redesign desktop sidebar and create mobile bottom navigation bar. Clean, organized, with active state indicators and smooth transitions.

**Requirements:** NAV-01, NAV-02, NAV-03

**Success Criteria:**
1. Desktop sidebar has clear section grouping, icon + label, and active state glow indicator
2. Mobile bottom nav bar appears below 768px with 5 key sections accessible via single tap
3. Page transitions use fade-in-up animation with no layout shift

| Plans | Progress |
|-------|----------|
| — | Not started |

---

### Phase 4: Dashboard Redesign

**Goal:** Transform the dashboard into an eye-catching command center with hero metrics, live signal feed, and WebSocket status — the first screen that wows.

**Requirements:** DASH-01, DASH-02, DASH-03, DASH-04

**Success Criteria:**
1. Hero section shows 4-6 key KPIs (PnL, win rate, active positions, daily trades) in premium glow cards
2. Signal feed shows latest signals with side-colored accents, animated entry, and live timestamp
3. WebSocket status indicator is visible in the header/hero with green/amber/red dot + label
4. Dashboard layout stacks properly on mobile with all metrics and controls accessible

| Plans | Progress |
|-------|----------|
| — | Not started |

---

### Phase 5: Risk & Prop Firm Redesign

**Goal:** Redesign risk monitor and prop firm challenge tracker — the highest-priority monitoring pages — with clear metric hierarchy and visual gauges.

**Requirements:** RISK-01, RISK-02, RISK-03

**Success Criteria:**
1. Risk monitor has tiered layout: critical metrics (drawdown, daily loss) at top with color-coded status, detail panels below
2. Prop firm tracker has visual progress bars/gauges showing challenge metrics against limits
3. Both pages are fully responsive on mobile with metric cards stacking vertically and controls accessible

| Plans | Progress |
|-------|----------|
| — | Not started |

---

### Phase 6: Remaining Pages Redesign

**Goal:** Apply the design system consistently to all remaining pages — positions, analytics, accounts, and all secondary pages.

**Requirements:** PAGE-01, PAGE-02, PAGE-03, PAGE-04

**Success Criteria:**
1. Positions page uses glass-panel cards, consistent table styling, and proper mobile layout
2. Analytics page has consistent chart styling (recharts theme tokens) and responsive layout
3. Accounts page uses consistent card/list styling with status indicators
4. All secondary pages (Board, Backtest, Rules, Journal, Execution Quality, Settings, Scanner, Strategies, Alerts) use design system tokens and have basic responsive layout

| Plans | Progress |
|-------|----------|
| — | Not started |

---

### Phase 7: Responsive Polish

**Goal:** Systematic mobile-first pass across all pages — ensure every page works perfectly on 320px-480px screens with full control (not just read-only).

**Requirements:** RESP-01, RESP-02, RESP-03

**Success Criteria:**
1. All pages tested and functional at 360px width — no overflow, no hidden controls
2. Data tables have mobile strategy (horizontal scroll with sticky first column, or card view)
3. Charts are readable and interactive on mobile (tooltips accessible, legends don't overlap)

| Plans | Progress |
|-------|----------|
| — | Not started |

---

### Phase 8: Micro-Interactions & Final Polish

**Goal:** Add the finishing touches — loading skeletons, page transitions, number animations, hover effects — that make the UI feel alive and premium.

**Requirements:** ANIM-01, ANIM-02, ANIM-03, ANIM-04

**Success Criteria:**
1. Skeleton loading states appear on all data-fetching pages during load
2. Page transitions use consistent fade-in-up animation
3. Numeric values (PnL, balance, metrics) use AnimatedNumber component for smooth transitions
4. All interactive cards/buttons have hover effects (lift, glow, border-color shift)

| Plans | Progress |
|-------|----------|
| — | Not started |

---

**Coverage:** 31 requirements → 8 phases → 100% mapped ✓

---
*Roadmap created: 2026-03-19*
*Last updated: 2026-03-19 — Phase 1 plans created (01-01, 01-02)*
