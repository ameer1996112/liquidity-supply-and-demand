# DEV-126 Signal Setup Evidence Delivery Design

## Summary

Extend the current setup-evidence flow so the same focused setup screenshot and structured chart context are reused everywhere a signal is surfaced:

- Discord open alerts
- Telegram open alerts
- optional close-alert reuse of the same opening screenshot
- the journal table and expanded journal detail view

The system should capture setup evidence once at signal/open time, persist it with the signal/trade record, and render it consistently across delivery channels and the journal UI.

## Goals

- Reuse one stored setup-evidence bundle instead of recapturing per destination.
- Append the focused setup screenshot below signal details in Discord and Telegram open alerts.
- Make the journal table aware of setup evidence without making the main table visually noisy.
- Show the full setup evidence inside the expanded journal row:
  - focused screenshot
  - focus zone summary
  - Pine snapshot / labels
- Keep close alerts simple in v1 by reusing the opening screenshot instead of capturing a second close-time chart image.

## Non-Goals

- No second screenshot capture at trade close in this slice.
- No automatic Discord/Telegram delivery for every later journal action.
- No redesign of the full journal page layout.
- No inline large thumbnails in the main journal table.
- No new always-on media storage system beyond what is needed to persist the existing provider artifact reference.

## Existing Context

The system already has:

- a local chart provider that returns `setup_evidence`
- a focused setup screenshot URL inside the provider payload
- an AI Operating Layer UI panel that can render setup evidence

The missing pieces are downstream reuse:

- open/close notifications still treat screenshots as generic optional images
- the journal table has no concept of setup evidence
- expanded journal rows do not show the stored setup screenshot or evidence summary

## Product Decision

### Source of truth

Use one stored `setup_evidence` bundle linked to the signal/trade record.

That bundle should be captured once at signal/open time and reused by:

- notification delivery
- journal UI
- future manual share flows

### Notification presentation

For signal-open notifications:

- keep the normal structured trade details first
- append the setup screenshot below those details

For signal-close notifications:

- do not capture a new screenshot in v1
- optionally reuse the same stored opening screenshot if available

This preserves readability while giving visual evidence directly under the signal data.

### Journal presentation

In the main table:

- add a compact `Setup` column
- use a tiny icon-button style affordance instead of a large thumbnail
- indicate whether setup evidence is available without increasing row height significantly

In the expanded row:

- render the focused setup screenshot
- render the focus zone summary
- render a short Pine snapshot / labels summary

This keeps the table scannable while making the detail view much more useful.

## Proposed Data Shape

Persist a setup-evidence object on the signal/trade payload with a shape compatible with the provider output.

Recommended structure:

```json
{
  "setup_evidence": {
    "status": "ok",
    "focus_zone": {
      "type": "horizontal_level",
      "label": "Institutional Liquidity Protocol [Pro]",
      "price": 0.72,
      "study": "Institutional Liquidity Protocol [Pro]"
    },
    "focus_image": {
      "path": "/abs/path/to/file.png",
      "region": "chart",
      "url": "https://.../provider-artifacts/file.png"
    },
    "pine_snapshot": {
      "zone_count": 1,
      "label_count": 42,
      "top_labels": [
        "LONG E: 0.71408 SL: 0.71311 TP: 0.71651"
      ]
    },
    "reason": ""
  }
}
```

The critical contract requirement is that persisted setup evidence must include:

- `status`
- `focus_zone`
- `focus_image.url` when an image is available

The Pine snapshot may be a compact derivative of existing labels/zones instead of a full duplicate dump.

## Notification Design

### Discord open alert

Use the existing notification card structure and attach setup evidence like this:

- keep the current signal fields and sections
- keep signal title, symbol, side, entry/SL/TP, R:R, account, AI, and zone context
- set the embed image to the stored `setup_evidence.focus_image.url`

Behavior:

- if setup evidence exists and has a usable URL, the screenshot appears below the embed fields
- if setup evidence is missing or degraded, the alert still sends normally without an image

### Telegram open alert

Preferred v1 behavior:

- send the setup screenshot as the primary photo message
- include the signal details in the caption when the caption stays within Telegram limits
- if the text is too long, send the current text message and then the photo immediately after

This still satisfies the product goal of showing the data first and the screenshot below it, while staying within Telegram’s delivery constraints.

### Close alert reuse

When a close notification is sent:

- if opening-time setup evidence exists, it may be reused as a reference image
- no close-time recapture happens in this slice

This keeps the close workflow simple and consistent.

## Journal Design

### Main table

Add a `Setup` column to the journal trade table.

Behavior:

- if setup evidence is present, show a compact icon button
- if setup evidence is missing, show a muted placeholder such as `--`
- clicking the row still expands the row as it does today

The icon should communicate “view setup evidence” without turning the table into a gallery.

### Expanded row

Add a dedicated setup-evidence block in the expanded journal row.

Recommended contents:

- focused setup screenshot
- focus zone label and price
- Pine snapshot summary:
  - zone count
  - label count
  - top setup label(s)

The screenshot should be visually primary, with the structured summary beside or below it.

## Data Flow

1. Signal/open event happens.
2. Current provider-backed setup evidence is captured once.
3. The resulting setup-evidence bundle is persisted on the signal/trade record.
4. Notification service reads the stored setup evidence and appends the screenshot to open alerts.
5. Journal APIs return the stored setup evidence alongside the signal/trade.
6. Journal table shows a compact setup indicator.
7. Expanded row renders the full setup evidence block.

## Failure Handling

### Missing setup evidence

If setup evidence is unavailable:

- do not block signal processing
- do not block notifications
- do not block journal rendering

Fallback behavior:

- alerts send without image
- journal `Setup` column shows no evidence state
- expanded row shows a clear “setup evidence unavailable” state

### Degraded screenshot

If structured setup evidence exists but no usable image URL is available:

- still persist the setup-evidence object
- still surface the zone and Pine snapshot in the journal
- still allow notifications to send without the image

## Files Likely Affected

Backend:

- `src/services/notification_service.py`
- `src/adapters/discord.py`
- Telegram delivery code in `src/adapters/discord.py`
- whichever signal/trade persistence layer stores and returns journal signal records

Frontend:

- `frontend/src/components/journal/TradeTable.tsx`
- `frontend/src/components/journal/ExpandableTradeRow.tsx`
- `frontend/src/types/trading.ts` or the current journal signal type definition

## Acceptance Criteria

- Open alerts include the stored setup screenshot when available.
- Close alerts can optionally reuse the same stored screenshot without recapturing.
- Journal table shows a compact `Setup` affordance instead of a large inline image.
- Expanded journal rows show the focused screenshot and setup summary.
- Missing or degraded evidence never blocks alert delivery or journal rendering.
- The screenshot shown in notifications and the journal comes from the same stored evidence bundle.

## Rollout

Recommended order:

1. persist setup evidence on the signal/trade record
2. wire notifications to reuse stored `focus_image.url`
3. add journal `Setup` column
4. add expanded-row setup evidence block

This order delivers the alert value first while keeping the UI change aligned to the same source of truth.
