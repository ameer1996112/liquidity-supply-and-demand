# Signal Setup Evidence Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist setup evidence on signal records and reuse it for Discord/Telegram notifications plus the journal table and expanded journal detail view.

**Architecture:** Add a `setup_evidence` JSONB column on `trading_signals`, persist the provider-backed evidence bundle together with a convenience `image_url`, and thread that data through the existing signal fetch and notification flows. On the frontend, keep the journal table compact with a new `Setup` icon column and render the full screenshot plus setup summary only in the expanded row.

**Tech Stack:** Supabase/Postgres JSONB, Python service layer, FastAPI/Supabase adapters, React 19, TypeScript, Vitest, Pytest

---

## File Structure

- Create: `migrations/080_signal_setup_evidence.sql`
  - Add persistent `setup_evidence` JSONB to `trading_signals`.
- Modify: `src/adapters/supabase.py`
  - Persist `setup_evidence` and a convenience `image_url` when alerts are saved.
- Modify: `src/logic.py`
  - Include persisted evidence fields when reloading a signal for notification dispatch.
- Modify: `src/services/notification_service.py`
  - Resolve notification images from stored setup evidence for open and close alerts.
- Modify: `src/adapters/discord.py`
  - Add Telegram overflow-safe photo delivery fallback while keeping Discord embed images unchanged.
- Modify: `frontend/src/types/trading.ts`
  - Add `SetupEvidence` types and carry them through normalization.
- Create: `frontend/src/components/journal/SetupEvidenceCell.tsx`
  - Compact journal table affordance for evidence presence.
- Create: `frontend/src/components/journal/SetupEvidenceDetail.tsx`
  - Expanded journal evidence panel with screenshot and structured summary.
- Modify: `frontend/src/components/journal/TradeTable.tsx`
  - Add the new `Setup` column.
- Modify: `frontend/src/components/journal/ExpandableTradeRow.tsx`
  - Render the stored setup evidence block in the expanded row.
- Create: `tests/adapters/test_supabase_setup_evidence.py`
  - Verify alert persistence carries `setup_evidence` and `image_url`.
- Create: `tests/services/test_notification_service.py`
  - Verify open/close notifications reuse stored evidence correctly.
- Create: `frontend/src/components/journal/__tests__/SetupEvidenceCell.test.tsx`
  - Verify compact table affordance.
- Create: `frontend/src/components/journal/__tests__/SetupEvidenceDetail.test.tsx`
  - Verify screenshot + summary rendering and degraded state.

### Task 1: Persist setup evidence on signal records

**Files:**
- Create: `migrations/080_signal_setup_evidence.sql`
- Modify: `src/adapters/supabase.py`
- Modify: `src/logic.py`
- Modify: `frontend/src/types/trading.ts`
- Test: `tests/adapters/test_supabase_setup_evidence.py`

- [ ] **Step 1: Write the failing persistence test**

```python
from src.adapters import supabase as supabase_module


class _InsertRecorder:
    def __init__(self) -> None:
        self.payload = None

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        return type("Response", (), {"data": [{"id": 123}]})()


class _Client:
    def __init__(self) -> None:
        self.recorder = _InsertRecorder()

    def table(self, name: str):
        assert name == "trading_signals"
        return self.recorder


def test_save_alert_persists_setup_evidence_and_image_url(monkeypatch) -> None:
    client = _Client()
    monkeypatch.setattr(supabase_module, "supabase", client)

    alert_id = supabase_module.save_alert(
        {
            "symbol": "VANTAGE:AUDUSD",
            "side": "BUY",
            "entry": 0.7156,
            "sl": 0.7148,
            "tp": 0.7172,
            "size": 0.25,
            "setup_evidence": {
                "status": "ok",
                "focus_zone": {"label": "Demand", "low": 0.7149, "high": 0.7153},
                "focus_image": {"url": "https://provider.example/setup.png"},
                "pine_snapshot": {"zone_count": 1, "label_count": 2, "top_labels": ["LONG"]},
                "reason": "",
            },
        }
    )

    assert alert_id == 123
    assert client.recorder.payload["setup_evidence"]["status"] == "ok"
    assert client.recorder.payload["image_url"] == "https://provider.example/setup.png"
```

