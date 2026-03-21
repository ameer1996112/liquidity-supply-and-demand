---
created: 2026-03-21T12:31:40.637Z
title: Optimize breakeven manager with buffer and trailing stop activation
area: api
files:
  - src/services/breakeven_manager.py
  - src/services/trailing_stop_manager.py
  - config/settings.py
  - .env
---

## Problem

The breakeven system (`BreakevenManager`) currently moves SL to **exactly** the entry price when triggered. This causes small losses ($44–$139) when price returns to breakeven because:
1. The SL lands at exact entry — no buffer for spread/commission
2. Once SL is at breakeven, there is no further trailing — winners get clipped at entry instead of running

**Confirmed from Supabase trade id 226 (GBPCAD -$44.14):**
- `be_triggered: true`
- `be_sl_price = entry = 1.84141`
- `exit_price = 1.84140` (1 pip below entry)
- Result: -$44.14 loss from a trade that hit profit first

Root cause: `be_sl_price` is Pine-computed and sent as exact entry. Python fires it as-is with no adjustment.

## Solution

Three-layer optimization (implement in order of priority):

**Layer 1 — BE Buffer (quick win, Python only):**
Add `breakeven_buffer_pips` setting (e.g. 3 pips). When `breakeven_manager.py` fires, shift `be_sl_price` by +buffer pips above entry for buys / -buffer for sells. Converts small losses into small wins. No Pine changes needed.

**Layer 2 — Trailing stop activation after BE (long-term):**
When `_mark_triggered()` completes successfully, call `TrailingStopManager.add_trailing_stop()` for the same position. The trailing stop then follows price up from the BE level instead of holding static. Converts breakeven exits into captured runners.

**Layer 3 — Partial close at TP1 (optional, complex):**
Use the existing `partial_close_percent` column + `TP1` field from webhook to close 50% at halfway target, then move remainder to BE. Requires Pine to send `tp1` field and Python to watch for it in the broker sync loop.

**Decision needed:** Does the Pine Script send `be_sl_price` as exact entry, or can it be modified to send entry + buffer? (Clarify before implementing Layer 1.)

**Config additions needed:**
```
BREAKEVEN_BUFFER_PIPS=3
BREAKEVEN_ACTIVATE_TRAILING=true
TRAILING_DISTANCE_PIPS=15
```
