# Multi-Account Alerts Design

Date: 2026-04-16
Status: Approved for planning

## Summary

Upgrade Telegram and Discord alerts so shared destinations work cleanly for multiple accounts without requiring per-account routing. Every alert should clearly identify its source account at the top, present richer trading context, and keep a clean professional look that remains easy to scan under high alert volume.

The design keeps the current centralized notification architecture and focuses the upgrade on formatting, payload consistency, and graceful fallback behavior.

## Goals

- Make every alert unmistakably account-specific in shared Telegram and Discord feeds.
- Improve the visual hierarchy so alerts feel cleaner and more premium.
- Add more useful context without turning alerts into noisy blocks of text.
- Keep the implementation scoped to notification formatting and notification payload contracts.

## Non-Goals

- Adding separate Telegram chats or Discord channels per account.
- Reworking alert routing beyond the current global routing model.
- Changing trading logic, execution flow, or strategy behavior.

## Product Direction

The product direction is account-first, information-rich alerts with a clean professional style.

This means:

- The account identity is always the first visible element.
- The trade action and symbol are always the second visual priority.
- The most important risk details stay near the top.
- AI and timing context are available but treated as secondary information.
- Telegram and Discord preserve the same information order even if the platform rendering differs.

## Multi-Account Model

Multi-account support will be handled through consistent alert identity, not through separate routing.

All notification types should resolve account identity before rendering. Every alert begins with an account badge in the header:

`ACC: <account name>`

When additional identity is available, such as firm, broker, or execution mode, it appears immediately below the title in a compact status line.

Examples:

- `Paper | FTMO`
- `Live | MetaApi`

Fallback rule:

- If account name is unavailable, render `ACC: Unknown Account`.

This ensures that shared destinations never receive anonymous alerts.

## Alert Layout

### Signal Alerts

Signal alerts use a layered structure:

1. Account badge
2. Action title
3. Compact status line
4. Primary trade block
5. Risk block
6. Decision block
7. Context block
8. Optional image

Recommended content structure:

- Account badge: `ACC: <account name>`
- Title: `<BUY/SELL> Signal - <symbol>`
- Status line: execution mode plus optional firm or broker
- Primary trade block: entry, stop loss, take profit, R:R
- Risk block: lot size, risk in USD, zone type
- Decision block: AI decision, confidence, short reason summary
- Context block: session, bar time, signal id
- Optional image: chart image if available

Example:

```text
ACC: Funded Alpha

BUY Signal - XAUUSD
Paper | FTMO

Entry: 3345.2
SL: 3338.0
TP: 3359.8
R:R: 1:2.10

Lot Size: 0.40 lots
Risk: $120.00
Zone: Demand

AI: GO
Confidence: 84.0%
Reason: London momentum aligned with demand retest

Session: London/NY Overlap
Bar Time: 13:30 UTC
Signal: #1842
```

### Close Alerts

Close alerts follow the same account-first structure:

1. Account badge
2. Outcome title
3. Summary block
4. Context block

Recommended content:

- Account badge
- Title: `Trade Closed - <symbol> <side>`
- Summary block: outcome, PnL, entry, exit
- Extended details: commission, swap, R multiple when available

### Guard And Operational Alerts

Guard and operational alerts also use the same top account badge so non-trade notifications remain attributable in shared feeds.

Recommended content:

- Account badge
- Title: alert type or warning title
- Severity
- Short reason
- Actionable detail lines

## Visual Style

The style should be clean and professional rather than high-energy or overly decorative.

Design rules:

- Account badge is visually distinct and always first.
- Title is short and bold.
- Important values are grouped together near the top.
- Secondary context is placed lower in the alert.
- Emoji use is restrained and consistent.
- Color remains semantic:
  - Green for buy and win
  - Red for sell and loss
  - Yellow or orange for warning and guard
  - Blue for informational updates

The result should feel polished, readable, and trustworthy under high notification volume.

## Formatting Requirements

The formatter should treat the account badge as a first-class concept, not just another field mixed into the payload.

Recommended section ordering:

- Identity
- Trade
- Risk
- AI
- Context

Signal, close, and alert formatting should all follow that same hierarchy so the system feels coherent.

## Payload Contract Expectations

The notification formatting path should consistently receive enough information to render account-aware alerts.

Required display context:

- Account name, with fallback if missing
- Notification type
- Core title data such as side and symbol for trade alerts

Optional context:

- Firm or broker
- Execution mode
- AI decision details
- Session and bar time
- Zone details
- Chart image URL

Any producer that creates notification payloads should supply account identity whenever it is available.

## Error Handling And Fallbacks

The richer layout must degrade cleanly when data is partial.

Rules:

- Missing account name: show `ACC: Unknown Account`
- Missing AI result: omit AI section entirely
- Missing session, bar time, or zone: omit those rows
- Missing image: render the alert without an image
- Missing optional firm or broker: omit compact status details rather than inserting placeholders
- Close alerts continue to prefer actual broker truth data when available

This keeps the upgraded notification format robust across uneven payloads.

## Testing Requirements

Implementation should verify these cases:

1. Two different accounts sending signal alerts into the same shared destination render clearly different account badges.
2. Signal alerts still render cleanly when AI data is absent.
3. Signal alerts still render cleanly when account metadata is partial.
4. Close alerts preserve account identity and correct PnL presentation.
5. Guard and operational alerts include the account badge.
6. Telegram and Discord preserve the same information priority and section ordering.
7. Optional chart images appear when available and do not break alerts when absent.

## Recommended Implementation Scope

The implementation should stay focused on notification formatting and notification payload consistency.

Recommended scope:

- Introduce a dedicated account header or badge concept in notification formatting.
- Standardize section ordering for signal, close, and guard or operational alerts.
- Ensure account identity is passed consistently into all notification formatting paths.
- Preserve the existing global routing model for now.

## Risks

- If account identity is not consistently available upstream, some alerts may fall back to `Unknown Account` more often than desired.
- If the formatter becomes too field-heavy, alerts may become harder to scan, especially on Telegram.
- Platform-specific rendering differences may require light per-platform adjustments while preserving the same information hierarchy.

## Decision

Proceed with a formatting-first multi-account alert upgrade:

- shared destinations remain in place
- every alert becomes account-first
- the layout becomes more informative through structured sections
- the visual direction stays clean and professional
