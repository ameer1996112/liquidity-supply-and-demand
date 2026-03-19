# ROADMAP.md — Frontend Redesign Milestone

**Milestone:** v1.0 — Frontend Redesign
**Defined:** 2026-03-19
**Status:** In Progress

## Overview

Complete visual redesign of the trading bot dashboard frontend. 7 phases from design system foundation through final polish. Each phase is independently deployable.

---

## Phase 1: Design System & Navigation

**Goal:** Establish the design foundation and unified navigation that all other phases build on.

**Requirements:** DS-01, DS-02, DS-03, DS-04, DS-05, DS-06, NAV-01, NAV-02, NAV-03, NAV-04

**Success Criteria:**
1. Color palette tokens are defined in Tailwind config and used in at least one sample component
2. Sidebar navigation renders on all pages with correct active state, icons, and collapse behavior
3. Card component with glass-morphism style is reusable and documented
4. Skeleton loading component is reusable and renders correctly
5. All monospace number styles are applied to price/number elements globally

---

## Phase 2: Dashboard (Main Page)

**Goal:** Redesign the main dashboard as a real-time command center for the trading bot.

**Requirements:** DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06

**Success Criteria:**
1. Signal feed displays real-time signals with AI verdict and guardrail status badges
2. P&L summary widget shows today's P&L with correct color-coding (green/red)
3. Bot status panel shows trading mode, last signal time, and active/inactive state
4. Risk snapshot widget shows daily loss %, drawdown %, and prop firm proximity
5. Signal card expands in-place to show AI rationale and guardrail breakdown
6. Dashboard layout fits without vertical scroll for critical widgets on 1080p screen

---

## Phase 3: Positions & Risk Pages

**Goal:** Redesign positions and risk monitoring pages with live data and visual risk indicators.

**Requirements:** POS-01, POS-02, POS-03, POS-04, RISK-01, RISK-02, RISK-03, RISK-04, RISK-05

**Success Criteria:**
1. Positions table shows all open positions with correct columns and heat-colored P&L rows
2. Positions update within 10 seconds of real changes
3. Risk gauges render for daily loss and drawdown with correct color zones (green/amber/red)
4. Portfolio VaR, sector, and correlation cards display and update correctly
5. Empty state renders on positions page when no open positions exist
6. Warning styling activates when any risk metric exceeds 80% of its limit

---

## Phase 4: Analytics & Execution Quality Pages

**Goal:** Redesign analytics and execution quality pages with dark-themed interactive charts.

**Requirements:** ANA-01, ANA-02, ANA-03, ANA-04, EXQ-01, EXQ-02, EXQ-03, EXQ-04

**Success Criteria:**
1. Equity curve chart renders with dark theme, glowing fill, and hover tooltips
2. Win rate heatmap or grouped bar chart renders by symbol and session
3. KPI cards at top of analytics show correct metrics from API
4. Execution trace timeline renders each signal's phase durations correctly
5. Latency breakdown chart shows bot vs broker latency correctly
6. Slippage chart renders with real data from trace API
7. Filter controls work for symbol, date range, and outcome on EXQ page

---

## Phase 5: Prop Firm & Accounts Pages

**Goal:** Redesign prop firm challenge tracker and account management pages.

**Requirements:** PROP-01, PROP-02, PROP-03, PROP-04, PROP-05, ACC-01, ACC-02, ACC-03

**Success Criteria:**
1. Prop firm page shows challenge phase badge, account name, and broker correctly
2. Daily loss and drawdown progress bars render with correct color zones
3. Profit target progress renders with % to target
4. Consistency tracker shows best day % vs 40% limit
5. Account cards show balance, equity, phase badge, and connection status
6. Disconnected/error accounts are visually distinct from healthy accounts

---

## Phase 6: Alerts, Settings & Strategies Pages

**Goal:** Redesign the remaining utility pages — alerts, settings, and strategies.

**Requirements:** ALRT-01, ALRT-02, SET-01, SET-02

**Success Criteria:**
1. Alerts page shows a filterable list with severity badges (info/warning/critical)
2. Alert items are visually distinct by severity with color and icon
3. Settings page uses organized form sections with clear labels
4. Strategies page shows active strategy cards with key config values
5. All three pages use the design system established in Phase 1

---

## Phase 7: Performance, Polish & QA

**Goal:** Optimize loading performance, fix any cross-page inconsistencies, and validate all pages pass a final quality bar.

**Requirements:** PERF-01, PERF-02, PERF-03, PERF-04

**Success Criteria:**
1. All pages have skeleton loading states — no empty/null flash on first load
2. React Query stale/cache times are tuned — no unnecessary refetches visible in network tab
3. Supabase Realtime used for signals and positions where previously polling was used
4. `npm run build` passes with no new errors compared to baseline
5. ESLint passes with no new warnings compared to baseline
6. All 7 phases are visually consistent — no page feels designed separately

---

## Coverage

| # | Phase | Requirements | Status |
|---|-------|-------------|--------|
| 1 | Design System & Navigation | DS-01–06, NAV-01–04 | Not Started |
| 2 | Dashboard (Main Page) | DASH-01–06 | Not Started |
| 3 | Positions & Risk | POS-01–04, RISK-01–05 | Not Started |
| 4 | Analytics & Execution Quality | ANA-01–04, EXQ-01–04 | Not Started |
| 5 | Prop Firm & Accounts | PROP-01–05, ACC-01–03 | Not Started |
| 6 | Alerts, Settings & Strategies | ALRT-01–02, SET-01–02 | Not Started |
| 7 | Performance, Polish & QA | PERF-01–04 | Not Started |

**7 phases** | **44 requirements mapped** | All v1 requirements covered ✓

---
*Roadmap created: 2026-03-19*
