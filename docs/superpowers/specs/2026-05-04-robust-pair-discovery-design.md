# Robust Pair & Settings Discovery System

**Date:** 2026-05-04
**Status:** Approved for planning
**Ticket:** DEV-266

---

## Summary

Build a multi-stage automated pipeline that discovers which pairs and parameter settings are genuinely robust for the ArgerFX LSD (Liquidity Supply & Demand) strategy on 5-minute charts — and which are just overfitting to one time window.

The pipeline runs overnight on TradingView Desktop via the existing MCP automation. The output is a locked `approved_pairs.json` file that the bot reads to decide what it is allowed to trade. If a pair is not in that file, the bot blocks it. The file is re-validated every 30 days automatically.

The goal is to reach a state where you can start a prop firm evaluation knowing exactly which pairs will be profitable, in which session, with proven settings — and the bot handles everything without you needing to watch.

---

## Problem Being Solved

The current optimizer finds the best parameters for a pair on one time window. Those parameters overfit — they look great on the training window but fail forward. Evidence: XAUUSD showed PF 0.29 on OOS 365d validation despite training well. USDJPY showed PF 1.08 and NAS100 PF 1.64 on the same OOS window — meaning some pairs genuinely hold up and others don't.

The system has no way to distinguish between "this pair works with this strategy" and "these params happened to fit this specific historical period." This design solves that.

---

## Target Pairs

The 7 pairs known to work with this strategy, to be validated by the pipeline:

- GBPJPY
- USDJPY
- EURJPY
- GBPUSD
- XAUUSD
- NAS100
- Futures (ES1!, NQ1! — treated separately due to contract sizing)

---

## Strategy Rules (ArgerFX LSD — 4-Step Checklist)

Every backtest and live signal must satisfy all 4 steps. These are the ground truth rules the Pine strategy enforces:

1. **Market direction** — price trending clearly up or down (bottom-left to top-right / top-left to bottom-right)
2. **Zone formation** — last bearish candle before strong bullish push (demand) or last bullish candle before strong bearish push (supply). Zone = top wick to bottom wick of that candle.
3. **Liquidity sweep** — price retraces to a swing high/low (retail stop-losses), sweeps it, but does NOT touch the zone. Sweep must be within halfway between zone edge and bottom of the move.
4. **Break of structure** — after the sweep, price breaks the previous swing high (for buys) or swing low (for sells), confirming trend continuation.
5. **Entry** — price returns to zone, wait for a directional close candle (green for buys, red for sells).
6. **SL** — below/above deepest wick inside the zone.
7. **TP** — 1:3 RR for all pairs, 1:4 for XAUUSD.

**Invalidations (auto-reject a setup):**
- Liquidity touches the zone before structure break
- Any candle closes inside the zone before entry
- Zone is too large relative to the setup
- Only one market structure swing (need ≥2)
- Liquidity distance > halfway from zone edge to bottom of move

---

## The 5-Stage Pipeline

### Stage 1 — Session Discovery

**Purpose:** Find which trading session each pair is actually alive in. Different pairs peak at different times. Trading XAUUSD at 3am produces noise, not setups.

**How it runs:**
For each of the 7 pairs, run 4 separate Bayesian optimizer runs — one per session window:
- Asian: 00:00–07:00 UTC
- London open: 07:00–12:00 UTC
- NY open: 13:00–17:00 UTC
- London-NY overlap: 12:00–17:00 UTC

Each run uses the full 365-day history with `filter_trading_hours=true`, `enable_date_filter=false`. Runs 150 Bayesian trials (Optuna) per session. Minimum 20 trades required for a session to be considered valid.

**Pass criteria per session:**
- PF ≥ 1.15
- Trade count ≥ 20
- Max DD ≤ 6%

**Output:** For each pair, the 1-2 winning sessions. If no session passes, the pair is eliminated at Stage 1.

**Optimizer runs:** 7 pairs × 4 sessions = 28 Bayesian runs (~7 hours overnight)

---

### Stage 2 — Multi-Year Robustness Grid

**Purpose:** Prove that the winning session + params work across independent years, not just the training window.

**How it runs:**
For each pair that passed Stage 1, take its winning session. Run the Bayesian optimizer on each of 5 independent yearly windows:
- 2021 (Jan–Dec)
- 2022 (Jan–Dec)
- 2023 (Jan–Dec)
- 2024 (Jan–Dec)
- 2025 (Jan–Dec)

This gives 5 sets of "best params" for each pair. Then run cross-validation: take the best params from each year and test them (single backtest, no Bayesian) on all other years. This is a 5×5 matrix per pair.

**Pass criteria:**
- A pair passes Stage 2 if its params produce PF ≥ 1.05 in at least 4 of 5 years during cross-validation.
- Any year with a catastrophic fold (DD > 8% or PF < 0.80) is an automatic Stage 2 fail.
- The "approved params" are the set that scored highest on the cross-validation median — not the best params from any single year.

**Output:** For each passing pair, the cross-validated parameter set (the most stable, not the most profitable on any one window).

**Optimizer runs:** 7 pairs × 5 years training = 35 Bayesian runs + up to 7 pairs × 5 params sets × 4 cross-validation backtests each = up to 140 simple backtests (~12 hours overnight, can overlap Stage 1 on separate TradingView windows)

---

### Stage 3 — Parameter Stability Test

**Purpose:** Ensure the approved params are not brittle. If nudging a parameter ±20% causes performance to collapse, the params are overfit even if they passed Stage 2.

**How it runs:**
Pure Python — no TradingView needed. Uses the existing `parameter_stability_tester.py`. For each approved param set:
- Nudge each tunable parameter ±20% independently
- Re-score using the cross-validation results already stored
- Calculate a stability score: % of nudges that keep PF ≥ 1.0

