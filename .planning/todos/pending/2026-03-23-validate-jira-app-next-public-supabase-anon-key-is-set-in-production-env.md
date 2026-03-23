---
created: 2026-03-23T14:12:04.036Z
title: Validate Jira app NEXT_PUBLIC_SUPABASE_ANON_KEY is set in production env
area: tooling
files:
  - jira/.env.local
  - jira/src/lib/supabase.ts
---

## Problem

The Jira Next.js app (`/jira`) requires `NEXT_PUBLIC_SUPABASE_ANON_KEY` for client-side Supabase access. This was missing from `.env.local` — only `NEXT_PUBLIC_SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` were set. Client components call `getSupabase()` which checks for this key first; without it the app throws `Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_KEY env vars`.

`SUPABASE_SERVICE_ROLE_KEY` is only available server-side (no `NEXT_PUBLIC_` prefix), so client components always need the anon key explicitly.

## Solution

1. Get the **anon public** key from Supabase Dashboard → Project Settings → API
2. Add to `jira/.env.local`:
   ```
   NEXT_PUBLIC_SUPABASE_ANON_KEY="eyJ..."
   ```
3. Verify the app boots without the error
4. If deploying (Vercel/etc.), ensure this env var is set in the production environment dashboard too
