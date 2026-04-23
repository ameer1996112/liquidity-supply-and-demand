# Bugs

- 2026-04-23 | `src/api_positions.py` | Dashboard live positions and live account summary only used one primary broker adapter, so multi-account live positions could disappear behind signal fallback even while other accounts were connected | Added profile-based live aggregation across eligible MetaAPI and cTrader accounts and corrected the frontend fallback mapper to preserve `signal.size`

- 2026-04-23 | `scripts/pinescript/strategies/SND_Strategy.pine` | `XAGUSD` zones could still be tagged as accuracy zones because the Pine gating excluded gold, indices, and platinum but not silver | Added `is_silver` to the `should_use_accuracy_zones` guard so silver matches gold behavior at the source

- 2026-04-16 | `src/api.py` | Silent exception handling in health checks, AI mode fallback, websocket cleanup, and webhook enqueue path hid production failures at the ingress boundary | Added structured logging for those branches, deduplicated CORS origin assembly, and fail-closed with HTTP 503 when queue enqueue fails
