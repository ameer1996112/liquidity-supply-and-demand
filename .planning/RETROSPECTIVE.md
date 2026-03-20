# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

---

## Milestone: v1.0 — Premium Dark Trading Terminal

**Shipped:** 2026-03-20  
**Phases:** 8 | **Plans:** 12 | **Duration:** 29 days (2026-02-19 → 2026-03-20)

### What Was Built

- **Design system:** 31 semantic CSS custom properties (`--to-*` tokens), typography scale, spacing, glass/glow utilities. Zero hardcoded hex values in components.
- **Component library:** `glow-card`, `glass-panel`, `to-panel-header` system. All shadcn/ui primitives (button, badge, card, table, input, skeleton) restyled with `--to-*` tokens.
- **Navigation:** Left-border active state glow on sidebar, `MobileNav` bottom bar (≤768px), keyboard shortcut modal, Command Palette.
- **Dashboard:** Hero bento KPI grid (1 hero + 3 standard), `ConnectionPill` (LIVE/PAPER/RECONNECTING), side-based signal row borders, `WaitingBanner` glass treatment.
- **Risk page:** `CompositeRiskScore` promoted to full-width hero row with severity-based left border (Critical=red/Elevated=amber/Moderate=blue/Low=green).
- **Global sweep:** 98 total `tv-card` → `glow-card` replacements across 49 files. Zero legacy card class remaining.
- **Mobile:** `DataTable min-w-max` for 360px horizontal scroll. All 14 pages with `animate-fade-in-up`.

### What Worked

- **Design system first** — building tokens in Phase 1 made every subsequent phase faster and lower-risk. Class swaps in Phases 6-7 were trivial precisely because the system was solid.
- **Smart discuss pattern** — presenting 2-3 grey areas with A/B/C options before execution kept decisions clean and fast. User never needed to think from scratch.
- **Direct execution without worktrees** — for a pure frontend redesign, working directly on main was safe and reduced overhead.
- **Sed for bulk replacements** — `sed -i '' "s/tv-card/glow-card/g"` across multiple files at once was the right tool. Fast, verifiable, low error rate.

### What Was Inefficient

- **Phase 6 only swept page.tsx files, not components** — found 67 more `tv-card` instances in Phase 7 across 40 component files. Should have scoped the sweep to `frontend/src/` (all .tsx) from the start, not just `app/**/page.tsx`.
- **REQUIREMENTS.md checkbox state not maintained** — COMP-01 through COMP-06, NAV-01 through NAV-03 were all shipped but left unchecked. Future: use GSD tools to check off reqs as phases complete.
- **Missing SUMMARY.md on Phases 3, 6** — disk_status showed "planned" for these phases even though they were executed autonomously. Summary files create the phase completion record.

### Patterns Established

- **`glow-card` + `to-panel-header` = standard panel** — use this everywhere (not `glass-panel` + ad-hoc headers)
- **`glass-panel` = elevated ambient containers** — WaitingBanner, prop firm section wrappers, info banners
- **Severity-based theming** — left border + background tint by severity (Critical/Elevated/Moderate/Low) is the established risk indicator pattern
- **`animate-fade-in-up` on root div** — standard page entry, apply to the first return div in every page component
- **DataTable scroll pattern** — `overflow-auto` wrapper + `min-w-max` on table = correct mobile scroll formula

### Key Lessons

1. **Scope component files alongside page files** — sweeps should always target `src/**/*.tsx`, never just `app/**/page.tsx`
2. **Write SUMMARY.md even for class-swap phases** — it completes the GSD record and prevents `disk_status: planned` confusion
3. **Design system investment pays off immediately** — Phase 1-2 token work meant Phases 5-8 were class swaps, not redesigns
4. **Grey areas resolved in 1 message** — A/B/C options with a clear recommended answer = instant unblock

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Duration | Key Pattern |
|---|---|---|---|---|
| v1.0 | 8 | 12 | 29 days | Design system → sweeps |
