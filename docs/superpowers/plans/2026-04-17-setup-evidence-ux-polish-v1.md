# Setup Evidence UX Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish setup-evidence presentation across Discord, Telegram, and the journal so the existing stored evidence feels intentional, stateful, and easier to review.

**Architecture:** Keep the current `setup_evidence` persistence contract unchanged and layer presentation polish on top of it. Backend changes stay inside notification formatting and transport adapters; frontend changes stay inside the journal evidence cell/detail surfaces with one small modal component for larger screenshot review.

**Tech Stack:** Python, FastAPI services, notification adapters, React, TypeScript, Vitest

---

## File Structure

- `src/services/notification_service.py`
  - Keep notification payload creation as the source of truth for setup-evidence summary text, status labeling, and optional close-alert reuse.
- `src/adapters/discord.py`
  - Render richer Discord embed fields and intentional Telegram photo delivery using the existing `image_url`.
- `tests/services/test_notification_service.py`
  - Extend payload-formatting coverage so alert summaries stay stable.
- `tests/adapters/test_discord.py`
  - Add/extend adapter-level tests for Discord embed fields and Telegram two-message delivery.
- `frontend/src/components/journal/SetupEvidenceCell.tsx`
  - Show compact, stateful setup-evidence status in the journal table.
- `frontend/src/components/journal/SetupEvidenceDetail.tsx`
  - Improve hierarchy, badge treatment, and screenshot interaction.
- `frontend/src/components/journal/SetupEvidenceModal.tsx`
  - New focused modal for in-place screenshot review.
- `frontend/src/components/journal/ExpandableTradeRow.tsx`
  - Wire modal open/close state and pass the selected evidence through.
- `frontend/src/components/journal/__tests__/SetupEvidenceCell.test.tsx`
  - Lock in icon state rendering for `ok`, `degraded`, and `missing`.
- `frontend/src/components/journal/__tests__/SetupEvidenceDetail.test.tsx`
  - Lock in badge/screenshot rendering and degraded copy.
- `frontend/src/components/journal/__tests__/SetupEvidenceModal.test.tsx`
  - Cover modal open/close behavior and evidence header content.

### Task 1: Polish Notification Setup-Evidence Presentation

**Files:**
- Modify: `src/services/notification_service.py`
- Modify: `src/adapters/discord.py`
- Modify: `tests/services/test_notification_service.py`
- Modify or Create: `tests/adapters/test_discord.py`

- [ ] **Step 1: Write the failing notification-formatting tests**

```python
def test_format_signal_includes_setup_evidence_summary() -> None:
    payload = format_signal(
        {
            "symbol": "GBPUSD",
            "direction": "SELL",
            "entry_price": 1.35414,
            "stop_loss": 1.35620,
            "take_profit": 1.34940,
            "image_url": "https://example.com/setup.png",
            "setup_evidence": {
                "status": "ok",
                "focus_zone": {"label": "SUPPLY A+"},
                "focus_image": {"url": "https://example.com/setup.png"},
            },
        }
    )

    assert payload["setup_evidence_summary"] == {
        "status": "ok",
        "status_label": "Setup Evidence: OK",
        "focus_zone_label": "SUPPLY A+",
        "has_image": True,
    }


def test_format_close_reuses_opening_setup_evidence_summary() -> None:
    payload = format_close(
        {
            "symbol": "GBPUSD",
            "direction": "SELL",
            "close_reason": "tp_hit",
            "image_url": "https://example.com/setup.png",
            "setup_evidence": {
                "status": "degraded",
                "reason": "focus zone fallback",
                "focus_zone": {"label": "SUPPLY A+"},
                "focus_image": {"url": "https://example.com/setup.png"},
            },
        }
    )

    assert payload["setup_evidence_summary"]["status"] == "degraded"
    assert payload["setup_evidence_summary"]["focus_zone_label"] == "SUPPLY A+"
```

