# Project

## What This Is

An institutional liquidity-based algorithmic trading system with a FastAPI backend (webhook signals, Redis queue, AI/ML guardrails, trade execution via MetaAPI), a Python worker, and a Next.js real-time dashboard. Manages multiple broker accounts across prop firm challenges and personal accounts with copy trading, risk management, and portfolio optimization.

Currently: multi-account management exists with manual prop firm configuration — hardcoded presets per firm, manual phase switching, global enforcement limits, and a separate /prop-firm page for challenge tracking.

## Core Value

Zero-config prop firm compliance — add an account, pick the firm, and the system handles rules, enforcement, and phase advancement automatically. Stale rules must never cause a breach.

## Current State

- Backend API running on port 8000 with FastAPI, Supabase, Redis
- Worker consumes signals, runs guardrails, executes via MetaAPI
- Frontend Next.js dashboard with accounts page, prop firm page, journal, analytics
- Per-account challenge settings stored in broker_profiles table
- prop_guard.py enforces risk limits but reads from global settings, not per-account
- Hardcoded PROVIDER_PRESETS in frontend for FTMO, ACG, MyFundedFX, TFT, E8
- MyFundedFX shut down Feb 2026 — preset is stale

## Architecture / Key Patterns

- **Backend**: FastAPI + Supabase + Redis. Settings via pydantic `config/settings.py` with `@lru_cache`. Dynamic config overrides in DB.
- **Frontend**: Next.js App Router, TanStack Query, Tailwind CSS, shadcn/ui components
- **Multi-account**: `account_strategies` table + `broker_profiles` table in Supabase. MetaAPI for broker connection.
- **Risk pipeline**: signal → consumer_validator → prop_guard/risk_engine → account_router → executor
- **Challenge settings**: stored per-account in `broker_profiles` columns, served via `/api/v1/portfolio-control/accounts/{name}/challenge`

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [ ] M001: Smart Prop Firm Rules Engine — Zero-config prop firm compliance with curated rules database, per-account enforcement, auto-phase advancement, and consolidated dashboard
