# M001: Smart Prop Firm Rules Engine

**Gathered:** 2026-03-18
**Status:** Ready for planning

## Project Description

An institutional liquidity-based algorithmic trading system that manages multiple broker accounts across prop firm challenges. Currently requires manual configuration of prop firm rules per account — hardcoded presets, manual phase switching, global enforcement limits. This milestone replaces all of that with a curated rules database, per-account enforcement, auto-phase advancement, and a consolidated dashboard.

## Why This Milestone

Manual prop firm configuration is the #1 friction point and the #1 risk vector. Traders manage multiple accounts across different firms (FTMO Phase 1 on one, ACG Funded on another), each with different limits. Getting a rule wrong — or leaving stale limits after a phase transition — can breach an account and lose a challenge. The system already has the plumbing for per-account settings in `broker_profiles`, but it's not wired to a rules database and enforcement still reads global settings.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Add a new prop firm account by picking firm → plan → size and have all limits auto-fill — zero manual rule entry
- See each account's challenge health, drawdown gauges, calendar, and analytics directly in the account detail page
- Trust that account A (FTMO Phase 1) and account B (ACG Funded) each enforce their own kill thresholds at trade time
- Watch phase transitions happen automatically when targets are met

### Entry point / environment

- Entry point: http://localhost:3000/accounts and http://localhost:3000/accounts/[name]
- Environment: local dev (frontend + backend + Supabase)
- Live dependencies involved: Supabase (rules DB, account config), MetaAPI (account metrics for phase detection)

## Completion Class

- Contract complete means: rules database returns correct limits for all covered firms/plans/sizes; per-account enforcement is unit-tested; auto-phase logic has test coverage
- Integration complete means: adding an account via wizard → rules auto-fill → enforcement uses those rules → phase advances when targets met — full chain works
- Operational complete means: none (local dev only)

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- A new FTMO 2-Step Standard $100k account can be added via wizard with correct limits auto-filled, and those limits are used by prop_guard when evaluating a signal for that account
- An account that reaches its profit target auto-advances to the next phase with new limits applied
- The account detail page shows challenge health, drawdown gauges, and calendar without needing the /prop-firm page

## Risks and Unknowns

- **prop_guard refactor scope** — Currently reads global settings via `get_settings()`. Refactoring to accept per-account params may touch the signal processing pipeline. Risk: unexpected side effects in trade execution.
- **Rules accuracy** — Curated rules must exactly match what each firm publishes. FTMO alone has 1-step vs 2-step, Standard vs Swing, 5 account sizes = 20 rule sets. Risk: data entry errors.
- **Phase advancement detection** — Requires reliable account metrics (profit, drawdown, trading days). MetaAPI sync must be recent enough. Risk: stale metrics trigger false phase advancement.
- **Frontend migration** — /prop-firm page has ~500 lines of complex UI with multiple data sources. Merging into account detail without breaking existing functionality. Risk: regression.

## Existing Codebase / Prior Art

- `src/core/guard_rails/prop_guard.py` — Current prop firm risk guard, reads from global settings. Must be refactored for per-account params.
- `src/api_portfolio_control.py` — Challenge settings CRUD endpoints already exist per-account in `broker_profiles`.
- `src/api_prop_firm.py` — Prop firm metrics API (drawdown, PnL, consistency). Currently account-aware.
- `frontend/src/components/accounts/AddAccountForm.tsx` — Current add form with hardcoded `PROVIDER_DEFAULTS`.
- `frontend/src/components/accounts/detail/ChallengeTab.tsx` — Per-account challenge settings with hardcoded `PROVIDER_PRESETS`.
- `frontend/src/app/prop-firm/page.tsx` — Standalone prop firm dashboard with health gauge, drawdown meters, calendar, analytics (~500 lines).
- `config/settings.py` — Global prop firm settings (evaluation_phase, phase1_*, phase2_*, funded_*).
- `src/core/broker_profiles.py` — Loads active broker profiles from DB or env.

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R001 — Prop firm rules database (primary deliverable of S01)
- R002 — Guided wizard (primary deliverable of S02)
- R003 — Per-account enforcement (primary deliverable of S03)
- R004 — Auto-phase advancement (primary deliverable of S04)
- R005 — Dashboard consolidation (primary deliverable of S05)
- R006 — Staleness warnings (delivered with S01, surfaced in S05)
- R008 — Major firm coverage day one (delivered with S01)
- R009 — Remove MyFundedFX (delivered with S01, cleanup in S02)

## Scope

### In Scope

- Curated rules database with FTMO, ACG, TFT, E8, FundedNext, The5ers
- Backend API for rules lookup by firm/plan/size
- Guided wizard for account creation with auto-fill
- Per-account prop_guard enforcement
- Auto-phase advancement with notification
- Dashboard consolidation (prop-firm page → account detail)
- Rules versioning and staleness warnings
- Custom/Other firm manual entry
- Removal of MyFundedFX references

### Out of Scope / Non-Goals

- Prop firm API integration (no firms have public APIs)
- Web scraping for auto-updating rules
- Changes to the core signal processing pipeline beyond prop_guard params
- Mobile-specific UI
- Deployment / CI changes

## Technical Constraints

- Rules database must live in Supabase (existing infrastructure)
- prop_guard refactor must not break existing trade execution for accounts without prop firm config
- Frontend must preserve existing account detail tabs (overview, positions, history, analytics, journal)
- Challenge settings backward-compatible with existing `broker_profiles` columns

## Integration Points

- **Supabase** — New `prop_firm_rules` table for curated rules; existing `broker_profiles` for per-account settings
- **prop_guard.py** — Refactored to accept per-account limits instead of global settings
- **account_router.py** — May need to pass account-specific limits downstream to prop_guard
- **MetaAPI** — Existing sync provides equity/balance data needed for phase advancement detection

## Open Questions

- **Drawdown calculation method** — FTMO 1-Step uses EOD trailing, 2-Step uses equity-based. Do we model this in the rules DB or simplify? Current thinking: model it, since it affects enforcement behavior.
- **Phase advancement threshold** — Should advancement trigger at exactly 100% of profit target, or at some buffer? Current thinking: 100% with all conditions met, since the firm does the same.
