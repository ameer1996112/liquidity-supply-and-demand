# TradingView Strategy Validation Harness Design

## Goal

Build a validation harness that uses TradingView as live evidence for the S&D strategy, then converts confirmed mismatches into repeatable regression artifacts.

The first milestone focuses on validating zone detection and invalidation for `SND_Strategy.pine` against a known reference indicator, manual examples, and saved fixtures. This should reduce the current trial-and-error loop where a Pine change fixes one chart but breaks another.

## Context

The project already embeds `mcp/tradingview-mcp`, a Node.js Chrome DevTools Protocol bridge for TradingView Desktop. It can set symbols and timeframes, control replay, read Pine boxes/labels/tables, capture screenshots, and run Pine compile checks.

Recent S&D work exposed a recurring problem: visual chart behavior is the source of truth, but regressions are currently found manually through screenshots. Static Pine tests help protect code shape, but they cannot prove that TradingView drew the right zone at the right price and time.

Current external tool candidates are useful as complements, not replacements:

- Chrome DevTools MCP can improve browser-level inspection, performance traces, screenshots, and page targeting.
- PineScript syntax checker MCPs can duplicate or complement server-side Pine compile checks.
- The existing TradingView MCP remains the only tool in this workspace that knows how to read TradingView-specific boxes, labels, replay state, and Pine editor state.

## Selected Approach

Use a hybrid validation harness.

TradingView remains the live evidence source. The harness captures real chart state through `tradingview-mcp`, compares the user's strategy zones with a reference script or manual expectations, and saves both a human report and a machine-readable fixture.

Confirmed important mismatches become long-lived fixtures. Later runs should be able to verify the same scenario without relying entirely on visual memory.

## Scope

In scope for the first milestone:

- Validate zone boxes and labels on TradingView charts.
- Compare `S&D Pro` zones against `Zones Liq S/D v23 - Myrtille` where both scripts are visible.
- Support manual expected zones for screenshots or replay examples.
- Produce reports, screenshots, and JSON artifacts.
- Add comparator and fixture tests outside TradingView.
- Add an MCP smoke test that proves the harness can connect and capture evidence.

Out of scope for the first milestone:

- Replacing `mcp/tradingview-mcp`.
- Fully automating TradingView login, subscription state, or account settings.
- Placing trades or changing broker execution settings.
- Refactoring the Pine strategy itself.
- Making live TradingView E2E the only validation gate.

## Architecture

### Scenario Runner

Loads a scenario that describes:

- symbol, exchange, and timeframe
- replay or visible-range target
- expected scripts
- comparison mode
- tolerances for price and time

It drives TradingView through the current MCP CLI/tools. It should select the correct target tab when `TV_TARGET_ID` is available and stop if the chart state cannot be trusted.

### Zone Extractor

Reads raw boxes and labels from TradingView and normalizes them into zone records:

```json
{
  "source": "S&D Pro",
  "side": "supply",
  "top": 4496.0,
  "bottom": 4492.0,
  "leftTime": "2026-05-20T03:45:00+03:00",
  "rightTime": "2026-05-20T13:00:00+03:00",
  "label": "S-19396"
}
```

Attribution should prefer script/study metadata when available. If attribution is ambiguous, the run is inconclusive.

### Comparator

Matches zones by side, price range, and approximate time. It classifies differences as:

- missing expected zone
- extra unexpected zone
- wrong zone high
- wrong zone low
- wrong side
- invalid zone still visible
- inconclusive attribution or chart state

The comparator should not depend on TradingView. It should run against saved JSON fixtures.

### Evidence Writer

For every validation run, write:

- `artifacts/tradingview-validation/<run-id>/report.md`
- `artifacts/tradingview-validation/<run-id>/zones.json`
- `artifacts/tradingview-validation/<run-id>/screenshot.png`
- optional fixture under `scripts/pinescript/validation/fixtures/`

The report should be readable by the user and include the scenario, screenshot path, extracted zones, mismatch summary, and suggested regression follow-up.

## Data Flow

1. Load scenario configuration.
2. Connect to the selected TradingView target.
3. Set symbol, timeframe, replay position, and visible range.
4. Verify that required scripts are visible.
5. Capture screenshot and raw chart objects.
6. Normalize boxes and labels into zone records.
7. Compare user zones against reference/manual expectations.
8. Write report and JSON artifacts.
9. Optionally save a fixture for repeatable comparator tests.

## Error Handling

The harness should fail loudly when state is ambiguous.

- If multiple TradingView tabs are open and no target can be selected, stop with a clear error.
- If required scripts are missing, report the missing script names.
- If zones cannot be attributed to a script, mark the run `inconclusive`.
- If replay cannot move to the target point, save current evidence and mark the scenario blocked.
- If no zones are found, distinguish between no zones expected, script not loaded, extraction failure, and actual mismatch.
- If TradingView MCP live calls fail, keep partial artifacts for debugging.

## Testing

### Unit Tests

Cover:

- box/label normalization
- source attribution
- price/time tolerance matching
- mismatch classification
- report generation

### Fixture Tests

Use saved `zones.json` examples to prove comparator behavior without opening TradingView.

### MCP Smoke Test

Optional local smoke test:

- connect to TradingView
- select the target chart
- read boxes and labels
- capture screenshot
- write a minimal evidence bundle

This test is not a required CI gate because live TradingView UI state is flaky.

### Manual Scenarios

Seed scenarios from known problem cases:

- XAUUSD 5m normal-zone boundaries
- XPTUSD 5m normal-zone boundaries
- NAS100 5m normal-zone boundaries
- GBPJPY 5m invalid zones after wick/close breaches

## Tool Upgrade Roadmap

### Milestone 1: Strategy Validation Harness

Build the harness around the existing TradingView MCP and current scripts. This is the highest-value first step because it protects strategy behavior before broader tooling changes.

### Milestone 2: TradingView MCP Hardening

Add or upstream practical fixes discovered by the harness:

- explicit target selection
- better script/source attribution
- more reliable box/label extraction
- stable screenshot paths
- clearer live-state errors

### Milestone 3: Companion Tools

Evaluate adding:

- Chrome DevTools MCP for browser-level debugging and screenshots.
- Pine syntax/docs MCPs for additional compile or documentation lookup.

Companion tools should complement `tradingview-mcp`; they should not replace it unless they can read TradingView-specific chart objects and Pine outputs.

## Success Criteria

The first milestone is successful when:

- A scenario can capture chart evidence for one symbol/timeframe.
- The harness can identify at least one missing/wrong/extra zone from saved data.
- A human-readable report and machine-readable fixture are written.
- Comparator tests pass without TradingView open.
- The design allows new scenarios to be added without editing comparison logic.

## References

- Current embedded MCP: `mcp/tradingview-mcp`
- Chrome DevTools MCP overview: https://developer.chrome.com/blog/chrome-devtools-mcp
- Chrome DevTools MCP repository and setup notes: https://github.com/ChromeDevTools/chrome-devtools-mcp
- Chrome DevTools for agents: https://developer.chrome.com/docs/devtools/agents
- PineScript syntax checker MCP listing: https://playbooks.com/mcp/erevus-cn/pinescript_syntax_checker
