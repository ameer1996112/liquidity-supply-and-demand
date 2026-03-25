# Frontend Polish Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up the UI duplicates and spacing anomalies introduced by embedding the DashboardView into the Account Detail page.

**Architecture:** We will adjust the conditional rendering in `DashboardView.tsx` and streamline the metrics shown in `AccountDetailPage` so there is a clear visual hierarchy without redundancies.

**Tech Stack:** Next.js, Tailwind CSS

---

## Chunk 1: Clean up DashboardView Embedded Header
**Files:**
- Modify: `frontend/src/components/dashboard/DashboardView.tsx`

- [ ] **Step 1: Simplify `hideHeader` logic**
Wrap the entire `<header>` block in `{!hideHeader && ( ... )}` so that the `ModeBadge`, `SessionRing`, and `ConnectionPill` are completely omitted when embedded inside the Account Details page (which already provides account-level context).

## Chunk 2: Polish Account Details Page Header
**Files:**
- Modify: `frontend/src/app/accounts/[account_name]/page.tsx`

- [ ] **Step 1: Remove overlapping Today PnL from Account header**
The `DashboardView` already prominently features a "Net Daily" hero card. Remove the `Today PnL` inline display from `AccountDetailPage` to prevent duplication and screen clutter.

- [ ] **Step 2: Consolidate active states**
Ensure the Quick-Switch tabs on the main Dashboard and the section Tabs on the Account page have consistent, obvious active/inactive states. (They are currently quite robust, so only minor tweaks if any).

- [ ] **Step 3: Commit**
```bash
git add frontend/src/components/dashboard/DashboardView.tsx frontend/src/app/accounts/[account_name]/page.tsx
git commit -m "style(ui): clean up duplicated KPIs and connection pills for embedded dashboard"
```
