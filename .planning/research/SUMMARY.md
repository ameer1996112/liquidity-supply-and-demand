# Project Research Summary

**Project:** Prop Firm Challenge Dashboard — embedded in Accounts page
**Domain:** Real-time prop firm challenge tracking for live automated trading bot
**Researched:** 2026-03-18
**Confidence:** HIGH (all four research files drawn from direct codebase inspection)

## Executive Summary

This feature embeds a compact prop firm challenge tracker directly into the existing account cards on the `/accounts` page. The system already has substantial prop firm infrastructure — a full standalone `/prop-firm` page, `PropFirmTracker` service, `EvaluationDashboard` component, and `broker_profiles` evaluation columns — but it lacks auto-detection of the firm from the MT5 server name, a normalized rules database, and an account-card-level progress display. The new work is a thin integration layer, not a greenfield build. The base trading stack (FastAPI, Supabase, Next.js, TanStack Query, MetaAPI) is unchanged; no new dependencies are required.

The recommended approach is additive and zero-risk to the existing execution pipeline: one new database migration (047) creates three tables (`prop_firm_server_mappings`, `prop_firm_rules`, `account_prop_firm_config`), two new backend services (`PropFirmDetector`, `PropFirmMetricsService`) delegate to existing `PropFirmTracker` without modifying it, and a single new React sub-component (`PropFirmSection` / `ChallengeProgressPanel`) is embedded in `EnhancedAccountCard` without changing the card's prop interface. The critical architectural constraint is that challenge data must be fetched from a dedicated endpoint at 10s polling intervals, decoupled from the 30s account comparison endpoint, because the two have different freshness requirements.

The primary risks are pre-existing bugs in `prop_firm_tracker.py` and `mtm_guardian.py` that will surface immediately once metrics are displayed: the daily reset boundary uses UTC midnight instead of New York midnight (FTMO resets at 00:00 EST/EDT), the maximum drawdown denominator is wrong for Phase 1/2 (should be initial balance, not trailing high-water mark), the `trades_today` field is hardcoded to 0, and the day-start snapshot captures `balance` instead of `equity`. These bugs must be fixed before the progress bars go live, not after.

## Key Findings

### Recommended Stack

The entire feature is built on the existing stack. No new libraries are needed. The MetaAPI `server` field (`FTMO-Server3`, `FTMO-Demo`) is already fetched, merged, and stored in `account_status_snapshots.server_name` by the existing `AccountSyncService`. Server-name-to-firm mapping belongs in a DB table (not hardcoded in Python) following the same pattern as `symbol_risk_rules` — this allows adding new firms by `INSERT` without a redeploy.

**Core technologies:**
- `@tanstack/react-query 5.90+`: data fetching and 10s polling — already used for all live data hooks
- `<Progress>` component (`ui/progress.tsx`): progress bars with three-color pattern — already exists with identical usage in `EvaluationDashboard.tsx`
- `<Badge>`, `<Alert>` components: firm label and warning banners — already installed
- `@supabase/supabase-js 2.93.3`: Supabase client — already installed; Realtime not needed (polling is sufficient and matches existing patterns)
- `lucide-react`, `date-fns`, `tailwind-merge`: icons, date formatting, class utilities — all present

### Expected Features

**Must have (table stakes):**
- Daily loss progress bar (% consumed vs FTMO 5% limit, dollar amount alongside %)
- Overall/trailing drawdown progress bar (FTMO 10% limit)
- Profit target progress bar (Phase 1: 10%, Phase 2: 5%, Funded: none)
- Trading days counter (X of 4 minimum, with close-date-based counting)
- Days remaining in challenge window (Phase 1: 30 days, Phase 2: 60 days)
- Current phase badge (Phase 1 / Phase 2 / Funded)
- 80% threshold warning banner (yellow) and breach banner (red)
- Auto-detection of prop firm from MT5 server name (gateway to all other features)
- One-time phase setup prompt per account (stored, never asked again)
- Floating PnL included in daily drawdown (FTMO counts open losses — must be visible)

**Should have (differentiators):**
- Challenge health score (0–100, already computed on `/prop-firm` page — surface on card)
- "Margin of safety" in dollars (`remaining = limit_usd - abs(daily_pnl_total)`)
- Bot kill threshold vs FTMO limit distinction (two lines on progress bars: bot kills at 80%, firm limit at 100%)
- Daily reset countdown timer (time until 00:00 EST/EDT)
- Phase transition readiness checklist ("Missing: 2 more trading days")

