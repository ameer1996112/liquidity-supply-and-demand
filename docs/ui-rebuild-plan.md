# Next-Level UI Rebuild Plan (Phase 2)

Date: 2026-02-19
Goal: Rebuild frontend to premium, fast, stable, and consistent **without breaking API/WebSocket contracts** and with incremental shippable steps.

---

## 1) New information architecture (navigation)

## Primary nav

1. **Dashboard** (`/`)

   - Global KPIs, active positions snapshot, risk snapshot, execution snapshot, recent signals.

2. **Positions & Orders** (`/positions`)

   - Active positions, account margin/balance, position actions (close/partial/SLTP).

3. **Risk Monitor (PropGuard)** (`/risk`, `/portfolio-risk`)

   - Real-time limits, daily/trailing DD, VaR/correlation/exposure.

4. **Analytics** (`/analytics`, `/execution-quality`)

   - Performance breakdown, equity/PNL analytics, TCA/execution telemetry.

5. **Backtest** (`/backtest`)

   - Runs, replay, performance tabs.

6. **Logs / Journal** (`/journal`, legacy log surfaces)

   - Historical signals/trades with filters/export.

7. **Accounts** (`/accounts`, `/accounts/[account_name]`)

   - Multi-account management + account detail tabs.

8. **Rules & Settings** (`/rules`, `/settings`)
   - Risk/strategy rules, AI config, connection/system health, alert rules.

## Secondary chrome behavior

- **Left Sidebar:** stable IA hierarchy + badges (alerts/risk state).
- **Topbar:** connection state, mode (LIVE/PAPER), kill switch, global quick actions.
- **Context panel (optional drawer):** row/signal details instead of route jumps where possible.

---

## 2) Design system tokens

Implement in CSS variables + Tailwind theme extension.

## Spacing / sizing

- Scale: `4, 8, 12, 16, 20, 24, 32, 40, 48`
- Dense data tables: compact row height token (`--row-h-compact`)

## Radii / elevation

- Radii: `6, 10, 14`
- Shadows: minimal, compositing-safe (avoid heavy blur glows)

## Typography

- UI font: Inter / system sans
- Data font: JetBrains Mono (tabular nums)
- Type roles: `display`, `title`, `label`, `caption`, `metric`

## Colors (semantic)

- Base surfaces: `bg/base`, `bg/elev-1`, `bg/elev-2`
- Text: `text/primary`, `text/secondary`, `text/muted`
- Status:
  - `success` (profit/healthy)
  - `danger` (loss/breach)
  - `warning` (approaching limits)
  - `info` (neutral/system)
- Trading semantics:
  - `buy`, `sell`, `active`, `closed`, `rejected`

## Dark/light theming

- Tokenized variables under `[data-theme='dark']` and `[data-theme='light']`
- Single theme toggle in Topbar persisted to localStorage.

---

## 3) Component system plan

Create reusable primitives and layout components under `/src/components/ui` and feature wrappers.

## Core layout

- `AppShell`
- `Sidebar`
- `Topbar`
- `PageHeader`

## Data display

- `StatCard`
- `MetricStrip`
- `StatusBadge`
- `PnlValue`

## Data interaction

- `FilterBar`
- `DataTable` (with optional virtualization adapter)
- `EmptyState`
- `SkeletonBlock`
- `ErrorState`

## Overlays

- `Drawer`
- `ConfirmDialog`
- `Toast` (deduplicated event toasts)

## Reliability wrappers

- Route-level `ErrorBoundary`
- `AsyncSection` wrapper (loading/error/empty/success states)

---

## 4) State architecture (single source of truth + selectors)

## Principles

- Keep server state in React Query.
- Keep ephemeral UI state local/context.
- Eliminate duplicate KPI calculation logic in components.

## Plan

1. Introduce domain selectors:

   - `/src/domain/metrics/selectors.ts`
   - `/src/domain/metrics/compute.ts`

2. Normalize signal status/mode once:

   - canonical enums in `/src/domain/types`
   - one status classifier (`isOpen`, `isClosed`, `isRejected`)

3. WebSocket batching:

   - buffer realtime events 250–500ms
   - apply merged cache updates per batch
   - avoid global invalidation per event

4. Query scoping:
   - use `select` for narrow subscriptions
   - avoid passing full arrays into global chrome when aggregate-only data is needed

---

## 5) Data layer plan (typed client, caching, errors/loading)

## Typed API client

- Centralize backend fetches in `/src/lib/api-client.ts` (or evolve existing `lib/api.ts`)
- Preserve all current endpoints/contracts unchanged.
- Add request/response TypeScript types per endpoint.

## Supabase/realtime adapter

- Keep protocol/table subscriptions intact.
- Move subscription logic behind a dedicated adapter module (`lib/realtime/signals.ts`).

## Caching and refresh policy

- Define query-key factories by domain (`signals`, `positions`, `risk`, `accounts`, `execution`).
- Route-aware `enabled` flags for heavy queries.
- Rationalize polling intervals to reduce overlap with realtime.

## Error/loading standards

- All pages use consistent async states:
  - skeleton during load
  - non-crashing fallback when partial numeric fields are missing
  - actionable error messages with retry

---

## 6) Migration strategy (strangler, incremental, shippable)

## Safety rules

- No endpoint changes.
- No WS protocol changes.
- Preserve every feature.
- Each step must compile, route, and ship independently.

## Step-by-step migration

### Step 0 — Foundation (pre-UI)

- Add `/src/domain/types` and `/src/domain/metrics`.
- Add safe numeric formatters and canonical KPI computations.
- Add unit tests for metrics + formatting guards.

### Step 1 — Realtime/perf stabilization

- Implement batched WS updates.
- Reduce unnecessary cache invalidations.
- Add `select`-based aggregate hooks for topbar/dashboard counters.

### Step 2 — Shell + design tokens

- Introduce new token system + theme toggle.
- Swap in upgraded `AppShell/Sidebar/Topbar` behind feature flag.

### Step 3 — Route migration order

1. **Dashboard** (highest visibility; validates KPI correctness + realtime behavior)
2. **Positions & Orders** (critical operational flow)
3. **Risk Monitor** (guard rails and kill-switch confidence)
4. **Logs/Journal** (virtualization + table standardization)
5. **Backtest/Analytics** (heavy routes + lazy loading)
6. **Settings/Rules/Accounts** (admin/config surfaces)

### Step 4 — Full polish + cleanup

- Remove deprecated styles/components after parity verified.
- Keep compatibility adapters until all old surfaces are retired.

---

## 7) Regression prevention

1. **Unit tests**

   - Metrics computations (`trades=0`, winrate handling, PnL math, status classification)
   - Number formatting null/NaN guards.

2. **Smoke tests**

   - Basic route render checks for core routes.

3. **Performance checks per phase**

   - Lighthouse rerun
   - React Profiler sampling on dashboard
   - WS event-to-render sanity verification

4. **Contract safety**
   - Keep endpoint paths and payload fields untouched.
   - Introduce mappers/adapters only on frontend side.

---

## 8) Definition-of-done mapping

- UI transformed and consistent via shared shell + tokens + ui kit.
- Correctness fixed via centralized domain metrics + guards.
- Performance improved via WS batching, selector scoping, virtualization, lazy heavy routes.
- Build/tests pass; routes/data/realtime continue working on existing backend contracts.
