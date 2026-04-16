# DEV-128 Setup Evidence UX Polish Design

## Summary

Polish the existing setup-evidence experience across notifications and the journal without changing the underlying evidence storage model.

This slice improves presentation only:

- Discord alerts feel more intentional and review-friendly
- Telegram delivery becomes clearer and less overloaded
- journal rows communicate evidence state at a glance
- expanded journal evidence can be viewed in a larger in-place modal

## Goals

- Keep the current `setup_evidence` persistence model unchanged.
- Improve Discord open and close alerts with clearer setup-evidence context.
- Make Telegram setup-evidence delivery feel deliberate rather than like a fallback artifact.
- Add clear evidence-state signaling in the journal table.
- Add a click-to-open modal for larger screenshot review in the journal.
- Improve visual hierarchy inside the journal evidence block.

## Non-Goals

- No new database columns.
- No new screenshot capture moments.
- No backfill or analytics coverage tooling in this slice.
- No major journal page redesign.
- No new external storage or media pipeline work.

## Existing Context

The current state already supports:

- stored `setup_evidence`
- notification reuse of the stored screenshot
- compact `Setup` column in the journal
- expanded journal evidence block

The remaining gaps are presentation quality:

- Discord currently attaches the image, but the evidence context is not explicitly summarized
- Telegram can split text and photo, but that split is utilitarian rather than intentional
- the journal `Setup` indicator does not reflect evidence state
- the expanded screenshot is useful but not optimized for close inspection

## Product Decision

### Presentation-only upgrade

Keep the evidence bundle exactly as it is and improve how it is presented.

This keeps the slice low risk, avoids more schema churn, and directly improves the operator experience.

## Discord Design

### Open alert

Keep the existing structured card and add a compact setup-evidence summary section above the image.

Recommended additions:

- a `Setup Evidence` field summarizing:
  - evidence status
  - focus zone label
  - whether a screenshot is attached

The screenshot remains the large embed image below the card fields.

### Close alert

If a stored opening screenshot exists:

- reuse the same image
- add a short setup-evidence summary field
- add outcome framing so the close alert reads as:
  - this was the original setup
  - this was the result

No new close-time screenshot capture is introduced.

## Telegram Design

Telegram should feel like a deliberate two-part alert when setup evidence exists.

Recommended behavior:

1. send a clean signal summary message
2. send the setup screenshot as a second message with a short caption such as:
   - `Setup Evidence`
   - focus zone label
   - optional status

This avoids oversized captions while making the screenshot feel like a designed companion message instead of a transport workaround.

For close alerts:

- the same pattern may be reused with a shorter outcome-oriented caption if the opening screenshot is available

## Journal Table Design

### Setup icon state

Keep the compact `Setup` icon, but make it stateful:

- `ok`:
  - green or positive accent
- `degraded`:
  - amber or warning accent
- `missing`:
  - muted placeholder

The goal is glanceable evidence quality without increasing table density.

### Interaction

The main row remains compact and still expands on row click.

The setup icon does not need to be the only interaction trigger, but it should visually communicate state immediately.

## Expanded Journal Detail Design

Improve the existing setup-evidence block with:

- clearer status badge
- stronger spacing and hierarchy
- screenshot treated as the primary review asset
- structured summary grouped beneath or beside it

Recommended content blocks:

- status badge
- focus zone summary
- Pine snapshot summary
- screenshot preview

## Screenshot Modal Design

Add an in-place modal for the journal screenshot.

Behavior:

- clicking the screenshot opens a modal overlay
- modal shows the full image at a larger size
- modal header includes:
  - `Setup Evidence`
  - focus zone summary
  - evidence status

This keeps the operator inside the journal workflow and avoids opening new tabs.

### Future compatibility

The modal should be simple in v1 but leave room for:

- zoom controls
- download/open-original action
- side-by-side comparison in later slices

## Failure Handling

### Missing evidence

When evidence is missing:

- journal table shows muted state
- expanded row shows the current unavailable copy
- no modal entry point is shown
- notifications continue without evidence image

### Degraded evidence

When evidence is degraded:

- journal table shows warning state
- expanded row shows structured summary and degraded reason
- modal is available only if an image still exists
- alerts still send, but the summary should clearly indicate degraded evidence

## Files Likely Affected

Backend:

- `src/adapters/discord.py`
- `src/services/notification_service.py`

Frontend:

- `frontend/src/components/journal/SetupEvidenceCell.tsx`
- `frontend/src/components/journal/SetupEvidenceDetail.tsx`
- likely one small new modal component under `frontend/src/components/journal/`

## Acceptance Criteria

- Discord alerts include an explicit setup-evidence summary field when evidence exists.
- Telegram setup evidence is delivered as a clean secondary photo message or a clearly intentional photo-first pattern.
- Journal `Setup` icon reflects `ok`, `degraded`, or `missing`.
- Expanded journal evidence has clearer hierarchy and status.
- Clicking the journal screenshot opens an in-place modal.
- No persistence or migration changes are required for this slice.

## Rollout

Recommended order:

1. polish Discord/Telegram presentation
2. add journal evidence-state affordances
3. add screenshot modal
4. refine expanded evidence layout

This yields the fastest visible improvement while keeping the slice purely presentational.
