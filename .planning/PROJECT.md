# Trading System — Project Context

**Stack:** Next.js 15 (frontend, `/frontend`), FastAPI (backend, `/src`), Supabase, Redis, MetaAPI

## Current State (Post v1.0)

The trading terminal ships with a premium dark UI: MobileNav, animated signal feed, risk gauges, prop firm challenge tracking, and fully responsive layout. Production build passes.

The Jira/tickets feature lives at `/frontend/src/app/tickets/page.tsx` — a single page with a ticket list fed by `GET /api/tickets` and a create form posting to Jira via `src/api_tickets.py`.

## Current Milestone: v1.1 — AI-Driven Jira Upgrade

**Goal:** Transform the tickets page into a premium, AI-driven project management board with Kanban view, rich ticket details, sprint tracking, and an AI agent activity timeline.

**Target features:**
- Kanban board — Todo / In Progress / Done drag-and-drop columns
- Rich ticket detail panel — description, labels, status history
- Sprint view — active sprint panel + progress indicator
- AI changelog timeline — rich visual feed of agent activity per ticket
- Premium UI — dark glassmorphism matching the trading terminal
- AI-driven — auto-suggest type/priority on creation, AI activity surfaced everywhere

## System Capabilities (Built)

- Jira REST proxy: `POST /api/tickets`, `GET /api/tickets`, `POST /api/tickets/{id}/ai-update`
- AI update schema: agent, old_status, new_status, summary, timestamp
- Design system: glass-panel, glow-card, page-title, animate-fade-in-up, stagger-children
- MobileNav, StatCard, PanelEmptyState — all premium components ready to reuse