- [ ] **Step 2: Run the new backend test to confirm it fails**

Run:

```bash
PYTHONPATH=. pytest tests/adapters/test_supabase_setup_evidence.py -v
```

Expected:

- Fails because `setup_evidence` and `image_url` are not yet persisted by `save_alert`

- [ ] **Step 3: Add the schema migration**

```sql
-- 080_signal_setup_evidence.sql
-- Persist provider-backed setup evidence for notifications and journal surfaces.

ALTER TABLE public.trading_signals
  ADD COLUMN IF NOT EXISTS setup_evidence JSONB;

COMMENT ON COLUMN public.trading_signals.setup_evidence IS
  'Provider-backed setup evidence bundle (focus zone, focus image, pine snapshot).';
```

- [ ] **Step 4: Persist `setup_evidence` and derive `image_url` in `save_alert`**

```python
    setup_evidence = data.get("setup_evidence")
    if setup_evidence is not None:
        insert_data["setup_evidence"] = setup_evidence
        focus_image = setup_evidence.get("focus_image") if isinstance(setup_evidence, dict) else None
        if isinstance(focus_image, dict) and focus_image.get("url"):
            insert_data["image_url"] = focus_image["url"]
```

- [ ] **Step 5: Include the stored fields when notifications reload the signal record**

```python
            _db_rec = (
                _sb.table("trading_signals")
                .select(
                    "id, symbol, side, entry, sl, tp, size, fill_price, "
                    "broker_symbol, zone_id, zone_type, broker_order_id, "
                    "image_url, setup_evidence"
                )
                .eq("id", alert_id)
                .maybe_single()
                .execute()
            )
```

- [ ] **Step 6: Extend the frontend signal types and normalization**

```ts
export interface SetupEvidenceFocusZone {
  type?: string;
  label?: string;
  price?: number;
  high?: number;
  low?: number;
  study?: string;
}

export interface SetupEvidenceFocusImage {
  path?: string | null;
  region?: string | null;
  url?: string | null;
}

export interface SetupEvidenceSnapshot {
  zone_count?: number;
  label_count?: number;
  top_labels?: string[];
}

export interface SetupEvidence {
  status?: 'ok' | 'degraded';
  focus_zone?: SetupEvidenceFocusZone | null;
  focus_image?: SetupEvidenceFocusImage | null;
  pine_snapshot?: SetupEvidenceSnapshot | null;
  reason?: string;
}
```

and on `TradingSignal`:

```ts
  image_url?: string | null;
  setup_evidence?: SetupEvidence | null;
```

- [ ] **Step 7: Run the persistence test again**

Run:

```bash
PYTHONPATH=. pytest tests/adapters/test_supabase_setup_evidence.py -v
```

Expected:

- PASS

- [ ] **Step 8: Commit the persistence slice**

```bash
git add migrations/080_signal_setup_evidence.sql src/adapters/supabase.py src/logic.py frontend/src/types/trading.ts tests/adapters/test_supabase_setup_evidence.py
git commit -m "DEV-126: persist signal setup evidence"
```

### Task 2: Reuse stored setup evidence in notifications

**Files:**
- Modify: `src/services/notification_service.py`
- Modify: `src/adapters/discord.py`
- Test: `tests/services/test_notification_service.py`

- [ ] **Step 1: Write the failing notification service tests**

