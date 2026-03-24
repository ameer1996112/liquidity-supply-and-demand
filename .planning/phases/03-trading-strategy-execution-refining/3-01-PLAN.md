---
wave: 1
depends_on: []
files_modified:
  - src/worker.py
autonomous: true
---

# Plan 1: 5-Minute Timeframe Execution Refining

## Objective
Update the Trading Strategy logic in the Python worker to enforce 5-minute alignments for FLIP models, rather than the legacy 15-minute alignments.

## Tasks

<task>
<id>3-01-01</id>
<title>Refactor FLIP Timing Validation to 5-Minute Boundaries</title>
<read_first>
- src/worker.py
</read_first>
<action>
Modify `src/worker.py`:
1. In `_validate_flip_timing(payload: Dict[str, Any]) -> Optional[str]:`, locate the 15-min boundary check logic: `if dt.minute not in {0, 15, 30, 45}:`.
2. Change it to mathematically enforce 5-minute boundaries: `if dt.minute % 5 != 0:`.
3. Update the corresponding error message to read: `FLIP entries require 5-min boundaries`.
4. In `_validate_futures_entry_model(payload: Dict[str, Any]) -> Optional[str]:` (Mangoe Rules), update the FLIP block error messages:
   - "Futures (Mangoe): FLIP entry requires bar_time for 5m boundary check. Use Break of Candle or Directional Close, or ensure Flip occurs on 5m candle open."
5. Also update any structural docstrings directly above these methods that mention `15m` boundaries to state `5m` instead.
</action>
<acceptance_criteria>
- `_validate_flip_timing` correctly uses modulus 5 to enforce the 5m TF constraint.
- Mangoe futures rules appropriately prompt users regarding 5m alignments.
- Full pytest suite (`PYTHONPATH=/workspace pytest tests/ -v`) passes cleanly without any execution regressions.
</acceptance_criteria>
</task>

## Verification
- Run `PYTHONPATH=/workspace pytest tests/ -v`.
- Run `grep -i "15m" src/worker.py` to ensure no trailing 15-minute legacy documentation exists inside the FLIP guards/functions.
