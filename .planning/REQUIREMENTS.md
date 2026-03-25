# Requirements

## v1 Requirements

### Data Alignment
- [ ] **SYNC-01**: Dashboard correctly surfaces active "Live PnL" calculated dynamically or pulled from broker, instead of showing `0.00`.
- [ ] **SYNC-02**: Closed trade PnL stored in the database matches MetaTrader exactly, capturing swaps, commissions, and precise exit pricing without discrepancies.
- [ ] **SYNC-03**: Account-level metrics (Balance, Used Margin, Daily Drawdown) are continuously synchronized from the MetaApi connection to the dashboard interface.

### Retroactive Fixes
- [ ] **REM-01**: Build a single-run or cron utility script that backfills and corrects the historical database records to match the actual MT4/MT5 history precisely.

## v2 Requirements
(None deferred)

## Out of Scope
- [Trading Strategy Enhancements] — Focus is entirely on fixing the reporting and data ingestion pipelines for existing PnL and metrics, not adding new trading entry logic.

## Traceability
<!-- Will be populated by the roadmap step -->
