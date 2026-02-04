# Railway Frontend Deployment Check (v9.1)

Use this checklist to verify the Mission Control frontend deploys correctly and displays Ensemble Brain data after changes (e.g. new types or SignalInspector updates).

---

## 1. Build command and types

- **Build command:** `npm run build` (runs `next build` from `frontend/package.json`).
- **TypeScript:** The build compiles all `.ts`/`.tsx` under `frontend/src`, including `src/types/trading.ts` and `src/components/SignalInspector.tsx`. New or updated types (e.g. `AIReasoning` v9.1 fields) are included automatically—no extra step.
- **Check:** From repo root, run:
  ```bash
  cd frontend && npm run build
  ```
  Build should finish with no type errors. Fix any `TS2345`/`TS2322` in the files above before deploying.

---

## 2. Environment variables (frontend ↔ backend / Supabase)

The frontend is **Next.js** (not Vite). Use `NEXT_PUBLIC_*` for client-visible values.

| Variable | Required | Purpose |
|----------|----------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | Supabase project URL; used for `trading_signals` and realtime. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes | Supabase anon key; used for read/realtime. |
| `NEXT_PUBLIC_API_URL` | Optional | Backend API base URL (health checks, webhook proxy). Set in Railway if the UI calls the backend (e.g. `frontend/src/lib/api.ts`). |

- There is **no** `VITE_API_URL`; this app uses Next.js env only.
- **Railway:** Set these in the **Frontend service** → **Variables** tab. For new builds, set them **before** triggering a deploy so the build sees the correct `NEXT_PUBLIC_*` values (they are inlined at build time).

---

## 3. Triggering a rebuild on Railway

After updating types or `SignalInspector.tsx`:

1. **Option A – Git push**  
   Commit and push to the branch connected to Railway. Railway will build and deploy the frontend service automatically (if that service is configured to deploy from this repo).

2. **Option B – Manual redeploy**  
   - Open [Railway Dashboard](https://railway.app/dashboard) → your project → **Frontend** service.  
   - Go to **Deployments**.  
   - On the latest deployment, open the **⋮** menu → **Redeploy** to rebuild from the same commit.

3. **Option C – Rebuild from latest commit**  
   - **Settings** → **Redeploy** (or use **Deploy** from the source tab if you use GitHub/GitLab integration).  
   This runs a new build with the current `frontend/` code and the env vars currently set in Railway.

After deploy, open Mission Control, open a signal that has `ai_reasoning` (e.g. from a recent webhook test), and confirm the **AI BRAIN** tab shows **Ensemble Decision**, **RAG Rules** list, and **GO**/ **NO_GO** badge as expected.
