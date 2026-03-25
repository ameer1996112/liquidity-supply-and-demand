# Phase 2: Historical PnL Precision - Context

## Objective
Ensure closed trade PnL stored in `trading_signals` exactly matches MetaTrader by correctly processing swaps, commissions, and exit pricing upon trade close via MetaApi.

## Initial Problem Statement
Closed trade PnL stored in the database currently mismatches MetaTrader history. Elements like swaps, commissions, and exact exit pricing might be ignored or miscalculated during the close event.

## Investigation Findings
1. During `close_order` in `src/logic.py`, there is an optimized block that already attempts to fetch broker actual PnL via `adapter.get_deals_by_position(broker_order_id)`.
2. However, it filters for deals where `entryType == "DEAL_ENTRY_OUT"`.
3. In MetaTrader, commissions are often charged on the opening deal (`DEAL_ENTRY_IN`). By discarding `DEAL_ENTRY_IN` deals, the entry commission is completely ignored in the calculation.
4. The sum correctly aggregates `profit`, `commission`, and `swap`, but because it drops half the deals associated with the position, the net realized PnL is mathematically inaccurate.

## Solution Direction
- Update `src/logic.py` to aggregate `profit`, `commission`, and `swap` from **ALL** deals associated with the `positionId` (both `DEAL_ENTRY_IN` and `DEAL_ENTRY_OUT`).
- Only use `DEAL_ENTRY_OUT` to determine if the position is fully closed (e.g., verifying an exit deal exists), but sum financial metrics across the entire position lifecycle.
