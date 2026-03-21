# Requirements: v1.1 Position Management & Risk Intelligence

## v1.1 Requirements

### Position Lifecycle (BE + Trailing)

- [ ] **POS-01**: System moves SL to `entry + N pips` (configurable, default 3) when breakeven is triggered — not exact entry price
- [ ] **POS-02**: System activates trailing stop automatically after breakeven fires on any position
- [ ] **POS-03**: Trailing stop distance is configurable per instrument type (forex: pips, indices: points) via `.env` or DB config
- [ ] **POS-04**: Trailing stop has configurable activation threshold — only starts trailing after price moves minimum distance from entry
- [ ] **POS-05**: Full position lifecycle is logged to `trade_events` table: entry → BE trigger → trail start → trail updates → exit

### Risk Visibility

- [ ] **RISK-01**: Dashboard shows current `risk_multiplier` value applied by `step_up` mode for active session
- [ ] **RISK-02**: Signal table includes a `Risk $` column showing the calculated USD risk for each executed trade
- [ ] **RISK-03**: Dashboard stat card shows "Effective Risk %" (actual risk after multiplier applied, not base 0.5%)

### Execution Monitoring

- [ ] **EXEC-01**: System tracks webhook receipt timestamp and fill confirmation timestamp per signal, storing latency in DB
- [ ] **EXEC-02**: System alerts (log + optional Telegram) when a signal is received but no fill confirmed within 30 seconds
- [ ] **EXEC-03**: System detects and flags signals that arrive outside market hours (dead signals) with `staleness_rejected` status populated correctly

## Future Requirements (v1.2+)

- Partial close at TP1 (close 50% at halfway target, let rest run to BE)
- Per-symbol risk overrides configurable from frontend UI (not just DB)
- Real-time trailing stop status panel in dashboard

## Out of Scope (v1.1)

- Pine Script changes — all optimizations implemented on Python/worker side
- New signal sources — TradingView webhook is the only signal input
- Frontend redesign — v1.0 design system stays as-is

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| POS-01 | Phase 9 | Pending |
| POS-02 | Phase 9 | Pending |
| POS-03 | Phase 9 | Pending |
| POS-04 | Phase 9 | Pending |
| POS-05 | Phase 9 | Pending |
| RISK-01 | Phase 10 | Pending |
| RISK-02 | Phase 10 | Pending |
| RISK-03 | Phase 10 | Pending |
| EXEC-01 | Phase 11 | Pending |
| EXEC-02 | Phase 11 | Pending |
| EXEC-03 | Phase 11 | Pending |
