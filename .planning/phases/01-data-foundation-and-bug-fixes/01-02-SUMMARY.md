---
status: "complete"
---

# Plan 01-02: Calculation Base Fixes - Summary

## Built
- **src/services/prop_firm_tracker.py**: Replaced `datetime.now(timezone.utc).replace(...)` with NY Midnight UTC resolution (`get_ny_midnight_utc()`). Updated `trailing_drawdown_pct` to use initial balance for Eval phases (Phase 1, Phase 2) and High Water Mark for Funded. Re-raised error exceptions during snapshots. Fetched `trades_today` from DB.
- **src/services/mtm_guardian.py**: Uses NY Midnight globally. Dynamically calculates `pip_value_per_lot` for JPY pairs based on entry price (`(0.01 / entry) * 100000`).
- **tests/test_prop_firm_phase1.py**: Test file adding verification for NY Midnight offset, drawdown calculation logic branching by phase, and dynamic JPY pairs.

## Review Notes
Everything verified working mathematically and logic flows match explicit Phase 1 boundaries. No further issues.

## Self-Check: PASSED
- [x] NY midnight offset universally implemented
- [x] JPY tests passing
- [x] Evaluation phase properly branching for drawdown calculations
