# Feature Landscape: Prop Firm Challenge Dashboard

**Domain:** Prop firm challenge tracker embedded in an automated trading bot's accounts page
**Researched:** 2026-03-18
**Confidence note:** FTMO rule values sourced from (1) existing codebase — `config/settings.py`, `api_prop_firm.py`, and `migrations/014_evaluation_progress.sql` which contain developer-confirmed values, and (2) training knowledge of FTMO's published rules. Web verification was unavailable in this session. Confidence: MEDIUM-HIGH (codebase is the most authoritative local source; values match training knowledge).

---

## FTMO Challenge Rules Reference

This is the factual foundation every feature in this dashboard must reflect correctly.

### Phase 1 — Challenge

| Rule | Value | Notes |
|------|-------|-------|
| Profit target | 10% of account | $5,000 on a $50k account |
| Max daily loss | 5% of initial balance | $2,500 on $50k — measured from start-of-day balance, includes floating |
| Max overall drawdown | 10% trailing | From highest equity ever reached — not from starting balance |
| Min trading days | 4 | Not 4 consecutive — just 4 calendar days with at least one closed trade |
| Max trading period | 30 calendar days | Challenge fails if not passed within 30 days |
| Consistency rule | 40% | No single day's profit can exceed 40% of the total profit for the challenge period |
| News trading | Allowed | No restriction on trading around news in standard FTMO |
| Weekend holding | Allowed | Positions can be held over weekends |

### Phase 2 — Verification

| Rule | Value | Notes |
|------|-------|-------|
| Profit target | 5% of account | $2,500 on a $50k account — half of Phase 1 |
| Max daily loss | 5% of initial balance | Same as Phase 1 |
| Max overall drawdown | 10% trailing | Same as Phase 1 |
| Min trading days | 4 | Same requirement as Phase 1 |
| Max trading period | 60 calendar days | Twice as long as Phase 1 |
| Consistency rule | 40% | Same rule applies |

### Funded Account

| Rule | Value | Notes |
|------|-------|-------|
| Profit target | None (ongoing) | Trader earns a split of profits |
| Max daily loss | 5% of balance | Resets each trading day |
| Max overall drawdown | 10% trailing | Trailing from highest equity |
| Min trading days | None | No minimum requirement |
| Max trading period | None | No expiry |
| Consistency rule | 40% | Applies per payout period |
| Profit split | 80% to trader | Standard FTMO — 90% available after scaling |

### Drawdown Calculation Details (Critical)

FTMO calculates drawdown from **equity** (balance + floating PnL), not balance alone. This means:

- A large open losing position counts against the daily loss limit even before it is closed.
- The overall drawdown is **trailing**: it tracks the all-time equity peak, not the starting balance.
- Daily reset happens at 00:00 server time (Central European Time — CET/CEST).
- The bot already implements this correctly in `prop_firm_tracker.py` via `daily_pnl_closed + daily_pnl_floating`.

### Bot Safety Buffer (Existing Implementation)

The codebase operates at 80% of firm limits to create a buffer before hard breach:

| Limit | FTMO Rule | Bot Kill Threshold |
|-------|-----------|-------------------|
| Daily loss | $2,500 (5% of $50k) | $2,000 (4% of $50k) |
| Overall drawdown | 10% | 8% |

The dashboard must display **FTMO limits** (5%, 10%), not bot kill thresholds, so traders understand where they stand against the actual firm rules.

---

## What Already Exists (Do Not Re-Build)

Before defining features, it is critical to know what is already built and working:

**Backend (fully implemented):**
- `prop_firm_tracker.py` — daily HWM tracking, floating+closed PnL, daily/trailing drawdown calculations, breach flags, days remaining, consistency analysis
- `api_prop_firm.py` — `/api/prop-firm/metrics`, `/api/prop-firm/history`, `/api/prop-firm/reset`, `/api/prop-firm/consistency`, `/api/prop-firm/mtm`
- `api_funding.py` — `/api/v1/funding/daily-pnl`, `/api/v1/funding/stats` (equity curve, aggregate stats)
- `guard_rails/prop_guard.py` — execution-time enforcement of daily loss and drawdown limits
- `evaluation_progress` table — challenge rules storage per account
- `prop_firm_metrics` table — time-series snapshots of compliance data
- `broker_profiles` table — per-account evaluation mode, phase, and rule limits

**Frontend (fully implemented):**
- `/prop-firm` page — full standalone challenge dashboard (health score gauge, daily/trailing drawdown circular gauges, consistency rule gauge, account overview, performance summary, calendar PnL view, historical snapshots)
- `usePropFirm` hooks — data fetching for metrics, history, MTM, daily reset mutation
- `CircularGauge` component — reusable gauge with color zones
- Phase badge, health score algorithm (0–100 scoring)

