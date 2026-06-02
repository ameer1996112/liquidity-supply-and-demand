# Liquidity Line Extension Design

Date: 2026-06-02

## Goal

Make `SND_Strategy.pine` zone-linked liquidity lines visually extend like the `Zones Liq S/D v23` raw liquidity lines:

- A liquidity line starts at the pivot candle.
- It extends right while price has not touched/crossed the level.
- It stops at the first wick that touches/crosses the level.

This is a visual extension rule only. It must not change zone detection, zone creation, trade entry rules, or strict liquidity sweep proof.

## Current Problem

The current zone-linked liquidity visuals are separate from the v23 raw-line lifecycle. They are recreated by `updateDemandLiquidityVisual()` and `updateSupplyLiquidityVisual()` using a computed line end. That means they can appear too short, extend differently, or stop based on sweep state instead of matching the first wick touch/cross behavior users expect from the v23 full-line liquidity display.

## Recommended Approach

Use a bounded visual helper inside the zone visual update path.

For a selected liquidity level:

1. Start from the liquidity pivot bar.
2. Scan forward from the next bar.
3. Find the first bar where the wick range touches/crosses the level:
   - `high >= level - tolerance`
   - `low <= level + tolerance`
4. Use that bar as the line `x2`.
5. If no wick has touched yet, use `bar_index` so the line keeps extending live.

Tolerance should match the v23 raw-line logic: `pip_size * 0.1`.

## Visual Rules

Demand zones:

- Liquidity low line uses `z.liqLowBar` and `z.liqLowPrice`.
- `x1 = z.liqLowBar`
- `y1 = y2 = z.liqLowPrice`
- `x2 = first wick-touch bar, or bar_index if untouched`

Supply zones:

- Liquidity high line uses `z.liqHighBar` and `z.liqHighPrice`.
- `x1 = z.liqHighBar`
- `y1 = y2 = z.liqHighPrice`
- `x2 = first wick-touch bar, or bar_index if untouched`

Target lines can remain on their current target-sweep visual behavior unless the user separately asks to make target lines match the same raw-line lifecycle.

## Non-Goals

- Do not turn on `plotLiq`.
- Do not draw global raw liquidity lines.
- Do not change `createZone()`.
- Do not change zone boundaries, ACC logic, duplicate-zone logic, or origin selection.
- Do not change strict sweep proof:
  - Demand sweep still requires a strict break below the stored liquidity low.
  - Supply sweep still requires a strict break above the stored liquidity high.

## Components

- `findLiquidityWickTouchBar(startBar, level)`: bounded forward scan that returns the first wick-touch bar.
- `liquidityVisualLineEnd(startBar, level)`: wraps the scan and falls back to `bar_index`.
- `updateDemandLiquidityVisual(idx)`: applies the helper to demand liquidity low line.
- `updateSupplyLiquidityVisual(idx)`: applies the helper to supply liquidity high line.

## Data Flow

1. Existing scanner stores zone-linked liquidity fields.
2. Visual update reads those fields.
3. Visual update computes the current line endpoint from candle wicks.
4. The line is redrawn with `x2` set to the first touch/cross bar or current bar.

## Error Handling

If `startBar` or `level` is `na`, no touch bar is returned and the wrapper safely falls back to `bar_index`. The scan is bounded by `liq_link_lookback_bars` and Pine history safety checks.

## Testing

Static tests should verify:

- Demand liquidity low line uses `liquidityVisualLineEnd(z.liqLowBar, z.liqLowPrice)`.
- Supply liquidity high line uses `liquidityVisualLineEnd(z.liqHighBar, z.liqHighPrice)`.
- The helper uses wick range touch/cross logic.
- `plotLiq` remains false.
- Scanner persistence and visual handle persistence still call `array.set(...)`.

