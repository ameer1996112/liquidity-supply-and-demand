# System Architecture

**Pattern:** Event-Driven DDD — TradingView webhook → Redis queue → Worker pipeline → MetaApi broker

## Route to the Right Module

| Task | Module in MODULE_MAP |
|------|---------------------|
| Change how webhooks are received / validated | Webhook Ingress |
| Change signal pipeline or guard rail order | Signal Pipeline |
| Add or modify a trade veto | Guard Rails |
| Change position sizing or risk calculations | Risk Engine |
| Change how trades open/close on broker | Trade Execution |
| Add or modify an API endpoint | API Endpoints |
| Add business logic (not in API, not in worker) | Services |
| Change AI/ML validation | AI / ML |
| Add cross-cutting event handling | Observers |
| Change external service integration | Adapters |
| Change frontend page or component | Frontend |
| Add a database migration | Database |

## Signal Flow (happy path)

```
TradingView webhook
  → POST /webhook (src/api.py)
  → Redis queue (src/adapters/redis_queue.py)
  → Worker loop (src/worker.py)
  → Guard rails chain (src/core/guard_rails/)
  → Risk engine → position sizing (src/core/risk_engine.py)
  → Trade execution (src/logic.py)
  → MetaApi broker (src/adapters/execution/meta_api_adapter.py)
  → Supabase persist (src/adapters/supabase.py)
  → Observers fire (src/core/observers/)
```

## Key Constraints

- All I/O is async/await
- Guards are veto-only — they never modify the signal
- Observers must never raise exceptions
- `src/logic.py` and `src/worker.py` are live trading paths — change with extreme care
- Multi-account: each signal is fanned out per `broker_profiles` row
