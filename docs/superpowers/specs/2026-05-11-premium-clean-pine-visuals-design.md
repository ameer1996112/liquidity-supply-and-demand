# Premium Clean Pine Strategy Visuals Design

Ticket: DEV-385
Date: 2026-05-11
Scope: Pine Script visuals for `scripts/pinescript/strategies/SND_Strategy.pine` and related SND libraries only.

## Goal

Make the S&D Pine strategy chart feel clean, premium, and execution-focused while preserving the existing strategy, webhook, risk, and zone detection behavior.

The default chart should help a trader read price action, active zones, and strategy state quickly. Detailed liquidity and debugging context should remain available, but only when intentionally enabled.

## Approved Direction

Use a **Premium Clean Strategy Default**:

- Show recent active zones only.
- Hide inactive and invalidated zones by default.
- Keep `Max Zones Displayed` configurable, interpreted per side.
- Use a lower premium default of 4 zones per side.
- Show zone labels as ID only, such as `D-18220` or `S-18225`.
- Place zone labels on the right edge of the zone.
- Extend active zones to the current bar plus a small padding, instead of a large fixed future projection.
- Keep fractal markers visible, but restyle them smaller and softer.
- Hide liquidity connectors, liquidity pivot lines, and target/inducement lines in Clean mode.
- Keep the results/performance table visible by default.
- Replace the full default Zone Inspector with a compact status panel in Clean mode.
- Keep the full Zone Inspector available in Analysis and Debug modes.

## Display Modes

Add a display mode setting:

- `Clean`: default execution view.
- `Analysis`: shows liquidity context and full inspector details for reviewing why zones exist.
- `Debug`: keeps developer-level diagnostic behavior available.

Where Pine input behavior makes derived toggles awkward, the implementation may preserve existing inputs for compatibility and route the actual display behavior through internal mode variables. The priority is that loading the strategy defaults to a clean chart.

## Default Settings

- `Display Mode`: `Clean`
- `Max Zones Displayed`: `4` per side
- `Zone Right Padding Bars`: `10`
- `Show Liquidity Connectors & Lines`: false in Clean, true in Analysis/Debug
- `Show Liquidity Pivot Lines`: false in Clean, true in Analysis/Debug
- `Show Fractal Triangles`: true, restyled as compact fractal markers
- `Zone Inspector Panel`: false in Clean, true in Analysis/Debug
- `Compact Status Panel`: true in Clean
- `Performance Table`: true
- `Zone Label Style`: ID-only by default
- `Show Grade on Zones`: false in Clean, optional in Analysis
- `Show AI Score on Labels`: false by default

## Visual System

The palette should be tuned for the user's current light gray TradingView theme.

Demand zones:

- Premium blue-teal family.
- Very subtle fill.
- Crisp but restrained border.

Supply zones:

- Muted rose/coral family.
- Very subtle fill.
- Crisp but restrained border.

Accuracy zones:

- Stay in the same demand/supply color family.
- Use a stronger border or small accent rather than switching to loud blue/purple fills.

Labels:

- ID only.
- Tiny or small enough to avoid covering candles.
- Positioned at the zone's right edge.
- Use a dark or matching premium label background with high-contrast text.

Analysis liquidity visuals:

- Thin amber for inducement.
- Thin muted violet/blue for target.
- No default connector clutter in Clean mode.

Fractal markers:

- Remain visible by default.
- Use smaller marker size.
- Use softer demand/supply accent colors that match the premium palette.
- Avoid the current loud red/green triangle feel.

## Implementation Boundaries

This work must not change:

- Strategy entry/exit behavior.
- Risk calculations.
- Webhook payloads.
- Backend-facing plots.
- Zone detection rules.
- Trade execution logic.

Expected primary file:

- `scripts/pinescript/strategies/SND_Strategy.pine`

Potential secondary files:

- `scripts/pinescript/libraries/SND_Core.pine`, only if a tiny visual field/helper is required on `Zone`.
- `scripts/pinescript/libraries/SND_Utils.pine`, likely no change.

## Object Lifecycle

The implementation must keep chart objects under control:

- Delete or hide inactive zone boxes and labels by default.
- Avoid leaking labels or lines when display mode changes.
- Update active zone right edges each bar to `bar_index + zone_right_padding_bars`.
- Keep liquidity lines deleted in Clean mode.
- Preserve existing cleanup behavior for pruned zones.

## Compact Status Panel

Clean mode should show a compact status panel instead of the full Zone Inspector.

Suggested contents:

- Active demand zones count.
- Active supply zones count.
- Most recent zone ID.
- AI filter state.
- Session or trading-hours state.

The compact panel should be small and visually aligned with the existing results table style without duplicating the full inspector's debugging rows.

## Testing And Review

Verification should include:

- Pine syntax/import compatibility.
- Confirm no changes to `strategy.entry`, `strategy.exit`, webhook payloads, or hidden backend plot meanings.
- Check inactive zones are not visible by default.
- Check recent active zone cap is per side.
- Check labels appear on the right edge and update as bars advance.
- Check Clean mode hides liquidity/target/connector lines.
- Check Analysis/Debug modes can show detailed visuals.
- Check fractal markers remain visible and less visually dominant.
- Check results table remains visible by default.

## Open Decisions

No unresolved product decisions remain for this first implementation pass.

Exact RGB/hex color values can be chosen during implementation, as long as they follow the approved light-theme premium palette direction.
