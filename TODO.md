# PnL Broker Truth Fix ✅ LIVE

Status: **INSTANT PRONG COMPLETE** | Priority: LOW | Est: 10min remaining

## Objective

Make `pnl_usd` **always match MT5** (profit + commission + swap):

- **Instant**: Exit webhook → close → fetch deal → update pnl_usd (<15s)
- **Fallback**: Background watermarking syncs silent closes
- **Historical**: backfill_actual_pnl.py fixes past discrepancies

✅ **NO DB MIGRATIONS** | ✅ Rate-limit safe | ✅ Production-scale

## Steps (Sequential)

### 1. Extract Deal Fetcher (15min)

**File**: `src/services/broker_reconciliation.py`

- Make `_fetch_closed_deal()` → public `fetch_closing_deal(adapter, position_id, symbol, since_time)`
- Watermark helper: `get_last_closed_timestamp(supabase)`

### 2. Instant PnL - Exit Webhook (20min)

**File**: `src/logic.py`

```
Exit handler → close_order() → fetch_recent_closing_deal(since=close_time)
→ pnl_usd = profit+comm+swap → save_result()
```

- 15s timeout window
- Log \"🚀 INSTANT PnL: ticket123 → $45.67\"

### 3. Watermark Background Sync (10min)

**Files**: `src/services/watchdog.py`, `src/services/broker_reconciliation.py`

```
watermark = get_last_closed_timestamp()  # LAST closed_at
deals = metaapi.get_historical_deals(watermark, now)  # NEW deals only
```

### 4. Verify & Deploy (10min)

```
✅ python scripts/verify_pnl_fix.py
✅ python scripts/backfill_actual_pnl.py --days 90
🚀 Railway deploy → tail logs "INSTANT PnL"
```

## Success Metrics

```
[ ] Dashboard pnl_usd == MT5 History (-$287.84 example)
[ ] Logs: "INSTANT PnL" on exit webhooks
[ ] API calls: <10/min (watermarking)
[ ] 100% historical match after backfill
```

## Risks/Mitigations

| Risk                    | Mitigation                              |
| ----------------------- | --------------------------------------- |
| No deal found instantly | Background sync + theoretical fallback  |
| Rate limits             | Watermarking + 15s windows              |
| Server lag              | Exponential backoff in meta_api_adapter |

**Next**: `read_file src/logic.py` → analyze exit handler → implement Step 2

**COMPLETION CHECKLIST** ✅

- [ ] All closes show MT5 pnl_usd
- [ ] No TradingView theoretical values
- [ ] Dashboard matches broker statements

- [ ] Build automated 5m/1H TradingView screenshot capture in Python backend.
  - **Why:** To feed live trades to the Visual Annotator asynchronously.
  - **Pros:** Fully automates the data collection for the Shadow Council.
  - **Cons:** Headless scraping is brittle (login walls, slow rendering).
  - **Context:** We are currently manually uploading screenshots to test Claude's grading. Once the rubric is proven, we need this capture mechanism.
  - **Depends on:** Validating the 4-dimension rubric works on historical screenshots.
