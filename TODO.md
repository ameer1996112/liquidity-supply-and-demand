# Frontend Professional Upgrade — Implementation Checklist

## Phase 1 — Infrastructure

- [x] Toast Notification System (ToastProvider + useToast hook)
- [x] CircularGauge shared component (extracted from PropFirm page)

## Phase 2 — Dashboard Improvements

- [x] Mini Sparklines in StatCards (reuse MiniSparkline component)
- [x] Session Performance Ring on Dashboard header
- [x] Live P&L Ticker bar for open positions
- [x] "Today's Best Setup" highlight card

## Phase 3 — Analytics Improvements

- [x] Rolling Metrics tab (30-day rolling win rate, profit factor, Sharpe)
- [x] Sharpe/Sortino/Calmar metric cards in Overview tab
- [x] Export to CSV button in Analytics

## Phase 4 — Risk Page Improvements

- [x] Circular Gauges replacing flat progress bars (Daily Loss + Drawdown)
- [x] Composite Risk Score (0–100) with weighted breakdown

## Phase 5 — Journal Improvements

- [x] Calendar P&L View (monthly heatmap with day tooltips)
- [ ] Trade Tags system (future — requires DB schema change)
- [x] Streak indicator in header (win/loss streak badge)

## Phase 6 — Position Card Improvements

- [x] Live P&L Flash using FlashValue component

## Phase 7 — Backtest Improvements

- [ ] Design token consistency (replace slate-\* with design tokens)
- [ ] Save/Load named configurations (localStorage)

## Phase 8 — Global Improvements

- [x] Keyboard Shortcuts Map modal (press ? to open)
- [x] Market Scanner page (/scanner route with mock + live data)
- [ ] AI Copilot real LLM wiring (fetchCopilotAnswer already imported)
- [ ] Command Palette enhancements (kill switch action)

---

## Files Created / Modified

### New Files

- `frontend/src/components/ui/toast.tsx` — upgraded toast with progress bar + signal variant
- `frontend/src/components/ui/CircularGauge.tsx` — shared SVG circular gauge
- `frontend/src/components/dashboard/SessionRing.tsx` — session P&L ring
- `frontend/src/components/dashboard/LivePnlTicker.tsx` — scrolling open-position ticker
- `frontend/src/components/dashboard/BestSetupCard.tsx` — best setup highlight card
- `frontend/src/components/analytics/RollingMetricsChart.tsx` — rolling win rate / PF / R:R
- `frontend/src/components/journal/CalendarPnlView.tsx` — monthly P&L calendar heatmap
- `frontend/src/components/layout/KeyboardShortcutsModal.tsx` — ? shortcut modal
- `frontend/src/app/scanner/page.tsx` — Symbol Scanner page

### Modified Files

- `frontend/src/components/dashboard/StatCard.tsx` — added sparklineData prop
- `frontend/src/components/positions/PositionCard.tsx` — FlashValue on live P&L
- `frontend/src/components/layout/AppShell.tsx` — added KeyboardShortcutsModal
- `frontend/src/components/layout/Sidebar.tsx` — added Scanner nav item
- `frontend/src/app/page.tsx` — SessionRing, LivePnlTicker, BestSetupCard, sparklines
- `frontend/src/app/analytics/page.tsx` — Rolling tab, Sharpe/Sortino cards, CSV export
- `frontend/src/app/risk/page.tsx` — CircularGauges + CompositeRiskScore
- `frontend/src/app/journal/page.tsx` — CalendarPnlView toggle + streak badge