**Defer (v2+):**
- Projected challenge completion date (needs N days of history; show N/A on new accounts)
- Per-trade MTM contribution to daily loss
- Consistency risk forecasting
- Multi-firm support (The5ers, FundedNext, E8) — schema is ready; seed data deferred
- Email/push notifications — requires new infrastructure

### Architecture Approach

All business logic lives in the backend; the frontend is a pure rendering layer. The backend endpoint `GET /api/v1/prop-firm/challenge/{account_name}` orchestrates firm detection, rules lookup, and metrics computation into a single `ChallengeResponse` that the card renders directly — no metric math in React. Challenge data is decoupled from `AccountResponse` (separate endpoint, separate hook) to avoid adding prop-firm query latency to every accounts page load and to allow independent 10s vs. 30s polling cadences. Existing tables (`broker_profiles`, `account_status_snapshots`, `prop_firm_metrics`, `portfolio_snapshots`) are read-only for this feature; no existing table schemas change.

**Major components:**
1. `prop_firm_server_mappings` (DB table) — maps MetaAPI server name substrings to firm slugs; add firms by INSERT, no code change
2. `prop_firm_rules` (DB table) — official firm limits per (firm_slug, challenge_type, account_size_usd); seeded with FTMO Phase 1, Phase 2, Funded for $50k and $100k
3. `account_prop_firm_config` (DB table) — one row per account; stores firm, phase, starting balance, challenge start date; written once on setup
4. `PropFirmDetector` (service) — `server_name → firm_slug` via ILIKE DB lookup; pure, thin, testable
5. `PropFirmMetricsService` (service) — adapts existing `PropFirmTracker` output into `ChallengeMetrics`; no duplication of calculation logic
6. `GET /api/v1/prop-firm/challenge/{account_name}` (endpoint) — orchestrates detection + rules + metrics; returns `ChallengeResponse` with pre-computed percentages and alert flags
7. `PropFirmSection` / `ChallengeProgressPanel` (React) — self-contained sub-component embedded in `EnhancedAccountCard`; calls `useChallengeStatus(accountName)` internally; renders nothing when firm is unknown and challenge not configured
8. `useChallengeStatus` (hook) — TanStack Query at 10s interval, `retry: 1`, matches existing live-data hook pattern

### Critical Pitfalls

1. **UTC midnight vs. New York midnight reset boundary** — `prop_firm_tracker.py:104` computes `today_start` in UTC; FTMO resets at 00:00 EST/EDT. Must use `zoneinfo` with `reset_tz` stored per firm rule. Add `reset_tz VARCHAR(64)` to `prop_firm_rules`; seed with `America/New_York` for FTMO.

