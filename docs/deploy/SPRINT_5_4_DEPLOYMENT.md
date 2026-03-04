## Sprint 5.4 – Deployment & Cost Optimization

This guide defines a **cost‑optimized deployment plan** for the trading system, with:

- **Two deployment targets**  
  - **A. Railway** (current platform, minimal changes)  
  - **B. Cheaper alternative** (single Linux VPS, Docker‑based)
- **Component architecture** for:
  - API service (`src.api:app`, FastAPI)
  - Worker service(s) (`src.worker:run`, Redis consumer)
  - DB (Supabase Postgres)
  - Redis (signal queue + metadata)
  - Frontend (Next.js dashboard)
- **Multi‑account scaling strategy** (no per‑account infra)
- **Exact deployment steps, env vars, health checks, and migrations**
- **Recommended defaults** for **cheap** vs **reliable** modes

This document extends, but does not replace:

- `docs/DEPLOYMENT_GUIDE.md` – earlier Railway monorepo guide  
- `docs/RAILWAY_SETUP.md` – example of env variables for dynamic risk  

---

## 1. Component architecture (cost‑optimized)

### 1.1 Logical components

- **API service (FastAPI)**
  - Entry: `src.api:app` (served via `uvicorn`)
  - Responsibilities:
    - Accept TradingView webhooks (`POST /webhook`)
    - Validate payloads and enqueue signals to Redis (`SIGNAL_TRANSPORT=redis`)
    - Serve dashboard APIs, health, portfolio and admin endpoints
  - Health endpoints:
    - Core liveness: `GET /health` (see `src/api.py`)
    - System / queue view (optional for ops):  
      - `GET /admin/health` (from `src/api_admin.py` router)  
      - `GET /portfolio/health` (from `src/api_portfolio_control.py` router)

- **Worker service(s)**
  - Entry: `python -m src.worker` or equivalent `src.worker:run`
  - Responsibilities:
    - Consume signals from Redis queue (`get_transport()` using `SIGNAL_TRANSPORT=redis`)
    - Run AI/ML guardrails + risk engines
    - Execute trades via MetaApi and log to Supabase
    - Support **multi‑account execution** (see `get_active_profiles` and `BROKER_PROFILES_JSON`)
  - Characteristics:
    - Long‑running loop (no HTTP server)
    - Safe to **horizontally scale**: multiple worker processes can share the same Redis queues and dead‑letter queue.

- **DB – Supabase Postgres**
  - External managed Postgres (Supabase)
  - Accessed via Supabase client (`SUPABASE_URL`, `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY`)
  - Schema managed via SQL files in `/migrations`
  - **Cost note:** Supabase free / lower tiers are often cheaper than self‑hosting Postgres once ops time is included; this guide assumes **Supabase remains the DB**.

- **Redis**
  - Required for:
    - Signal queue (`SIGNAL_TRANSPORT=redis`)
    - Dead‑letter queue and health telemetry
    - Some guardrails and kill‑switch state
  - Must be reachable on `REDIS_URL` from **both** API and worker processes.

- **Frontend (Next.js)**
  - Directory: `frontend/`
  - Talks to:
    - Supabase (`NEXT_PUBLIC_SUPABASE_*`)
    - Backend API (`NEXT_PUBLIC_API_URL`)
  - Can be deployed as:
    - Static site + Node server (Railway / VPS)
    - Fully managed static host (Vercel, Netlify) for extra savings

### 1.2 Cost‑optimized boundaries

For **minimal infra cost**:

- **Run API + worker in the same container/service** where possible:
  - Use existing `start.sh` (starts API and worker together) on Railway or VPS.
  - Scale **vertically** first (slightly bigger instance) before running many replicas.
- **Keep Supabase as managed DB**:
  - Avoid re‑implementing auth/storage and RLS in self‑hosted Postgres.
- **Use a single Redis instance**:
  - Same `REDIS_URL` for API + worker(s).
- **Deploy frontend separately**:
  - Either as a small Node service on Railway / VPS
  - Or as a static deployment on a cheap host (Vercel free/low tiers).

