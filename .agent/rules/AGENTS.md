# AGENTS.md — Safety Rules for AI Coding Agents (Trading Bot)

This repository powers a trading system:
TradingView Pine Strategy -> Webhook -> Python Backend -> Supabase DB -> Dashboard + Discord + Paper Trader.

## 0) Prime Directive (Non-Negotiable)

**DO NOT change strategy behavior.**

- Same entries/exits
- Same trades
- Same PnL

If a change could alter trades/PnL, it is NOT allowed unless explicitly approved.

---

## 1) What You ARE Allowed To Change

### Pine Script (allowed)

✅ Telemetry only (alerts payload fields, metadata, timestamps)  
✅ Alert gating (whether webhook alerts are sent), as long as **strategy.entry/exit logic remains unchanged**  
✅ UI performance (tables/labels rendering optimization)  
✅ Code refactors that are provably behavior-preserving (no logic changes)

### Backend (allowed)

✅ Webhook parsing (robust JSON parsing, content-type handling)  
✅ Storage schema (add columns/tables for live vs backtest)  
✅ Dashboard UI (more columns, filtering reasons, lifecycle)  
✅ Discord/webhook reliability, retries/timeouts, logging  
✅ Paper-trader lifecycle (open/close matching, trade_key correlation)  
✅ NAS100/index pip/point handling **for display/alerts/backend computations**

---

## 2) What You MUST NOT Change

### Pine Script (forbidden)

❌ Any entry/exit condition logic  
❌ Any filter logic that decides whether a trade is taken  
❌ Any zone detection / selection / invalidation logic  
❌ Any RR/SL/TP computation used by orders  
❌ Any use of lookahead/repainting changes  
❌ Anything that changes number of trades or PnL

### Backend (forbidden without approval)

❌ Any logic that changes whether an incoming trade is accepted/filtered
unless the change is purely bug-fix and is validated with parity tests.

---

## 3) Required Workflow For Any Change

### Step A — Identify Scope

Before editing, state:

- Which files will change
- Whether change is Pine telemetry/UI only, backend only, or DB/UI
- Why it is safe (why it cannot change trades)

### Step B — Implement With Feature Flags

All risky or visible changes must be behind toggles:

- Pine: `input.bool` toggles defaulting to current behavior
- Backend: env vars defaulting to current behavior

### Step C — Run Safety Checks

You MUST run:

1. Pine parity check:
   - Same symbol/timeframe/date range
   - Total trades, net profit, profit factor, win rate must match EXACTLY
2. Webhook replay smoke test (backend):
   - Use saved sample payloads (entry/exit/filtered)
   - Verify DB writes, dashboard shows correct lifecycle, discord send status

If you cannot run a check, say why and provide a minimal manual verification plan.

---

## 4) Acceptance Criteria (Definition of Done)

A change is acceptable only if:

- Pine parity results match EXACTLY (same trades + same PnL)
- Dashboard shows accurate:
  - open time, close time
  - outcome (win/loss)
  - pnl (USD and/or R)
  - filter reasons (if filtered)
- Live vs backtest data separation works:
  - LIVE is default view
  - BACKTEST stored separately or tagged, not shown in LIVE view

---

## 5) Data Model Rules (Supabase)

- Store `run_mode` (LIVE/BACKTEST), `run_id`, and `trade_key`
- Correlate entry↔exit by `trade_key` (fallback zone_id only if missing)
- Never overwrite LIVE trade records using BACKTEST updates

---

## 6) Logging & Reliability Rules

- Every webhook request must log:
  - parsed event_type (entry/exit)
  - symbol, side, trade_key
  - filtering decision + ALL filter reasons (if filtered)
  - discord_sent true/false + error
  - paper_trade executed true/false + error
- Discord/webhook calls must have a timeout and surface failures.

---

## 7) Pine Alert Payload Requirements

### Entry payload MUST include:

- event_type="entry"
- symbol, side, entry, sl, tp, size
- run_mode, run_id
- trade_key
- bar_time (preferred time_close), plus server_time optional

### Exit payload MUST include:

- event_type="exit"
- trade_key
- entry_time, exit_time
- outcome, pnl_r, pnl_usd (if available), exit_type

Backwards compatibility:

- Backend must tolerate missing new fields.

---

## 8) Deployment Guardrails (Railway)

- A deploy must not be considered successful unless:
  - /health endpoint returns OK
  - webhook replay smoke test passes
  - supabase connection is confirmed

---

## 9) If Unsure

If you are not 100% sure a change is behavior-preserving:

- STOP and propose two options:
  1. “Telemetry-only safe option”
  2. “Behavior-changing option requiring explicit approval”
