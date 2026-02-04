## Railway v9.1 Environment Checklist

This checklist covers **all env vars** needed for the v9.1 Trading Bot on Railway, including
RAG, OpenAI, and Step-Up Risk. Set these in your Railway service( s) before going live.

### Core infrastructure (existing)

- **`SUPABASE_URL`**  
  Supabase project URL (e.g. `https://xxxx.supabase.co`).

- **`SUPABASE_ANON_KEY`**  
  Public anonymous key (used by frontend or read-only clients).

- **`SUPABASE_SERVICE_ROLE_KEY`**  
  Service role key with full access. Used by the worker, RAG ingestion, and scripts.  
  Mapped in code to `Settings.supabase_service_role_key`.

- **`REDIS_URL`**  
  Redis instance URL (Railway provides this for the Redis service).

- **`WEBHOOK_SECRET`**  
  Shared secret for `/webhook` authentication (TradingView + simulators must send it).

### AI / RAG / OpenAI (v9.1 – **NEW / UPDATED**)

- **`OPENAI_API_KEY`**  *(NEW for v9.1)*  
  Used by:
  - `src/ai/rag_engine.py` (embeddings via `text-embedding-3-small`)
  - `src/ai/brain.py` (ensemble LLM: `gpt-4o-mini`)
  - Transcript ingestion scripts in `scripts/` (`ingest_transcript_folder.py`, etc.)

- **`ENABLE_LLM_FILTER`** *(NEW flag, default `True`)*  
  - When `True`: `ensemble_decision` runs RF → RAG → LLM and gates trades.
  - When `False`: worker falls back to RF-only decisions.

- **`RUN_SHADOW_MODE`** *(NEW for shadow launch)*  
  - `True`: If AI says `NO_GO`, worker **logs the rejection but still executes** the trade.
  - `False`: If AI says `NO_GO`, worker blocks trade (`status="ai_rejected"`).

### Risk engine / Step-Up / Volatility (v9.1 – **UPDATED**)

These map to fields in `config/settings.py` and are already given sane defaults, but you
can override them via Railway env:

- **`RISK_MODE`** *(NEW value `step_up`)*  
  - `"step_up"`: Enable Asymmetric Compounding (Step-Up Protocol) in `PropGuard`.
  - `"linear"`: Traditional fixed-percentage risk.

- **`ENABLE_RISK_SCALING`** *(Dynamic risk scaling toggle)*  
  - `True`: Enable drawdown-based scaling via `enable_risk_scaling`.
  - `False`: Disable swarm-style risk reduction.

- **`VOLATILITY_TARGETING`**  
  - `True`: Use ATR-based position sizing (normalize risk across assets).
  - `False`: Use pure SL-distance sizing.

- **Step-Up thresholds (optional overrides)**  
  - `STEP_UP_THRESHOLD_1` (default `0.02`)  
  - `STEP_UP_RISK_1` (default `1.0`)  
  - `STEP_UP_THRESHOLD_2` (default `0.05`)  
  - `STEP_UP_RISK_2` (default `2.0`)  
  - `SURVIVAL_RISK` (default `0.5`)

### Trading / execution behavior (existing but important)

- **`LIVE_TRADING` / `LIVE_TRADING_ENABLED`**  
  - `false` / `0`: DRY_RUN mode (no live orders, only logging + paper logic).
  - `true` / `1`: Allow live execution (subject to adapters).

- **`PAPER_TRADING_ENABLED`**  
  - `true`: Allow paper positions via `PaperTrader`.

- **`PAPER_AUTO_EXECUTE`**  
  - `true`: Auto-open paper trades that pass all guards.

- **`PAPER_SYMBOLS`**  
  Comma-separated list of symbols allowed for paper auto-execution.

### Frontend / CORS (existing)

- **`FRONTEND_URL`**  
  Optional. If set, added to allowed CORS origins for the FastAPI backend.

### Summary of **new / v9.1-specific** envs

- `OPENAI_API_KEY`  
- `ENABLE_LLM_FILTER`  
- `RUN_SHADOW_MODE`  
- `RISK_MODE` (now expected to be `"step_up"` in v9.1)  
- `ENABLE_RISK_SCALING`

Make sure all of the above are set in Railway **before** running the v9.1 shadow launch in
production.

