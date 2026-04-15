# 2026-04-15 — Multi‑Venue Bot (Prop + Personal + Crypto) — Design Spec

## Goal

Build a “set & forget” trading system which:

- Uses **TradingView alerts as the single signal source (v1)**
- Executes across **multiple venues**:
  - Prop firm accounts (forex/indices) via **cTrader** where available, and **MT5** where required
  - Personal crypto accounts on **Binance** and **Bybit** (spot + futures)
- Provides **streaming PnL / fills / trade-close events** per venue and normalizes them into the same database model used by the dashboard

The system must support:

- **Prop firm mode** (strict risk constraints and account rules)
- **Personal mode** (less strict constraints)
- Multiple concurrent accounts (10+ in the future)

Non-goals (v1):

- Building a new strategy engine for crypto (signals come from TradingView)
- Rewriting core trading logic/strategy rules

## Current System (Observed)

The backend already supports multi-account execution using “broker profiles” with MetaApi, and has:

- A common execution wrapper (`ExecutionEngine`) with TCA capture
- A MetaApi execution adapter (`MetaApiAdapter`)
- A MetaApi streaming service for real-time deal close / PnL persistence
- Risk/guardrail layers that can be reused for prop mode

## Key Decisions

### D1 — Single signal source (TradingView) for v1

All venues (prop + personal + crypto) receive the same normalized signal event, then route to accounts via profiles.

Why:

- One alert schema to maintain
- Easier debugging and monitoring
- Faster iteration during forward-testing

### D2 — Profiles as the routing unit

Generalize the concept of “broker profiles” into a broader **AccountProfile** which includes:

- `venue`: `metaapi_mt5 | ctrader | binance | bybit`
- `mode`: `prop | personal`
- `asset_class`: `forex_cfd | crypto`
- Credential reference (env var key or secrets manager key)
- Risk configuration overrides (per profile)
- Symbol mapping overrides (per profile / venue)

### D3 — Streaming is first-class

Each venue must provide a streaming source of truth for:

- Order fills / position open/close
- Deal PnL / realized PnL (preferred over derived PnL)

Streaming updates normalize into existing tables (e.g., trading signals / positions) so the dashboard remains venue-agnostic.

## Architecture Overview

### Components

1. **Webhook Ingress**
   - Receives TradingView webhook payload
   - Validates and queues to Redis (existing)

2. **Signal Pipeline**
   - Dequeues signals
   - Applies guard rails + risk
   - Routes to one or more `AccountProfile`s for execution (existing pattern)

3. **Execution Layer**
   - `ExecutionEngine` wraps adapter calls (existing)
   - Venue-specific execution adapters implement the common interface:
     - `MetaApiAdapter` (existing)
     - `cTraderAdapter` (new)
     - `BinanceAdapter` (new)
     - `BybitAdapter` (new)

4. **Streaming Layer**
   - Venue-specific streaming services:
     - MetaApi streaming (existing)
     - cTrader streaming (new)
     - Binance user data stream (new)
     - Bybit user data stream (new)

5. **Normalization + Persistence**
   - Streaming events update the DB with authoritative fill/close/PnL data
   - Dashboard consumes one model regardless of venue

### Data Flow (High-Level)

TradingView → API → Redis → Worker Pipeline → (AccountProfiles) → Venue Adapter → Execution
                                                   ↓
                                              Streaming Services
                                                   ↓
                                                DB Updates
                                                   ↓
                                                Dashboard

## Venue Strategy

### Forex/Indices (Prop + Personal)

Preferred:

- **cTrader** (Open API) when available on the prop firm / broker

Fallback:

- **MT5** when required by the firm
  - During early testing: MetaApi is acceptable for 1–2 accounts
  - At 10+ accounts: move to a Windows VPS MT5 bridge to avoid per-account MetaApi pricing

### Crypto (Personal)

- **Binance**: spot + futures execution + user-data streaming
- **Bybit**: spot + futures execution + user-data streaming

## Risk Model

### Prop mode

Prop mode should enforce stricter constraints:

- Max daily loss, max drawdown
- Max risk per trade
- Max concurrent positions
- Venue/product constraints (e.g., leverage caps)

### Personal mode

Personal mode can relax limits and allow a different risk percent / max positions.

### Cross-cutting

- Per-venue symbol mapping and pip/lot sizing rules
- Separate “paper trading” capability must remain functional
- No changes to strategy logic unless explicitly requested

## Reliability / “Set & Forget” Requirements

- Automatic reconnection for streaming (with exponential backoff)
- Idempotent event handling (avoid double-closing / duplicate PnL writes)
- Clear “account health” status (connected/disconnected, last event time)
- Fail-closed for prop mode when account state cannot be trusted (configurable)
- Scheduling: optionally run active window **06:00–23:00 Israel time** (future)

## Testing Strategy (v1)

- Unit tests for:
  - Signal normalization into a unified internal schema (if needed)
  - Per-venue adapter request construction (mock HTTP/WebSocket)
  - Streaming event normalization and DB update logic
  - Prop vs personal risk presets routing
- End-to-end smoke test using:
  - **FTMO cTrader Free Trial** as the main “realistic” testbed
  - A small Binance/Bybit sandbox/testnet if feasible; otherwise a very small live account with strict limits

## Rollout Plan (Conceptual)

1. Keep existing MetaApi profiles working (no regressions)
2. Add Binance + Bybit adapters + streaming for personal crypto
3. Add cTrader adapter + streaming; verify using FTMO free trial
4. Add routing/risk presets for prop vs personal
5. Optional: replace MetaApi for MT5 scale with VPS bridge when account count grows

## Open Questions

- Exact unified internal “signal” schema to support both CFD and crypto (fields like leverage, contract type, reduce-only)
- Prop firm rule variations that may require per-profile rule toggles (news trading, min hold time)
- Whether to run multi-venue streaming in one process or split per-venue workers for isolation

