# EMA200 Learning Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add EMA200 learning fields to Pine alert context without changing trade entry behavior.

**Architecture:** Extend the existing Pine feature pipeline in `scripts/pinescript/strategies/SND_Strategy.pine`. Reuse the already-computed `feature_ema200`, `atr14`, and `pip_size`, derive zone midpoint EMA context directly inside the alert builders, then append the fields to both long and short `ai_features` strings. Keep this source-only and alert-only; do not add a Pine settings toggle or entry-blocking condition.

**Tech Stack:** Pine Script v6, TradingView MCP CLI, Python `pytest` source contract tests.

---

## File Structure

- Modify `tests/test_optimizer_param_contract.py`
  - Add a source-level regression test that verifies EMA200 learning fields are present and that no EMA200 blocking reason exists.
- Modify `scripts/pinescript/strategies/SND_Strategy.pine`
  - Add `EMA200_SLOPE_LOOKBACK`.
  - Derive EMA200 context inline in each alert builder to avoid TradingView function-consistency warnings.
  - Append EMA200 fields to long and short alert feature strings.
- No backend code change in this phase.
  - The current alert feature-string path already carries `F:*` context fields. Backend analysis can consume the new fields once alerts arrive.

---

### Task 1: Add Pine Contract Test For EMA200 Learning Fields

**Files:**
- Modify: `tests/test_optimizer_param_contract.py`
- Test: `tests/test_optimizer_param_contract.py`

- [ ] **Step 1: Write the failing test**

Add this test after `test_pine_strategy_sends_ai_and_grade_context_without_filtering`:

```python
def test_pine_strategy_sends_ema200_learning_context_without_filtering() -> None:
    source = DEFAULT_PINE_SOURCE.read_text()

    expected_context_fields = {
        "F:ema200_value=",
        "F:ema200_zone_mid_distance_pips=",
        "F:ema200_zone_side=",
        "F:ema200_slope=",
        "F:ema200_aligned=",
    }

    for field in expected_context_fields:
        assert source.count(field) == 2

    assert "EMA200_SLOPE_LOOKBACK = 10" in source
    assert "get_ema200_zone_context" not in source
    assert "EMA200 filter" not in source
    assert "Blocked by EMA200" not in source
    assert "ema200_zone_filter" not in source
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
PYTHONPATH=. pytest tests/test_optimizer_param_contract.py::test_pine_strategy_sends_ema200_learning_context_without_filtering -q
```

Expected: `FAIL` because `F:ema200_value=` and the other new fields are not in the Pine source yet.

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/test_optimizer_param_contract.py
git commit -m "test: cover EMA200 learning context fields"
```

---

### Task 2: Add EMA200 Lookback Constant In Pine

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`
- Test: `tests/test_optimizer_param_contract.py`

- [ ] **Step 1: Add the slope lookback constant**

Near the other constants at the top of `SND_Strategy.pine`, after `const int MAX_LIQ_SCAN_BARS = 500`, add:

```pine
const int EMA200_SLOPE_LOOKBACK = 10
```

- [ ] **Step 2: Keep EMA200 context source-only**

Do not add a helper function or Pine input toggle. The context calculation is repeated inside each alert builder so TradingView does not warn about a function being called only inside conditional trade branches.

- [ ] **Step 3: Run Pine contract tests**

Run:

```bash
PYTHONPATH=. pytest tests/test_optimizer_param_contract.py -q
```

Expected: the new EMA200 test still fails because the constant exists, but alert fields have not been appended yet.

---

