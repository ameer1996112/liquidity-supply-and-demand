# Frontend Audit (Phase 0)

## 1) Tech stack summary

### Core framework/runtime

- **Framework:** Next.js `16.1.6` (App Router)
- **React:** `19.2.3`
- **Language:** TypeScript
- **Build/deploy hints:** `next.config.ts` uses `output: 'standalone'` (container-friendly)

### Routing

- **File-based routing** under `frontend/src/app/*`
- Root shell in `app/layout.tsx`; per-route pages in `app/**/page.tsx`
- `/terminal` is kept as legacy route but currently redirects to `/`

### State management

- **Server/cache state:** TanStack React Query (`@tanstack/react-query`)
- **Client UI state:** React local state + Context providers
  - `QueryProvider`
  - `SidebarProvider`
  - `TradingModeProvider`
  - `AlertProvider`

### Data/realtime

- **Supabase client:** `@supabase/supabase-js`
- **Realtime/WebSocket:** Supabase Realtime channels (primarily `trading_signals` table events)
- **HTTP backend:** Fetch wrappers in `src/lib/api.ts` + direct fetches in multiple hooks/components

### Styling/UI

- **Tailwind CSS v4**
- **Shadcn + Radix UI** primitives (dialogs, tabs, tooltip, etc.)
- **Custom global design system** in `src/app/globals.css` (tokens + utility classes)
- **Icons:** `lucide-react`

### Charts/tables

- **Charts:** `recharts`, `lightweight-charts`
- **Tables:** custom tables + shadcn table primitives (no virtualization currently)

### Lint/config

- ESLint Next core-web-vitals + TS config (`frontend/eslint.config.mjs`)
- Shadcn registry config (`frontend/components.json`)
- Env checking script (`frontend/scripts/check_env.js`)

---

## 2) Folder map + entry points

## Repo areas relevant to frontend

- `frontend/src/app` → routes/pages
- `frontend/src/components` → presentation + composed feature components
- `frontend/src/hooks` → data access + polling/realtime orchestration
- `frontend/src/lib` → API/supabase/config/utils/formatting
- `frontend/src/providers` → app-level providers (query/sidebar/mode)
- `frontend/src/types` → shared TS domain-ish types

## Frontend entry points

- `frontend/src/app/layout.tsx`
  - Wraps app with providers and `AppShell`
- `frontend/src/components/layout/AppShell.tsx`
  - Main shell composition (`Sidebar` + `TopBar` + content)
- `frontend/src/app/page.tsx`
  - Dashboard route (`/`)

---

## 3) Page map (routes → purpose → data sources)

| Route                      | Purpose                                                                           | Main data sources                                                                                                                          |
| -------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `/`                        | Dashboard command center (equity, active trades, signals, risk/execution widgets) | `useTradingSignals`, `useSignalStats`, `useEvaluationStats`, `useExecutionQuality`, `useRiskDashboard`, `useRiskStatus`, Supabase realtime |
| `/positions`               | Active positions + account status + optimizer actions                             | `useActivePositions` (`/positions/active`), `useAccountStatus` (`/positions/account`), optimizer APIs                                      |
| `/risk`                    | Risk monitor (read-only guard rails/status from backend)                          | `useRiskMonitor` (`/api/risk/monitor`)                                                                                                     |
| `/accounts`                | Multi-account manager (table/cards, add/delete, allocator/copy config)            | `useAccountsComparison` (`/api/portfolio-control/accounts/comparison`), account mutations                                                  |
| `/accounts/[account_name]` | Account detail tabs: overview/positions/history/analytics/journal                 | `fetchAccountDetail`, `syncAccount`, account-specific endpoints                                                                            |
| `/analytics`               | Portfolio/trade analytics dashboard                                               | `useAnalytics` (Supabase signals compute), `useBreakdown/useStreaks/useDrawdown/useSummary` (HTTP analytics endpoints)                     |
| `/portfolio-risk`          | VaR/correlation/sector exposure + risk tables                                     | `useRiskDashboard`, `useCorrelationMatrix`, `useRiskContribution`, `useSectorExposure`                                                     |
| `/execution-quality`       | TCA/execution quality metrics and alerts                                          | `useTCASummary`, `useSlippageBySymbol`, `useSlippageByHour`, `useLatencyBreakdown`, `useTCAAlerts`                                         |
| `/backtest`                | Backtest runner + replay + results/perf tabs                                      | `backtestAPI.runBacktest` (`/api/backtest/run`)                                                                                            |
| `/journal`                 | Historical signals/trades + filters + export + inspector                          | `useJournalSignals` (Supabase signals), CSV export                                                                                         |
| `/rules`                   | Risk rules + strategy knowledge base management                                   | `RiskRulesPanel` (direct Supabase table ops), `StrategyRulesPanel` (Supabase + `/api/rules/strategy`)                                      |
| `/settings`                | Connections/AI config/system health/alert rules/environment visibility            | `fetchAiConfig`, `useSystemHealth`, `useDeadLetters`, `useAlerts`/alert-rules APIs, env vars                                               |
| `/terminal`                | Legacy route; now redirects to dashboard                                          | client redirect only                                                                                                                       |

---

## 4) API client, websocket handlers, env vars, config files

## API/data client modules

- `src/lib/api.ts`
  - Primary HTTP client (`apiFetch`) + endpoint functions (backtest, portfolio-control, accounts, alerts, config, etc.)
- `src/lib/supabase.ts`
  - Supabase client init, signal fetching, stats derivation, mock fallback
- `src/lib/config.ts`
  - Additional API URL config layer (**duplicates intent in `api.ts`**)

## Websocket/realtime handlers (Supabase)

