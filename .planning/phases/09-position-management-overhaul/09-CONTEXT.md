# Phase 9: Position Management Overhaul - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Chain breakeven and trailing stop managers into a unified position lifecycle. When BE fires, SL moves to entry + configurable buffer (not exact entry). Trailing stop then auto-activates. All events logged to trade_events. Backend-only — no Pine Script changes, no frontend redesign.

</domain>

<decisions>
## Implementation Decisions

### Breakeven Buffer
- [auto] Buffer = `entry + BREAKEVEN_BUFFER_PIPS * pip_size` for buys, `entry - buffer` for sells (recommended: absorbs spread/commission)
- [auto] Default = 3 pips (configurable via `.env` as `BREAKEVEN_BUFFER_PIPS=3`)
- [auto] Buffer applied inside `BreakevenManager._evaluate_and_trigger()` before calling `_modify_broker_sl()` — not in Pine, not in DB
- [auto] If `be_sl_price` from Pine is already above entry (unusual), use it as-is without adding buffer

### Trailing Stop Auto-Activation
- [auto] Hook point: `BreakevenManager._mark_triggered()` — after successful BE fire, call `TrailingStopManager.add_trailing_stop()` for same position
- [auto] TrailingStopManager already exists and has `add_trailing_stop(signal_id, symbol, side, trail_distance_pips, activation_price, entry_price)` — reuse as-is
- [auto] Activation threshold: `activation_price = entry_price + (TRAIL_ACTIVATION_PIPS * pip_size)` for buys — trail doesn't start until price passes this point
- [auto] Default `TRAIL_ACTIVATION_PIPS = 0` (trail starts immediately from BE) — can be tuned to e.g. 5 to avoid being trailed out early
- [auto] If `TrailingStopManager` is None (not initialized), log warning and skip — graceful degradation

### Per-Symbol Trail Distance
- [auto] Forex pairs (default): `TRAIL_DISTANCE_PIPS_FOREX = 15`
- [auto] Index CFDs (NAS100, US30, UK100, GER40, etc.): `TRAIL_DISTANCE_POINTS_INDICES = 30`
- [auto] Gold (XAUUSD): `TRAIL_DISTANCE_PIPS_GOLD = 50` (wider due to volatility)
- [auto] Detection: if symbol contains index keyword → use indices distance, elif XAU/GOLD → gold distance, else → forex
- [auto] Per-symbol DB overrides via `symbol_risk_rules` table take precedence over env defaults (already supported)

### Lifecycle Logging
- [auto] Use existing `trade_events` table and `log_event()` helper (already implemented in breakeven_manager.py)
- [auto] Events to log: `be_triggered` (already logged), `trail_started` (new), `trail_updated` (already logged by TrailingStopManager)
- [auto] `trail_started` event payload: `{ trail_distance_pips, activation_price, entry_price, symbol }`

### Claude's Discretion
- Error handling strategy (retry vs skip on broker failures)
- Exact pip_size lookup logic for new instrument types added in future
- Test fixture structure for unit tests

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Core Services
- `src/services/breakeven_manager.py` — Full BreakevenManager implementation; hook point is `_mark_triggered()` and `_evaluate_and_trigger()`
- `src/services/trailing_stop_manager.py` — Full TrailingStopManager; `add_trailing_stop()` is the entry point to activate a new trailing stop
- `src/core/risk_engine.py` — `calculate_max_position_size()` for pip_size lookup patterns per symbol type

### Configuration
- `config/settings.py` — Settings class; new env vars must be added here with defaults
- `.env` — Runtime config; new vars: `BREAKEVEN_BUFFER_PIPS`, `TRAIL_DISTANCE_PIPS_FOREX`, `TRAIL_DISTANCE_POINTS_INDICES`, `TRAIL_DISTANCE_PIPS_GOLD`, `TRAIL_ACTIVATION_PIPS`
- `.env.example` — Must be updated alongside `.env`

### Worker Integration
- `src/worker.py` lines 131-140 — Where TrailingStopManager and BreakevenManager are initialized; both are passed to each other's constructors
- `src/worker.py` lines 1617-1634 — Periodic tasks loop; `trailing_stop_manager.update_trailing_stops()` every 60s

### Data
- `src/services/trade_events.py` (or equivalent) — `log_event()` helper for audit trail
- Supabase `trading_signals` table — `be_triggered`, `be_sl_price`, `broker_order_id`, `entry` are key columns
- Supabase `trailing_stops` table — `trail_distance_pips`, `activation_price`, `is_activated` are key columns

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TrailingStopManager.add_trailing_stop(signal_id, symbol, side, trail_distance_pips, activation_price, entry_price, wait_for_breakeven=False)` — complete, just needs to be called from BreakevenManager
- `log_event(signal_id, event_type, source, payload)` — already used in breakeven_manager.py for `breakeven_triggered` event; reuse for `trail_started`
- `PIP_SIZES` dict in TrailingStopManager — use same patterns for instrument detection

### Established Patterns
- Settings via Pydantic `BaseSettings` in `config/settings.py` — add new fields with env var names and defaults
- Pip size detection: `if "JPY" in symbol → 0.01`, `elif XAU/GOLD → 0.01`, `else → 0.0001` (from risk_engine.py)
- Graceful degradation: log warning and skip if adapter is None (existing pattern in both managers)

### Integration Points
- BreakevenManager gets `adapter` and `supabase_client` in `__init__` — can receive `trailing_stop_manager` reference too
- Worker initializes both managers; can pass trailing_stop_manager to breakeven_manager after both are created
- `_mark_triggered()` returns None — add trailing stop activation call here after DB update

</code_context>

<specifics>
## Specific Ideas

- User trades forex (EURUSD, GBPUSD, GBPCAD, NZDJPY, USDJPY) and indices — both must work correctly
- 5M timeframe: positions open for minutes to hours — trailing stop at 15 pips for forex is reasonable
- Confirmed from Supabase: GBPCAD -$44.14 was BE triggered with be_sl_price = exact entry; this is the primary bug to fix
- User wants "winners to run" — trailing stop after BE is the key insight

</specifics>

<deferred>
## Deferred Ideas

- Partial close at TP1 (close 50% at halfway target, let rest run to BE) — Phase 9 only handles BE+trail, not partial closes
- Frontend UI for trailing stop status panel — Phase 10 handles risk visibility, not trailing stop display
- Per-symbol overrides via frontend UI — future milestone

</deferred>

---

*Phase: 09-position-management-overhaul*
*Context gathered: 2026-03-21*
