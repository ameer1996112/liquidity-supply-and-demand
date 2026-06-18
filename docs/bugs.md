# Bugs

- 2026-06-18 | `scripts/pinescript/indicators/SND_Raw_RD_Forex_LAB.pine`, `scripts/pinescript/indicators/SND_Raw_RD_Forex_PROD.pine` | Raw local high/low fallback made liquidity detection too broad and created incorrect lines across zones | Rolled back raw local fallback; keep liquidity selection limited to strict and one-candle pivot candidates while preserving candidate visibility fixes

- 2026-06-18 | `scripts/pinescript/indicators/SND_Raw_RD_Forex_LAB.pine`, `scripts/pinescript/indicators/SND_Raw_RD_Forex_PROD.pine` | 23:10 demand zone could choose `29793.07` instead of the lower `29782.85` liquidity because local one-candle pivots were only scanned when no strict pivot existed | Let local one-candle liquidity candidates compete with strict pivots so the closer valid level can win

- 2026-06-18 | `scripts/pinescript/indicators/SND_Raw_RD_Forex_LAB.pine`, `scripts/pinescript/indicators/SND_Raw_RD_Forex_PROD.pine` | Valid liquidity candidates could disappear or freeze on an older level because the scanner stopped after `liquidityValid` and line display waited for `targetSwept` | Keep rescanning until liquidity or target sweep proof and keep valid unswept liquidity candidates visible

- 2026-06-18 | `scripts/pinescript/indicators/SND_Raw_RD_Forex*.pine` | NAS100 LAB/PROD suppressed ACC bounds, so the 23:10 origin fell back to a broad standard demand zone instead of the compact upper wick-to-body zone shown by the reference | Allowed ACC bounds on index symbols and aligned ACC bounds so demand uses origin high to body high while supply uses body low to origin low

- 2026-04-23 | `src/api_positions.py` | Dashboard live positions and live account summary only used one primary broker adapter, so multi-account live positions could disappear behind signal fallback even while other accounts were connected | Added profile-based live aggregation across eligible MetaAPI and cTrader accounts and corrected the frontend fallback mapper to preserve `signal.size`

- 2026-04-23 | `scripts/pinescript/strategies/SND_Strategy.pine` | `XAGUSD` zones could still be tagged as accuracy zones because the Pine gating excluded gold, indices, and platinum but not silver | Added `is_silver` to the `should_use_accuracy_zones` guard so silver matches gold behavior at the source

- 2026-04-16 | `src/api.py` | Silent exception handling in health checks, AI mode fallback, websocket cleanup, and webhook enqueue path hid production failures at the ingress boundary | Added structured logging for those branches, deduplicated CORS origin assembly, and fail-closed with HTTP 503 when queue enqueue fails
