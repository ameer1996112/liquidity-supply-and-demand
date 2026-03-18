# M001: Smart Prop Firm Rules Engine

**Vision:** Zero-config prop firm compliance. Add an account, pick the firm, and the system handles rules, enforcement, and phase advancement automatically. Stale rules must never cause a breach.

## Success Criteria

- User can add a prop firm account by picking firm → plan → size with all limits auto-filled
- Each account enforces its own prop firm limits at trade time — two accounts with different firms get different kill thresholds
- Phase transitions happen automatically when profit target + all conditions are met
- All challenge tracking (health gauge, drawdown, calendar, analytics) lives in account detail — no separate /prop-firm page
- Rules database shows version and last-verified date; stale rules (>90 days) trigger a warning

## Key Risks / Unknowns

- **prop_guard refactor** — Currently tightly coupled to global `get_settings()`. Changing to per-account params could have side effects in the signal processing pipeline.
- **Rules accuracy at scale** — FTMO alone has 20+ rule set variations. Data entry errors in the rules database are the exact failure mode the user fears most.
- **Phase advancement reliability** — Depends on MetaAPI sync recency. Stale account metrics could trigger false advancement or miss a real one.

## Proof Strategy

- prop_guard refactor → retire in S03 by proving two accounts with different limits are enforced correctly in a test
- Rules accuracy → retire in S01 by verifying rules against published firm documentation for each entry
- Phase advancement → retire in S04 by proving an account at profit target auto-advances with new limits applied

## Verification Classes

- Contract verification: pytest for rules engine, per-account enforcement, phase advancement logic
- Integration verification: full chain — wizard → rules auto-fill → enforcement → phase advance
- Operational verification: none (local dev)
- UAT / human verification: add a real account via wizard, confirm limits look right, confirm challenge tab shows correct data

## Milestone Definition of Done

This milestone is complete only when all are true:

- Rules database returns correct limits for all covered firms (FTMO 1-step/2-step Standard/Swing across 5 sizes, ACG, TFT, E8, FundedNext, The5ers)
- Guided wizard auto-fills all challenge fields from rules DB
- prop_guard enforces per-account limits (not global settings) at trade time
- Phase advancement auto-triggers when conditions met
- Account detail page shows full challenge dashboard (health, drawdown, calendar, analytics)
- /prop-firm page is removed from navigation
- MyFundedFX references removed from all code
- Rules versioning and staleness warnings are visible in UI
- Backend tests pass, frontend builds clean

## Requirement Coverage

- Covers: R001, R002, R003, R004, R005, R006, R007, R008, R009
- Partially covers: none
- Leaves for later: R010 (web scraping — deferred)
- Orphan risks: none

## Slices

- [ ] **S01: Prop Firm Rules Engine & Database** `risk:high` `depends:[]`
  > After this: Backend API returns correct rules for any supported firm/plan/size combo. `GET /api/prop-firm-rules/FTMO/2-step-standard/100000` returns profit target, daily loss limit, max drawdown, min trading days, consistency rule, drawdown type — all verified against published docs.

- [ ] **S02: Guided Account Creation Wizard** `risk:medium` `depends:[S01]`
  > After this: Adding a new account via the UI: pick FTMO → 2-Step Standard → $100k → all challenge fields auto-fill from the rules API. Custom/Other firm option allows manual entry. MyFundedFX removed from all dropdowns.

- [ ] **S03: Per-Account Prop Guard Enforcement** `risk:high` `depends:[S01]`
  > After this: Bot evaluating a signal for account X reads account X's prop firm limits from DB. Two accounts with different firms enforce different kill thresholds. Verified by unit tests with two-account scenario.

- [ ] **S04: Auto-Phase Advancement** `risk:medium` `depends:[S01,S03]`
  > After this: Account at FTMO Phase 1 that reaches 10% profit target + min 4 trading days + no breaches → system auto-advances to Phase 2, applies new limits, logs the transition. Verified by test with mock metrics.

- [ ] **S05: Dashboard Consolidation** `risk:medium` `depends:[S01,S02]`
  > After this: Account detail ChallengeTab shows full prop firm dashboard — health gauge, drawdown meters, calendar PnL, performance analytics, staleness warnings. /prop-firm page removed from sidebar and routing.

## Boundary Map

### S01 → S02

Produces:
- `prop_firm_rules` Supabase table — rows keyed by (firm, plan_type, account_size) with all rule fields
- `GET /api/prop-firm-rules/{firm}` — list available plans and sizes for a firm
- `GET /api/prop-firm-rules/{firm}/{plan_type}/{account_size}` — returns full rule set
- `GET /api/prop-firm-rules/firms` — list all supported firms
- Python type: `PropFirmRuleSet` dataclass with all rule fields + version + last_verified_at

Consumes:
- nothing (first slice)

### S01 → S03

Produces:
- `PropFirmRuleSet` dataclass — used by prop_guard to know account-specific limits
- `get_rules_for_account(account_name)` — resolves account → firm/plan/size → rule set

Consumes:
- nothing (first slice)

### S01 → S04

Produces:
- `PropFirmRuleSet.profit_target` — used to detect when target is reached
- `PropFirmRuleSet.min_trading_days` — used to verify trading day requirement
- Phase-specific rule sets — S04 needs to know what the *next* phase's rules are

Consumes:
- nothing (first slice)

### S01 → S05

Produces:
- Rules metadata (version, last_verified_at) — displayed in staleness warnings
- `GET /api/prop-firm-rules/firms` — for any UI that lists available firms

Consumes:
- nothing (first slice)

### S02 → S05

Produces:
- Accounts created with `prop_firm_id`, `plan_type`, `account_size` fields in `broker_profiles` — S05 reads these to display firm-specific UI
- Updated `AddAccountForm` component — wizard pattern that S05's ChallengeTab may reference for consistency

Consumes from S01:
- Rules API endpoints for auto-fill

### S03 → S04

Produces:
- Per-account enforcement infrastructure — `check_safety()` accepts account-specific params
- Account-level metrics tracking (daily PnL, drawdown) scoped to each account

Consumes from S01:
- `get_rules_for_account(account_name)` — resolves account to rule set
