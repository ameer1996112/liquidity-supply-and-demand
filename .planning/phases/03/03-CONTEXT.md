# Phase 3: Frontend Optimization & Analytics - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

## Phase Boundary
Implement dynamic Prop Firm phase detection and resolve production CORS and JavaScript blockages affecting the Accounts page.
- CORS policy updates in FastAPI (`src/api.py`).
- Frontend hardening (`l.map is not a function`) in React (`frontend/`).
- Auto-detect Prop Firm phase during MetaAPI sync based on server/platform strings.