---

## 2. Deployment Target A – Railway (minimal‑change plan)

This section assumes Railway remains your primary deployment target and builds on `docs/DEPLOYMENT_GUIDE.md`.

### 2.1 High‑level Railway topology

- **Service: `backend` (API + Worker)**  
  - Root directory: repository root  
  - Start command: `chmod +x start.sh && ./start.sh`  
  - Contents:
    - Starts FastAPI (`src.api:app`) + Redis worker (`src.worker.run()`)
  - Uses environment from project root `.env` (via `config.settings`).

- **Service: `frontend` (Next.js dashboard)**  
  - Root directory: `/frontend`  
  - Start command: `npm run start` (or as auto‑detected by Railway)  
  - Uses `frontend/.env` or Railway variables for `NEXT_PUBLIC_*`.

- **Add‑ons / external services**
  - **Redis:** Railway Redis add‑on → maps to `REDIS_URL`
  - **DB:** Supabase project → maps to `SUPABASE_URL` and keys

### 2.2 Exact deployment steps (Railway)

#### Step 1 – Create / reuse Supabase project

1. In Supabase:
   - Create a project (or reuse existing).
   - Note `SUPABASE_URL` and `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY`.
2. In Supabase SQL Editor, run **migrations** (see 2.5 below).

#### Step 2 – Create / reuse Railway project

1. In Railway:
   - Create a new project (or reuse existing) connected to this GitHub repo.

#### Step 3 – Configure `backend` service

1. In Railway, open the **backend** service:
   - Root Directory: `/` (project root)
   - Start command: `chmod +x start.sh && ./start.sh`
2. Configure **Watch Paths** (see `docs/DEPLOYMENT_GUIDE.md` for details):
   - `src/**`
   - `config/**`
   - `migrations/**`
   - `start.sh`
   - `railway.json`
   - `nixpacks.toml`
3. Attach **Redis add‑on**:
   - In the project → Add Redis → note `REDIS_URL`.

#### Step 4 – Configure `frontend` service

1. Create a second Railway service from the same repo:
   - Root Directory: `/frontend`
   - Watch Paths: `frontend/**`
2. Build / start:
   - Railway detects Next.js from `package.json`.

#### Step 5 – Set environment variables (Railway)

**Backend + worker** (same `.env` / same service):

Minimum required for production:

- **Core connectivity**
  - `SUPABASE_URL` – from Supabase
  - `SUPABASE_ANON_KEY` – anon key (for read‑only ops; optional but recommended)
  - `SUPABASE_SERVICE_ROLE_KEY` – service key (for writes / RLS bypass)
  - `REDIS_URL` – from Railway Redis
  - `SIGNAL_TRANSPORT=redis`
- **Webhooks / security**
  - `WEBHOOK_SECRET` – shared secret between TradingView and API
- **Execution + risk baseline**
  - `ACCOUNT_BALANCE` – e.g. `50000`
  - `RISK_PERCENT` – e.g. `0.5`
  - `LIVE_TRADING=false` (start in DRY_RUN)
  - `RUN_MODE=DRY_RUN` (or `PAPER` / `LIVE` when ready)
- **AI / ML**
  - `AI_ENABLED` – `true` or `false` depending on cost profile
  - `AI_PROVIDER` – e.g. `anthropic`
  - `AI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` – required if AI is on
  - `ML_GUARDIAN_ENABLED` – `true` or `false`
  - `TRINITY_ENABLED` – `true` or `false`
- **CORS**
  - `FRONTEND_URL` – public frontend URL (for browser CORS)

Optional but recommended for production:

- Notifications: `DISCORD_WEBHOOK_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Portfolio/risk analytics: `PORTFOLIO_VAR_ENABLED`, `CORRELATION_MATRIX_ENABLED`, `TCA_ENABLED`
- Prop‑firm evaluation: `EVALUATION_MODE`, `EVALUATION_PHASE`, `CONSISTENCY_ENABLED`, etc.
- Multi‑account execution: `BROKER_PROFILES_JSON`, `META_API_TOKEN`, `META_API_REGION`

**Frontend**:

- Required:
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- Recommended:
  - `NEXT_PUBLIC_API_URL` – public URL of the backend service (e.g. `https://your-backend.up.railway.app`)