- [ ] **Step 2: Run the targeted notification-service tests to verify the new contract is missing**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_notification_service.py -k "setup_evidence_summary" -v
```

Expected: FAIL with missing `setup_evidence_summary` fields or assertion mismatches.

- [ ] **Step 3: Implement minimal setup-evidence summary helpers in `notification_service.py`**

```python
def _build_setup_evidence_summary(signal: Mapping[str, Any]) -> dict[str, Any] | None:
    setup_evidence = signal.get("setup_evidence") or {}
    if not setup_evidence:
        return None

    status = str(setup_evidence.get("status") or "missing").lower()
    focus_zone = setup_evidence.get("focus_zone") or {}
    image_url = _resolve_setup_image_url(signal)

    return {
        "status": status,
        "status_label": f"Setup Evidence: {status.upper()}",
        "focus_zone_label": focus_zone.get("label") or "No focus zone detected",
        "has_image": bool(image_url),
        "reason": setup_evidence.get("reason") or "",
    }


def format_signal(signal: Mapping[str, Any]) -> dict[str, Any]:
    payload = _existing_signal_payload(signal)
    payload["setup_evidence_summary"] = _build_setup_evidence_summary(signal)
    return payload


def format_close(signal: Mapping[str, Any]) -> dict[str, Any]:
    payload = _existing_close_payload(signal)
    payload["setup_evidence_summary"] = _build_setup_evidence_summary(signal)
    return payload
```

- [ ] **Step 4: Re-run the notification-service tests**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_notification_service.py -k "setup_evidence_summary" -v
```

Expected: PASS

- [ ] **Step 5: Write the failing adapter tests for Discord and Telegram presentation**

```python
async def test_send_discord_signal_adds_setup_evidence_field(discord_client: DummyDiscordClient) -> None:
    payload = {
        "title": "GBPUSD SELL",
        "image_url": "https://example.com/setup.png",
        "setup_evidence_summary": {
            "status_label": "Setup Evidence: OK",
            "focus_zone_label": "SUPPLY A+",
            "has_image": True,
        },
    }

    await send_discord_message(discord_client, payload)

    embed = discord_client.sent_embeds[0]
    assert any(field["name"] == "Setup Evidence" for field in embed["fields"])
    assert embed["image"]["url"] == "https://example.com/setup.png"


async def test_send_telegram_signal_sends_summary_then_photo_when_image_present(
    telegram_client: DummyTelegramClient,
) -> None:
    payload = {
        "text": "GBPUSD SELL\nEntry: 1.35414",
        "image_url": "https://example.com/setup.png",
        "setup_evidence_summary": {
            "status_label": "Setup Evidence: OK",
            "focus_zone_label": "SUPPLY A+",
            "has_image": True,
        },
    }

    await send_telegram_message(telegram_client, payload)

    assert telegram_client.calls[0]["method"] == "sendMessage"
    assert telegram_client.calls[1]["method"] == "sendPhoto"
    assert "SUPPLY A+" in telegram_client.calls[1]["caption"]
```

- [ ] **Step 6: Run the adapter tests to verify they fail**

Run:

```bash
PYTHONPATH=. pytest tests/adapters/test_discord.py -k "setup_evidence" -v
```

Expected: FAIL because the embed field and explicit Telegram sequencing do not exist yet.

- [ ] **Step 7: Implement the Discord embed field and intentional Telegram secondary photo behavior**