```python
from src.services.notification_service import NotificationService


def test_format_signal_prefers_setup_evidence_image_url() -> None:
    payload = NotificationService().format_signal(
        {
            "id": 44,
            "symbol": "VANTAGE:AUDUSD",
            "side": "BUY",
            "entry": 0.7156,
            "sl": 0.7148,
            "tp": 0.7172,
            "size": 0.25,
            "setup_evidence": {
                "status": "ok",
                "focus_image": {"url": "https://provider.example/setup.png"},
            },
        }
    )

    assert payload.image_url == "https://provider.example/setup.png"


def test_format_close_reuses_opening_setup_evidence_image() -> None:
    payload = NotificationService().format_close(
        {
            "id": 44,
            "symbol": "VANTAGE:AUDUSD",
            "side": "BUY",
            "entry": 0.7156,
            "exit_price": 0.7172,
            "pnl_usd": 42.5,
            "setup_evidence": {
                "status": "ok",
                "focus_image": {"url": "https://provider.example/setup.png"},
            },
        }
    )

    assert payload.image_url == "https://provider.example/setup.png"
```

- [ ] **Step 2: Run the notification tests to confirm they fail**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_notification_service.py -v
```

Expected:

- Fails because `format_signal` and/or `format_close` do not yet derive image URLs from `setup_evidence`

- [ ] **Step 3: Add a single helper in `NotificationService` to resolve image URLs from stored evidence**

```python
    def _resolve_setup_image_url(
        self,
        signal: dict[str, Any],
        explicit_image_url: Optional[str] = None,
    ) -> Optional[str]:
        if explicit_image_url:
            return explicit_image_url

        setup_evidence = signal.get("setup_evidence")
        if isinstance(setup_evidence, dict):
            focus_image = setup_evidence.get("focus_image")
            if isinstance(focus_image, dict) and focus_image.get("url"):
                return str(focus_image["url"])

        image_url = signal.get("image_url")
        return str(image_url) if image_url else None
```

- [ ] **Step 4: Use the helper from both `format_signal` and `format_close`**

```python
        resolved_image_url = self._resolve_setup_image_url(signal, image_url)
```

and in `format_close`’s return value:

```python
            image_url=self._resolve_setup_image_url(signal),
```

- [ ] **Step 5: Add Telegram overflow-safe fallback in the adapter**

```python
            if payload.image_url and len(text) <= 900:
                r = requests.post(
                    f"https://api.telegram.org/bot{s.telegram_bot_token}/sendPhoto",
                    json={
                        "chat_id": s.telegram_chat_id,
                        "photo": payload.image_url,
                        "caption": text,
                        "parse_mode": "HTML",
                    },
                    timeout=10,
                )
            elif payload.image_url:
                requests.post(
                    f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
                    json={"chat_id": s.telegram_chat_id, "text": text, "parse_mode": "HTML"},
                    timeout=10,
                )
                r = requests.post(
                    f"https://api.telegram.org/bot{s.telegram_bot_token}/sendPhoto",
                    json={"chat_id": s.telegram_chat_id, "photo": payload.image_url},
                    timeout=10,
                )
            else:
                r = requests.post(
                    f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
                    json={"chat_id": s.telegram_chat_id, "text": text, "parse_mode": "HTML"},
                    timeout=10,
                )
```

- [ ] **Step 6: Run the notification tests**

Run:

```bash
PYTHONPATH=. pytest tests/services/test_notification_service.py -v
```

Expected:

- PASS

- [ ] **Step 7: Commit the notification slice**

```bash
git add src/services/notification_service.py src/adapters/discord.py tests/services/test_notification_service.py
git commit -m "DEV-126: reuse setup evidence in notifications"
```

### Task 3: Add setup evidence to the journal table and expanded row

**Files:**
- Create: `frontend/src/components/journal/SetupEvidenceCell.tsx`
- Create: `frontend/src/components/journal/SetupEvidenceDetail.tsx`
- Modify: `frontend/src/components/journal/TradeTable.tsx`
- Modify: `frontend/src/components/journal/ExpandableTradeRow.tsx`
- Test: `frontend/src/components/journal/__tests__/SetupEvidenceCell.test.tsx`
- Test: `frontend/src/components/journal/__tests__/SetupEvidenceDetail.test.tsx`

- [ ] **Step 1: Write the failing frontend tests**

```tsx
/** @vitest-environment jsdom */

