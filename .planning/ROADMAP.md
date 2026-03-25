# Roadmap

## Phase 1: Real-time Live PnL & Account Metrics
**Goal:** Dashboard accurately displays Live PnL and overall account metrics (Balance, Margin, Drawdown).
**Requirements:** SYNC-01, SYNC-03

**Success Criteria:**
1. Live PnL continuously updates on the Next.js frontend without showing `0.00` for recognized active trades.
2. Frontend accurately lists Account Balance, Used Margin, and Daily Drawdown, mirroring the MetaTrader account state.

## Phase 2: Historical PnL Precision
**Goal:** Closed trade PnL stored in the database exactly matches MetaTrader.
**Requirements:** SYNC-02

**Success Criteria:**
1. PnL algorithm correctly processes swaps, commissions, and exit pricing upon trade close via MetaApi.
2. Backend pipeline inserts the finalized closed state into Supabase with zero precision loss.

## Phase 3: Retroactive Database Remediation
**Goal:** Fix all previously logged faulty PnL data in Supabase.
**Requirements:** REM-01

**Success Criteria:**
1. An idempotent Python script fetches all correct, finalized PnL data directly from the MetaApi history layer.
2. Script safely backfills the `positions`/relevant historical tables in Supabase without duplicating rows.
3. Dashboard historical analytics charts mathematically verify against MT4 built-in reports post-run.
