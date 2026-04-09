# 1-Candle Liquidity Confidence Scoring System

## Status: Design Approved — Ready for Implementation
**Date:** 2026-04-01  
**Branch:** feature/DEV-86-pinescript-implement-instant-flip-entry-for

---

## Problem Statement

The current single filter (`AI score ≥ 55`) is too permissive for 1-candle liquidity trades. Failing trades share common patterns:
- Zone `NOT_FOUND` in backend arrays (Pine sends signal without valid zone data)
- `Primed: NO` — zone not ready but signal fires anyway
- Low AI scores (e.g. 18) bypassing the threshold in some code paths
- Multiple simultaneous failure modes — no single fix is sufficient

**Current state:** ~28-33% win rate, overall negative PnL on higher trade volume.  
**Goal:** Fewer, higher-quality trades. Quality over quantity.

---

## Architecture: Two-Path System

```
Pine Script
    │
    ▼
⚡ FAST PATH (< 100ms — critical execution path)
    ├─ Pine Hard Gates (filtered before webhook fires)
    ├─ Rule-based Composite Scorer (cached market data)
    ├─ Historical Win Rate Lookup (indexed Supabase query)
    └─ EXECUTE or REJECT instantly

         (async, non-blocking — never delays execution)
    ▼
🧠 SLOW PATH (2-5s)
    ├─ AI Council Review
    ├─ Journal enrichment
    └─ Weight tuning over time
```

**Key principle:** The AI Council is never in the execution critical path. Scalping requires < 100ms decision time.

---

## Phase 1: Pine Hard Gates + Enriched Webhook

### Hard Gates (all must pass — any failure blocks webhook)

```pine
bool gate_primed         = primed == true
bool gate_zone_found     = zone_found == true
bool gate_leg_candles    = leg_candles == 1
bool gate_zone_caused_sw = zone_caused_sweep == true
bool gate_ai_score       = ai_score >= 55
bool gate_not_zone_used  = zone_used == false

bool all_gates_pass = gate_primed
                   and gate_zone_found
                   and gate_leg_candles
                   and gate_zone_caused_sw
                   and gate_ai_score
                   and gate_not_zone_used
```

### Enriched Webhook Payload (add to existing fields)

```json
{
  "primed": true,
  "zone_found": true,
  "leg_candles": 1,
  "zone_caused_sweep": true,
  "sweep_to_touch_bars": 0,
  "peak_to_touch_bars": 4,
  "liq_source": "MAKUCHAKU_PIVOT",
  "zone_grade": "A",
  "zone_size_pips": 6.9,
  "bars_since_zone": 13,
  "liq_distance_pips": 5.8,
  "close_type": "Bearish"
}
```

### Supabase Schema Changes

Add columns to `signals` table:
- `primed` BOOLEAN
- `zone_found` BOOLEAN
- `leg_candles` INTEGER
- `zone_caused_sweep` BOOLEAN
- `sweep_to_touch_bars` INTEGER
- `peak_to_touch_bars` INTEGER
- `liq_source` TEXT
- `zone_grade` TEXT
- `zone_size_pips` FLOAT
- `bars_since_zone` INTEGER
- `liq_distance_pips` FLOAT
- `liquidity_score` INTEGER  ← composite score computed by backend

---

## Phase 2: Fast Composite Scorer

### Component 1 — Zone Quality Score (from Pine payload)

| Factor | Points |
|---|---|
| `sweep_to_touch_bars` = 0 | 30 |
| `sweep_to_touch_bars` = 1 | 15 |
| `sweep_to_touch_bars` ≥ 2 | 0 |
| `peak_to_touch_bars` ≤ 3 | 20 |
| `peak_to_touch_bars` ≤ 6 | 10 |
| `peak_to_touch_bars` > 6 | 0 |
| `liq_source` = MAKUCHAKU_PIVOT | 15 |
| `zone_grade` = A | 15 |
| `ai_score` ≥ 70 | 20 |
| `ai_score` 55–69 | 10 |

**Max: 100 pts**

### Component 2 — Market Context Score (pre-cached, refreshed every 60s)

| Factor | Points |
|---|---|
| Price on correct side of 200 EMA | 25 |
| ATR-normalized zone size in optimal range | 15 |
| Session = London or NY open | 20 |
| Day = Monday or Tuesday | 10 |

