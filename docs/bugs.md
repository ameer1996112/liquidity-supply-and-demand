# Bugs

- 2026-04-16 | `src/api.py` | Silent exception handling in health checks, AI mode fallback, websocket cleanup, and webhook enqueue path hid production failures at the ingress boundary | Added structured logging for those branches, deduplicated CORS origin assembly, and fail-closed with HTTP 503 when queue enqueue fails
