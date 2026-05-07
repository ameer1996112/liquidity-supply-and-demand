# Latest Signals Trading Blotter Design

Date: 2026-05-07
Status: Approved for implementation planning
Ticket: DEV-306

## Goal

Redesign the Dashboard Latest Signals area so it reads like a professional trading blotter: dense, calm, fast to scan, and visually aligned with an institutional trading terminal. The current version feels cramped, overly decorated, mono-heavy, and visually uneven. The redesign should make signal comparison easier without changing trading logic.

## Visual Thesis

Calm institutional trading terminal: dark surface, thin dividers, restrained color, sharp numeric alignment, and no noisy badge treatment.

## Scope

In scope:

- Latest Signals table layout inside the Dashboard page.
- Column names, column sizing, row typography, cell hierarchy, and row state styling.
- The relationship between Latest Signals and the adjacent Live Log panel.
- Existing data shown in Latest Signals: time, symbol, account/strategy, side, entry, stop loss, take profit, P&L, risk, setup quality, AI confidence, council status, and signal status.
- Frontend tests for table labels and risk display.

Out of scope:

- Trading execution logic.
- Risk calculation behavior already persisted by backend.
- Journal page layout.
- New backend fields.
- Screenshot/setup evidence capture.

## Recommended Approach

Use a professional trading blotter layout.

Why:

- It matches the user workflow: scanning many signals, comparing risk and outcomes, and spotting open/rejected/closed states quickly.
- It avoids wasting vertical space on card-style rows.
- It creates a more serious operating surface than the current pill-heavy feed.

Rejected alternatives:

- Compact dashboard list: easier visually, but weaker for comparing many signals.
- Card-like signal feed: more polished per item, but too slow to scan with 80+ signals.

## Layout

Latest Signals should become the primary surface in its panel.

- The table should use the available panel width instead of leaving a large empty right area.
- If the Live Log is present in the same horizontal region, it should be narrower, collapsible, or moved below on constrained widths.
- The table should keep a stable minimum width for dense data, but should not look like it stops halfway across a wide screen.
- Rows should use consistent height, approximately 48-54px.
- Row separators should be thin and low contrast.
- Open/selected rows should use a subtle left rail and darker surface, not heavy glow.

## Columns

Use direct operator labels:

- Time
- Symbol
- Side
- Entry
- SL
- TP
- P&L
- Risk
- Setup
- AI
- Status

Column behavior:

- Time, Side, P&L, Risk, Setup, AI, and Status should have fixed widths.
- Symbol should be wide enough for symbol plus quiet account/strategy metadata.
- Entry, SL, and TP should be separate numeric columns or a clearly aligned grouped trade-plan region. Separate columns are preferred if horizontal room allows.
- Numeric values should align right and use tabular numerals.
- Text labels should align left.

## Typography

Use font roles deliberately:

- Sans font for headers, symbols, side labels, status labels, and metadata.
- Mono font only for prices, money, risk, time, and numeric scores.
- Avoid excessive uppercase tracking in row cells.
- Header labels should be small, calm, and legible.
- Symbols should be readable but not oversized.
- P&L and risk should be visually stronger than setup metadata, because they are operationally more important.

## Color And States

Color should communicate meaning, not decorate every cell.

- Buy/positive: existing green semantic token.
- Sell/loss/risk: existing red semantic token.
- Warning/pending: existing amber token.
- Closed/rejected/filtered states: muted surfaces and text.
- Keep side/status as compact text badges, but reduce border and fill strength.
- Avoid multiple badge styles in the same row unless they carry different operational meaning.

## Content Hierarchy

Each row should scan in this order:

1. What signal is this? Time, symbol, account/strategy.
2. What is the trade? Side, entry, SL, TP.
3. What happened or what is exposed? P&L and Risk.
4. Can I trust it? Setup, AI, council/status.

Account and strategy metadata should sit under Symbol as quiet secondary text, not as large pills.

Setup score should remain visible, but not dominate the row.

Council status may stay compact. If there is no council result, use a quiet dash instead of a decorative placeholder.

## Interaction

- Hover should gently raise row contrast.
- Sorting should stay available through headers with small arrows.
- Clicking a row should preserve the existing signal selection behavior.
- Stale broker status may dim the row, but should not make the data unreadable.
- No new animations are required; table readability is more important than motion.

## Data Flow

The redesign should consume the existing `TradingSignal`, `brokerMap`, and `councilMap` inputs from `SignalTable`.

The component should continue to use:

- `getPnl(signal)` for realized DB P&L when appropriate.
- Live broker P&L for open broker-backed positions.
- `calculateJournalRisk(signal)` and `formatJournalRisk(signal)` for risk display.
- Existing setup score fields.
- Existing status normalization helpers.

No backend or data contract changes are required for this visual pass.

## Error And Empty States

- Empty/filter states should keep the existing shared empty state.
- Missing entry, SL, TP, P&L, risk, setup, or AI values should display a quiet dash.
- Missing values should not create wide visual holes or oversized placeholder badges.

## Testing

Update or add targeted frontend tests for:

- New column labels.
- Risk still renders from signal risk fields.
- Strategy/account metadata still renders.
- Existing filtering tabs still work.
- Closed signals still prefer realized DB P&L over live broker P&L.

Run:

- `cd frontend && npx vitest run src/components/dashboard/SignalTable.test.tsx`
- `cd frontend && npm run build`

Known pre-existing unrelated frontend test failures can remain out of scope.

## Implementation Notes

Prefer a small component cleanup inside `SignalTable.tsx` over a broad redesign of the dashboard.

Possible internal units:

- `SIGNAL_GRID_STYLE` or equivalent column definition.
- `SignalBlotterHeader`
- `SignalBlotterRow`
- Small cell components only if they reduce repeated class clutter.

Do not introduce a new table library. The existing custom layout is sufficient, but it needs better composition, typography, and width behavior.

## Acceptance Criteria

- Latest Signals no longer looks cramped, toy-like, or half-width on the dashboard.
- Column labels are clear and professional.
- Font usage feels intentional: sans for identity/labels, mono for numbers.
- Entry, SL, TP, P&L, and risk are easy to compare across rows.
- Risk remains visible in Latest Signals.
- Existing filters, sorting, row selection, P&L source behavior, and status handling continue to work.
- Targeted SignalTable tests and frontend build pass.
