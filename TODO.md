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
- [x] 2.4 Add global QueryProvider defaults (gcTime, retry backoff, mutations no-retry) ✅

## Phase 3 — Premium UI Transformation (Frontend)

- [x] 3.1 Design token overhaul in `globals.css` ✅ + added GlowCard, bento-grid, fade-in-up, stagger, skeleton-shimmer, sidebar-glass, nav-item-active
- [x] 3.2 Create `AnimatedNumber.tsx` + `FlashValue` component ✅
- [x] 3.3 GlowCard CSS utility class added to `globals.css` ✅
- [x] 3.4 Create `ErrorBoundary.tsx` + `AsyncSection.tsx` ✅ exported from shared/index.ts
- [x] 3.5 Upgrade Sidebar — sidebar-glass, ConnectionPill, correct HealthStatus types ✅
- [x] 3.6 Create `MiniSparkline.tsx` — pure SVG inline sparklines ✅
- [x] 3.9 Upgrade StatCard — animated numbers, FlashValue, trend arrows ✅
- [x] 3.7 Upgrade AppShell — ShellActionsProvider, removed window globals, route fade-in-up ✅
- [x] 3.8 Upgrade Dashboard page — bento grid, 7 stat cards, stagger-children, glow-card panels ✅
- [x] 3.10 Upgrade SignalTable — score col, relative time, row accent bar, sortable ✅
- [x] 3.11 Upgrade ActiveTradesPanel — PnL-based row accent, pulsing live dot, account col ✅
- [x] 3.12 Upgrade LiveLog — level pill badges, PAUSED indicator, newest-entry fade-in ✅
- [ ] 3.13 Upgrade Risk page (gauge charts, animated progress bars)
- [ ] 3.14 Upgrade Positions page (real-time P&L transitions)
- [ ] 3.15 Upgrade Analytics page (premium chart suite)
- [ ] 3.16 Upgrade Journal page (advanced filters, virtualized table)
- [ ] 3.17 Upgrade Settings page (clean panels, toggle switches)
- [ ] 3.18 Complete ThemeProvider (dark/light with smooth transition)

## Phase 4 — Backend Performance & API Completeness

- [x] 4.1 Create `src/services/redis_cache.py` — generic cache-aside helper ✅
- [x] 4.2 Add cache invalidation to symbol rules CRUD in `api_rules.py` ✅
- [x] 4.3 Add Redis caching to `_lookup_symbol_overrides()` in worker (TTL=60s) ✅
- [x] 4.4 Add Redis caching to daily trade count in `_validate_pine_filters()` (TTL=30s) ✅
- [x] 4.8 Migrate api.py on_event → lifespan context manager (eliminates deprecation warnings) ✅
- [x] 4.5 Enhance `GET /api/v1/webhook/stats/summary` — rich KPIs + 30s Redis cache ✅
- [x] 4.6 Rate limiting on `/webhook` endpoint (60/min per IP via slowapi) ✅
- [x] 4.7 Add `slowapi>=0.1.9` to `requirements.txt` ✅

## Phase 5 — Deployment Preparation

- [x] 5.1 Security headers added to `frontend/next.config.ts` (X-Frame-Options, HSTS, CSP, etc.) ✅
- [ ] 5.2 Verify Railway configs
- [x] 5.3 Final build verification — frontend build ✅ | pytest 254 passed ✅
- [ ] 5.4 Deploy to Railway
