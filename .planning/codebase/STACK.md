# Technology Stack

## Backend
- **Language**: Python 3.11+
- **Framework**: FastAPI (v0.109+) - A modern, high-performance web framework for building the API.
- **Runtime**: Uvicorn - The lightning-fast ASGI server for running the FastAPI application.
- **Task Scheduling**: APScheduler (Advanced Python Scheduler) for background tasks, maintenance routines, and periodic jobs.
- **Message Broker**: Redis - Acts as the primary signal queue (transporting signals from the API to the Worker) and as a transient data caching layer.
- **Database**: Supabase (PostgreSQL) - Reliable persistent storage for trade history, signal logs, and configuration.
- **Machine Learning & Data Science**:
  - `scikit-learn`: Industry-standard machine learning library.
  - `lightgbm`: High-performance gradient boosting framework.
  - `pandas`, `numpy`: Core libraries for data manipulation and numerical analysis.
  - `numba`: JIT compiler used for high-speed numerical functions.
  - `pyarrow`: Memory-efficient columnar data format.
  - `backtesting.py`: Strategy testing and verification platform.
- **AI & Agentic Orchestration**:
  - `langchain`: Used for orchestrating multi-agent LLM workflows.
  - `openai`, `anthropic`: SDKs for integrating cutting-edge LLM providers.
- **Security & Efficiency**:
  - `slowapi`: Implementation of rate limiting for public-facing endpoints.
  - `pydantic-settings`: Management of environment variables and configuration objects.

## Frontend
- **Framework**: Next.js 16.1.6 (App Router) - Leveraging the latest features of Next.js and the React 19 ecosystem.
- **Core Library**: React 19.2.3
- **Language**: TypeScript - Ensuring type safety across the dashboard.
- **State Management**:
  - `Tanstack Query` (v5): Efficient management of server state and real-time data synchronization.
- **UI & Styling**:
  - `Tailwind CSS 4`: Utility-first styling with the latest v4 engine.
  - `Radix UI`: Accessible, unstyled UI primitives for complex components like Dialogs and Selects.
  - `Lucide React`: Modern and clean icon set.
  - `Tanstack Table` (v8): Advanced data grid management for trade and signal tables.
- **Data Visualization**:
  - `Recharts`: Flexible charting library for dashboard analytics.
  - `Lightweight Charts`: Optimized financial charting for real-time price action display.

## Infrastructure & Tooling
- **Deployment**: Railway (referenced in environment and configuration files).
- **Build Strategy**:
  - `Nixpacks`: For automated, reproducible deployment builds.
  - `Docker`: Using specialized Dockerfiles for individual services (`Dockerfile.api`, `Dockerfile.worker`).
- **Development Workflow**: `Makefile` and `start.sh` are used to orchestrate local development across multiple services (API + Worker + Frontend).
