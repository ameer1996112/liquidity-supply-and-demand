# Notification Screenshot Delivery Design

Date: 2026-04-20
Ticket: DEV-160

## Goal

Make Discord and Telegram trade notifications attach screenshots only when an image URL already exists in the underlying trade data.

Desired behavior:
- Trade open notifications attach the existing setup screenshot when available.
- Trade open notifications remain text-only when no setup screenshot exists.
- Trade close notifications attach a screenshot only when a dedicated close screenshot URL exists.
- Trade close notifications remain text-only when no close screenshot exists.
- No chart generation fallback is allowed.
- Close notification text should be reformatted to look cleaner and more intentional.

## Current State

- `NotificationPayload` already supports `image_url`.
- `NotificationService.format_signal()` already resolves setup screenshots via `_resolve_setup_image_url(...)`.
- `NotificationService.format_close()` currently also calls `_resolve_setup_image_url(signal)`, which incorrectly makes close notifications reuse setup imagery.
- `dispatch_payload(...)` in `src/adapters/discord.py` already sends:
  - Telegram text + `sendPhoto` when `payload.image_url` is present
  - text-only otherwise
- Signal open flow in `src/logic.py` currently does two screenshot-related things:
  - passes the existing `image_url` into `NotificationService.format_signal(...)`
  - separately generates charts via `chart_generator.generate_chart_async(...)` and sends them through `send_chart_to_channels_async(...)`

## Problems

1. Open notifications can send generated charts even when no stored screenshot exists.
2. Close notifications reuse the setup screenshot instead of requiring a true close screenshot.
3. Close notification formatting is functional but visually noisy for Telegram/Discord consumption.

## Design

### 1. Image Source Rules

#### Open notifications
- Source image from existing setup/signal evidence only.
- Valid sources remain:
  - explicit `image_url` passed into `format_signal(...)`
  - `signal.setup_evidence.focus_image.url`
  - `signal.image_url`
- If none exist, `NotificationPayload.image_url` must be `None`.

#### Close notifications
- Add a dedicated close-image resolver in `NotificationService`.
- Valid sources for close images:
  - `signal.close_image_url`
  - `signal.exit_image_url`
  - `signal.close_screenshot_url`
  - optionally `signal.close_evidence.focus_image.url` if the close path already stores structured evidence there
- Explicitly do not fall back to setup/open image fields.
- If no close image exists, `NotificationPayload.image_url` must be `None`.

### 2. Notification Formatting

#### Open notifications
- Keep the current overall structure.
- Preserve screenshot attachment behavior, but only from existing data.

#### Close notifications
- Keep the core facts:
  - account
  - symbol
  - side
  - outcome
  - PnL
  - entry
  - exit
  - commission
  - swap
  - strategy
  - signal id
- Reformat the close title/body so it reads like a compact trade report rather than raw status/debug text.
- Keep field names concise and consistent between Discord and Telegram output.

### 3. Delivery Rules

#### Discord
- Continue using `payload.image_url` as the only trigger for an image-bearing notification.
- If `payload.image_url` exists, include it in the sent embed/media path.
- If `payload.image_url` is absent, send text/embed only.

#### Telegram
- Continue using photo delivery only when `payload.image_url` exists.
- If absent, send a plain text message only.

### 4. Remove Generated Chart Fallback

- Disable the generated chart delivery block in `src/logic.py` for this notification flow.
- Specifically, remove or gate off the `generate_chart_async(...)` + `send_chart_to_channels_async(...)` path for trade-open notifications.
- This ensures the system never sends a screenshot unless it already exists in persisted trade data.

## Data Flow

### Trade open
1. Trade is executed.
2. Logic fetches enriched `trading_signals` row.
3. `NotificationService.format_signal(...)` resolves existing setup image URL if present.
4. `dispatch_payload_async(...)` sends:
   - text + image when URL exists
   - text only when URL does not exist
5. No generated chart is produced.

### Trade close
1. Close flow builds the final closed-signal payload.
2. `NotificationService.format_close(...)` resolves only dedicated close-image fields.
3. `dispatch_payload_async(...)` sends:
   - text + image when close image URL exists
   - text only when URL does not exist

## Files To Change

- `src/services/notification_service.py`
  - add dedicated close-image resolver
  - stop `format_close()` from using setup/open image resolution
  - polish close notification field/title layout

- `src/logic.py`
  - remove or disable the generated chart delivery path for trade notifications

- `src/adapters/discord.py`
  - likely no behavior change needed beyond verifying existing `payload.image_url` handling still matches the new contract

- tests touching notification formatting / dispatch
  - add or update tests for:
    - open with existing screenshot
    - open without screenshot
    - close with dedicated close screenshot
    - close without close screenshot
    - close does not reuse open/setup screenshot

## Risks

- Existing close flows may not yet populate a dedicated close-image field, which means close notifications will become text-only until that data is stored upstream.
- Some callers may currently rely on generated chart delivery; removing that path changes behavior intentionally.
- Telegram and Discord formatting differences may require small snapshot/test updates.

## Testing

- Unit tests for notification formatting:
  - `format_signal()` resolves only existing open/setup images
  - `format_close()` resolves only dedicated close images
  - `format_close()` does not reuse setup/open image fields

- Delivery tests:
  - Telegram uses photo path only when `payload.image_url` exists
  - text-only path when absent

- Regression checks:
  - no generated chart dispatch from trade-open flow
  - close notification text remains readable without images

## Implementation Notes

- Keep the change narrow: this is a delivery/formatting fix, not a redesign of screenshot generation or evidence ingestion.
- Do not change trading logic or execution behavior.
- Prefer adapting the existing notification payload contract instead of introducing a new delivery abstraction.