Use `.env.example` at repo root as the master reference for values and descriptions.

#### Step 6 – Health checks on Railway

**Backend service**:

- Configure Railway HTTP health check to:
  - **Path:** `/health`
  - **Expected status:** `200`
  - **Interval:** 30s–60s
- Optionally, add dashboards for:
  - `/admin/health` – includes Redis/dead‑letter info
  - `/portfolio/health` – includes background worker health summary

**Frontend service**:

- Default Next.js health:
  - Railway uses root `/` – ensure it responds once the build is complete.

#### Step 7 – Database migration strategy (Supabase)

Migrations are in `/migrations` with numeric prefixes (e.g. `028_accounts.sql`, `036_reconcile_metadata.sql`).

**Initial setup (new environment):**

1. In your local repo, list migrations:
   - `migrations/000_*.sql` ... `migrations/036_*.sql`
2. In Supabase SQL Editor:
   - Apply all migration files in **numeric order** (000 → 001 → ... → 036).
3. Verify:
   - Core tables like `trading_signals`, `accounts`, `ai_runs`, `backtests`, etc. exist.

**Ongoing deployments (incremental):**

1. For each new sprint:
   - Apply only the **new** migration files (e.g. `031_ai_mode_graduation.sql` up through `036_reconcile_metadata.sql`).
2. Keep a simple checklist in your release process (e.g. “Supabase migrations up to 036 applied”).

**When deploying a new Railway environment** (e.g. staging vs prod):

1. Use **the same migration set** in both environments.
2. Confirm `SUPABASE_URL` and keys point to the intended project (staging vs prod).

---

## 3. Deployment Target B – Cheaper Alternative (Linux VPS)

For lower monthly cost and more control, run the stack on a **single small VPS** using Docker:

- Example providers:
  - Hetzner CX11/CX22
  - DigitalOcean 1–2 GB droplet
  - OVH / Contabo low‑end VPS

### 3.1 High‑level VPS topology

On a single VPS:

- **Container: `api-worker`**
  - Image built from repo root
  - Command: `./start.sh` (starts API + worker)
  - Exposes port `8000` (FastAPI)
- **Container: `redis`**
  - Official Redis image
  - Exposes port `6379` (internal only)
- **Reverse proxy: `nginx` or `caddy`**
  - Terminates TLS
  - Proxies `https://your-domain` → `api-worker:8000`
- **Frontend options:**
  - Host Next.js on the same VPS (separate container)
  - Or deploy the frontend to Vercel and only host API + worker + Redis on VPS.

Supabase remains external (no DB on the VPS).

### 3.2 Example Docker Compose (VPS)

Create `docker-compose.yml` (example only; adjust image/build details to match your repo):

```yaml
version: "3.9"

services:
  api-worker:
    build: .
    command: ["./start.sh"]
    env_file:
      - .env
    ports:
      - "8000:8000"
    depends_on:
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    ports:
      - "6379:6379"
    command: ["redis-server", "--save", "", "--appendonly", "no"]

  # Optional: nginx or caddy reverse proxy
  # frontend: (optional) Next.js container
```

Key points:

- `.env` at repo root is mounted into `api-worker` (same format as local).
- `REDIS_URL` should be `redis://redis:6379` inside the compose network.
- Health check hits `/health` on the API.

### 3.3 Exact VPS deployment steps

1. **Provision VPS**
   - Choose OS: Ubuntu 22.04 LTS.
   - Configure firewall: allow `80` and `443`, optionally `22` for SSH.
2. **Install Docker + Compose**
   - Install Docker Engine and Docker Compose Plugin from official docs.
3. **Clone repo**
   - `git clone` the trading repo to `/opt/trading` (or similar).
