# Trading Bot v2.0 - Cleanup & Consolidation Audit Report

**Generated:** 2026-01-31
**Auditor:** Claude Code Quality Auditor
**Status:** DRY RUN - No changes made

---

## Executive Summary

Your codebase has **evolved from a monolithic Flask app** (`trading_bot.py`) to a **modern FastAPI + Redis Worker architecture** (`main.py` + `worker.py`). The old code is still present and should be archived.

| Category | Files | Action |
|----------|-------|--------|
| Core Production | 8 | KEEP |
| Useful Utilities | 8 | KEEP |
| Legacy/Deprecated | 3 | ARCHIVE |
| Test Scripts | 2 | ARCHIVE |
| Junk (logs, cache) | 3+ | DELETE |

---

## Detailed File Analysis

### KEEP - Core Production Files

| File | Purpose | Imported By |
|------|---------|-------------|
| `backend/main.py` | FastAPI server entry point | Direct execution |
| `backend/worker.py` | Redis queue worker | Direct execution |
| `backend/config.py` | Pydantic settings | main.py, worker.py |
| `backend/supabase_db.py` | Database operations | main.py, worker.py, logic.py |
| `backend/logic.py` | Core trading logic | worker.py |
| `backend/news_filter.py` | News event filter | logic.py, trading_bot.py |
| `backend/paper_trader.py` | Paper trading module | logic.py, trading_bot.py |
| `backend/ai_guardian.py` | LLM-based trade validation | worker.py |

### KEEP - Useful Utility Scripts

| File | Purpose | Usage |
|------|---------|-------|
| `backend/train_model.py` | Train ML model from CSV | Manual: `python train_model.py` |
| `backend/backtest_ai_filter.py` | Backtest AI filter performance | Manual |
| `backend/export_training_data.py` | Export Supabase data for retraining | Manual |
| `backend/monitor_shadow_mode.py` | Compare AI predictions vs outcomes | Manual |
| `backend/daily_report.py` | Generate daily performance summary | Scheduled/Manual |
| `scripts/verify_prod.py` | Verify Railway deployment | Manual |
| `scripts/check_connection.py` | Test CORS configuration | Manual |
| `backend/migrate_database.py` | SQLite schema migration | One-time/Legacy |

### ARCHIVE - Legacy/Deprecated Code

| File | Size | Reason | Notes |
|------|------|--------|-------|
| `backend/trading_bot.py` | 1330 lines | **Superseded by main.py + worker.py** | Old monolithic Flask app with embedded dashboard. All functionality now split between FastAPI API and async worker. |
| `backend/pine_guardian.py` | NEW | **Duplicate of ai_guardian.py?** | Untracked file. Review before archiving - may be experimental. |
| `backend/test_bot.py` | 315 lines | **Test for deprecated trading_bot.py** | Tests the old Flask endpoints, not the new FastAPI ones. |
| `backend/test_news_logic.py` | 48 lines | **Simple test with hardcoded mocks** | One-time test script, not proper pytest. |

### ARCHIVE - Development/Testing Scripts (Untracked)

| File | Reason | Notes |
|------|--------|-------|
| `scripts/reset_system.py` | Untracked (git ??) | Likely dev utility - review before archiving |
| `scripts/test_full_system.py` | Untracked (git ??) | Integration test - review before archiving |

### DELETE - Junk Files

| Pattern | Location | Type |
|---------|----------|------|
| `backend/bot.log` | Backend | Log file |
| `backend/trading_bot.log` | Backend | Log file |
| `dashboard/.next/dev/logs/*.log` | Dashboard | Next.js dev logs |
| `backend/__pycache__/` | Backend | Python bytecode cache |
| `scripts/__pycache__/` | Scripts | Python bytecode cache |

---

## Redundancy Analysis

### 1. `trading_bot.py` vs `main.py + worker.py`

**Verdict: ARCHIVE `trading_bot.py`**

| Feature | trading_bot.py (OLD) | main.py + worker.py (NEW) |
|---------|---------------------|---------------------------|
| Framework | Flask | FastAPI |
| Architecture | Monolithic | Microservices |
| Async Processing | Synchronous | Redis Queue |
| AI Validation | Pickle ML model | LLM-based (ai_guardian.py) |
| Dashboard | Embedded HTML template | Separate Next.js app |
| Config | os.getenv() | Pydantic Settings |

The old `trading_bot.py` is completely superseded. It was the original "all-in-one" server, but you've since refactored into:
- `main.py` - FastAPI REST API
- `worker.py` - Async signal processor with AI Guardian
- `dashboard/` - Separate Next.js frontend

### 2. `test_bot.py` vs Proper Tests

**Verdict: ARCHIVE `test_bot.py`**

This script tests the OLD Flask `/webhook` endpoint. It won't work with the new FastAPI implementation. Consider creating proper pytest tests for the new API.

### 3. `migrate_database.py` - SQLite Migration

**Verdict: KEEP (for now)**

This script adds columns to SQLite `trades.db`. You've migrated to Supabase, so this may be obsolete. However, keeping it costs nothing and might be useful for local dev.

---

## Recommended Actions

### Immediate (Safe)

1. **Delete log files** - No risk, regenerated automatically
2. **Clean `__pycache__`** - No risk, regenerated on import
3. **Archive `trading_bot.py`** - Old monolithic app, superseded

### After Review

1. **Review `pine_guardian.py`** - It's untracked. Check if it's:
   - A duplicate of `ai_guardian.py` (delete)
   - An experimental feature (archive or integrate)

2. **Review `scripts/reset_system.py`** - Untracked. Might be useful for dev.

3. **Review `scripts/test_full_system.py`** - Untracked. Integration test.

---

## Architecture Diagram (Current)

```
                    TradingView
                        │
                        ▼
                ┌───────────────┐
                │   main.py     │  ◄── FastAPI REST API
                │  (FastAPI)    │
                └───────┬───────┘
                        │ Redis Queue
                        ▼
                ┌───────────────┐
                │  worker.py    │  ◄── Async Signal Processor
                │ (AI Guardian) │
                └───────┬───────┘
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
    ┌─────────┐   ┌──────────┐   ┌──────────┐
    │Supabase │   │ Discord  │   │ Telegram │
    │   DB    │   │ Webhook  │   │   Bot    │
    └─────────┘   └──────────┘   └──────────┘
         ▲
         │
    ┌─────────┐
    │Dashboard│  ◄── Next.js Frontend (separate app)
    └─────────┘
```

---

## Files to Review Manually

Before running the cleanup script, please review these untracked files:

1. **`backend/pine_guardian.py`** - What is this?
2. **`scripts/reset_system.py`** - Is this useful?
3. **`scripts/test_full_system.py`** - Keep for integration testing?

---

## Next Step

Run the cleanup script in **dry-run mode** first:

```bash
python scripts/cleanup_workspace.py --dry-run
```

Then, if satisfied:

```bash
python scripts/cleanup_workspace.py
```

---

*This report was generated automatically. Always review before executing cleanup actions.*
