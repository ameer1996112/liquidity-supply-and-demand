# Domain Research - Stack

## Overview
Standard 2025 tech stack recommendations for refactoring and maintaining an institutional algorithmic trading system.

## Recommended Stack
- **Backend Framework**: FastAPI remains the industry standard for high-performance Python APIs, especially for webhook processing.
- **Data & AI Guardrails**: LightGBM is preferred over standard scikit-learn random forests for low-latency, memory-constrained environments. Rank-BM25 is excellent for NLP triage.
- **Frontend**: Next.js (App Router) with React 19 and Tailwind v4 represents the bleeding edge of performance and maintainability.
- **State Management**: React Query (@tanstack/react-query) is essential for real-time dashboard data synchronization.

## Rationale
Fast execution and low latency are non-negotiable in algorithmic trading. The separation of the webhook receiver (FastAPI) from the execution engine (Worker via Redis) is a highly recommended pattern to prevent missed webhooks during processing spikes.

## What NOT to use
- Avoid synchronous ORM calls in FastAPI (blocks the async event loop).
- Avoid heavy client-side state management (like Redux) if React Query can handle server state caching natively.