**What is NOT yet built:**
- Auto-detection of prop firm from MT5 server name (e.g., `FTMO-Server3` → FTMO)
- One-time challenge type setup per account (Phase 1 / Phase 2 / Funded selection saved to DB)
- Internal `prop_firm_rules` database table (firm + challenge_type → rules JSON)
- Prop firm metrics embedded inside account cards on the `/accounts` page
- 80% threshold alert/warning banners on account cards

---

## Table Stakes

Features every prop trader expects a challenge tracker to have. Missing any of these makes the dashboard feel unfinished or untrustworthy.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Daily loss progress bar with % consumed vs limit | Every prop trader checks this multiple times per day — it is the most common account blow reason | Low | Already computed by backend; needs embedding in account card UI |
| Overall/trailing drawdown progress bar | Second most critical rule — breach ends the account immediately | Low | Already computed by backend |
| Profit target progress bar | Traders need to know how far they are from passing | Low | `current_profit_usd / profit_target_usd * 100` |
| Trading days counter (X of min required) | Minimum trading days is a common gotcha — traders forget to trade on some days | Low | `days_traded / min_trading_days` |
| Days remaining in challenge | Time pressure is a primary source of bad decisions | Low | `evaluation_start_date + max_days - today` |
| Current phase badge (Phase 1 / Phase 2 / Funded) | Context for all rules shown | Low | Simple label from stored phase |
| "Safe to trade" / "At risk" status | Binary status that summarizes all rule checks | Low | Already computed: `not (daily_loss_breach or drawdown_breach)` |
| 80% threshold warning banner | Standard risk practice — early warning without being noise | Low | Trigger at `consumed / limit >= 0.8` |
| Floating PnL included in daily loss calculation | FTMO counts open losses — this is a common misconception that trips up traders | Medium | Backend already does this; must be visible in UI so traders understand |
| Dollar amounts alongside percentages | "You have $800 left today" is more actionable than "3.2% consumed" | Low | Both units side by side |
| Phase-specific rule display | Different rules per phase — showing Phase 1 rules on a Phase 2 account is misleading | Low | Fetch rules from `prop_firm_rules` table keyed by firm + phase |
| Auto-detection of firm from server name | Traders should not configure rules manually | Medium | Parse MetaAPI `server` field for firm name keywords |
| One-time phase setup (saved, never asked again) | Setup friction kills adoption | Medium | Single modal on first account detection; stored in `broker_profiles` |
| Consistency rule tracking | FTMO's 40% rule catches traders off guard | Medium | Already computed by `ConsistencyAnalyzer`; needs display in card |

## Differentiators

Features not universally expected but that make this dashboard exceptional — things that go beyond what the FTMO web portal shows.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Challenge health score (0–100) | Single number traders can glance at instead of reading 4 gauges — more actionable | Medium | Already implemented in `/prop-firm` page as a computed score from daily DD + trailing DD + consistency; needs to be surfaced on account card too |
| "Margin of safety" display | Show how many more dollars the trader can lose before hitting each limit — more intuitive than % consumed | Low | `remaining_usd = limit_usd - abs(daily_pnl_total)`; already in backend response |
| Projected challenge completion date | Given current daily profit rate, estimate when the profit target will be hit vs the challenge deadline | Medium | `profit_target - current_profit / avg_daily_profit` — gives traders a simple timeline check |
| Bot kill threshold vs FTMO limit distinction | Bot kills at 80% of FTMO limits — traders need to know both numbers so they are not confused when the bot stops before the FTMO limit is hit | Low | Show two horizontal lines on progress bars: bot kill (dashed, amber) and FTMO limit (solid, red) |
| Daily reset countdown timer | Shows time until daily loss counter resets — prevents traders from making last-minute panicked trades | Low | `time_until_next_00:00_CET` |
| Per-trade contribution to daily loss | Show which open positions are consuming the most daily budget right now | Medium | Requires MTM data per position — already available via `/api/prop-firm/mtm` |
| Consistency risk forecasting | Warn the trader if current trajectory will violate the 40% rule if today's profit continues at the same rate | Medium | `(today_profit / total_profit_if_goal_met) * 100` — simple projection |
| Phase transition readiness checklist | When all rules are met, show a clear "Ready to advance" or "Missing: 2 more trading days" summary | Low | Composite check: profit >= target AND days_traded >= min_days AND no breach |

## Anti-Features

