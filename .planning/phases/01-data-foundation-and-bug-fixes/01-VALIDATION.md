---
phase: 1
slug: data-foundation-and-bug-fixes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (already installed) |
| **Config file** | `tests/conftest.py` |
| **Quick run command** | `pytest tests/test_prop_firm_phase1.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_prop_firm_phase1.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | DATA-01, DATA-02, DATA-03 | manual | Run migration SQL in Supabase editor; verify row counts | N/A | ⬜ pending |
| 1-02-01 | 02 | 2 | BUG-01 | unit | `pytest tests/test_prop_firm_phase1.py::test_ny_midnight_winter -x` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 2 | BUG-02 | unit | `pytest tests/test_prop_firm_phase1.py::test_equity_baseline -x` | ❌ W0 | ⬜ pending |
| 1-02-03 | 02 | 2 | BUG-03 | unit | `pytest tests/test_prop_firm_phase1.py::test_drawdown_denominator -x` | ❌ W0 | ⬜ pending |
| 1-02-04 | 02 | 2 | BUG-04 | unit | `pytest tests/test_prop_firm_phase1.py::test_trades_today -x` | ❌ W0 | ⬜ pending |
| 1-02-05 | 02 | 2 | BUG-05 | unit | `pytest tests/test_prop_firm_phase1.py::test_save_snapshot_error_propagation -x` | ❌ W0 | ⬜ pending |
| 1-02-06 | 02 | 2 | BUG-06 | unit | `pytest tests/test_prop_firm_phase1.py::test_jpy_pip_value_dynamic -x` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 3 | DATA-04 | unit | `pytest tests/test_prop_firm_phase1.py::test_firm_detector -x` | ❌ W0 | ⬜ pending |
| 1-03-02 | 03 | 3 | API-01 | integration | `pytest tests/test_prop_firm_phase1.py::test_challenge_status_endpoint -x` | ❌ W0 | ⬜ pending |
| 1-03-03 | 03 | 3 | API-02 | integration | `pytest tests/test_prop_firm_phase1.py::test_challenge_config_patch -x` | ❌ W0 | ⬜ pending |
| 1-03-04 | 03 | 3 | API-03 | integration | `pytest tests/test_prop_firm_phase1.py::test_challenge_status_unknown_firm -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_prop_firm_phase1.py` — stubs for all Phase 1 requirements (BUG-01 through BUG-06, DATA-04, API-01, API-02, API-03)
- [ ] Supabase mock fixtures following `tests/conftest.py` pattern — mock `self.supabase.table(...)` with `MagicMock` returning controlled `.data`

*Create these in Plan 01-02 (bug fixes) so unit tests are ready before Plan 01-03 adds integration tests.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Migration creates tables with correct schema | DATA-01, DATA-02 | DDL cannot be tested with mocks | Run `047_prop_firm_data_foundation.sql` in Supabase SQL editor; `SELECT count(*) FROM prop_firm_server_mappings` returns ≥1; `SELECT count(*) FROM prop_firm_rules` returns 3 |
| FTMO seed data present | DATA-03 | Depends on live Supabase | After migration: `SELECT * FROM prop_firm_rules WHERE firm_id='ftmo'` returns 3 rows with daily_dd_pct=5.0, total_dd_pct=10.0 |
| FTMO reset timezone matches actual FTMO policy | DATA-03 | External verification needed | Check current FTMO FAQ for reset boundary; compare against seeded `reset_tz='America/New_York'` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
