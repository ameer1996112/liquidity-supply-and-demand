---
phase: 5
slug: pre-filter-hardening-ev-score
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` or `pytest.ini` (existing) |
| **Quick run command** | `pytest tests/test_pine_filters_phase1.py -v` |
| **Full suite command** | `pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_pine_filters_phase1.py -v`
- **After every plan wave:** Run `pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 5-01-T1 | 01 | 1 | RUBRIC-01 (settings) | unit | `pytest tests/test_pine_filters_phase1.py::test_rubric_settings -v` | ❌ W0 | ⬜ pending |
| 5-01-T2 | 01 | 1 | RUBRIC-02 (news medium) | unit | `pytest tests/test_pine_filters_phase1.py::test_news_medium_impact -v` | ❌ W0 | ⬜ pending |
| 5-01-T3 | 01 | 1 | RUBRIC-03 (premium_discount parse) | unit | `pytest tests/test_pine_filters_phase1.py::test_premium_discount_parsing -v` | ❌ W0 | ⬜ pending |
| 5-01-T4 | 01 | 1 | RUBRIC-03 (kill_zone parse) | unit | `pytest tests/test_pine_filters_phase1.py::test_kill_zone_parsing -v` | ❌ W0 | ⬜ pending |
| 5-01-T5 | 01 | 1 | EV score formula | unit | `pytest tests/test_pine_filters_phase1.py::test_ev_score_formula -v` | ❌ W0 | ⬜ pending |
| 5-01-T6 | 01 | 1 | Existing 4 vetoes still pass | regression | `pytest tests/test_pine_filters_phase1.py -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pine_filters_phase1.py` — Add stubs for new tests (T1-T5 above); existing 4 tests stay unchanged
- [ ] Verify `conftest.py` fixture for mock account state is reusable

*Note: Existing infrastructure (pytest) covers all phase requirements. No new framework install needed. Existing `tests/test_pine_filters_phase1.py` already has 4 passing tests — only new test cases need stubs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| EV score appears in worker.py logs | RUBRIC-01 | Log output, not return value | Run a test signal locally, inspect logs for ev_score |
| Fail-closed + Discord alert on Supabase outage | RUBRIC-01 | Requires real Supabase + Discord env | Simulate outage, check Discord channel |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