Features to explicitly NOT build in this milestone. They sound useful but add scope, complexity, or risk that outweighs the benefit right now.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Email or push notifications | Requires new infrastructure (SendGrid, FCM, etc.) — out of scope per PROJECT.md | Dashboard banner at 80% threshold is sufficient for this milestone |
| Auto-pause trading on rule breach | The risk engine (`prop_guard.py`) already enforces this at execution time — duplicating it in the UI creates a confusing second enforcement layer | Trust the existing guard rail; display its status in the UI |
| Manual rules configuration UI | Traders should not need to enter "5% daily loss" themselves — that creates data entry errors | Auto-detect firm from server name; rules come from the internal `prop_firm_rules` table seeded by the developer |
| Multi-firm support (The5ers, FundedNext, E8, etc.) | Adds seeding and testing scope for rules the developer has not verified | Seed FTMO only at launch; schema already supports adding more firms without code changes |
| FTMO API / dashboard integration | FTMO does not expose a public API; screen-scraping would be brittle and violates terms | Use internal rules DB + MetaAPI broker data — the same data FTMO uses to make their calculations |
| Custom rules editor | Edge case for non-FTMO firms — creates maintenance burden and risk of misconfiguration | The `prop_firm_rules` table can be seeded via SQL migration when adding new firms |
| Historical challenge comparison | "How did this challenge compare to my last one?" is a nice-to-have analytics feature | Out of scope; the `/prop-firm` page already has historical snapshots for the current challenge |
| Profit split / payout request tracking | This is account management, not challenge compliance | Out of scope for this milestone |

---

## Feature Dependencies

```
Auto-detect firm from server name
  → One-time phase setup modal (firm must be known before phase is shown)
    → prop_firm_rules table lookup (phase must be known to fetch rules)
      → Daily loss progress bar (rules must be fetched)
      → Trailing drawdown progress bar (rules must be fetched)
      → Profit target progress bar (rules must be fetched)
      → Trading days counter (rules must be fetched for min_trading_days)
      → Days remaining (rules must be fetched for max_trading_period)
      → 80% threshold alert banner (rules must be fetched for limit values)
      → Consistency rule display (rules must be fetched for 40% limit)
      → Phase transition readiness checklist (rules must be fetched for all targets)

Challenge health score
  → Daily loss % consumed (dependency)
  → Trailing drawdown % consumed (dependency)
  → Consistency % consumed (dependency)

Bot kill threshold vs FTMO limit display
  → Bot kill threshold from broker_profiles (already stored)
  → FTMO rule values from prop_firm_rules table (new table)
```

---

## MVP Recommendation

Prioritize in this order:

1. **Auto-detect firm from server name** — this unlocks everything; without it the user must configure manually, which is the problem being solved
2. **One-time phase setup modal** — minimal friction, stored once in `broker_profiles`, never shown again
3. **`prop_firm_rules` table seeded with FTMO values** — 6 rows (Phase 1, Phase 2, Funded for FTMO Standard and FTMO Aggressive), single SQL migration
4. **Account card prop firm section** — embed 4 progress bars (daily loss, overall drawdown, profit target, trading days) and the "safe to trade" status directly in the existing account card layout
5. **80% alert banner on account card** — yellow warning when any metric reaches 80% of its limit; red when breached

**Defer to later iteration:**
- Projected completion date: requires N days of history to compute a meaningful average — show "N/A" on new accounts; implement after data accumulates
- Per-trade MTM contribution: useful but not needed for challenge compliance awareness
- Consistency risk forecasting: nice-to-have; standalone `/prop-firm` page already shows consistency status

---

## Existing `/prop-firm` Page vs. Account Card Scope

The `/prop-firm` page is a deep-dive view that already works. The new work is:

- The **account card** on the `/accounts` page needs a condensed prop firm section (no charts, no calendar — just bars and numbers)
- The `/prop-firm` page may need updates to consume `prop_firm_rules` from the new table instead of hardcoded values
- The two surfaces should share the same data source (the new `/api/v1/prop-firm/challenge-status/:account_name` endpoint or equivalent)

The feature list above applies to the **account card embedded view** specifically, unless noted otherwise.

---

## Sources

- `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/config/settings.py` — FTMO rule values confirmed in settings (lines 340–417)
- `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/src/api_prop_firm.py` — existing endpoints and hardcoded FTMO constants (daily_limit_pct=5.0, consistency limit=40%)
- `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/migrations/014_evaluation_progress.sql` — `min_trading_days`, `consistency_max_day_pct` schema comments confirm FTMO values
- `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/migrations/021_per_account_evaluation.sql` — default values: `max_daily_loss_pct=5.0`, `max_drawdown_pct=10.0`, `consistency_limit_pct=40.0`
- `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/src/services/prop_firm_tracker.py` — Phase 1 = 30 days, Phase 2 = 60 days, funded = no limit (lines 193–198)
- `/Users/ameeramer/dev/projects/galilsoftware/sources/trading/.planning/PROJECT.md` — active requirements and out-of-scope decisions
- Training knowledge of FTMO published rules — MEDIUM confidence (verified against codebase constants)
