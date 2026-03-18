# Roadmap: Prop Firm Dashboard Upgrade

## Overview

This milestone embeds real-time prop firm challenge tracking directly into the existing account cards. The work proceeds in three phases: first fix the pre-existing metrics bugs and build the backend data foundation so the numbers are trustworthy; then wire the correct data to the frontend account card UI; finally add Redis caching to keep Supabase load sustainable as more accounts are tracked.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Data Foundation and Bug Fixes** - Correct metrics backend with firm auto-detection, DB schema, and FTMO rules seeded
- [ ] **Phase 2: Account Card UI** - Progress bars and challenge status embedded in account cards with 80% warning banners
- [ ] **Phase 3: Caching and Polish** - Redis caching for multi-account sustainability and UX differentiators

## Phase Details

### Phase 1: Data Foundation and Bug Fixes
**Goal**: The backend produces correct prop firm metrics for FTMO accounts — firm auto-detected from server name, rules in DB, all six known calculation bugs fixed
**Depends on**: Nothing (first phase)
**Requirements**: BUG-01, BUG-02, BUG-03, BUG-04, BUG-05, BUG-06, DATA-01, DATA-02, DATA-03, DATA-04, API-01, API-02, API-03
**Success Criteria** (what must be TRUE):
  1. An FTMO account's server name (e.g. `FTMO-Server3`) is automatically mapped to firm "FTMO" — no manual input required
  2. Daily drawdown resets at New York midnight (not UTC midnight) — correct for winter and summer time
  3. The challenge-status API returns daily DD, total DD, profit target, and trading days as correct percentages for all three FTMO challenge types
  4. An unrecognized server name returns `firm_detected: false` with empty metrics — the system does not crash or return wrong data
  5. One-time challenge type selection (Phase 1 / Phase 2 / Funded) can be saved per account and is never asked again
**Plans**: TBD

Plans:
- [ ] 01-01: DB migration — create prop_firm_server_mappings, prop_firm_rules, account_prop_firm_config tables; seed FTMO data
- [ ] 01-02: Fix six bugs in prop_firm_tracker.py and mtm_guardian.py (reset tz, equity baseline, drawdown denominator, trades_today, silent exceptions, JPY pip value)
- [ ] 01-03: PropFirmDetector service and PropFirmMetricsService adapter; register API endpoints

### Phase 2: Account Card UI
**Goal**: Every account card with a linked MT5 account shows its prop firm challenge progress in real-time — progress bars, trading days counter, and warning banners — all without leaving the accounts page
**Depends on**: Phase 1
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08, UI-09
**Success Criteria** (what must be TRUE):
  1. The account card shows daily drawdown, total drawdown, and profit target progress bars with green/amber/red color states at the 80% threshold
  2. The trading days counter displays "X days / 4 min" and shows a checkmark once the minimum is met
  3. A warning banner appears inside the card when any metric reaches 80% of its limit, naming which limit is close
  4. An account with an unrecognized server shows "Unknown firm" with the raw server name — no broken UI
  5. The inline challenge type selector appears only when firm is detected but phase not yet configured, then disappears permanently after selection
**Plans**: TBD

Plans:
- [ ] 02-01: PropFirmSection component, usePropFirmChallenge hook (10s polling), embedded in EnhancedAccountCard
- [ ] 02-02: Progress bar sub-components (daily DD, total DD, profit target), trading days counter, warning banner, unknown-firm fallback state

### Phase 3: Caching and Polish
**Goal**: The system sustains real-time polling for multiple simultaneous accounts without saturating Supabase connections — and the daily reset countdown makes it clear when the trading day resets
**Depends on**: Phase 2
**Requirements**: CACHE-01, CACHE-02, CACHE-03
**Success Criteria** (what must be TRUE):
  1. The challenge-status endpoint returns a cached response within 30s TTL — Supabase is not queried on every frontend poll
  2. A background worker updates Redis every 20s per account independently of frontend polling
  3. Adding a second or third MT5 account does not increase Supabase query rate proportionally
**Plans**: TBD

Plans:
- [ ] 03-01: Background worker writing prop_firm metrics to Redis (key: prop_firm:metrics:{account_id}, TTL 30s, interval 20s)
- [ ] 03-02: Update challenge-status endpoint to read from Redis with DB fallback on cache miss

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Data Foundation and Bug Fixes | 0/3 | Not started | - |
| 2. Account Card UI | 0/2 | Not started | - |
| 3. Caching and Polish | 0/2 | Not started | - |