2. **Broker equity as primary source, not calculated floating PnL** — `mtm_guardian.py` uses `yfinance` prices and hardcoded JPY pip values (94× error) for floating PnL, and silently returns $0 on weekends/market close. Use `account_status_snapshots.equity` (broker's own figure, already includes floating PnL, commissions, swap) as the equity source. Fall back to calculated only if snapshot is stale (>5 min).

3. **Wrong drawdown denominator for Phase 1/2** — `prop_firm_tracker.py:153-157` divides by `max_historical_equity` (correct for Funded/trailing), but Phase 1/2 FTMO measures max drawdown from the **initial account balance** (`$50,000`), not the high-water mark. Encode `drawdown_reference: "initial_balance" | "trailing_high_water_mark"` in `prop_firm_rules`.

4. **`trades_today` hardcoded to 0** — `prop_firm_tracker.py:255` has a TODO comment; the field is always 0. Trading days progress bar will always show 0 until this is implemented. Count `DISTINCT DATE(closed_at IN firm timezone)` from `trading_signals` since `challenge_start_date`.

5. **Day-start balance captures `balance` not `equity`** — `mtm_guardian.py:236` uses `balance` as the starting reference; FTMO measures daily drawdown from equity at reset time. Must store `day_start_equity` (not `day_start_balance`) in a `daily_reset_snapshots` table keyed by `(account_name, date_in_firm_tz)`.

## Implications for Roadmap

Based on combined research, a 3-phase approach is recommended. The pre-existing bugs in the metrics layer are blockers for display; they must be addressed before wiring up the UI.

### Phase 1: Data Foundation and Bug Fixes

**Rationale:** All downstream features depend on correct data. Six confirmed bugs in `prop_firm_tracker.py` and `mtm_guardian.py` will produce silently wrong values the moment progress bars go live. Fixing them first means Phase 2 can trust the data it renders. The DB schema (migration 047) must also exist before any service code can be written.

**Delivers:** Correct metrics infrastructure, firm detection, rules catalogue
**Addresses:** Auto-detection (table stakes), `prop_firm_rules` table, FTMO rule seeding
**Fixes required before Phase 2:**
- UTC midnight → New York midnight reset boundary (`prop_firm_tracker.py:104`, `mtm_guardian.py:104`)
- Day-start equity source: `balance` → `equity` (`mtm_guardian.py:236`)
- Max drawdown denominator: trailing high-water mark → initial balance for Phase 1/2 (`prop_firm_tracker.py:153-157`)
- Broker equity as primary floating PnL source (replaces yfinance approximation)
- Silent exception swallowing at 7 locations in `prop_firm_tracker.py`

**Artifacts:**
- `migrations/047_prop_firm_server_mappings.sql` (creates all 3 new tables, seeds FTMO data)
- `src/services/prop_firm_detector.py` (~20 lines, DB-backed ILIKE lookup)
- `src/services/prop_firm_metrics_service.py` (thin adapter over existing `PropFirmTracker`)
- `GET /api/v1/prop-firm/challenge/{account_name}` endpoint registered in `api.py`
- `PUT /api/v1/prop-firm/challenge/{account_name}/config` (one-time setup)

### Phase 2: Account Card UI

**Rationale:** Backend is correct and endpoint exists; now wire up the frontend. All UI components (`<Progress>`, `<Badge>`, `<Alert>`) are already installed. Pattern is confirmed from `EvaluationDashboard.tsx`. This phase can proceed rapidly once Phase 1 is stable.

**Delivers:** Prop firm progress bars embedded in account cards; 80% warning banners; one-time challenge setup prompt
**Implements:** `ChallengeProgressPanel`, `PropFirmBadge`, `ChallengeSetupPrompt`, `useChallengeStatus` hook
**Avoids:**
- Computing metrics in React (all percentages pre-computed in backend)
- Embedding challenge data in `AccountResponse` (separate endpoint, separate hook)
- Adding WebSocket infrastructure (10s polling is sufficient)
- Altering `broker_profiles` for display config (uses new `account_prop_firm_config` table)
**Also fixes in this phase:**
- `trades_today` hardcoded 0 (implement before trading days bar goes live)
- Trading day counting: use `closed_at` not `created_at` (FTMO counts close date)
- Progress bar clamping: server-side `max(0.0, min(pct, 100.0))` before returning
- MetaAPI snapshot staleness indicator (show "as of Xs ago" badge)

### Phase 3: Differentiators and Polish

**Rationale:** Core compliance tracking is live. Phase 3 adds the features that make the dashboard genuinely better than the FTMO web portal. These require the Phase 1 and Phase 2 infrastructure to exist first.

**Delivers:** Health score on account card, bot kill threshold vs FTMO limit dual markers, daily reset countdown, phase transition readiness checklist, Redis caching for high-frequency polling
**Notes:**
- Redis caching (Phase 3) becomes important if more than 3 accounts are tracked simultaneously (108+ Supabase queries/min otherwise)
- "Reassign challenge type" button (Phase 3) handles Phase 1 → Phase 2 promotion edge case
- Projected completion date shows N/A on new accounts; implement once data accumulates

### Phase Ordering Rationale

- Phase 1 before Phase 2: data bugs produce wrong values; displaying wrong values destroys trust faster than showing nothing
- Bug fixes co-located with DB schema: the same migration that adds `reset_tz` to rules enables the correct reset boundary fix — they are one atomic unit
- Phase 2 before Phase 3: health score and dual-threshold markers depend on the same `ChallengeResponse` shape established in Phase 1/2
- Services before frontend: `PropFirmDetector` and `PropFirmMetricsService` can be built and tested without any frontend work; reduces blast radius of backend changes

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (reset timezone):** FTMO's exact reset timezone (New York midnight is research-knowledge; needs verification against current FTMO FAQ before seeding `reset_tz` in rules DB — web access was unavailable during research)
- **Phase 1 (trailing vs balance-based drawdown):** `PropFirmTracker` trailing drawdown logic must be audited to confirm it correctly handles both `"initial_balance"` and `"trailing_high_water_mark"` denominator modes — not currently implemented
- **Phase 3 (Redis caching pattern):** Caching pattern exists (`logic.py` balance cache) but `PropFirmMetricsService` integration with Redis has not been designed

Phases with standard patterns (skip research-phase):
- **Phase 2 (UI components):** All components confirmed present; pattern confirmed from `EvaluationDashboard.tsx`; TanStack Query hook pattern confirmed from `useEvaluationStats.ts` and `usePropFirmMetrics`
- **Phase 1 (DB migration):** Migration pattern confirmed from migrations 015, 021, 028; schema is fully designed in ARCHITECTURE.md
- **Phase 1 (firm detection):** `PropFirmDetector` is ~20 lines; pattern is a simple ILIKE query; no research needed

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All libraries confirmed present in `package.json` and `pyproject.toml` via codebase inspection; no new dependencies needed |
| Features | MEDIUM-HIGH | FTMO rule values (5%/10%/4 days) confirmed from existing codebase constants; exact reset timezone and trailing vs balance-based drawdown semantics need external verification |
| Architecture | HIGH | Component boundaries and data flow derived entirely from existing production code; 3-table additive schema confirmed clean against existing migration patterns |
| Pitfalls | HIGH | 6 specific bugs identified with exact file/line references in the current codebase; not hypothetical |

**Overall confidence:** HIGH

### Gaps to Address

- **FTMO reset timezone:** Research identifies New York midnight (00:00 EST/EDT) but this was not verified against current FTMO documentation (web access denied during research). Before seeding the `reset_tz` field, verify at https://ftmo.com/en/trading-rules/ or FTMO FAQ. If wrong, it creates systematic daily PnL miscalculation.
- **FTMO trailing vs balance-based drawdown per phase:** FEATURES.md and PITFALLS.md agree that Phase 1/2 use balance-based (initial account value as denominator) and Funded uses trailing high-water mark. The existing `PropFirmTracker` uses trailing for all phases. The schema fix (`drawdown_reference` field) is designed, but the corresponding Python computation branch does not yet exist — must be implemented in Phase 1.
- **Challenge setup UX (inline vs modal):** Whether the one-time phase selection appears inline in the card or in a modal is an unresolved frontend design decision. Both `useChallengeSettings` and `useUpdateChallengeSettings` hooks already exist in `useChallenge.ts` for the PUT endpoint call. Decision needed before Phase 2 implementation begins.
- **FTMO rule values may change without notice:** The `source_url` and `effective_date` columns in `prop_firm_rules` exist to flag when a manual re-check is due. Check FTMO's published rules before each seeded migration.

## Sources

### Primary (HIGH confidence)
- `src/services/prop_firm_tracker.py` — metrics computation, confirmed bugs at lines 104, 153-157, 255
- `src/core/guard_rails/mtm_guardian.py` — day-start balance bug at line 236, JPY pip value error at line 168
- `src/adapters/execution/meta_api_adapter.py` — `server` field confirmed available
- `src/services/account_sync_service.py` — `server_name` write path confirmed
- `migrations/014_evaluation_progress.sql`, `021_per_account_evaluation.sql` — existing schema reference
- `frontend/src/components/accounts/detail/ChallengeTab.tsx` — existing challenge setup UI
- `frontend/src/components/ui/progress.tsx` — Progress component confirmed
- `frontend/src/hooks/usePropFirm.ts` — polling pattern confirmed (10s interval)
- `.planning/PROJECT.md` — feature scope and anti-features

### Secondary (MEDIUM confidence)
- Training knowledge of FTMO published rules — rule values match codebase constants; reset timezone assumed New York midnight pending external verification
- `.planning/codebase/CONCERNS.md` — Supabase connection limit concern (informs Redis caching recommendation)

---
*Research completed: 2026-03-18*
*Ready for roadmap: yes*
