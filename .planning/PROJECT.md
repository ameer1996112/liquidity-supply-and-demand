# Prop Firm Page Overhaul

## What This Is

Overhaul of the Prop Firm challenge tracking page in the TradeOps frontend. The page monitors prop firm evaluation/funded accounts with drawdown tracking, performance metrics, and challenge compliance. This milestone focuses on performance, design, and data accuracy improvements.

## Core Value

Accurate, instant prop firm challenge monitoring — traders must trust the metrics they see and be able to switch between accounts without delay.

## Requirements

### Validated

- ✓ Challenge health score gauge — existing
- ✓ Account switching between multiple accounts — existing
- ✓ Daily/Max drawdown tracking with circular gauges — existing
- ✓ Account overview (balance, equity, P&L) — existing
- ✓ Performance summary with trade stats — existing
- ✓ Calendar PnL view — existing
- ✓ Challenge header with phase badge — existing
- ✓ Component extraction (ChallengeHeader, HealthScoreGauge, etc.) — existing

### Active

- [ ] Hide irrelevant metrics per firm (e.g. Consistency Rule gauge hidden for firms without it)
- [ ] Fix slow account switching — prefetch/cache data for all accounts
- [ ] Improve page design — richer stat cards, better visual hierarchy
- [ ] Add firm-specific rules summary — show which rules apply per firm with limits

### Out of Scope

- Backend API changes — frontend-only improvements
- New prop firm detection logic — using existing backend data
- Database schema changes — working with current data model

## Context

- **Current problem**: ACG-DEMO shows "Consistency Rule: 100% — Danger Zone" even though ACG doesn't have a consistency rule. This is misleading and erodes trust.
- **Performance**: Account switching triggers fresh API calls for metrics, history, MTM, and signals. No prefetching or caching beyond React Query's staleTime.
- **Architecture**: Prop Firm page recently refactored from 814-line monolith into 6 extracted components. The component structure is clean — this work builds on that foundation.
- **Data source**: `usePropFirmMetrics` hook fetches from `/api/prop-firm/metrics?account_name=X`. The response includes `consistency` field — need to check if backend signals whether consistency rule applies.

## Constraints

- **Frontend only**: All changes in `frontend/src/` — no backend modifications
- **Existing hooks**: Must work with current `usePropFirm*.ts` and `usePropFirmChallenge.ts` hooks
- **Production deploy**: Changes deploy via Railway — must pass `npm run build`

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Hide gauges for non-applicable rules | ACG shows misleading 100% Danger Zone for consistency | — Pending |
| Prefetch adjacent account data | Switching accounts currently triggers full refetch cycle | — Pending |
| Use FirmInfo from usePropFirmChallenge for rule visibility | This hook already returns firm-specific limits (max_daily_loss_pct, profit_target_pct, etc.) | — Pending |

---
*Last updated: 2026-03-18 after initialization*
