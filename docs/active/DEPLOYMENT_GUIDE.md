# Railway Deployment Guide - Monorepo Setup

This guide explains how to deploy the **Backend (Python/FastAPI)** and **Frontend (Next.js Dashboard)** as **separate services** in the same Railway project with independent rebuild triggers.

---

## Architecture Overview

```
trading/
├── backend/              # Python FastAPI + Worker
│   ├── main.py          # FastAPI app
│   ├── worker.py        # Background worker
│   └── requirements.txt
├── frontend/             # Next.js Frontend
│   ├── src/
│   ├── package.json
│   └── railway.json     # Frontend-specific config
├── start.sh             # Backend entry point
├── railway.json         # Backend config (root)
├── nixpacks.toml        # Backend build config
└── .dockerignore        # Excludes dashboard from backend builds
```

---

## Step 1: Create Railway Project

1. Go to [railway.app](https://railway.app) and log in
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Connect your repository

---

## Step 2: Configure Backend Service

The first service created will be your **Backend**. Configure it as follows:

### 2.1 Open Service Settings

1. Click on the service card
2. Go to **Settings** tab

### 2.2 Set Root Directory

1. Find **"Root Directory"** section
2. Leave it as `/` (empty/root)
   - This allows `start.sh` and `railway.json` at root to work correctly

### 2.3 Configure Watch Paths (CRITICAL)

1. Find **"Watch Paths"** section
2. Click **"Add Pattern"** and add these paths:
   ```
   backend/**
   start.sh
   railway.json
   nixpacks.toml
   ```
3. This ensures the backend ONLY rebuilds when Python code changes

### 2.4 Verify Start Command

1. Go to **Settings** → **Deploy**
2. Start Command should be: `chmod +x start.sh && ./start.sh`
   - This is auto-detected from `railway.json`

### 2.5 Set Environment Variables

1. Go to **Variables** tab
2. Add all required env vars from `backend/.env.example`:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `DISCORD_WEBHOOK_URL`
   - `OPENAI_API_KEY` (or other AI provider keys)
   - etc.

### 2.6 Rename Service (Optional)

1. In Settings, rename service to `backend` or `api`

---

## Step 3: Create Frontend Service

### 3.1 Add New Service

1. In your Railway project, click **"+ New"**
2. Select **"GitHub Repo"**
3. Choose the **same repository**

### 3.2 Set Root Directory (CRITICAL)

1. Click on the new service → **Settings**
2. Find **"Root Directory"**
3. Set it to: `/frontend`
   - This tells Railway to treat `frontend/` as the project root

### 3.3 Configure Watch Paths

1. Find **"Watch Paths"** section
2. Add this pattern:
   ```
   frontend/**
   ```
3. This ensures frontend ONLY rebuilds when Next.js code changes

### 3.4 Verify Build Settings

With Root Directory set to `/frontend`, Railway will:

- Auto-detect Next.js from `package.json`
- Run `npm install` and `npm run build`
- Start with `npm run start`

### 3.5 Set Environment Variables

1. Go to **Variables** tab
2. Add frontend env vars from `frontend/.env.example`:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_API_URL` (pointing to your backend service URL)

### 3.6 Rename Service

1. Rename to `dashboard` or `frontend`

---

## Step 4: Connect Services (Internal Networking)

### 4.1 Get Backend Internal URL

1. Click on Backend service → **Settings**
2. Find **"Private Networking"** section
3. Copy the internal URL (e.g., `backend.railway.internal:8000`)

### 4.2 Set Frontend API URL

1. Go to Frontend service → **Variables**
2. Set `NEXT_PUBLIC_API_URL` to backend's **public URL** (for client-side calls)
3. Optionally set `API_URL` to backend's **internal URL** (for server-side calls)

---

## Step 5: Verify Watch Paths Work

### Test Backend-Only Changes

1. Make a change to any file in `backend/`
2. Push to GitHub
3. **Expected:** Only Backend service rebuilds

### Test Frontend-Only Changes

1. Make a change to any file in `frontend/`
2. Push to GitHub
3. **Expected:** Only Frontend service rebuilds

---

## Summary: Service Configuration

| Setting            | Backend Service                                           | Frontend Service   |
| ------------------ | --------------------------------------------------------- | ------------------ |
| **Root Directory** | `/` (empty)                                               | `/frontend`        |
| **Watch Paths**    | `backend/**`, `start.sh`, `railway.json`, `nixpacks.toml` | `frontend/**`      |
| **Start Command**  | `chmod +x start.sh && ./start.sh`                         | `npm run start`    |
| **Builder**        | Nixpacks (Python)                                         | Nixpacks (Node.js) |

---

## Supabase schema (optional): Alerts

The app works without the alerts tables. If you want **alerts** (dashboard bell, alert rules, AlertEngine):

1. In Supabase Dashboard → **SQL Editor**, run in order:
   - Contents of `migrations/004_trading_alerts.sql`
   - Contents of `migrations/005_alert_rules.sql`
2. If these tables are missing, the API returns empty lists for `/alerts` and `/alerts/active` and no ERROR logs after the change; mutations (acknowledge, create rule) return 503 with a message to run the migrations.

---

## Troubleshooting

### Both services rebuild on every push

- Double-check Watch Paths are set correctly
- Ensure patterns don't overlap

### Backend can't find modules

- Verify `PYTHONPATH` is set correctly in `start.sh`
- Check `nixpacks.toml` installs from `backend/requirements.txt`

### Frontend build fails

- Ensure Root Directory is exactly `/frontend`
- Check `package.json` has correct build scripts

### Services can't communicate

- Use Railway's Private Networking for server-to-server calls
- Use public URLs for client-side (browser) calls

---

## Files Reference

| File                     | Purpose                                  |
| ------------------------ | ---------------------------------------- |
| `railway.json`           | Backend service config (root)            |
| `dashboard/railway.json` | Frontend service config                  |
| `nixpacks.toml`          | Backend Python build config              |
| `.dockerignore`          | Excludes `frontend/` from backend builds |
| `frontend/.dockerignore` | Excludes `backend/` from frontend builds |
| `start.sh`               | Backend entry point (API + Worker)       |