- `useTradingSignals.ts`
  - Subscribes to `postgres_changes` on `public.trading_signals` with `event: '*'`
  - Updates React Query cache on INSERT/UPDATE/DELETE
- `PineConfigStatus.tsx`
  - Subscribes to INSERT on `trading_signals` to track account balance source
- `ConnectionStatus.tsx`
  - Creates realtime health-check channel in settings page

## Environment variables in use (frontend-relevant)

- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NODE_ENV`

## Config files (frontend)

- `frontend/package.json`
- `frontend/next.config.ts`
- `frontend/eslint.config.mjs`
- `frontend/components.json`
- `frontend/src/app/globals.css`
- `frontend/scripts/check_env.js`
- root `.env.example` (frontend + backend var guidance)

---

## 5) Component inventory (key components + responsibilities)

## Layout/system

- `AppShell` → structural shell + route chrome behavior
- `Sidebar` → nav, collapse behavior, route highlighting
- `TopBar` → global KPIs, mode toggle, refresh, alerts, risk strip
- `ToastProvider`, `AlertProvider` → global notifications

## Dashboard

- `ActiveTradesPanel`, `RecentSignalsPanel`, `SignalInspector`
- `MiniEquityChart`
- `ExecutionQualityWidget`, `PortfolioRiskWidget`, `PineConfigStatus`
- `EvaluationDashboard`

## Accounts

- `AccountsTable`, `EnhancedAccountCard`, `AddAccountForm`
- `CapitalAllocator`, `CopyConfigurator`
- account detail tabs: `OverviewTab`, `PositionsTab`, `HistoryTab`, `AnalyticsTab`, `JournalTab`

## Risk/Rules

- `RiskBar` (kill-switch + gauge strip)
- Risk monitor page cards (daily risk, drawdown, guard rails)
- `RiskRulesPanel`, `StrategyRulesPanel`

## Analytics/Portfolio/Execution

- Analytics charts/tables (`EquityCurveChart`, `WinRateDonut`, `BreakdownTable`, etc.)
- Portfolio risk widgets/tables
- Execution quality charts + alerts table

## Backtest

- `BacktestChart`, `FXReplayController`, `BacktestPerformanceTab`

## Shared/UI primitives

- `components/ui/*` (button/card/table/tabs/dialog/skeleton/toast/etc.)
- `components/shared/*` (`PnLDisplay`, `StatusBadge`, placeholders)

---

## 6) Data flow map (API + WS → store/cache → UI)

## Primary flow

1. **Data ingress**

   - HTTP fetches from backend endpoints via hooks (`usePositions`, `usePortfolioRisk`, etc.)
   - Supabase query fetches (`fetchSignals`, `fetchSignalStats`)
   - Supabase realtime events (`trading_signals`)

2. **State/cache layer**

   - TanStack Query caches per `queryKey`
   - `useTradingSignals` mutates cache (`setQueryData`) on realtime events
   - Additional invalidations (`invalidateQueries`) refresh dependent metrics

3. **Derived data**

   - KPI computations happen in multiple places:
     - `fetchSignalStats` (`lib/supabase.ts`)
     - `TopBar` local `useMemo`
     - `useAnalytics.computeAnalytics`
     - `useLiveTrading.calculateStats`

4. **Presentation**
   - Pages compose widgets/tables/charts from hooks and derived values
   - Contexts influence UI behavior (`TradingModeProvider`, `SidebarProvider`)

---

## 7) Current pain points (bug sources + perf sources)

## Correctness / bug-risk sources

1. **Inconsistent metric definitions**

   - Win rate/PnL computed in several modules with slightly different filters.
   - Likely source of contradictory KPIs across TopBar/Analytics/Accounts.

2. **Unsafe numeric formatting (`toFixed`) surface area is high**

   - Many locations call `.toFixed(...)` on potentially nullable/optional values.
   - Example pattern found: `tcaSummary?.avg_spread_cost_usd.toFixed(2)` (still unsafe if field undefined).

3. **Mode/status normalization complexity**

   - `mode` vs `run_mode`, mixed status semantics (`executed` sometimes treated as active).
   - Easy to create inconsistent filtering between features.

4. **Account win-rate scaling ambiguity**

   - UI often does `(account.win_rate * 100)` while other parts treat values as percentages directly.
   - Potential double-scaling bug depending on backend payload contract.

5. **Untyped data access in critical areas**
   - `any` usage in risk/rules panels and direct Supabase table operations increases runtime bug risk.

## Performance / architecture sources

1. **Potential realtime render storms**

   - `useTradingSignals` subscribes per hook usage and updates cache on every event.
   - Stats invalidation on each event can cascade re-renders in global chrome (`TopBar`).

2. **No websocket batching/coalescing yet**

   - Incoming realtime events are applied immediately, no 250–500ms buffer.

3. **Global top-level expensive dependencies**

   - `TopBar` mounted across app computes KPIs from signals; frequent updates impact all routes.

4. **Heavy polling spread across many hooks**

   - 1s/5s/10s/30s intervals across subsystems; can create network and render pressure.

5. **Large table surfaces are not virtualized**

   - Journal/backtest/account detail tables can grow large.

6. **Data layer fragmentation**

   - Mix of direct fetches, `api.ts`, `config.ts`, and direct Supabase in components.
   - Harder to enforce consistency, caching policy, and typed contracts.

7. **Duplicate API config responsibility**
   - Both `lib/api.ts` and `lib/config.ts` define API-base behavior.

---

## 8) Immediate Phase-0 conclusions

- Frontend is feature-rich and already uses a solid base (Next + Query + Supabase + chart stack).
- Biggest risks before redesign are **metric correctness consistency** and **realtime/polling-induced render pressure**.
- Architecture is functional but fragmented; a typed domain/data layer and unified KPI computation module will provide the safest foundation for Phases 1–3.