4. **Set environment**
   - Copy `.env.example` → `.env` at repo root.
   - Fill in all required variables (see Section 2.5).
   - Set `REDIS_URL=redis://redis:6379`.
5. **Run migrations**
   - Use Supabase SQL Editor as described in Section 2.7 (no change vs Railway).
6. **Start stack**
   - `docker compose up -d --build`
   - Verify:
     - API: `curl http://localhost:8000/health` → `{"status": "ok", "service": "api"}`
     - Redis: `docker exec -it <redis-container> redis-cli ping` → `PONG`
7. **Configure reverse proxy + HTTPS**
   - Use Caddy or nginx with Let’s Encrypt:
     - Proxy `https://your-domain` → `http://localhost:8000`
   - Update `FRONTEND_URL` and `NEXT_PUBLIC_API_URL` to `https://your-domain`.

### 3.4 Frontend on VPS (optional)

If you also want to host the frontend on the VPS:

1. Build a Next.js production image from `frontend/`.
2. Add a `frontend` service to `docker-compose.yml`:
   - `build: ./frontend`
   - `command: ["npm", "run", "start"]`
   - `ports: ["3000:3000"]`
3. Adjust reverse proxy to:
   - `https://app.your-domain` → frontend
   - `https://api.your-domain` → backend (`api-worker`).

For **maximum cost savings**, you can instead deploy the frontend to Vercel (free/low tier) and only host backend + Redis on the VPS.

---

## 4. Multi‑account scaling strategy

### 4.1 Add new accounts without multiplying infra cost

Multi‑account support is implemented in code (see `src.worker`, `src.core.broker_profiles`, and `migrations/028_accounts.sql` and related migrations). You **do not** need a new API/worker instance per account.

Pattern:

- **Representation**
  - Each trading account is represented in Supabase tables (`accounts`, `broker_profiles`, etc.).
  - The worker reads configuration per account (via `BROKER_PROFILES_JSON` or Supabase tables).
- **Execution**
  - Incoming TradingView signals **do not change** per account.
  - Worker routes execution to multiple accounts in parallel inside `process_trade`:
    - `get_active_profiles()` → list of active profiles
    - Per‑account guards, risk and consistency checks
    - Per‑account kill switches and MTM guards (`trading:kill_switch:{account}` in Redis)
  - A **single worker fleet** can handle many accounts.

To add accounts:

1. Add new account rows in Supabase (via admin UI or SQL).
2. If using `BROKER_PROFILES_JSON`, update this env var with a JSON array of profile configs for the new account(s).
3. Redeploy/restart worker(s) so the new configuration is loaded.

No additional infra services are required; you only scale workers when the combined traffic exceeds capacity.

### 4.2 Running multiple workers safely

The worker is designed to be horizontally scalable:

- Uses Redis queue abstraction (`SignalTransport`) so:
  - Multiple worker processes can `dequeue` tasks concurrently.
  - Dead‑lettering is centralized.
- Guards for safety:
  - Idempotency checks on `trade_key` (per `broker_profile_id`).
  - Per‑account MTM guard and kill switches.
  - Per‑account correlation and consistency guards.

Scaling rules:

- On Railway:
  - Start with **1 backend service** (API + worker in same container).
  - For more throughput:
    - Option 1 (cheap): increase CPU/RAM of the backend service.
    - Option 2 (reliable): add a **separate worker service** running `python -m src.worker` pointing at the same `REDIS_URL`.
- On VPS:
  - Use Docker Compose with:
    - `scale api-worker=<N>` (Compose v2 `deploy.replicas`) or
    - Multiple `api-worker` containers in a swarm.
  - All replicas share the same Redis service.

Always monitor:

- Redis CPU/memory and latency.
- Supabase rate limits (per second).
- Worker logs for dead‑letters or consistent `model_error` / `ai_rejected` patterns.

---

## 5. Recommended defaults – Cheap vs Reliable Modes

This section maps env vars in `.env.example` / `config.settings` to two profiles:

- **Cheap Mode** – minimize infra + AI spend for early testing / hobby users.
- **Reliable Mode** – safer for production, prop‑firm challenges, and many accounts.

### 5.1 Core env defaults

**Shared defaults (both modes):**

- `SIGNAL_TRANSPORT=redis`
- `RUN_MODE=DRY_RUN` for initial deployments, then:
  - `RUN_MODE=PAPER` for paper trading
  - `RUN_MODE=LIVE` only when fully validated
- `LIVE_TRADING=false` initially; only set `true` once guards are validated.

### 5.2 Cheap Mode (cost‑optimized)

Goal: Minimize compute and external AI costs while keeping core risk rails that are cheap.

- **Infra**
  - Railway: **1 backend service** (API + worker), **smallest** viable plan.
  - Redis: single low‑tier instance.
  - Frontend: deploy to Vercel or small Railway service.
- **Env toggles (recommended)**
  - `AI_ENABLED=false` (skip LLM calls)
  - `AI_FILTER_ENABLED=false` or `AI_SHADOW_MODE=true` (log only, never block)
  - `ML_GUARDIAN_ENABLED=false` (disable RF if model hosting is expensive)
  - `TRINITY_ENABLED=true` but tuned conservatively (limits enabled, values close to defaults)
  - `MEMORY_ENABLED=false`
  - `PORTFOLIO_VAR_ENABLED=false`
  - `CORRELATION_MATRIX_ENABLED=true` (low cost, strong risk value)
  - `TCA_ENABLED=false`
  - `EVALUATION_MODE=false`
  - `ACCOUNT_SYNC_ENABLED=false`
  - `METAAPI_POSITIONS_FETCH_ENABLED=false`
- **Account / risk**
  - `ACCOUNT_BALANCE` and `RISK_PERCENT` tuned for your test account size (e.g. `50000` and `0.5`).
  - Limit number of active accounts (e.g. 1–2) to keep traffic low.

### 5.3 Reliable Mode (production / prop‑firm)

Goal: Maximize safety and analytics, accepting slightly higher infra and AI costs.

- **Infra**
  - Railway:
    - Backend service with higher CPU/RAM (or separate API + worker services).
    - Redis on a more reliable tier (latency‑optimized).
  - VPS:
    - 2–3 `api-worker` replicas behind a reverse proxy.
- **Env toggles (recommended)**
  - `AI_ENABLED=true`
  - `AI_FILTER_ENABLED=true`
  - `AI_MODE=enforce` (once shadow results show a positive edge and sample size ≥ `AI_GRADUATION_MIN_SAMPLE_SIZE`)
  - `ML_GUARDIAN_ENABLED=true`, `ML_MIN_CONFIDENCE≈0.60`
  - `TRINITY_ENABLED=true` with default or stricter parameters
  - `MEMORY_ENABLED=true` (trade reflection + memory loop)
  - `PORTFOLIO_VAR_ENABLED=true`
  - `CORRELATION_MATRIX_ENABLED=true`
  - `TCA_ENABLED=true`
  - `EVALUATION_MODE=true` (for prop‑firm challenges)
  - `ACCOUNT_SYNC_ENABLED=true` (if you rely on MetaApi account sync)
  - `METAAPI_POSITIONS_FETCH_ENABLED=true`
- **Account / risk**
  - Use `BROKER_PROFILES_JSON` or Supabase UI to define multiple accounts.
  - Carefully set per‑account `risk_pct`, `max_positions`, etc.

---

## 6. Summary

- **Railway** remains the easiest target with minimal code changes: one backend (API+worker) + one frontend service, Redis add‑on, Supabase DB.
- A **single Linux VPS** with Docker (API+worker + Redis) is a **cheaper runtime alternative** while still keeping Supabase as managed DB.
- **Multi‑account scaling** is implemented at the worker and DB layers; you grow by adding accounts in Supabase and scaling workers, not by cloning infra per account.
- Use the **Cheap Mode** and **Reliable Mode** env presets above to quickly switch between cost‑optimized and safety‑optimized deployments.

