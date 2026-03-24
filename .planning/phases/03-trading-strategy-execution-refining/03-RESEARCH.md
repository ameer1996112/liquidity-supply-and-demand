# Phase 3 Research: Trading Strategy Execution Refining

## Objective
Research how to implement Phase 3: "Ensure the trading logic fully aligns with the 5-minute timeframe and incorporates Liquidity, Supply, and Demand concepts (Flip & Directional Close mechanics)."

## Key Findings
1. **Existing Logic Locations**: 
   - `src/worker.py` contains the primary structural guards for entry models.
   - `_validate_flip_timing(payload)` (Lines 454-487) currently enforces `dt.minute not in {0, 15, 30, 45}` for `FLIP` entries, rejecting them if they are not exactly on those 15-min boundaries.
   - `_validate_futures_entry_model(payload)` (Lines 510-542) enforces Mangoe rules for Futures, strictly requiring `FLIP` models to align to the 15m/1H boundaries.
2. **Directional Close**:
   - The system already accepts `dir_close` or `directional close` natively inside `_validate_futures_entry_model`.
3. **The Implementation Path**:
   - Update `_validate_flip_timing` to use `dt.minute % 5 != 0` to enforce 5-minute timeframe validities (`0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55`).
   - Update error messages in `_validate_flip_timing` and `_validate_futures_entry_model` to reference `5m boundary check` and `5-min boundaries` instead of `15m/1H`.
   - Ensure tests reflect the timeframe shift.

## Validation Architecture
- **Testing Approach**: 
  - Unit tests or integration test stubs if they exist.
  - Inspect `tests/` directory (if applicable) or verify worker initialization parsing using simple mock payloads sent to `_validate_flip_timing`.

## RESEARCH COMPLETE
