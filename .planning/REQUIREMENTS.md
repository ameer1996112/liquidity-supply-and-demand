# Requirements: Trading Bot Dashboard — Frontend Redesign

**Defined:** 2026-03-19
**Core Value:** The trader must always know what the bot is doing in real-time through a single premium dashboard.

## v1 Requirements

### Design System

- [ ] **DS-01**: A unified dark terminal color palette is applied consistently across all pages (`#0a0b0d` base, `#0f1117` card bg, `#00d2ff`/`#3a7bd5` accent, `#2ed573` profit, `#ff4757` loss)
- [ ] **DS-02**: Typography uses Inter or Geist with monospace for all price/number values
- [ ] **DS-03**: A shared card component style exists (glass-morphism: `bg-white/5 backdrop-blur border border-white/10`) used consistently across all pages
- [ ] **DS-04**: Skeleton loading states replace all empty/loading placeholders across all pages
- [ ] **DS-05**: Micro-animations on data updates (number changes, status changes) feel smooth and non-distracting
- [ ] **DS-06**: A persistent sidebar navigation replaces any top-nav or scattered nav — includes icons + labels + live status indicators

### Dashboard (Main Page)

- [ ] **DASH-01**: Dashboard displays a real-time signal feed with signal cards showing symbol, side, AI verdict, and guardrail status
- [ ] **DASH-02**: A live P&L summary widget shows today's realized + unrealized P&L with color-coded delta
- [ ] **DASH-03**: An AI/Bot status panel shows whether the bot is active, last signal received, and current trading mode (live/dry-run/paper)
- [ ] **DASH-04**: A risk snapshot widget shows daily loss %, drawdown %, and prop firm limit proximity in gauge or bar form
- [ ] **DASH-05**: Dashboard layout is a responsive multi-column grid — command center feel without scrolling for critical info
- [ ] **DASH-06**: Signal cards in the feed expand in-place to show full AI rationale and guardrail breakdown (Signal Inspector)

### Positions

- [ ] **POS-01**: Positions page displays a live table of all open positions with symbol, side, open price, current price, unrealized P&L, and duration
- [ ] **POS-02**: Rows are heat-colored by unrealized P&L (green gradient for profits, red for losses)
- [ ] **POS-03**: Page updates in real-time or on a short polling interval (≤10s)
- [ ] **POS-04**: Empty state shows a friendly placeholder when no positions are open

### Risk

- [ ] **RISK-01**: Risk page shows daily loss as a visual gauge (0% → limit % → current %) with color zones
- [ ] **RISK-02**: Risk page shows drawdown % with a threshold indicator
- [ ] **RISK-03**: Portfolio VaR, sector exposure, and correlation metrics are displayed in scannable cards
- [ ] **RISK-04**: All risk metrics update in real-time or on short polling intervals
- [ ] **RISK-05**: Critical thresholds (approaching limits) trigger visible warning styling (amber/red)

### Analytics

- [ ] **ANA-01**: Analytics page shows an equity curve chart (dark-themed, glowing line/area fill)
- [ ] **ANA-02**: Win rate by symbol/session is displayed as a heatmap or grouped bar chart
- [ ] **ANA-03**: Key performance metrics (total trades, win rate, avg R:R, avg holding time) are shown as KPI cards at the top
- [ ] **ANA-04**: Charts are interactive (hover tooltips, zoom where applicable)

### Execution Quality

- [ ] **EXQ-01**: Execution Quality page shows a trace timeline — each signal execution as a horizontal timeline with phase durations (guardrails, order, fill)
- [ ] **EXQ-02**: Latency breakdown is visualized (bot latency vs broker latency vs total)
- [ ] **EXQ-03**: Slippage per trade is shown in a chart or table
- [ ] **EXQ-04**: Filter by symbol, date range, and outcome (filled/rejected/error)

### Prop Firm

- [ ] **PROP-01**: Prop Firm page shows active challenge with phase name (Eval Ph1, Eval Ph2, Funded), account name, and broker
- [ ] **PROP-02**: Daily loss limit is shown as a progress bar (used % of limit) that turns red when ≥80%
- [ ] **PROP-03**: Drawdown limit is shown as a progress bar with color-coded zones
- [ ] **PROP-04**: Profit target progress is shown (current / target with %)
- [ ] **PROP-05**: Consistency tracker shows best day % of total profit vs the 40% allowed limit

### Accounts

- [ ] **ACC-01**: Accounts page shows account cards with broker name, account ID, balance, equity, prop firm phase badge, and connection status
- [ ] **ACC-02**: Account cards show a mini sparkline or delta indicator for balance change
- [ ] **ACC-03**: Disconnected/error accounts are clearly highlighted with actionable status

### Alerts

- [ ] **ALRT-01**: Alerts page shows a searchable, filterable list of historical alerts (risk limit hits, circuit breaker triggers, errors)
- [ ] **ALRT-02**: Alert severity levels (info / warning / critical) are visually distinct with color and icon

### Settings & Strategies

- [ ] **SET-01**: Settings page uses clean form layout with organized sections (trading mode, risk params, AI config, notifications)
- [ ] **SET-02**: Strategies page shows active strategy cards with key config values

### Navigation & Layout

- [ ] **NAV-01**: Sidebar navigation is collapsible (expanded with labels / collapsed to icon-only)
- [ ] **NAV-02**: Active page is clearly indicated in the sidebar
- [ ] **NAV-03**: Navigation includes global live status indicators (Redis connected, bot active, last heartbeat)
- [ ] **NAV-04**: Page transitions feel smooth (not jarring white flashes)

### Loading & Performance

- [ ] **PERF-01**: All pages show skeleton loading states — no empty/null renders on first load
- [ ] **PERF-02**: React Query cache configuration prevents unnecessary refetches
- [ ] **PERF-03**: Real-time data (signals, positions) uses Supabase Realtime subscriptions rather than polling where available
- [ ] **PERF-04**: Bundle size does not regress — no new heavy dependencies without justification

## v2 Requirements

### Future Enhancements

- **V2-01**: Mobile-responsive layout (trading desk context, desktop first now)
- **V2-02**: Keyboard shortcuts for navigation
- **V2-03**: Dark/light theme toggle
- **V2-04**: Notification center panel in sidebar
- **V2-05**: Drag-and-drop dashboard widget customization
- **V2-06**: AI Trade Journal (narrative generated per trade by LLM)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Backend API changes | Frontend redesign milestone only — API stays as-is |
| New features / capabilities | Redesign existing pages, no new bot features this milestone |
| Mobile app | Single trader, desktop context |
| Multi-tenant / client UI | Solo operator tool |
| Authentication flow redesign | Auth works fine, redesign the post-login dashboard only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DS-01 → DS-06 | Phase 1 | Pending |
| DASH-01 → DASH-06 | Phase 2 | Pending |
| POS-01 → POS-04 | Phase 3 | Pending |
| RISK-01 → RISK-05 | Phase 3 | Pending |
| ANA-01 → ANA-04 | Phase 4 | Pending |
| EXQ-01 → EXQ-04 | Phase 4 | Pending |
| PROP-01 → PROP-05 | Phase 5 | Pending |
| ACC-01 → ACC-03 | Phase 5 | Pending |
| ALRT-01 → ALRT-02 | Phase 6 | Pending |
| SET-01 → SET-02 | Phase 6 | Pending |
| NAV-01 → NAV-04 | Phase 1 | Pending |
| PERF-01 → PERF-04 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 44 total
- Mapped to phases: 44
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-19*
*Last updated: 2026-03-19 after initial definition*
