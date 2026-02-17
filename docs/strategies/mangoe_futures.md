# Mangoe Futures Strategy (Liquidity Supply & Demand)

## Overview

Optimized for **Futures** instruments (Crude Oil, Nasdaq, Gold) where execution is precise (no spreads) but volatility is high. Uses the **5-minute timeframe** exclusively for trend and entry to maximize trade frequency and precision.

---

## Trading Parameters

| Parameter | Value |
|-----------|--------|
| **Timeframe** | 5 minutes only |
| **Session** | 08:00 – 15:00 UK Time (London & New York overlap) |
| **Risk Reward** | Fixed **1:4** (strict) |
| **Stop Loss** | Zone High/Low **+ 1 pip buffer** (crucial for avoiding wick-outs) |

---

## Entry Logic

1. **Identify Trend:** 5m chart MUST show clear market structure (HH/HL for Buy, LH/LL for Sell).
2. **Identify Zone:** Locate fresh Supply/Demand zones created by aggressive expansion.
3. **Liquidity Check:** Ensure "Engineering Liquidity" (swings) exists prior to the zone. Avoid zones with weak/single-candle liquidity.
4. **Trigger:** Wait for price to tap the zone and form one of:
   - **Directional Close** (close outside zone in direction of trade), or
   - **Break of Candle** (breaking the previous candle's wick in the intended direction).

**Entry models:** Directional Close or Break of Candle are primary. Flip entries are only valid when they occur on a **15m/1H candle open** (minute 00, 15, 30, 45).

---

## Invalidations

- Price violates the zone by more than **1 pip**.
- Trade setup occurs **outside** the 08:00–15:00 UK window.
- Structure on 5m is **unclear or ranging** (no clear HH/HL or LH/LL).

---

## Implementation Reference

### Pine Script (`SND_Strategy.pine`)

- **Input:** `use_futures_rules` (Boolean, default `false`) — enables Mangoe Futures mode.
- **Input:** `sl_buffer_pips` (Float, default `1.0`) — buffer added to zone edge for SL.
- When `use_futures_rules` is true:
  - Session filter: **08:00–15:00 UK** (Europe/London).
  - SL = **Zone distal line + sl_buffer_pips** (demand: zone bottom − buffer; supply: zone top + buffer).
  - TP = **4.0R** (fixed 1:4).
  - **5m only** (other timeframes blocked).
  - **HTF trend filter ignored** (5m market structure only).

### Python / RAG (`src/worker.py`)

- For symbols treated as Futures (e.g. CL, NQ, GC, XAUUSD):
  - **Entry model validation:** Break of Candle or Directional Close are allowed.
  - **Flip** entries are **rejected** unless `bar_time` is on a 15-minute boundary (00/15/30/45); missing `bar_time` for a Flip on a Futures symbol is rejected.

---

## Rules Summary (Quick Reference)

| Rule | Value |
|------|--------|
| Timeframe | 5m only |
| SL | Zone + 1 pip |
| TP | Strict 1:4 |
| Session | 08:00–15:00 UK |
| Entry | Directional Close or Break of Candle (Flip only on 15m/1H open) |
