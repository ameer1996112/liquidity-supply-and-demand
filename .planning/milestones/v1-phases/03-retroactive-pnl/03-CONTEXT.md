# Phase 3: Retroactive Database Remediation - Context

## Objective
Fix all previously logged faulty PnL data in Supabase by running an idempotent script that recalculates the accurate PnL from the broker's deal history.

## Initial Problem Statement
Historical PnL data in Supabase is inaccurate because previous pipeline runs dropped entry commissions. We need to retroactively heal the dataset.

## Execution Strategy
The project already contains a specialized script `scripts/backfill_actual_pnl.py` which:
1. Queries Supabase for CLOSED live trades over a specified timeframe.
2. Uses the MetaApi adapter to retrieve the full history of deals.
3. Groups all deals by `positionId` and accurately sums `profit`, `commission`, and `swap` exactly as we fixed it in Phase 2.
4. Idempotently updates the `pnl_usd`, `commission`, and `swap` fields in `trading_signals` if a delta > 1% is detected.

We will run this script for a 365-day lookback to ensure the entire historical dataset matches the broker.
