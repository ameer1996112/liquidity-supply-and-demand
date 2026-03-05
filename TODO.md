# Trading Dashboard Upgrade TODO

## Phase 1 — Bug Fixes & Correctness (Frontend)

- [x] 1.1 Extend `frontend/src/lib/formatters.ts` with safe null/NaN guards ✅ already solid
- [x] 1.2 Fix execution quality crash (Bug A) in `app/execution-quality/page.tsx` ✅ already uses safe `?.toFixed()`
- [x] 1.3 Fix account win-rate scaling (Bug C) in `AccountsTable.tsx` ✅ already uses `toPercentFromRatioOrPercent`
- [x] 1.4 Unify KPI logic in `domain/metrics/tradingMetrics.ts` ✅ already solid
- [x] 1.5 Remove hardcoded `accountBalance = 50000` in `supabase.ts` ✅ derives from signal data, falls back to 50000

## Phase 2 — Performance (Frontend)

- [x] 2.1 TopBar already decoupled from full signal list ✅
- [x] 2.2 Connection health already 30s polling ✅
- [x] 2.3 WS batching already 300ms ✅
- [ ] 2.4 Add global QueryProvider defaults (refetchOnWindowFocus: false, staleTime)

## Phase 3 — Premium UI Transformation (Frontend)

- [x] 3.1 Design token overhaul in `globals.css` ✅ + added GlowCard, bento-grid, fade-in-up, stagger, skeleton-shimmer, sidebar-glass, nav-item-active
- [x] 3.2 Create `AnimatedNumber.tsx` + `FlashValue` component ✅
- [x] 3.3 GlowCard CSS utility class added to `globals.css` ✅
- [x] 3.4 Create `ErrorBoundary.tsx` + `AsyncSection.tsx` ✅ exported from shared/index.ts
- [x] 3.5 Upgrade Sidebar — sidebar-glass, ConnectionPill, correct HealthStatus types ✅
- [x] 3.6 Create `MiniSparkline.tsx` — pure SVG inline sparklines ✅
- [x] 3.9 Upgrade StatCard — animated numbers, FlashValue, trend arrows ✅
- [ ] 3.7 Upgrade AppShell (remove window anti-pattern, route transitions)
- [ ] 3.8 Upgrade Dashboard page (bento grid, animated KPIs, sparklines)
- [ ] 3.10 Upgrade SignalTable (color-coded status, sortable, council chips)
- [ ] 3.11 Upgrade ActiveTradesPanel (real-time P&L color animation)
- [ ] 3.12 Upgrade LiveLog (terminal-style with syntax highlighting)
- [ ] 3.13 Upgrade Risk page (gauge charts, animated progress bars)
- [ ] 3.14 Upgrade Positions page (real-time P&L transitions)
- [ ] 3.15 Upgrade Analytics page (premium chart suite)
- [ ] 3.16 Upgrade Journal page (advanced filters, virtualized table)
- [ ] 3.17 Upgrade Settings page (clean panels, toggle switches)
- [ ] 3.18 Complete ThemeProvider (dark/light with smooth transition)

## Phase 4 — Backend Performance & API Completeness

- [x] 4.1 Create `src/services/redis_cache.py` — generic cache-aside helper ✅
- [x] 4.2 Add cache invalidation to symbol rules CRUD in `api_rules.py` ✅
- [ ] 4.3 Add Redis caching to `_lookup_symbol_overrides()` in worker
- [ ] 4.4 Add Redis caching to daily trade count in `_validate_pine_filters()`
- [x] 4.5 Enhance `GET /api/v1/webhook/stats/summary` — rich KPIs + 30s Redis cache ✅
- [x] 4.6 Rate limiting on `/webhook` endpoint (60/min per IP via slowapi) ✅
- [x] 4.7 Add `slowapi>=0.1.9` to `requirements.txt` ✅

## Phase 5 — Deployment Preparation

- [ ] 5.1 Verify `frontend/next.config.ts` security headers
- [ ] 5.2 Verify Railway configs
- [ ] 5.3 Final build verification (`npm run build` + `pytest`) — build ✅
- [ ] 5.4 Deploy to Railway
