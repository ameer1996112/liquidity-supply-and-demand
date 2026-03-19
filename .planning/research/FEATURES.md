# Domain Research - Features

## Overview
Table stakes and differentiators when refactoring an existing algorithmic trading system to professional standards.

## Table Stakes (Must-Haves)
- **Strict Typing & Validation**: Pydantic models for all incoming/outgoing data. No loose dictionary passing.
- **Zero-Warning Linting**: Enforcing strict `ruff` and `eslint` pipelines.
- **Comprehensive Testing**: 80%+ coverage on core execution paths and AI guardrails. Vitest and Pytest are the standard.

## Differentiators
- **Latency Optimization**: Caching broker states, reusing price data for TCA, and bypassing serial pre-fetching when executing trades.
- **Resilience**: Robust error handling for broker API timeouts (e.g., MetaAPI 5-second timeout mitigation).

## Anti-Patterns
- Tightly coupling the TradingView webhook payload directly to the broker execution wrapper. (Instead, parse -> validate -> queue -> execute).
