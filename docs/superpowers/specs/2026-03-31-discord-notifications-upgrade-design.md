# Discord Notifications Upgrade — Design Spec

**Date:** 2026-03-31
**Status:** Approved
**Scope:** Signal + Close embeds (Guard/Bug/Digest in follow-up)

---

## Goal

Upgrade Discord trade notification embeds from a flat generic field list to a Discord-native premium layout: author block, thumbnail (chart or currency flag), grouped 3-column field rows, compact AI inline fields, and full AI reasoning posted to the per-trade thread.

---

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Design direction | Discord-native (author, thumbnail, sections) | Leverages Discord embed features Telegram can't match |
| Scope | Signal + Close first | Highest frequency, highest value; Guard/Bug/Digest unchanged |
| Thumbnail | Chart screenshot → currency flag fallback → omit | Reuses existing `image_url` field; flags always look polished |
| Field layout | Two 3-column rows | Scannable at a glance; Discord auto-groups consecutive inline fields |
| AI Analysis in embed | Compact (Decision + Confidence only) | Avoid 1024-char field limit hits; cleans up the embed |
| Full AI reasoning | Discord thread reply (when bot token present) | Keeps main embed clean; detail available on-demand |

---

## Signal Embed Structure

```
┌─────────────────────────────────────────────────┐
│ 🤖 Trading Bot · FTMO-50K          [EUR flag/  │
│                                     chart img]  │
│ 📈 BUY EURUSD — Signal #142                     │
│ Execute manually · 🇬🇧 London · 14:30 UTC       │
│─────────────────────────────────────────────────│
│ 🎯 Entry      🛑 Stop Loss    💰 Take Profit    │
│ 1.08420       1.08320 (10p)   1.08620 (20p)     │
│─────────────────────────────────────────────────│
│ ⚖️ R:R        📊 Lot Size     💸 Risk           │
│ 1:2.00        0.82 lots       $125.00           │
│─────────────────────────────────────────────────│
│ 🧠 AI Decision        🎯 AI Confidence          │
│ ✅ GO                  78.4%                    │
│─────────────────────────────────────────────────│
│ Signal #142 · /close 142          14:30 UTC     │
└─────────────────────────────────────────────────┘
```

**Optional fields** (appended after row 2 when present, inline):
- Zone Type (🟢 DEMAND / 🔴 SUPPLY)
- Account (if not already in author block)
- Session (if bar_time present)

**Color:** `#00C853` (BUY) / `#F44336` (SELL) / `#3B82F6` (PAPER)

---

## Close Embed Structure

```
┌─────────────────────────────────────────────────┐
│ 🤖 Trading Bot · FTMO-50K          [EUR flag]  │
│                                                 │
│ 🟢 Trade Closed — EURUSD BUY                   │
│ Signal #142 closed                              │
│─────────────────────────────────────────────────│
│ 📈 PnL        ⚖️ Outcome      📊 R Multiple     │
│ +$248.50      WIN             +1.99R            │
│─────────────────────────────────────────────────│
│ 🎯 Entry      🏁 Exit         💸 Commission     │
│ 1.08420       1.08618         -$8.20            │
│─────────────────────────────────────────────────│
│ Signal #142                       16:47 UTC     │
└─────────────────────────────────────────────────┘
```

**Color:** `#22C55E` (WIN) / `#EF4444` (LOSS) / `#64748B` (BREAKEVEN)

**Swap field:** Appended inline when non-zero.

---

## Thumbnail Logic

```
_get_symbol_thumbnail_url(symbol, image_url):
  if image_url → return image_url
  base_currency = extract_base_currency(symbol)  # EUR from EURUSD
  flag_code = CURRENCY_FLAG_MAP.get(base_currency)  # EUR → "eu"
  if flag_code → return f"https://flagcdn.com/w80/{flag_code}.png"
  return None  (omit thumbnail key from embed)
```

**Currency → flag code map** (minimum viable set):
`EUR→eu, GBP→gb, USD→us, JPY→jp, CAD→ca, AUD→au, NZD→nz, CHF→ch`

Indices (NAS100, US30, SPX500): map to `us`.
XAU, BTC, ETH: no flag → omit thumbnail.

---

## AI Analysis Handling

### In the embed (always)
`NotificationService.format_signal()` replaces the single `"🧠 AI Analysis"` text field with two compact inline fields:

```python
fields["🧠 AI Decision"]   = "✅ GO" | "⛔ NO_GO"
fields["🎯 Confidence"]    = "78.4%"
```

### In the thread (when bot token configured)
After posting the signal embed, `dispatch_payload()` posts the full AI reasoning as a thread reply:
- Decision, Confidence, Reason, RAG Wisdom (up to 5 rules)
- Only fires when `DISCORD_BOT_TOKEN` is set and `thread_id` is available
- Uses existing `post_to_discord_thread()` infrastructure

---

## R Multiple on Close

`format_close()` computes R Multiple when `risk_usd` is available on the signal:

```python
r_multiple = pnl / risk_usd  if risk_usd > 0 else None
# e.g. pnl=$248.50, risk_usd=$125.00 → +1.99R
```

Field label: `📊 R Multiple`, value: `+1.99R` / `-0.50R`

---

## Files Changing

| File | Change |
|---|---|
| `src/adapters/discord.py` | Upgrade `_payload_to_discord_embed()`: author block, thumbnail, field icon helpers |
| `src/adapters/discord.py` | Add `_get_symbol_thumbnail_url()` helper |
| `src/adapters/discord.py` | `dispatch_payload()`: post full AI reasoning to thread after signal |
| `src/services/notification_service.py` | `format_signal()`: split AI block into 2 compact inline fields |
| `src/services/notification_service.py` | `format_close()`: add R Multiple field |
| `tests/test_discord_render.py` | Update + extend tests for new embed structure |

---

## Out of Scope

- Guard, Bug, Daily Digest embed redesign (follow-up ticket)
- Telegram changes (already upgraded in DEV-80)
- New Discord channels or routing changes
- Interactive Discord buttons/components