**Pass criteria:**
- Stability score ≥ 70% (at least 70% of parameter nudges keep the strategy profitable)
- No single parameter nudge causes DD to exceed prop firm limits (10%)

**Output:** Stability score per pair. Pairs below 70% are flagged as `WATCH_ONLY` (not blocked, but traded at 25% normal risk until re-validated).

**Runtime:** ~5 minutes in Python.

---

### Stage 4 — Prop Firm Survival Simulation

**Purpose:** Translate the cross-validated results into a probability of passing an Alpha Capital 50K evaluation within 30 trading days.

**Alpha Capital rules:**
- Target: +10% ($5,000 on 50K)
- Max daily loss: 5% ($2,500)
- Max total drawdown: 10% ($5,000)
- Min trading days: typically 5

**How it runs:**
Uses the existing `prop_account_simulator.py`. For each approved pair, run 500 Monte Carlo simulations of the trade sequence (sampling from the actual trade distribution found in cross-validation). Each simulation tracks equity curve, daily loss, and total drawdown against Alpha Capital rules.

**Output per pair:**
- Probability of passing evaluation within 30 trading days
- Median days to reach 10% target
- Probability of hitting max drawdown before target
- Recommended risk per trade for this pair on this account size

**Pass criteria for `approved_pairs.json`:**
- Pass probability ≥ 60%
- Probability of max DD hit ≤ 25%

Pairs that pass Stage 3 but fail Stage 4 at normal risk are retested at 50% risk. If they pass at 50% risk, they enter `approved_pairs.json` as `TRADE_REDUCED_RISK`.

---

### Stage 5 — 30-Day Lock + Auto Re-Validation

**Purpose:** Keep the approved pair list accurate over time without manual intervention.

**How it works:**
- Every approved pair gets an `approved_until` date = approval date + 30 days
- A scheduled job (existing `daily_candidate_selector.py` extended) checks expiry daily
- 3 days before expiry: re-run Stages 3 and 4 only (using the last 30 days of live data as the new validation window). No full Bayesian re-run unless the pair fails.
- If a pair fails re-validation: downgrade to `TRADE_REDUCED_RISK` for 7 days, then full re-run
- If a pair fails full re-run: remove from `approved_pairs.json`, block in guard rail

**Output:** `approved_pairs.json` always has accurate expiry dates. The daily decision report shows days remaining until re-validation for each pair.

---

## Output Artifacts

### `approved_pairs.json`
Machine-readable. Consumed by the bot's guard rail on every signal.

```json
{
  "schema_version": 2,
  "generated_at": "2026-05-04T02:00:00Z",
  "pairs": {
    "USDJPY": {
      "status": "TRADE_NORMAL_RISK",
      "session_utc": {"start": 0, "end": 9},
      "approved_until": "2026-06-04",
      "pass_probability_pct": 72,
      "stability_score_pct": 84,
      "cross_val_median_pf": 1.31,
      "params": {
        "liq_max_distance_pips_forex": 18.0,
        "liq_entry_max_dist": 10.0,
        "max_sweep_to_touch_bars": 15,
        "max_peak_to_touch_bars": 35,
        "rr_mode": "fixed_3.0",
        "trading_start_hour": 0,
        "trading_end_hour": 9
      }
    }
  }
}
```

### `pair_discovery_report.md`
Human-readable morning report:
- Approved pairs with session, pass probability, stability score, expiry date
- Rejected pairs with exact rejection stage and reason
- Pairs expiring within 7 days
- Recommended trade configuration for today

### Frontend Dashboard Widget
New widget in the existing React dashboard:
- Green card per approved pair: session window, pass probability, days until re-validation
- Yellow card: `TRADE_REDUCED_RISK` pairs
- Red card: recently rejected pairs with reason
- "Last validated" timestamp

### Guard Rail Integration
New `ApprovedPairsGuard` in `src/core/guard_rails/approved_pairs_guard.py`:
- Reads `approved_pairs.json` on startup and caches with 5-minute TTL
- Rejects any signal for a pair not in the approved list
- Rejects any signal outside the approved session window for that pair
- Logs rejection reason clearly

---

## What This Does Not Include

- Auto-promoting optimizer results to live trading without human review of the report
- Changing the Pine strategy logic or the 4-step entry rules
- Building a portfolio allocator or capital scheduler
- Re-running Stage 1 or Stage 2 automatically (only manual trigger or on hard re-validation failure)
- Adding new pairs beyond the 7 target pairs without a manual Stage 1+2 run

---

## Implementation Order

1. Add `enable_date_filter` + `start_date`/`end_date` support to the optimizer MCP runner (required for yearly windows)
2. Build Stage 1: session sweep runner — 4 sessions per pair, outputs winning session
3. Build Stage 2: multi-year grid runner — 5 yearly windows + cross-validation matrix
4. Extend Stage 3: `parameter_stability_tester.py` to produce stability score
5. Extend Stage 4: `prop_account_simulator.py` to produce pass probability
6. Write pipeline orchestrator that chains Stages 1→2→3→4 and writes `approved_pairs.json`
7. Write `pair_discovery_report.md` generator
8. Build `ApprovedPairsGuard` guard rail
9. Build frontend dashboard widget
10. Build Stage 5: 30-day re-validation scheduler

---

## Success Criteria

- Running the full pipeline overnight produces `approved_pairs.json` with at least 3 pairs
- Every approved pair has cross-validation median PF ≥ 1.10 and stability score ≥ 70%
- The bot refuses to trade any pair not in `approved_pairs.json`
- After 30 days of live trading, approved pairs continue to perform within 20% of their projected metrics
- At least one approved pair has Monte Carlo pass probability ≥ 60% for Alpha Capital 50K evaluation
