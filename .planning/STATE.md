---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Position Management & Risk Intelligence
status: complete
last_updated: "2026-03-21T15:27:00.000Z"
progress:
  total_phases: 3
  completed_phases: 3
  total_plans: 5
  completed_plans: 5
  percent: 100
---

# Project State

## Current Position

Phase: All 3 phases complete
Plan: All plans executed
Status: Milestone complete — 259 tests passing

Last activity: 2026-03-21 — Milestone v1.1 complete (commits 53f7e2c, eb18c3f, b486e8e)

## Progress

Progress: ░░░░░░░░░░ 0%
Phases: 0/3 complete

## Current Milestone

**v1.1: Position Management & Risk Intelligence**

- 3 phases planned (9, 10, 11)
- 11 requirements mapped
- Backend-focused: breakeven, trailing stops, risk visibility, execution monitoring
- Trading on 5M timeframe, forex + indices, TradingView → Vantage → MetaTrader flow

## Accumulated Context

### Decisions

- All v1.0 decisions (dark theme, mobile-first, shadcn/ui, etc.) carry forward
- v1.1 is backend-only — no frontend redesign
- No Pine Script changes — Python/worker side only
- BE buffer default: 3 pips above entry (configurable via .env)
- Trail activation: after BE fires, not independently
- Per-symbol trail distance: forex uses pips, indices use points
- `step_up` risk mode is active — risk_multiplier is dynamic and currently invisible to the trader

### Key Patterns

- Existing design system uses `--to-*` token prefix (TradeOps)
- `trading_signals` table is the source of truth for all trade state
- `be_trigger_price` + `be_sl_price` sent from TradingView Pine webhook
- `BreakevenManager.check_and_trigger()` runs on every worker loop
- `TrailingStopManager.update_trailing_stops()` runs every 60s
- Both managers are initialized in `worker.py` and disconnected — not chained

### Codebase Notes

- Backend: FastAPI (src/api.py) + Worker (src/worker.py)
- Position management: src/services/breakeven_manager.py, src/services/trailing_stop_manager.py
- Risk engine: src/core/risk_engine.py (calculate_max_position_size)
- Risk mode logic: src/core/dynamic_config.py (step_up mode)
- Frontend: Next.js 16, dashboard at frontend/src/app/page.tsx
- Signal table: frontend/src/components/dashboard/SignalTable.tsx

## Blockers / Concerns

None

---
*State initialized: 2026-03-21*
