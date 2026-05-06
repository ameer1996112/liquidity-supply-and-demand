# EMA200 Learning Context Design

## Goal

Collect EMA200 context from the 5-minute Pine strategy without changing entry behavior. The script should continue to take the same trades it takes today, while every alert carries enough EMA200 context for backend analysis and future filter testing.

This is intentionally not a live filter yet. The first success criterion is data quality: we should be able to compare later whether long trades above EMA200 and short trades below EMA200 perform better.

## Current Context

`scripts/pinescript/strategies/SND_Strategy.pine` already computes:

- `feature_ema200 = ta.ema(close, 200)`
- `feature_trend = close > feature_ema200 ? 1 : 0`
- `trend_ema = ta.ema(close, ema_trend_length)` where `ema_trend_length` is currently hardcoded to `200`

The strategy already includes feature strings in alert messages, such as `F:trend`, `F:htf_trend`, `F:rvol`, and `F:ai_pine_score`. Those fields are context only and do not block entries.

## Proposed Behavior

Add EMA200 learning fields to both long and short alert feature strings:

- `F:ema200_value`: current EMA200 value.
- `F:ema200_zone_mid_distance_pips`: signed distance from zone midpoint to EMA200 in pips.
- `F:ema200_zone_side`: `1` when the zone midpoint is meaningfully above EMA200, `-1` when meaningfully below EMA200, `0` when near EMA200.
- `F:ema200_slope`: signed EMA200 slope over a short lookback.
- `F:ema200_aligned`: `1` when the zone side aligns with the trade direction, otherwise `0`.

The zone midpoint is:

```pine
zone_mid = (z.top + z.bottom) / 2.0
```

The signed distance is:

```pine
ema200_zone_mid_distance_pips = pip_size > 0 ? (zone_mid - feature_ema200) / pip_size : na
```

Alignment means:

- Long/demand alert: aligned when zone midpoint is above EMA200.
- Short/supply alert: aligned when zone midpoint is below EMA200.

## Neutral Buffer

Use an adaptive neutral buffer to reduce noisy labels around EMA200:

```pine
ema200_neutral_buffer = atr14 * 0.1
```

If `abs(zone_mid - feature_ema200) <= ema200_neutral_buffer`, set `F:ema200_zone_side=0`.

This is preferable to a fixed pip buffer because the strategy runs across forex, JPY, gold, indices, and other symbols with different price scales. It also fits the existing script, which already computes `atr14`.

## Slope

Add a small slope lookback constant, initially 10 bars on the 5-minute chart:

```pine
ema200_slope_lookback = 10
ema200_slope_pips = pip_size > 0 ? (feature_ema200 - feature_ema200[ema200_slope_lookback]) / pip_size : na
```

This records whether EMA200 was rising or falling recently. It should not block trades.

## Data Flow

1. Pine calculates EMA200 context on each bar.
2. When a long or short alert is built, Pine calculates zone midpoint relative to EMA200.
3. Pine appends the EMA200 fields to `ai_features`.
4. The existing backend alert ingestion receives the added fields as payload context.
5. Later analysis can compare trade outcomes by EMA side, distance, alignment, and slope.

## Non-Goals

- Do not block long or short entries based on EMA200.
- Do not add a user-facing Pine filter toggle yet.
- Do not change risk, stops, take profit, liquidity logic, or entry model selection.
- Do not copy the full TradingView EMA indicator. The strategy only needs `ta.ema(close, 200)`.

## Upgrade Path

After enough data is collected, evaluate:

- Long win rate and expectancy when `ema200_aligned=1` vs `0`.
- Short win rate and expectancy when `ema200_aligned=1` vs `0`.
- Performance when `ema200_zone_side=0`, meaning the zone is near EMA200.
- Whether positive/negative `ema200_slope` improves filtering.

If the evidence is strong, a later design can add a backend or Pine filter. The first filter candidate should be backend-side so we can keep Pine simple and preserve alert context.

## Testing

Add source-level contract coverage that verifies:

- EMA200 learning fields are present in Pine alert feature strings.
- The script does not contain an EMA200 entry-blocking reason.
- Existing Pine contract validation still passes.
- TradingView Pine check compiles with zero errors.

## Acceptance Criteria

- Existing strategy entries remain unchanged by EMA200 context.
- Long and short alert paths include the EMA200 learning fields.
- No new TradingView settings block is added for an EMA200 filter.
- Backend receives enough context to analyze EMA200 alignment later.