```python
def _build_setup_evidence_field(summary: Mapping[str, Any] | None) -> dict[str, str] | None:
    if not summary:
        return None
    screenshot_state = "attached" if summary.get("has_image") else "not attached"
    return {
        "name": "Setup Evidence",
        "value": (
            f"{summary['status_label']}\n"
            f"Zone: {summary['focus_zone_label']}\n"
            f"Screenshot: {screenshot_state}"
        ),
        "inline": False,
    }


async def send_discord_message(client: DiscordClient, payload: Mapping[str, Any]) -> None:
    embed = _build_existing_embed(payload)
    setup_field = _build_setup_evidence_field(payload.get("setup_evidence_summary"))
    if setup_field:
        embed.setdefault("fields", []).append(setup_field)
    if payload.get("image_url"):
        embed["image"] = {"url": payload["image_url"]}
    await client.send_embed(embed)


async def send_telegram_message(client: TelegramClient, payload: Mapping[str, Any]) -> None:
    await client.send_message(payload["text"])
    if payload.get("image_url"):
        summary = payload.get("setup_evidence_summary") or {}
        caption = "\n".join(
            filter(
                None,
                [
                    "Setup Evidence",
                    summary.get("focus_zone_label"),
                    summary.get("status_label"),
                ],
            )
        )
        await client.send_photo(payload["image_url"], caption=caption)
```

- [ ] **Step 8: Re-run adapter and service tests**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_notification_service.py tests/adapters/test_discord.py -v
```

Expected: PASS

- [ ] **Step 9: Commit the notification polish**

```bash
git add src/services/notification_service.py src/adapters/discord.py tests/services/test_notification_service.py tests/adapters/test_discord.py
git commit -m "DEV-128: polish setup evidence alerts"
```

### Task 2: Add Journal Evidence State and Screenshot Modal

**Files:**
- Modify: `frontend/src/components/journal/SetupEvidenceCell.tsx`
- Modify: `frontend/src/components/journal/SetupEvidenceDetail.tsx`
- Create: `frontend/src/components/journal/SetupEvidenceModal.tsx`
- Modify: `frontend/src/components/journal/ExpandableTradeRow.tsx`
- Modify: `frontend/src/components/journal/__tests__/SetupEvidenceCell.test.tsx`
- Modify: `frontend/src/components/journal/__tests__/SetupEvidenceDetail.test.tsx`
- Create: `frontend/src/components/journal/__tests__/SetupEvidenceModal.test.tsx`

- [ ] **Step 1: Write the failing frontend tests for stateful cell rendering**

```tsx
it("renders a positive setup icon for ok evidence", () => {
  render(
    <SetupEvidenceCell
      signal={{
        image_url: "https://example.com/setup.png",
        setup_evidence: { status: "ok" },
      }}
    />
  );

  expect(screen.getByLabelText("Setup evidence ok")).toHaveClass("text-emerald-400");
});

it("renders a warning setup icon for degraded evidence", () => {
  render(
    <SetupEvidenceCell
      signal={{
        image_url: "https://example.com/setup.png",
        setup_evidence: { status: "degraded" },
      }}
    />
  );

  expect(screen.getByLabelText("Setup evidence degraded")).toHaveClass("text-amber-400");
});
```

- [ ] **Step 2: Run the cell tests to verify the state styles do not exist**

Run:

```bash
cd frontend && npx vitest run src/components/journal/__tests__/SetupEvidenceCell.test.tsx
```

Expected: FAIL because the current cell does not render stateful labels/classes.

- [ ] **Step 3: Implement the stateful journal setup cell**

```tsx
const STATE_STYLES: Record<string, { label: string; className: string }> = {
  ok: { label: "Setup evidence ok", className: "text-emerald-400" },
  degraded: { label: "Setup evidence degraded", className: "text-amber-400" },
  missing: { label: "Setup evidence missing", className: "text-slate-500" },
};