**Max: 70 pts**

### Component 3 — Historical Performance Lookup

```sql
SELECT 
    COUNT(*) FILTER (WHERE pnl_usd > 0) * 100.0 / COUNT(*) AS win_rate,
    AVG(rr_actual) AS avg_rr
FROM journal
WHERE model = 'BREAK_CANDLE'
  AND session = :session
  AND zone_type = :zone_type
  AND ai_score >= :ai_score_lower 
  AND ai_score < :ai_score_upper
  AND created_at > NOW() - INTERVAL '60 days'
```

| Win Rate | Bonus Points |
|---|---|
| ≥ 50% | +20 |
| ≥ 40% | +10 |
| < 40% | 0 |

### Final Score

```
raw_score = component_1 + component_2 + component_3
normalized_score = (raw_score / 190) * 100   -- normalize to 0-100
```

**Minimum to execute: ≥ 70 / 100**

### Python Implementation Skeleton

```python
class LiquidityScorer:
    
    def score(self, signal: dict, cached_market: dict) -> int:
        score = 0
        
        # Component 1: Zone quality
        stb = signal.get("sweep_to_touch_bars", 99)
        if stb == 0:   score += 30
        elif stb == 1: score += 15
        
        ptb = signal.get("peak_to_touch_bars", 99)
        if ptb <= 3:   score += 20
        elif ptb <= 6: score += 10
        
        if signal.get("liq_source") == "MAKUCHAKU_PIVOT": score += 15
        if signal.get("zone_grade") == "A":               score += 15
        
        ai = signal.get("ai_score", 0)
        if ai >= 70:   score += 20
        elif ai >= 55: score += 10
        
        # Component 2: Market context (from 60s cache)
        if cached_market.get("ema_aligned"):    score += 25
        if cached_market.get("zone_atr_ok"):    score += 15
        if cached_market.get("session_prime"):  score += 20
        if cached_market.get("day_prime"):      score += 10
        
        # Component 3: Historical win rate
        win_rate = self._lookup_win_rate(signal)
        if win_rate >= 50:   score += 20
        elif win_rate >= 40: score += 10
        
        # Normalize to 0-100
        return int((score / 190) * 100)
    
    def should_execute(self, score: int) -> bool:
        return score >= 70
```

---

## Phase 3: Weight Tuning (after 30+ trades)

After collecting 30+ BREAK_CANDLE trades with scores logged:
1. Run correlation analysis: which factors most predict wins?
2. Adjust component weights based on actual data
3. Add `liquidity_score` column to Journal page UI

---

## What Good vs Bad Looks Like

### Good Trade (GBPJPY example)
- `primed: true` ✓
- `zone_found: true` ✓
- `leg_candles: 1` ✓
- `sweep_to_touch_bars: 0` → +30pts
- `peak_to_touch_bars: 4` → +10pts
- `liq_source: MAKUCHAKU_PIVOT` → +15pts
- `zone_grade: A` → +15pts
- `ai_score: 70+` → +20pts
- **Expected score: ~85/100 → EXECUTE**

### Bad Trade (USDJPY example)
- `zone_found: false` → **HARD BLOCKED in Pine**
- `primed: false` → **HARD BLOCKED in Pine**
- `ai_score: 18` → **HARD BLOCKED in Pine**
- **Never reaches backend**

---

## Decision Log

| Decision | Alternatives Considered | Reason |
|---|---|---|
| Two-path architecture (fast + async) | AI Council in critical path | Scalping requires < 100ms; council takes 2-5s |
| Pine hard gates before webhook | Backend-only filtering | Eliminates wasted webhook calls and network latency |
| Pre-cached market data (60s refresh) | On-demand MetaAPI fetch at signal time | Adds 200-500ms latency per trade |
| Rule-based composite scorer | LLM-based scoring | Speed + determinism + debuggability |
| Historical win rate from journal | Assumed static weights | Real data from actual trades beats assumptions |
| Enrich Pine payload with zone fields | Backend re-calculating zone data | Pine is the authoritative S&D source |

---

## Non-Goals

- Not changing S&D zone detection logic
- Not rebuilding the backend signal pipeline
- Not replacing the AI Council (it keeps running async for learning)
- Not adding external market data providers (MetaAPI is sufficient)
