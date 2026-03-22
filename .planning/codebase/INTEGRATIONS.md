# External Integrations

## Core Infrastructure
- **Supabase**:
  - **Database**: PostgreSQL hosted on Supabase, acting as the primary store for trades, signals, and user data.
  - **Authentication**: Managed identity service for secure access to the trading dashboard.
  - **PostgREST**: Automatic API generation layer.
- **Redis**:
  - **Signal Queue**: Critical bridge between the Backend API (Producer) and the Worker (Consumer).
  - **Caching**: High-speed storage for symbol rules, rate-limiting states, and ephemeral session data.

## Trading & Brokerage
- **MetaApi**:
  - **Purpose**: A cloud-based bridge between the trading system and MetaTrader 4/5 (MT4/MT5).
  - **Functionality**: Enables the system to place trades, manage orders, and monitor real-time balance on institutional brokers.
  - **Adapters**: Custom broker-specific logic implemented for providers like **Vantage**, **IC Markets**, and **FXCM**.

## Signal & Information Sources
- **TradingView**:
  - **Inbound Webhooks**: Receives signals from TradingView via `POST /webhook` protected by a secret token.
  - **Signal Schema**: Accepts JSON payloads including `symbol`, `side`, `entry`, `sl`, `tp`, and `size`.
- **Yahoo Finance (`yfinance`)**: Integrates price history and ticker metadata for symbol verification and historical context.

## AI & LLM Ecosystem
- **Large Language Models**:
  - **OpenAI (GPT-4)**: Primary brain for complex signal validation and "Council" debates.
  - **Anthropic (Claude)**: Utilized for high-reasoning tasks and alternative risk perspectives.
  - **Groq**: Integrated for ultra-fast Llama-based inference where latency is critical.
- **Orchestration**: Managed via `langchain` and custom implementations for the "Trinity" risk guardrail.

## Monitoring & Communication
- **Discord**:
  - **Webhooks**: Automatic broadcast of trade executions, risk alerts, and system health status.
  - **Bot**: Interactive interface for managing "Debate" threads where AI agents analyze potential trades.
- **Telegram**:
  - **Bot Integration**: Instant notifications for trade signals and account state changes directly to the user's mobile device.

## Deployment & Hosting
- **Railway**: Used for hosting the full stack (API, Worker, Frontend, Redis).
- **Environment Management**: Configuration is driven by `.env` with a centralized approach via `pydantic-settings`.