export function SetupEvidenceCell({ signal }: { signal: TradingSignal }) {
  const status = signal.setup_evidence?.status ?? "missing";
  const style = STATE_STYLES[status] ?? STATE_STYLES.missing;

  return (
    <button
      type="button"
      aria-label={style.label}
      className={cn("inline-flex items-center justify-center rounded-md", style.className)}
    >
      <Camera className="h-4 w-4" />
    </button>
  );
}
```

- [ ] **Step 4: Re-run the setup cell tests**

Run:

```bash
cd frontend && npx vitest run src/components/journal/__tests__/SetupEvidenceCell.test.tsx
```

Expected: PASS

- [ ] **Step 5: Write the failing detail/modal tests**

```tsx
it("shows an evidence badge and opens the modal when the screenshot is clicked", async () => {
  const user = userEvent.setup();
  render(
    <SetupEvidenceDetail
      signal={{
        image_url: "https://example.com/setup.png",
        setup_evidence: {
          status: "ok",
          focus_zone: { label: "SUPPLY A+" },
          focus_image: { url: "https://example.com/setup.png" },
        },
      }}
    />
  );

  expect(screen.getByText("OK")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /open setup evidence/i }));
  expect(screen.getByRole("dialog", { name: /setup evidence/i })).toBeInTheDocument();
});
```

- [ ] **Step 6: Run the detail tests to verify modal support is missing**

Run:

```bash
cd frontend && npx vitest run src/components/journal/__tests__/SetupEvidenceDetail.test.tsx src/components/journal/__tests__/SetupEvidenceModal.test.tsx
```

Expected: FAIL because the current detail view has no modal entry point.

- [ ] **Step 7: Add the screenshot modal component and upgraded detail layout**

```tsx
export function SetupEvidenceModal({
  open,
  onOpenChange,
  signal,
}: SetupEvidenceModalProps) {
  if (!open) return null;

  return (
    <div role="dialog" aria-label="Setup Evidence" className="fixed inset-0 z-50 bg-black/70">
      <div className="mx-auto mt-16 max-w-5xl rounded-2xl border border-slate-800 bg-slate-950 p-6">
        <header className="mb-4 flex items-start justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-500">Setup Evidence</p>
            <h3 className="mt-2 text-lg font-semibold text-white">
              {signal.setup_evidence?.focus_zone?.label ?? "No focus zone detected"}
            </h3>
          </div>
          <button onClick={() => onOpenChange(false)} aria-label="Close setup evidence">
            Close
          </button>
        </header>
        <img
          src={signal.setup_evidence?.focus_image?.url ?? signal.image_url ?? ""}
          alt="Focused setup evidence"
          className="w-full rounded-xl border border-slate-800 object-contain"
        />
      </div>
    </div>
  );
}
```

```tsx
export function SetupEvidenceDetail({ signal }: { signal: TradingSignal }) {
  const [modalOpen, setModalOpen] = useState(false);
  const status = signal.setup_evidence?.status ?? "missing";

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
      <div className="mb-4 flex items-center gap-3">
        <span className={badgeClassForStatus(status)}>{status.toUpperCase()}</span>
        <p className="text-sm text-slate-400">
          {signal.setup_evidence?.focus_zone?.label ?? "No focus zone detected"}
        </p>
      </div>
      {signal.image_url ? (
        <>
          <button
            type="button"
            className="group block overflow-hidden rounded-xl border border-slate-800"
            onClick={() => setModalOpen(true)}
            aria-label="Open setup evidence"
          >
            <img src={signal.image_url} alt="Setup evidence preview" className="w-full object-cover transition group-hover:scale-[1.01]" />
          </button>
          <SetupEvidenceModal open={modalOpen} onOpenChange={setModalOpen} signal={signal} />
        </>
      ) : (
        <p className="text-sm text-slate-500">Setup evidence unavailable</p>
      )}
    </section>
  );
}
```

- [ ] **Step 8: Wire the modal-friendly detail component through the expanded row**

```tsx
<td colSpan={19} className="bg-[#0B1220] px-4 py-5">
  <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
    <SetupEvidenceDetail signal={signal} />
    <ExistingTechnicalAndAnalysisPanels signal={signal} />
  </div>
</td>
```

- [ ] **Step 9: Re-run the frontend journal tests**

Run:

```bash
cd frontend && npx vitest run \
  src/components/journal/__tests__/SetupEvidenceCell.test.tsx \
  src/components/journal/__tests__/SetupEvidenceDetail.test.tsx \
  src/components/journal/__tests__/SetupEvidenceModal.test.tsx
