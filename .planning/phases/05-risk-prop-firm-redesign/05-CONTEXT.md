# Phase 5: Risk & Prop Firm Redesign — Context

**Phase:** 05
**Date:** 2026-03-20
**Status:** CONTEXT CAPTURED

## Phase Goal
Redesign risk monitor and prop firm challenge tracker with clear metric hierarchy, premium card system, and visual gauges.

## Pages in Scope
- `frontend/src/app/risk/page.tsx` (710 lines)
- `frontend/src/app/prop-firm/page.tsx` (516 lines)
- `frontend/src/components/risk/` (GuardRailToggle, KillSwitchConfirmDialog, RiskBar, RiskKnob, SymbolOverrideTable)

## Current State
### Risk Page
- Has: CircularGauge, CompositeRiskScore SVG ring, PanelCard wrapper, Guard Rails section
- Problem: `PanelCard` uses `tv-card` (legacy) — needs upgrade to `glow-card`
- Problem: CompositeRiskScore is one equal column in a 3-col grid — no visual hierarchy
- Grid: `grid-cols-1 lg:grid-cols-3` for score + 2 gauges, then `grid-cols-1 lg:grid-cols-2` for detail panels

### Prop Firm Page
- Has: ChallengeHeader, HealthScoreGauge, ChallengeMetrics, ChallengeRules, PerformanceSummary, CalendarPnlView
- Problem: "Account Overview" container = `tv-card p-6` (legacy)
- Problem: "Daily Performance Calendar" container = `tv-card p-6` (legacy)

## User Decisions (Accepted)

### Area 1: Risk Page — PanelCard Upgrade Scope → **A (All panels)**
- Upgrade ALL `PanelCard` instances to `glow-card` + `to-panel-header`
- Affects: Daily Risk Status, Position Limits, Drawdown Status, Active Settings, Guard Rails Status, Symbol Overrides
- Implementation: Change `PanelCard` component — replace `tv-card` wrapper with `glow-card`, replace header `div` with `to-panel-header` class
- Also: change `CompositeRiskScore` from `tv-card` to `glow-card`

### Area 2: CompositeRiskScore Positioning → **A (Hero treatment)**
- Move risk score to full-width top hero row ABOVE the gauges
- Row layout: full-width `glow-card` with colored left border + background tint matching severity
  - Critical (≥75): `border-l-4 border-[var(--to-short)] bg-[var(--to-short)]/5`
  - Elevated (≥50): `border-l-4 border-[var(--to-warning)] bg-[var(--to-warning)]/5`
  - Moderate (≥25): `border-l-4 border-[var(--to-accent-blue)]/60 bg-[var(--to-accent-blue)]/5`
  - Low (<25): `border-l-4 border-[var(--to-long)] bg-[var(--to-long)]/5`
- Content: score ring on left + severity label + mini breakdown bars on right, all in one row
- Gauges (Daily Loss + Drawdown) remain in the `lg:grid-cols-2` below the hero row

### Area 3: Prop Firm — Container Upgrade → **A (glass-panel)**
- Account Overview container: `tv-card p-6` → `glass-panel p-6`
- Daily Performance Calendar container: `tv-card p-6` → `glass-panel p-6`
- Consistent with WaitingBanner treatment applied in Phase 4

## Constraints
- All changes are visual/class upgrades only — no data model changes
- Both `useRiskMonitor` and `usePropFirmMetrics` hooks remain untouched
- Existing `CircularGauge`, `HealthScoreGauge`, `ChallengeMetrics`, etc. components — preserve as-is
- TypeScript must compile with zero errors after all changes
