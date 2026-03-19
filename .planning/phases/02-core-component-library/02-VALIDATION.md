---
phase: 2
slug: core-component-library
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | None (visual/snapshot testing not configured in frontend) |
| **Config file** | No jest.config.*, vitest.config.*, or playwright.config.* found |
| **Quick run command** | `cd frontend && npm run build` |
| **Full suite command** | Manual visual inspection across 5 target pages |
| **Estimated runtime** | ~30 seconds (build check) |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npm run build` — catches TypeScript errors and class string regressions
- **After every plan wave:** Visual inspection of all 5 target pages in browser (Dashboard, Positions, Analytics, Risk, PropFirm)
- **Before `/gsd:verify-work`:** All 6 component files verified visually + build green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Req | Wave | Test Type | Automated Command | Status |
|---------|-----|------|-----------|-------------------|--------|
| button.tsx restyle | COMP-01 | 1 | build + visual | `cd frontend && npm run build` | ⬜ pending |
| card.tsx → glass-panel | COMP-02 | 1 | build + visual | `cd frontend && npm run build` | ⬜ pending |
| badge.tsx restyle | COMP-04 | 1 | build + visual | `cd frontend && npm run build` | ⬜ pending |
| table.tsx restyle | COMP-03 | 1 | build + visual | `cd frontend && npm run build` | ⬜ pending |
| input.tsx create | COMP-05 | 1 | build + visual | `cd frontend && npm run build` | ⬜ pending |
| skeleton.tsx shimmer | COMP-06 | 2 | build + visual | `cd frontend && npm run build` | ⬜ pending |
| Page skeleton wrappers | COMP-06 | 2 | build + visual | `cd frontend && npm run build` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/src/components/ui/input.tsx` — new file required for COMP-05; does not exist yet

*No automated test framework — all visual validation is manual. Build-time checks (tsc + Tailwind) catch class-string and import errors.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Primary button shows amber glow on hover | COMP-01 | No visual regression test infra | Open /dashboard, hover primary buttons, check gold glow |
| Card renders as frosted glass | COMP-02 | Visual effect only | Check backdrop-filter blur visible on cards vs background |
| Table rows highlight on hover | COMP-03 | Interaction state | Hover table rows on /positions, verify --to-surface-raised lift |
| Input focus shows amber glow ring | COMP-05 | Interaction state | Click any input, verify gold ring appears |
| Skeleton shimmer (not pulse) on 5 pages | COMP-06 | Animation visual | Load each page with throttled network, verify left-to-right shimmer |

---

## Validation Sign-Off

- [ ] All tasks have build-time verify or wave 0 dependencies
- [ ] Sampling continuity: build check after every component file change
- [ ] Wave 0 covers input.tsx MISSING reference
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s (build + visual)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
