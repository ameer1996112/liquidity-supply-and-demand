# Requirements — Prop Firm Page Overhaul

## v1 Requirements

### Data Accuracy
- [ ] **DATA-01**: Hide Consistency Rule gauge when firm has no consistency rule (e.g. ACG)
- [ ] **DATA-02**: Hide Profit Target gauge when firm has no profit target (funded accounts)
- [ ] **DATA-03**: Derive rule applicability from `FirmInfo` fields (`limit_pct`, `profit_target_pct`, etc.) — if field is null/0, hide the gauge

### Performance
- [ ] **PERF-01**: Prefetch metrics for all accounts on page load (not just selected)
- [ ] **PERF-02**: Keep cached data visible during account switch (show stale + loading indicator instead of blank)
- [ ] **PERF-03**: Account switch should feel instant (<500ms perceived)

### Design
- [ ] **UI-01**: Richer stat cards in Account Overview — larger numbers, trend indicators, subtle backgrounds
- [ ] **UI-02**: Better visual hierarchy — differentiate primary metrics from secondary
- [ ] **UI-03**: Consistent section spacing and dividers across all sections

### Firm Rules Display
- [ ] **RULES-01**: Add "Challenge Rules" section showing which rules apply to the selected firm
- [ ] **RULES-02**: Display each rule with its limit value (e.g. "Daily Loss Limit: 5%", "Max Drawdown: 8%")
- [ ] **RULES-03**: Mark rules as "Not Applicable" or omit them when the firm doesn't enforce them

## v2 Requirements (Deferred)

- Inline rule editing from the Prop Firm page
- Historical drawdown chart overlay
- Multi-firm comparison view

## Out of Scope

- Backend API endpoint changes — using existing response data
- New prop firm auto-detection — handled by existing `usePropFirmChallenge` hook
- Database schema modifications

## Traceability

| Requirement | Phase |
|-------------|-------|
| DATA-01, DATA-02, DATA-03 | Phase 1 |
| PERF-01, PERF-02, PERF-03 | Phase 2 |
| UI-01, UI-02, UI-03 | Phase 3 |
| RULES-01, RULES-02, RULES-03 | Phase 1 |
