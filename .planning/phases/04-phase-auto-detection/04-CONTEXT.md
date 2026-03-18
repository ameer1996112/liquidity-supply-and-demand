# Phase 4: Phase Auto-Detection - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Eliminate manual dropdown selections for determining Prop Firm challenge phases (Phase 1, Phase 2, Funded). The backend must aggressively auto-detect the phase directly from `server_name` and `account_name` keywords.
</domain>

<decisions>
## Implementation Decisions

### Phase Detection Logic
- Evaluate Server Name: If `LIVE` or `SERVER` (without `DEMO`) is present, it's strictly `funded`.
- Evaluate Account Name: Scan for substrings:
  - `FUNDED`, `MASTER`, `STEP 3`, `LIVE` -> `funded`
  - `PHASE 2`, `P2`, `STEP 2`, `VERIF` -> `phase_2`
  - `PHASE 1`, `P1`, `STEP 1`, `EVAL` -> `phase_1`
- Fallback: `phase_1`

### Backend Changes
- `PropFirmDetector`: Attach an `auto_detect_challenge_type(server_name, account_name)` function.
- `api_prop_firm_v1` and `worker.py`: Swap dict `get("challenge_type")` reads with the live auto-detect computation.

### Frontend Cleanup
- UI: Complete deletion of `ChallengeSelector.tsx`.
- Component: `PropFirmSection` should simply render the prop firm UI directly, assuming phase has always been inferred by the server.
</decisions>