import { createRoot } from 'react-dom/client';
import { act } from 'react';
import { describe, expect, test } from 'vitest';
import { SetupEvidenceCell } from '../SetupEvidenceCell';

describe('SetupEvidenceCell', () => {
  test('shows a compact evidence icon when setup evidence exists', () => {
    const container = document.createElement('div');
    const root = createRoot(container);

    act(() => {
      root.render(
        <SetupEvidenceCell
          evidence={{
            status: 'ok',
            focus_image: { url: 'https://provider/setup.png' },
          }}
        />
      );
    });

    expect(container.querySelector('[data-testid=\"setup-evidence-icon\"]')).not.toBeNull();
    root.unmount();
  });
});
```

```tsx
/** @vitest-environment jsdom */

import { createRoot } from 'react-dom/client';
import { act } from 'react';
import { describe, expect, test } from 'vitest';
import { SetupEvidenceDetail } from '../SetupEvidenceDetail';

describe('SetupEvidenceDetail', () => {
  test('renders screenshot and pine snapshot summary', () => {
    const container = document.createElement('div');
    const root = createRoot(container);

    act(() => {
      root.render(
        <SetupEvidenceDetail
          evidence={{
            status: 'ok',
            focus_zone: { label: 'Demand', low: 0.7149, high: 0.7153 },
            focus_image: { url: 'https://provider/setup.png' },
            pine_snapshot: { zone_count: 1, label_count: 2, top_labels: ['LONG'] },
            reason: '',
          }}
        />
      );
    });

    expect(container.querySelector('img[alt=\"Setup evidence\"]')?.getAttribute('src')).toBe('https://provider/setup.png');
    expect(container.textContent).toContain('Demand');
    expect(container.textContent).toContain('LONG');
    root.unmount();
  });
});
```

- [ ] **Step 2: Run the new frontend tests to confirm they fail**

Run:

```bash
cd frontend && npx vitest run src/components/journal/__tests__/SetupEvidenceCell.test.tsx src/components/journal/__tests__/SetupEvidenceDetail.test.tsx
```

Expected:

- Fails because the new components do not exist yet

- [ ] **Step 3: Create the compact table cell component**

```tsx
import { Image as ImageIcon } from 'lucide-react';
import { SetupEvidence } from '@/types/trading';

interface SetupEvidenceCellProps {
  evidence?: SetupEvidence | null;
}

export function SetupEvidenceCell({ evidence }: SetupEvidenceCellProps) {
  if (!evidence || !evidence.focus_image?.url) {
    return <span className="text-[var(--to-text-dim)] text-[11px]">--</span>;
  }

  return (
    <button
      type="button"
      data-testid="setup-evidence-icon"
      className="inline-flex items-center justify-center rounded-md border border-[var(--to-border)] bg-[var(--to-surface-raised)] px-1.5 py-1 text-[var(--to-text-secondary)]"
      aria-label="Setup evidence available"
      tabIndex={-1}
    >
      <ImageIcon className="h-3 w-3" />
    </button>
  );
}
```

- [ ] **Step 4: Create the expanded setup-evidence detail component**

```tsx
import { SetupEvidence } from '@/types/trading';

interface SetupEvidenceDetailProps {
  evidence?: SetupEvidence | null;
}

