# Requirements

This file is the explicit capability and coverage contract for the project.

Use it to track what is actively in scope, what has been validated by completed work, what is intentionally deferred, and what is explicitly out of scope.

## Active

### R001 — Prop firm rules database with firm/plan/size coverage
- Class: core-capability
- Status: active
- Description: A curated, versioned database of prop firm rules (profit targets, daily loss limits, max drawdown, min trading days, consistency rules, drawdown type) keyed by firm + plan type + account size. Covers FTMO (1-step, 2-step, Standard, Swing), ACG, TFT, E8, FundedNext, The5ers.
- Why it matters: Eliminates manual rule entry — the single biggest friction point. If rules are wrong, traders breach limits and lose accounts.
- Source: user
- Primary owning slice: M001/S01
- Supporting slices: none
- Validation: unmapped
- Notes: Rules must include last-verified date and version tracking. No API exists from any firm — all rules are curated from published documentation.

### R002 — Guided account creation wizard
- Class: primary-user-loop
- Status: active
- Description: When adding a prop firm account, user picks firm → plan type → account size and all challenge limits auto-fill from the rules database. Override any field if needed. Custom/Other firm option allows manual entry.
- Why it matters: Zero-config experience — the user shouldn't need to know what "trailing EOD drawdown" means to set up an account correctly.
- Source: user
- Primary owning slice: M001/S02
- Supporting slices: none
- Validation: unmapped
- Notes: Replaces current AddAccountForm with its hardcoded PROVIDER_DEFAULTS.

### R003 — Per-account prop firm enforcement at trade time
- Class: core-capability
- Status: active
- Description: When the bot evaluates a signal for account X, it reads account X's specific prop firm limits (daily loss kill %, drawdown kill %, etc.) from the database — not from global settings. Different accounts can have different kill thresholds running simultaneously.
- Why it matters: Without this, having multiple accounts with different firms is meaningless — they'd all share one set of limits.
- Source: user
- Primary owning slice: M001/S03
- Supporting slices: none
- Validation: unmapped
- Notes: Currently prop_guard.py reads from global `get_settings()`. Must be refactored to accept per-account parameters.

### R004 — Auto-phase advancement
- Class: core-capability
- Status: active
- Description: When account metrics show the profit target is reached and all rules are satisfied (min trading days, consistency, no breaches), the system auto-advances to the next phase and applies new limits. Phase 1 → Phase 2 → Funded.
- Why it matters: Manual phase switching is error-prone and can leave stale limits active during a critical transition.
- Source: user
- Primary owning slice: M001/S04
- Supporting slices: M001/S03
- Validation: unmapped
- Notes: Should log phase transitions and notify the user. Phase advancement changes the rules applied by enforcement.

### R005 — Consolidate /prop-firm page into account detail
- Class: primary-user-loop
- Status: active
- Description: All challenge tracking — health gauge, drawdown meters, calendar PnL, performance analytics — moves into the account detail view. The separate /prop-firm page is removed. The accounts page becomes the single hub for all prop firm information.
- Why it matters: Currently prop firm data is split across two pages with duplicated logic and inconsistent account selection.
- Source: user
- Primary owning slice: M001/S05
- Supporting slices: none
- Validation: unmapped
- Notes: The current /prop-firm page has ~500 lines of complex UI. This is a migration, not a rewrite — preserve the gauges and analytics, re-parent them into ChallengeTab.

### R006 — Rules versioning with staleness warnings
- Class: failure-visibility
- Status: active
- Description: Each rule set in the database tracks a version number and last-verified date. When rules haven't been verified in >90 days, the UI shows a staleness warning. When a rule set is updated, the version increments.
- Why it matters: User's #1 fear is stale rules causing breaches. Staleness visibility is the defense.
- Source: user
- Primary owning slice: M001/S01
- Supporting slices: M001/S05
- Validation: unmapped
- Notes: Staleness threshold configurable. Warning appears in account detail challenge section.

### R007 — Custom/Other firm support with manual rule entry
- Class: core-capability
- Status: active
- Description: For prop firms not in the curated database, user can select "Other" and manually enter all rule fields. These custom rules are stored per-account and participate in enforcement like curated rules.
- Why it matters: New prop firms appear constantly. The system shouldn't be blocked by an incomplete database.
- Source: user
- Primary owning slice: M001/S02
- Supporting slices: none
- Validation: unmapped
- Notes: Custom rules are account-specific, not added to the shared rules database.

### R008 — Major firm coverage day one
- Class: launchability
- Status: active
- Description: Rules database ships with complete coverage for FTMO (1-step Standard, 1-step Swing, 2-step Standard, 2-step Swing, across all account sizes), ACG, TFT, E8 Funding, FundedNext, The5ers.
- Why it matters: If the most popular firms aren't covered at launch, the feature isn't useful.
- Source: user
- Primary owning slice: M001/S01
- Supporting slices: none
- Validation: unmapped
- Notes: FTMO has the most plan variations (1-step vs 2-step, Standard vs Swing, 5 account sizes). Research each firm's current published rules.

### R009 — Remove MyFundedFX preset
- Class: quality-attribute
- Status: active
- Description: Remove MyFundedFX from all hardcoded presets and the new rules database. The firm shut down in February 2026 and is no longer operational.
- Why it matters: Stale presets for a dead firm is exactly the kind of thing that erodes trust.
- Source: research
- Primary owning slice: M001/S01
- Supporting slices: M001/S02
- Validation: unmapped
- Notes: Currently referenced in AddAccountForm.tsx PROVIDER_DEFAULTS, ChallengeTab.tsx PROVIDER_PRESETS, and prop-firm page.

## Validated

(none yet)

## Deferred

### R010 — Web scraping for auto-updating rules
- Class: operability
- Status: deferred
- Description: Periodically scrape prop firm websites for rule changes and auto-update the database.
- Why it matters: Would make staleness detection unnecessary if it worked reliably.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Rejected in favor of curated database. Scraping is fragile — sites change layouts, use JS rendering, block bots. Revisit if manual curation becomes a burden.

## Out of Scope

### R011 — Prop firm API integration
- Class: constraint
- Status: out-of-scope
- Description: Direct API calls to prop firms to fetch account-specific rules and status.
- Why it matters: Would be the ideal solution but no prop firm exposes public APIs for this.
- Source: research
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Confirmed via research — FTMO, ACG, and all major firms have web dashboards only, no public APIs.

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R001 | core-capability | active | M001/S01 | none | unmapped |
| R002 | primary-user-loop | active | M001/S02 | none | unmapped |
| R003 | core-capability | active | M001/S03 | none | unmapped |
| R004 | core-capability | active | M001/S04 | none | unmapped |
| R005 | primary-user-loop | active | M001/S05 | none | unmapped |
| R006 | failure-visibility | active | M001/S01 | M001/S05 | unmapped |
| R007 | core-capability | active | M001/S02 | none | unmapped |
| R008 | launchability | active | M001/S01 | none | unmapped |
| R009 | quality-attribute | active | M001/S01 | M001/S02 | unmapped |
| R010 | operability | deferred | none | none | unmapped |
| R011 | constraint | out-of-scope | none | none | n/a |

## Coverage Summary

- Active requirements: 9
- Mapped to slices: 9
- Validated: 0
- Unmapped active requirements: 0