### Task 3: Append EMA200 Fields To Long Alerts

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`
- Test: `tests/test_optimizer_param_contract.py`

- [ ] **Step 1: Add long-side EMA200 context variables**

In the long alert block, after:

```pine
[ai_pine_score_val, _ai_bd] = Core.calculate_ai_quality_score(z, true, feature_rvol, feature_session, feature_trend, feature_adx, feature_htf_trend, feature_rsi, (z.top - z.bottom) / atr14)
// Pine rule-based AI score — sent to backend as context feature, not a gate
ai_features += " | F:ai_pine_score=" + str.tostring(ai_pine_score_val, "#.0")
```

add:

```pine
float ema200_zone_mid = (z.top + z.bottom) / 2.0
float ema200_neutral_buffer = atr14 * 0.1
float ema200_zone_mid_distance_pips = pip_size > 0 ? (ema200_zone_mid - feature_ema200) / pip_size : na
int ema200_zone_side = math.abs(ema200_zone_mid - feature_ema200) <= ema200_neutral_buffer ? 0 : (ema200_zone_mid > feature_ema200 ? 1 : -1)
float ema200_slope = pip_size > 0 ? (feature_ema200 - feature_ema200[EMA200_SLOPE_LOOKBACK]) / pip_size : na
int ema200_aligned = ema200_zone_side == 1 ? 1 : 0
ai_features += " | F:ema200_value=" + str.tostring(feature_ema200, format.mintick)
ai_features += " | F:ema200_zone_mid_distance_pips=" + (not na(ema200_zone_mid_distance_pips) ? str.tostring(ema200_zone_mid_distance_pips, "#.##") : "N/A")
ai_features += " | F:ema200_zone_side=" + str.tostring(ema200_zone_side)
ai_features += " | F:ema200_slope=" + (not na(ema200_slope) ? str.tostring(ema200_slope, "#.##") : "N/A")
ai_features += " | F:ema200_aligned=" + str.tostring(ema200_aligned)
```

- [ ] **Step 2: Run the focused test**

Run:

```bash
PYTHONPATH=. pytest tests/test_optimizer_param_contract.py::test_pine_strategy_sends_ema200_learning_context_without_filtering -q
```

Expected: `FAIL`; each `F:ema200_*` field appears once, and the test expects exactly two appearances, one long and one short.

---

### Task 4: Append EMA200 Fields To Short Alerts

**Files:**
- Modify: `scripts/pinescript/strategies/SND_Strategy.pine`
- Test: `tests/test_optimizer_param_contract.py`

- [ ] **Step 1: Add short-side EMA200 context variables**

In the short alert block, after:

```pine
[ai_pine_score_val, _ai_bd] = Core.calculate_ai_quality_score(z, false, feature_rvol, feature_session, feature_trend, feature_adx, feature_htf_trend, feature_rsi, (z.top - z.bottom) / atr14)
// Pine rule-based AI score — sent to backend as context feature, not a gate
ai_features += " | F:ai_pine_score=" + str.tostring(ai_pine_score_val, "#.0")
```

add:

```pine
float ema200_zone_mid = (z.top + z.bottom) / 2.0
float ema200_neutral_buffer = atr14 * 0.1
float ema200_zone_mid_distance_pips = pip_size > 0 ? (ema200_zone_mid - feature_ema200) / pip_size : na
int ema200_zone_side = math.abs(ema200_zone_mid - feature_ema200) <= ema200_neutral_buffer ? 0 : (ema200_zone_mid > feature_ema200 ? 1 : -1)
float ema200_slope = pip_size > 0 ? (feature_ema200 - feature_ema200[EMA200_SLOPE_LOOKBACK]) / pip_size : na
int ema200_aligned = ema200_zone_side == -1 ? 1 : 0
ai_features += " | F:ema200_value=" + str.tostring(feature_ema200, format.mintick)
ai_features += " | F:ema200_zone_mid_distance_pips=" + (not na(ema200_zone_mid_distance_pips) ? str.tostring(ema200_zone_mid_distance_pips, "#.##") : "N/A")
ai_features += " | F:ema200_zone_side=" + str.tostring(ema200_zone_side)
ai_features += " | F:ema200_slope=" + (not na(ema200_slope) ? str.tostring(ema200_slope, "#.##") : "N/A")
ai_features += " | F:ema200_aligned=" + str.tostring(ema200_aligned)
```

- [ ] **Step 2: Run the focused test**

Run:

```bash
PYTHONPATH=. pytest tests/test_optimizer_param_contract.py::test_pine_strategy_sends_ema200_learning_context_without_filtering -q
```

Expected: `PASS`; each field appears exactly twice.

- [ ] **Step 3: Run the full contract file**

Run:

```bash
PYTHONPATH=. pytest tests/test_optimizer_param_contract.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit Pine and test changes**

