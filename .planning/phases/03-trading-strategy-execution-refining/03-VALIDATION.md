---
phase: 3
slug: trading-strategy-execution-refining
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-24
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Pytest |
| **Config file** | `pytest.ini` / Project Root |
| **Quick run command** | `PYTHONPATH=/workspace pytest tests/` |
| **Full suite command** | `PYTHONPATH=/workspace pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run full test suite to check for compilation/syntax regressions.
- **Before `/gsd-verify-work`:** Read the modified source files to verify 5-minute math (`% 5 == 0`).
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 1 | 5-min Flip Guard | unit | `grep "% 5 != 0" src/worker.py` | ✅ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-03-24
