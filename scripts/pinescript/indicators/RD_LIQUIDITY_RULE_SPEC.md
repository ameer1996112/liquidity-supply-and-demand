# RD_LIQUIDITY_RULE_SPEC

Scope: `SND_Raw_RD_Forex.pine` must detect RD Forex supply/demand zones, the linked liquidity, and the post-liquidity target with the same practical behavior as the `Zones Liq S/D v23 - Myrtille` reference indicator.

## Sources Used

Video evidence:

- `E5EBc1MtiXQ` - "The Trading Strategy That Changed My Life - RD Concepts Full Guide"
- `kxh_3__oAqg` - "FULL course for LIQUIDITY supply and demand best NEW trading strategy 2026"
- `LCydpj3CaHo` - "Liquidity Supply & Demand Scalping Strategy FULL COURSE (Updated 2025)"
- `zglv2r9xXnE` - "Liquidity supply & demand live trading - 5m timeframe"

Reference behavior:

- TradingView MCP snapshot on `OANDA:XPTUSD`, 5m, with studies `SND Raw RD Forex` and `Zones Liq S/D v23 - Myrtille`.
- Reference visible/near-current zones: `1714.922-1713.829`, `1707.888-1700.834`, `1707.828-1703.904`, `1689.565-1683.406`, `1679.001-1675.324`, `1666.826-1664.491`, `1645.220-1637.174`.
- Reference nearby linked lines: `1712.992`, `1710.766`, `1697.612`, `1681.969`.

## Zone Rules

1. Use only new/untapped supply and demand zones.
   - Source: `E5EBc1MtiXQ` 03:54-04:28; `kxh_3__oAqg` 03:43-04:16.
   - A zone is untapped when no candle after the formation/departure has returned to the zone before the candidate entry/touch.
   - Same-color candles that are part of the departure leg do not count as retaps, but an opposite-color candle wick back into the zone does count.

2. Standard zone origin is the opposite-color candle before the move.
   - Source: `E5EBc1MtiXQ` 04:38-04:53.
   - Demand origin: last bearish candle before the bullish departure.
   - Supply origin: last bullish candle before the bearish departure.

3. Accuracy-zone bounds override full-wick bounds when the origin candle overshoots the first departure candle.
   - Source: `E5EBc1MtiXQ` 05:02-06:34; `kxh_3__oAqg` 07:46-12:33; `LCydpj3CaHo` 13:35-14:19.
   - Demand: if any part of the bearish origin candle goes above the first bullish departure candle, use the origin body high as zone high, while keeping the lowest relevant wick as zone low.
   - Supply: if any part of the bullish origin candle goes below the first bearish departure candle, use the origin body low as zone low, while keeping the highest relevant wick as zone high.
   - Futures/metals should not draw separate ACC-colored boxes; demand stays teal and supply stays red. Accuracy bounds are still a bounds choice, not a separate visual class.

4. A close back inside the zone invalidates the zone.
   - Source: `kxh_3__oAqg` 03:43-03:47; `LCydpj3CaHo` 13:43-13:52; live commentary evidence around 15:56-16:14.
   - This is evaluated after the departure has occurred, excluding departure candles allowed by the untapped rule.

## Liquidity Rules

5. A zone without valid liquidity in front of it is invalid for display/trading.
   - Source: `E5EBc1MtiXQ` 02:45-03:37 and 08:12-08:38; `kxh_3__oAqg` 03:43-03:47.
   - Demand requires sell-side liquidity below/near the later approach to the demand zone.
   - Supply requires buy-side liquidity above/near the later approach to the supply zone.

6. Liquidity must take out its own high/low before the zone is valid.
   - Source: `kxh_3__oAqg` 05:07-07:25.
   - Demand: the liquidity leg forms a low, then price must break the high that belongs to that liquidity leg before returning to the demand zone.
   - Supply: the liquidity leg forms a high, then price must break the low that belongs to that liquidity leg before returning to the supply zone.
   - If this own-high/own-low break is missing, the zone remains invalid even if price reacts from the zone.

7. Prefer at least two opposite-direction candles for valid liquidity.
   - Source: `kxh_3__oAqg` 23:11-24:27; `LCydpj3CaHo` 15:00-17:24.
   - Demand liquidity is normally two or more bearish candles forming a proper low.
   - Supply liquidity is normally two or more bullish candles forming a proper high.
   - One-candle liquidity is lower quality and should be rejected by default on 5m unless a debug/experimental setting explicitly allows it.

8. Internal liquidity must be stricter.
   - Source: `zglv2r9xXnE` 04:38-05:10.
   - If the liquidity cannot reasonably take the major swing high/low, an internal liquidity candidate needs a stronger proof: break its own level twice and return to the zone before being accepted.

9. Liquidity must be close enough to influence the zone.
   - Source: `E5EBc1MtiXQ` 08:40-10:28.
   - Liquidity far from the zone is invalid because it no longer affects the zone; it becomes ordinary supply/demand behavior.
   - The videos do not provide a universal numeric value. Implementation should use a volatility-relative distance cap and expose it as an input for tuning.

## Visual And Lifecycle Rules

10. Demand and supply use the same colors across standard and accuracy bounds.
    - User requirement: futures do not have ACC zones and should not show extra ACC colors.
    - Demand boxes are teal, supply boxes are red. Reference may show orange/yellow for its internal lifecycle state; this script should keep side colors consistent.

11. Linked liquidity/target lines must be visible when enabled.
    - Reference behavior: nearby horizontal lines were exposed by TradingView MCP at `1712.992`, `1710.766`, `1697.612`, `1681.969` in the active XPTUSD snapshot.
    - Lines should be tied to the zone's accepted RD liquidity proof, not generic pivots.

12. Invalid zones should not clutter the chart.
    - Zones rejected by no liquidity, far liquidity, one-candle liquidity, missing own-level break, retap before valid sweep, or close-inside invalidation should be hidden unless debug mode explicitly requests rejected diagnostics.

## Implementation Implications

- Replace generic pivot-only liquidity linking with a stateful RD liquidity scan.
- Keep existing zone origin/departure detection where it satisfies rules 1-4, but bounds must be adjusted by the accuracy-zone rule without creating separate ACC visuals.
- A zone can be drawn only after it has an accepted liquidity side and a target side:
  - Demand: accepted liquidity low plus the high that liquidity must break.
  - Supply: accepted liquidity high plus the low that liquidity must break.
- Liquidity distance should default to an ATR-relative cap, with a symbol/tick-safe fallback.
- Debug mode should expose candidate rejection reasons using rule names, not silently skip.

## Current Patch Targets

- Keep `plotLiq` defaulted on so linked liquidity/target levels are visible during comparison.
- Do not route liquidity through generic pivot-only helpers; a pivot is only a candidate after RD candle-structure, unswept, and distance checks pass.
- Keep ACC concepts as internal bounds logic only; futures/metals must not show separate ACC colors.
- Enforce two-candle liquidity as the default minimum.
- Enforce a volatility-relative liquidity distance cap sourced from the RD "too far" rule.