export function SetupEvidenceDetail({ evidence }: SetupEvidenceDetailProps) {
  if (!evidence) {
    return <div className="text-[11px] text-[var(--to-text-dim)]">Setup evidence unavailable</div>;
  }

  return (
    <div className="space-y-3">
      {evidence.focus_image?.url ? (
        <img
          src={evidence.focus_image.url}
          alt="Setup evidence"
          className="w-full max-w-md rounded-lg border border-[var(--to-border)]"
        />
      ) : (
        <div className="text-[11px] text-[var(--to-text-dim)]">{evidence.reason || 'Setup image unavailable'}</div>
      )}

      <div className="grid gap-2 text-[11px]">
        <div>
          <span className="text-[var(--to-text-dim)]">Zone</span>
          <span className="ml-2 font-mono text-[var(--to-text-secondary)]">
            {evidence.focus_zone?.label || 'No focus zone'}
          </span>
        </div>
        <div>
          <span className="text-[var(--to-text-dim)]">Snapshot</span>
          <span className="ml-2 font-mono text-[var(--to-text-secondary)]">
            {(evidence.pine_snapshot?.top_labels || []).join(' • ') || 'No Pine labels captured'}
          </span>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Add the `Setup` column to the table**

```tsx
type SortKey =
  | 'date'
  | 'symbol'
  | 'side'
  | 'status'
  | 'account'
  | 'setup'
  | 'zone'
```

and:

```tsx
  { key: 'setup', label: 'Setup' },
```

and sort value:

```tsx
    case 'setup':
      return signal.setup_evidence?.focus_image?.url ? 1 : 0;
```

- [ ] **Step 6: Render the compact cell in the row and the detail in the expansion**

```tsx
        <td className="py-2.5 px-3">
          <SetupEvidenceCell evidence={signal.setup_evidence} />
        </td>
```

and in the expanded row content:

```tsx
              <div className="space-y-2">
                <span className="text-[10px] text-text-dim uppercase tracking-wider font-medium">
                  Setup Evidence
                </span>
                <SetupEvidenceDetail evidence={signal.setup_evidence} />
              </div>
```

- [ ] **Step 7: Run the frontend tests and build**

Run:

```bash
cd frontend && npx vitest run src/components/journal/__tests__/SetupEvidenceCell.test.tsx src/components/journal/__tests__/SetupEvidenceDetail.test.tsx
cd frontend && npm run build
```

Expected:

- Both Vitest files pass
- Frontend build succeeds

- [ ] **Step 8: Commit the journal UI slice**

```bash
git add frontend/src/types/trading.ts frontend/src/components/journal/SetupEvidenceCell.tsx frontend/src/components/journal/SetupEvidenceDetail.tsx frontend/src/components/journal/TradeTable.tsx frontend/src/components/journal/ExpandableTradeRow.tsx frontend/src/components/journal/__tests__/SetupEvidenceCell.test.tsx frontend/src/components/journal/__tests__/SetupEvidenceDetail.test.tsx
git commit -m "DEV-126: add journal setup evidence views"
```

## Final Verification

- [ ] **Step 1: Run the backend verification set**

```bash
PYTHONPATH=. pytest tests/adapters/test_supabase_setup_evidence.py tests/services/test_notification_service.py -v
```

Expected:

- PASS

- [ ] **Step 2: Run the frontend verification set**

```bash
cd frontend && npx vitest run src/components/journal/__tests__/SetupEvidenceCell.test.tsx src/components/journal/__tests__/SetupEvidenceDetail.test.tsx
cd frontend && npm run build
```

Expected:

- PASS

- [ ] **Step 3: Run a manual signal-notification smoke check**

Run:

```bash
./scripts/run_local_chart_stack.sh --fresh
curl "http://127.0.0.1:8765/chart-context?symbol=VANTAGE:AUDUSD&timeframe=5m" | grep -q '"setup_evidence"'
```

Expected:

- Provider responds with `setup_evidence`
- A new signal saved after this point can carry the stored evidence into notifications and the journal

- [ ] **Step 4: Create the final implementation commit**

```bash
git add migrations/080_signal_setup_evidence.sql src/adapters/supabase.py src/logic.py src/services/notification_service.py src/adapters/discord.py frontend/src/types/trading.ts frontend/src/components/journal/SetupEvidenceCell.tsx frontend/src/components/journal/SetupEvidenceDetail.tsx frontend/src/components/journal/TradeTable.tsx frontend/src/components/journal/ExpandableTradeRow.tsx tests/adapters/test_supabase_setup_evidence.py tests/services/test_notification_service.py frontend/src/components/journal/__tests__/SetupEvidenceCell.test.tsx frontend/src/components/journal/__tests__/SetupEvidenceDetail.test.tsx
git commit -m "DEV-126: deliver setup evidence to alerts and journal"
```