```

Expected: PASS

- [ ] **Step 10: Commit the journal polish**

```bash
git add frontend/src/components/journal/SetupEvidenceCell.tsx frontend/src/components/journal/SetupEvidenceDetail.tsx frontend/src/components/journal/SetupEvidenceModal.tsx frontend/src/components/journal/ExpandableTradeRow.tsx frontend/src/components/journal/__tests__/SetupEvidenceCell.test.tsx frontend/src/components/journal/__tests__/SetupEvidenceDetail.test.tsx frontend/src/components/journal/__tests__/SetupEvidenceModal.test.tsx
git commit -m "DEV-128: polish journal setup evidence ux"
```

### Task 3: Verify the Full Presentation Slice End-to-End

**Files:**
- Verify only: `src/services/notification_service.py`
- Verify only: `src/adapters/discord.py`
- Verify only: `frontend/src/components/journal/SetupEvidenceDetail.tsx`

- [ ] **Step 1: Run the backend regression tests**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_notification_service.py tests/adapters/test_discord.py -v
```

Expected: PASS

- [ ] **Step 2: Run the frontend journal tests**

Run:

```bash
cd frontend && npx vitest run \
  src/components/journal/__tests__/SetupEvidenceCell.test.tsx \
  src/components/journal/__tests__/SetupEvidenceDetail.test.tsx \
  src/components/journal/__tests__/SetupEvidenceModal.test.tsx
```

Expected: PASS

- [ ] **Step 3: Build the frontend**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS with no new build errors.

- [ ] **Step 4: Smoke-test the local chart stack contract before UI/manual QA**

Run:

```bash
./scripts/run_local_chart_stack.sh --fresh
curl -s "http://127.0.0.1:8765/chart-context?symbol=VANTAGE:AUDUSD&timeframe=5m" | jq '.setup_evidence'
```

Expected: JSON object with `status`, `focus_zone`, and `focus_image`.

- [ ] **Step 5: Manual QA checklist**

Open the app and verify:

```text
1. Trigger a fresh signal with setup evidence available.
2. Confirm Discord open alert shows a "Setup Evidence" field and the screenshot below it.
3. Confirm Telegram sends a summary message followed by a screenshot message.
4. Confirm the journal "Setup" icon is green for ok evidence, amber for degraded, muted for missing.
5. Expand the journal row and click the screenshot.
6. Confirm the modal opens in place with the focus zone label and status in the header.
```

Expected: All six checks succeed.

- [ ] **Step 6: Commit any final polish or test updates**

```bash
git add src/services/notification_service.py src/adapters/discord.py tests/services/test_notification_service.py tests/adapters/test_discord.py frontend/src/components/journal/SetupEvidenceCell.tsx frontend/src/components/journal/SetupEvidenceDetail.tsx frontend/src/components/journal/SetupEvidenceModal.tsx frontend/src/components/journal/ExpandableTradeRow.tsx frontend/src/components/journal/__tests__/SetupEvidenceCell.test.tsx frontend/src/components/journal/__tests__/SetupEvidenceDetail.test.tsx frontend/src/components/journal/__tests__/SetupEvidenceModal.test.tsx
git commit -m "DEV-128: finalize setup evidence ux polish"
```

## Self-Review

- Spec coverage:
  - Discord summary field: Task 1
  - Telegram intentional secondary photo flow: Task 1
  - Journal `ok` / `degraded` / `missing` state: Task 2
  - In-place modal: Task 2
  - No schema changes: preserved throughout
- Placeholder scan:
  - No `TODO`, `TBD`, or “handle appropriately” placeholders remain.
- Type consistency:
  - Uses the existing `setup_evidence`, `image_url`, and `focus_zone.label` names already established by DEV-126.