```bash
git add scripts/pinescript/strategies/SND_Strategy.pine tests/test_optimizer_param_contract.py
git commit -m "feat: add EMA200 learning context to Pine alerts"
```

---

### Task 5: Verify In TradingView MCP

**Files:**
- Verify: `scripts/pinescript/strategies/SND_Strategy.pine`
- No source modifications in this task unless compile fails.

- [ ] **Step 1: Run server-side Pine check**

Run:

```bash
node mcp/tradingview-mcp/src/cli/index.js pine check --file scripts/pinescript/strategies/SND_Strategy.pine
```

Expected:

```json
{
  "success": true,
  "compiled": true,
  "error_count": 0
}
```

Warnings with `severity: 4` are acceptable if they match the existing consistency/shadowing warnings.

- [ ] **Step 2: Push source to the open TradingView editor**

Run:

```bash
node mcp/tradingview-mcp/src/cli/index.js pine set --file scripts/pinescript/strategies/SND_Strategy.pine
```

Expected:

```json
{
  "success": true,
  "lines_set": 5035
}
```

The exact `lines_set` may differ slightly after edits.

- [ ] **Step 3: Compile in the open TradingView editor**

Run:

```bash
node mcp/tradingview-mcp/src/cli/index.js pine compile
```

Expected: no severity-1/2/3 compile errors. The command may report existing severity-4 warnings.

- [ ] **Step 4: Verify live editor source contains the fields**

Run:

```bash
node -e 'const {spawnSync}=require("child_process"); const r=spawnSync("node",["mcp/tradingview-mcp/src/cli/index.js","pine","get"],{encoding:"utf8",maxBuffer:50*1024*1024}); const s=(r.stdout||"")+(r.stderr||""); const terms=["F:ema200_value=","F:ema200_zone_mid_distance_pips=","F:ema200_zone_side=","F:ema200_slope=","F:ema200_aligned="]; const missing=terms.filter(t=>!s.includes(t)); console.log(JSON.stringify({exit:r.status, missing}, null, 2)); process.exit(missing.length?1:0)'
```

Expected:

```json
{
  "exit": 0,
  "missing": []
}
```

- [ ] **Step 5: Save the TradingView editor**

Run:

```bash
node mcp/tradingview-mcp/src/cli/index.js pine save
```

Expected:

```json
{
  "success": true,
  "action": "Ctrl+S_dispatched"
}
```

---

### Task 6: Final Verification And Handoff

**Files:**
- Verify: `scripts/pinescript/strategies/SND_Strategy.pine`
- Verify: `tests/test_optimizer_param_contract.py`
- Verify: `docs/superpowers/plans/2026-05-05-ema200-learning-context.md`

- [ ] **Step 1: Run whitespace/diff hygiene**

Run:

```bash
git diff --check -- scripts/pinescript/strategies/SND_Strategy.pine tests/test_optimizer_param_contract.py docs/superpowers/plans/2026-05-05-ema200-learning-context.md
```

Expected: no output and exit code `0`.

- [ ] **Step 2: Run final contract tests**

Run:

```bash
PYTHONPATH=. pytest tests/test_optimizer_param_contract.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Confirm no EMA200 blocking text exists**

Run:

```bash
rg -n "EMA200 filter|Blocked by EMA200|ema200_zone_filter" scripts/pinescript/strategies/SND_Strategy.pine
```

Expected: no matches and exit code `1`.

- [ ] **Step 4: Report results**

In the final handoff, include:

- The fields added to alert payload context.
- Confirmation that no entry blocking was added.
- `pytest` result.
- TradingView MCP compile/check result.
