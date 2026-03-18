# Requirements: Prop Firm Dashboard Upgrade

**Defined:** 2026-03-18
**Core Value:** Each connected MT5 account automatically shows its prop firm challenge status in real-time — the trader sees exactly where they stand against the rules without leaving the accounts page.

## v1 Requirements

### Bug Fixes

- [ ] **BUG-01**: Daily drawdown reset boundary uses NY midnight (EST/EDT), not UTC midnight — 6-hour gap in winter produces wrong FTMO attribution
- [ ] **BUG-02**: Daily drawdown baseline uses equity at day start, not balance — FTMO measures from equity (includes floating PnL at reset)
- [ ] **BUG-03**: Max drawdown denominator uses initial account balance for Phase 1/2, not trailing high-water-mark — Funded accounts use HWM (two branches required)
- [ ] **BUG-04**: `trades_today` counter implemented correctly (currently hardcoded to 0 in `prop_firm_tracker.py`)
- [ ] **BUG-05**: Silent exception swallowing removed from `prop_firm_tracker.py` — errors must surface to logs
- [ ] **BUG-06**: JPY pip value calculation corrected in floating PnL computation (94× error confirmed)

### Data Foundation

- [ ] **DATA-01**: Migration creates `prop_firm_server_mappings` table (server_name prefix → firm_id, firm_display_name)
- [ ] **DATA-02**: Migration creates `prop_firm_rules` table (firm_id + challenge_type → daily_dd_pct, total_dd_pct, profit_target_pct, min_trading_days, reset_tz, drawdown_reference)
- [ ] **DATA-03**: FTMO Phase 1, Phase 2, and Funded rules seeded with correct values (daily 5%, total 10%, profit 10%/5%/none, min days 4, reset_tz NY midnight)
- [ ] **DATA-04**: `prop_firm_detector.py` service maps account server name to firm_id via prefix lookup in DB (unknown firms return `null` gracefully, no crash)

### API

- [ ] **API-01**: `GET /api/v1/prop-firm/challenge-status/{account_id}` returns pre-computed metrics: firm_id, firm_name, challenge_type, daily_dd_pct, daily_dd_limit_pct, total_dd_pct, total_dd_limit_pct, profit_pct, profit_target_pct, trades_today, min_trading_days, warnings (list of metrics at ≥80%), detected (bool)
- [ ] **API-02**: `PATCH /api/v1/prop-firm/challenge-config/{account_id}` saves challenge_type (phase_1 / phase_2 / funded) to broker_profiles — idempotent, single field update
- [ ] **API-03**: Endpoint returns `firm_detected: false` with empty metrics for unrecognized server names — frontend shows "Unknown firm" gracefully

### Account Card UI

- [ ] **UI-01**: `PropFirmSection` component embedded in `EnhancedAccountCard` — appears only when account has a linked MT5 account
- [ ] **UI-02**: Daily drawdown progress bar — shows current_pct / limit_pct, green → amber → red at 80% threshold
- [ ] **UI-03**: Total drawdown progress bar — same color logic
- [ ] **UI-04**: Profit target progress bar — shown for Phase 1 and Phase 2 only, hidden for Funded
- [ ] **UI-05**: Trading days counter — "12 days / 4 min" format, checkmark when met
- [ ] **UI-06**: Inline challenge type selector — compact dropdown (Phase 1 / Phase 2 / Funded) shown in card when firm detected but phase not yet configured; disappears after selection
- [ ] **UI-07**: Warning banner in card when any metric reaches ≥80% of its limit — shows which limit is close
- [ ] **UI-08**: "Unknown firm" fallback state — shows server name with prompt to contact support, no crash
- [ ] **UI-09**: `usePropFirmChallenge` hook — polls `/challenge-status/{account_id}` at 10s interval, separate from account list polling

### Caching

- [ ] **CACHE-01**: Prop firm metrics computed by background worker and stored in Redis (key: `prop_firm:metrics:{account_id}`, TTL: 30s)
- [ ] **CACHE-02**: `/challenge-status` endpoint reads from Redis cache; falls back to live DB query if cache miss
- [ ] **CACHE-03**: Background worker runs every 20s per account, updates Redis cache — prevents Supabase connection saturation at multi-account polling rates

## v2 Requirements

### Additional Prop Firms

- **FIRMS-01**: The5ers rules seeded in prop_firm_rules table
- **FIRMS-02**: FundedNext rules seeded
- **FIRMS-03**: E8 Funding rules seeded
- **FIRMS-04**: Server-name mappings extended for each new firm

### Enhanced Display

- **UX-01**: Health score gauge (composite of all metrics) per account
- **UX-02**: Calendar view of trading days within challenge window
- **UX-03**: Phase transition UI — celebrate passing Phase 1, prompt to set Phase 2
- **UX-04**: Challenge history — past challenges with outcome (pass/fail)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Email/push notifications on limit breach | Dashboard banner sufficient for v1; notification infrastructure separate |
| Auto-pause trading on drawdown limit | Risk engine guard rails handle this; display is separate from execution |
| Prop firm API integration (FTMO MetriX etc.) | APIs not stable/public; rules in internal DB is more reliable |
| FTMO Aggressive account variant | Different profit targets only; defer — schema supports it when ready |
| FTMO Swing account restrictions | Trading hour enforcement out of scope |
| Other prop firms at launch | Schema supports them; data not seeded until v2 |

## Traceability

*Populated during roadmap creation.*

| Requirement | Phase | Status |
|-------------|-------|--------|
| BUG-01 | Phase 1 | Pending |
| BUG-02 | Phase 1 | Pending |
| BUG-03 | Phase 1 | Pending |
| BUG-04 | Phase 1 | Pending |
| BUG-05 | Phase 1 | Pending |
| BUG-06 | Phase 1 | Pending |
| DATA-01 | Phase 1 | Pending |
| DATA-02 | Phase 1 | Pending |
| DATA-03 | Phase 1 | Pending |
| DATA-04 | Phase 1 | Pending |
| API-01 | Phase 1 | Pending |
| API-02 | Phase 1 | Pending |
| API-03 | Phase 1 | Pending |
| CACHE-01 | Phase 2 | Pending |
| CACHE-02 | Phase 2 | Pending |
| CACHE-03 | Phase 2 | Pending |
| UI-01 | Phase 2 | Pending |
| UI-02 | Phase 2 | Pending |
| UI-03 | Phase 2 | Pending |
| UI-04 | Phase 2 | Pending |
| UI-05 | Phase 2 | Pending |
| UI-06 | Phase 2 | Pending |
| UI-07 | Phase 2 | Pending |
| UI-08 | Phase 2 | Pending |
| UI-09 | Phase 2 | Pending |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-18*
*Last updated: 2026-03-18 after initial definition*
