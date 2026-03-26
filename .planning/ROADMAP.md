# Roadmap: Trade Evaluation Rubric

## Milestones

- ✅ **v1.2 UI Cleanup** — Phase 4 (shipped 2026-03-25)
- 🚧 **v1.3 Trade Evaluation Rubric** — Phases 5–6 (in progress)

---

## v1.3 Trade Evaluation Rubric

**Goal:** Implement a four-dimension grading rubric that ensures the LLM council only fires on genuinely high-conviction setups. Phase 1 adds hard pre-filter vetoes and EV-adjusted scoring. Phase 2 implements the full rubric engine with composite score gating.

---

### Phase 5: Pre-filter Hardening & EV Score
**Goal:** Add 4 hard vetoes to the worker.py pre-filter stack, change the output score to EV-adjusted, and wire premium_discount and kill_zone from Pine webhook payloads into the evaluation pipeline.
**Requirements:** RUBRIC-01, RUBRIC-02, RUBRIC-03
**Plans:** 1/1 plans complete

Plans:
- [x] 05-01-PLAN.md — Settings + news medium filter + payload parsing + EV score formula + tests

**Success Criteria:**
1. Signals arriving during Sydney session (session=0) are blocked before reaching any ML or LLM stage.
2. Signals arriving on Friday after 14:00 UTC are blocked.
3. Signals arriving within 30 minutes of high-impact news for the traded currency pair are blocked (using NewsFilter singleton from src/core/news_filter.py).
4. Signals arriving when account daily drawdown > 80% are blocked per-account (not globally) — Supabase unavailability triggers fail-closed + Discord alert.
5. The evaluation pipeline outputs an ev_score (informational) alongside composite_score (decisional).
6. Tests pass: tests/test_pine_filters_phase1.py (4 tests covering the 4 vetoes).

---

### Phase 6: Four-Dimension Rubric Engine
**Goal:** Implement rubric_engine.py with all four weighted dimensions (Liquidity Context 35%, Zone Quality 25%, Structural Alignment 25%, Account & Environment 15%). Wire composite score (≥70) as the LLM council pre-gate. Add RUBRIC_ENGINE_ENABLED feature flag for instant rollback.
**Requirements:** RUBRIC-04, RUBRIC-05, RUBRIC-06

**Success Criteria:**
1. rubric_engine.score_trade(payload, account_state) returns RubricResult with composite_score, ev_score, dimension_scores, vetoed_by, proceed, gate_status.
2. composite_score < 70 → council does not fire; composite_score 70–77 → council fires in shadow mode; composite_score ≥ 78 → council fires and can execute.
3. All hard vetoes (sweep_candle_close=True, Sydney session, drawdown > 80%, news < 30min) score 0 and block immediately.
4. JSONB rubric_score column written to signals table via migration.
5. RUBRIC_COUNCIL_GATE and RUBRIC_EXEC_GATE configurable via env vars (default 70/78).
6. Tests pass: tests/test_rubric_engine.py (≥20 unit tests covering all 4 dimensions, hard vetoes, composite formula, EV formula).

---

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 5. Pre-filter Hardening & EV Score | v1.3 | 1/1 | Complete   | 2026-03-26 |
| 6. Four-Dimension Rubric Engine | v1.3 | 0/? | Not started | - |
