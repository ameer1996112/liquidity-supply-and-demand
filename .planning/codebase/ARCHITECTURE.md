# ARCHITECTURE

## System Overview
The system is an institutional liquidity-based algorithmic trading system consisting of three distinct services, designed with Domain-Driven Design (DDD) principles (v9 DDD).

## Component Boundaries & Data Flow
1. **Frontend (Next.js, port 3000)**
   - Provides real-time trading dashboard displaying signal feeds, risk monitoring, and analytics.
   - Fetches data via REST APIs or Supabase directly.

2. **Backend API (FastAPI, port 8000)**
   - Acts as the entry point for TradingView webhook signals (`POST /webhook`).
   - Validates incoming signal payloads (symbol, side, entry, sl, tp, size).
   - Validates webhook secrets using environment variables.
   - Pushes validated signals into a Redis queue.

3. **Background Worker (Python)**
   - Consumes trading signals asynchronously from the Redis queue.
   - Executes AI/ML guardrails (AI_FILTER, ML_GUARDIAN, TRINITY) before trade execution.
   - Executes actual trades through broker APIs (e.g., MetaAPI).

## Key Patterns
- **Asynchronous Processing**: Webhooks are acknowledged instantly by FastAPI, pushing the actual heavy lifting (ML guardrails, execution) to the background worker to prevent webhook timeouts.
- **Multi-Agent Trading Council**: Utilizes NLP/LLMs to debate and validate trading decisions before execution.
