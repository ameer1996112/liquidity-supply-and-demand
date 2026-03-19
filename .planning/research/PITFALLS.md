# Domain Research - Pitfalls

## Common Mistakes
- **Timeouts**: Failing to adjust broker API timeouts. MetaAPI can take 5+ seconds for reconciliation, which blocks the thread and delays actual trade execution.
  - *Prevention*: Maintain separate execution paths and timeouts for live high-priority trades versus background reconciliation tasks.
- **Cache Invalidation**: Using `@lru_cache` for `.env` credentials in `config/settings.py` prevents dynamic credential updates.
  - *Prevention*: Ensure environment loading is robust without requiring full container restarts where inappropriate, or explicitly document the restart requirement.
- **CORS Policies**: Overly rigid FastAPI CORS settings breaking the Next.js frontend in production.
  - *Prevention*: Configure exact origins in production `.env` and align with Reverse Proxies / Supabase setup.
