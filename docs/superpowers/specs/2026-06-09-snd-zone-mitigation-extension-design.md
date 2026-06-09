# SND Zone Mitigation Extension Design

Date: 2026-06-09

## Goal

Make `SND_Raw_RD_Forex.pine` stop each zone's visual extension at the first candle after the origin candle whose wick touches the zone.

This is a display lifecycle change only. It must not change zone detection, zone bounds, model classification, liquidity linking, sweep state, invalidation state, alerts, or strategy behavior.

## Approved Rule

For every zone:

1. Start scanning at `originBar + 1`.
2. Ignore the origin candle itself.
3. Find the first candle where the candle range overlaps the zone:
   - `high >= zone.bottom`
   - `low <= zone.top`
4. Use that candle's bar index as the zone's display right edge.
5. If no later candle overlaps the zone, keep the existing projection behavior.

The same overlap rule applies to demand and supply zones.

## Scope

In scope:

- Update the display right-edge lifecycle helper used by `zoneRightBar()`.
- Keep the behavior deterministic from historical bars, not dependent only on live mutation state.
- Add or update static tests that lock the origin-scan wick-stop rule.
- Run the Pine compile gate:
  `node mcp/tradingview-mcp/src/cli/index.js pine check --file scripts/pinescript/indicators/SND_Raw_RD_Forex.pine`
- Reload the indicator in TradingView and inspect live box coordinates for the XAUUSD 5m case.

Out of scope:

- Zone origin detection.
- Zone top/bottom calculations.
- Standard versus ACC classification.
- Liquidity line selection.
- Liquidity sweep detection.
- Invalidation state.
- Alerts, entries, exits, tables, strategy behavior, filters, or risk logic.

## Expected Verification

The implementation is accepted only if:

- Static lifecycle tests pass.
- Existing focused static tests for mitigation, liquidity linking, and projection hours still pass.
- Pine compile passes with zero errors.
- On the XAUUSD 5m visual case, SND zone boxes stop at the first wick-touch candle after origin instead of extending past mitigation.
- Protected indicator parity is checked visually and, where possible, by comparing box right-edge coordinates.

## Risk

The main risk is stopping zones too early if the protected reference intentionally ignores some early wick touches. If that appears in a golden case, the rule must be revised explicitly rather than adding hidden exceptions.
