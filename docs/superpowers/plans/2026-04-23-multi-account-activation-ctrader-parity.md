# Multi-Account Activation with cTrader Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `Activate` a true multi-select trading enablement control so multiple MetaAPI and cTrader accounts can stay active together, appear together on the dashboard, and receive the same signal independently.

**Architecture:** Keep `selected_for_trading` as the enabled-for-trading flag, but remove exclusive clearing behavior from the broker-profile API. Route dashboard and portfolio-control live account data through the generic execution router so cTrader profiles use `CTraderAdapter` and MetaAPI profiles use `MetaApiAdapter`. Preserve per-account error isolation so one broker failure does not block the other activated accounts.

**Tech Stack:** FastAPI, Supabase, Python services/adapters, pytest, cTrader Open API adapter, MetaAPI adapter

---

## File Structure

- Modify: `src/api_broker_profiles.py`
  Responsibility: make activation/deactivation semantics truly multi-select and align comments/API behavior with that meaning.

- Modify: `src/services/account_orchestrator.py`
  Responsibility: keep all activated broker profiles visible in comparison output and enrich standalone profile cards with venue-aware live data and open-position counts.

- Modify: `src/api_portfolio_control.py`
  Responsibility: replace MetaAPI-only broker-position fetching with adapter routing by venue so cTrader accounts return the same class of live detail.

- Modify: `src/core/broker_profiles.py`
  Responsibility: make execution fan-out honor `selected_for_trading` so only activated accounts receive signals.

- Modify: `src/adapters/execution/router.py`
  Responsibility: add a reusable helper that resolves a concrete adapter for a specific broker profile without falling back to unrelated single-account state.

- Create: `tests/test_api_broker_profiles_activation.py`
  Responsibility: verify activation no longer clears previously activated accounts and deactivation remains scoped.

- Create: `tests/test_account_orchestrator_profiles.py`
  Responsibility: verify standalone activated profiles render for both MetaAPI and cTrader and remain visible when another profile fetch fails.

- Create: `tests/test_api_portfolio_control_positions.py`
  Responsibility: verify account position fetching uses venue-aware adapters instead of MetaAPI-only logic.

## Task 1: Make Account Activation Truly Multi-Select

**Files:**
- Modify: `src/api_broker_profiles.py`
- Test: `tests/test_api_broker_profiles_activation.py`

- [ ] **Step 1: Write the failing activation tests**

```python
from fastapi.testclient import TestClient


def test_activate_profile_keeps_existing_selected_profiles(client: TestClient, fake_supabase):
    fake_supabase.seed_profiles(
        [
            {"id": 1, "name": "ACG-DEMO-3", "is_active": True, "selected_for_trading": True, "venue": "metaapi_mt5"},
            {"id": 2, "name": "FTMO - TRAIL - 50K", "is_active": True, "selected_for_trading": False, "venue": "ctrader"},
        ]
    )

    response = client.post("/api/broker-profiles/2/activate")

    assert response.status_code == 200
    rows = fake_supabase.table("broker_profiles").select("id,selected_for_trading").execute().data
    by_id = {row["id"]: row["selected_for_trading"] for row in rows}
    assert by_id == {1: True, 2: True}


def test_deactivate_profile_only_unselects_requested_profile(client: TestClient, fake_supabase):
    fake_supabase.seed_profiles(
        [
            {"id": 1, "name": "ACG-DEMO-3", "is_active": True, "selected_for_trading": True, "venue": "metaapi_mt5"},
            {"id": 2, "name": "FTMO - TRAIL - 50K", "is_active": True, "selected_for_trading": True, "venue": "ctrader"},
        ]
    )

    response = client.put("/api/broker-profiles/2", json={"is_active": False})

    assert response.status_code == 200
    rows = fake_supabase.table("broker_profiles").select("id,is_active,selected_for_trading").execute().data
    by_id = {row["id"]: (row["is_active"], row["selected_for_trading"]) for row in rows}
    assert by_id[1] == (True, True)
    assert by_id[2] == (False, False)
```

- [ ] **Step 2: Run the tests to verify current exclusive behavior fails**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_broker_profiles_activation.py -v
```

Expected: FAIL because activation currently clears `selected_for_trading` on the first profile.

- [ ] **Step 3: Update activation semantics in `src/api_broker_profiles.py`**

```python
@router.post("/{profile_id}/activate", response_model=BrokerProfileResponse)
def activate_broker_profile(profile_id: int):
    """
    Mark this profile as trading-enabled without affecting other enabled profiles.
    """
    try:
        sb = _get_supabase()
        check = (
            sb.table("broker_profiles")
            .select("id, is_active, venue, selected_for_trading")
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        rows = check.data or []
        if not rows:
            raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
        if not rows[0].get("is_active", True):
            raise HTTPException(status_code=409, detail="Cannot activate a disabled profile")

        sb.table("broker_profiles").update({"selected_for_trading": True}).eq("id", profile_id).execute()

        resp = (
            sb.table("broker_profiles")
            .select(_SELECT)
            .eq("id", profile_id)
            .limit(1)
            .execute()
        )
        return _to_response((resp.data or [])[0])
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("activate_broker_profile error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
```

- [ ] **Step 4: Keep deactivation scoped to the requested profile and update comments**

```python
# When disabling a profile, also unset selected_for_trading for that same row
# so the account stops participating in execution without affecting peers.
if body.is_active is False:
    patch["selected_for_trading"] = False
```

- [ ] **Step 5: Run the focused tests again**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_broker_profiles_activation.py -v
```

Expected: PASS with both profiles able to remain selected after activation.

- [ ] **Step 6: Commit the activation change**

```bash
git add src/api_broker_profiles.py tests/test_api_broker_profiles_activation.py
git commit -m "DEV-209: allow multi-account activation"
```

## Task 2: Add a Reusable Venue-Aware Adapter Resolver

**Files:**
- Modify: `src/adapters/execution/router.py`
- Modify: `src/core/broker_profiles.py`
- Test: `tests/test_account_orchestrator_profiles.py`

- [ ] **Step 1: Write the failing resolver tests**

```python
from src.adapters.execution.router import get_profile_adapter
from src.core.broker_profiles import get_active_profiles


def test_get_profile_adapter_returns_ctrader_adapter_for_ctrader_profile():
    adapter = get_profile_adapter(
        {
            "name": "FTMO - TRAIL - 50K",
            "venue": "ctrader",
            "token": "refresh-token",
            "meta_api_account_id": "17093647",
            "run_mode": "LIVE",
        }
    )

    assert adapter.__class__.__name__ == "CTraderAdapter"


def test_get_profile_adapter_returns_metaapi_adapter_for_metaapi_profile():
    adapter = get_profile_adapter(
        {
            "name": "ACG-DEMO-3",
            "venue": "metaapi_mt5",
            "token": "metaapi-token",
            "meta_api_account_id": "90f46635-c700-436b-91fd-a12e45ca7ca4",
            "run_mode": "LIVE",
        }
    )

    assert adapter.__class__.__name__ == "MetaApiAdapter"


def test_get_active_profiles_only_returns_selected_profiles(fake_supabase, monkeypatch):
    fake_supabase.seed_profiles(
        [
            {"id": 1, "name": "ACG-DEMO-3", "venue": "metaapi_mt5", "is_active": True, "selected_for_trading": True, "token": "token-1", "meta_api_account_id": "acct-1"},
            {"id": 2, "name": "FTMO - TRAIL - 50K", "venue": "ctrader", "is_active": True, "selected_for_trading": True, "token": "token-2", "meta_api_account_id": "17093647"},
            {"id": 3, "name": "ACG-DEMO-2", "venue": "metaapi_mt5", "is_active": True, "selected_for_trading": False, "token": "token-3", "meta_api_account_id": "acct-3"},
        ]
    )

    profiles = get_active_profiles()

    assert [profile["name"] for profile in profiles] == ["ACG-DEMO-3", "FTMO - TRAIL - 50K"]
```
```

- [ ] **Step 2: Run the resolver tests**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_account_orchestrator_profiles.py -k get_profile_adapter -v
```

Expected: FAIL because `get_profile_adapter` does not exist yet and `get_active_profiles()` still returns non-selected active profiles.

- [ ] **Step 3: Extract adapter selection into a reusable helper in `src/adapters/execution/router.py`**

```python
def get_profile_adapter(profile: Dict[str, Any], settings: Settings | None = None) -> ExecutionAdapter:
    if not profile or not isinstance(profile, dict):
        raise ValueError("profile is required")

    adapter = get_adapter(settings=settings, profile=profile)
    if adapter.__class__.__name__ in {"DryRunAdapter", "LiveAdapter"}:
        raise ValueError(
            f"Could not resolve broker adapter for profile {profile.get('name') or profile.get('id')}"
        )
    return adapter
```

- [ ] **Step 4: Make execution fan-out honor `selected_for_trading` in `src/core/broker_profiles.py`**

```python
r = (
    client.table("broker_profiles")
    .select(
        "id, name, venue, meta_api_account_id, token, token_env_key, "
        "api_key, api_secret, risk_pct, max_positions, run_mode, "
        "evaluation_mode, evaluation_phase, consistency_enabled"
    )
    .eq("is_active", True)
    .eq("selected_for_trading", True)
    .execute()
)
```

- [ ] **Step 5: Run the resolver tests again**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_account_orchestrator_profiles.py -k get_profile_adapter -v
```

Expected: PASS with cTrader profiles resolving to `CTraderAdapter` and MetaAPI profiles to `MetaApiAdapter`.

- [ ] **Step 6: Commit the router helper and selected-profile filter**

```bash
git add src/adapters/execution/router.py src/core/broker_profiles.py tests/test_account_orchestrator_profiles.py
git commit -m "DEV-209: route only selected active broker profiles"
```

## Task 3: Make Dashboard Standalone Profiles Venue-Aware

**Files:**
- Modify: `src/services/account_orchestrator.py`
- Test: `tests/test_account_orchestrator_profiles.py`

- [ ] **Step 1: Write the failing orchestrator tests**

```python
def test_standalone_ctrader_profile_uses_profile_adapter(fake_supabase, monkeypatch):
    orchestrator = AccountOrchestrator(fake_supabase)
    profile = {
        "id": 2,
        "name": "FTMO - TRAIL - 50K",
        "venue": "ctrader",
        "token": "refresh-token",
        "meta_api_account_id": "17093647",
        "run_mode": "LIVE",
        "selected_for_trading": True,
    }

    class FakeAdapter:
        def get_account_information(self):
            return {
                "balance": 50000.0,
                "equity": 50120.0,
                "freeMargin": 49000.0,
                "margin": 1120.0,
                "leverage": 100,
                "platform": "ctrader",
                "broker": "FTMO",
            }

        def get_open_positions(self):
            return [{"positionId": "123"}]

    monkeypatch.setattr("src.services.account_orchestrator.get_profile_adapter", lambda profile, settings=None: FakeAdapter())

    snapshot = orchestrator._fetch_live_profile_snapshot(profile)

    assert snapshot["balance"] == 50000.0
    assert snapshot["equity"] == 50120.0
    assert snapshot["platform_type"] == "ctrader"
    assert snapshot["open_positions"] == 1


def test_profile_snapshot_failure_isolated_per_profile(fake_supabase, monkeypatch):
    orchestrator = AccountOrchestrator(fake_supabase)
    good = {"id": 1, "name": "ACG-DEMO-3", "venue": "metaapi_mt5", "selected_for_trading": True}
    bad = {"id": 2, "name": "FTMO - TRAIL - 50K", "venue": "ctrader", "selected_for_trading": True}

    def fake_fetch(profile):
        if profile["name"] == "FTMO - TRAIL - 50K":
            raise RuntimeError("ctrader unavailable")
        return {
            "balance": 49000.0,
            "equity": 49000.0,
            "free_margin": 48000.0,
            "margin_used": 1000.0,
            "margin_level_pct": 4900.0,
            "server_name": "MetaAPI",
            "platform_type": "mt5",
            "leverage": 100,
            "last_sync_time": None,
            "connection_status": "connected",
            "open_positions": 0,
        }

    monkeypatch.setattr(orchestrator, "_fetch_live_profile_snapshot", fake_fetch)
```

- [ ] **Step 2: Run the orchestrator tests**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_account_orchestrator_profiles.py -v
```

Expected: FAIL because snapshots do not currently expose open-position counts and do not use a reusable profile adapter helper.

- [ ] **Step 3: Update `_fetch_live_profile_snapshot` to use `get_profile_adapter` and return open-position counts**

```python
from src.adapters.execution.router import get_profile_adapter


adapter = get_profile_adapter(profile_for_adapter, settings=get_settings())

if hasattr(adapter, "get_account_information"):
    account_info = adapter.get_account_information()
    ...

open_positions = []
if hasattr(adapter, "get_open_positions"):
    try:
        open_positions = adapter.get_open_positions() or []
    except Exception as exc:
        logger.warning("Failed to fetch open positions for standalone profile %s: %s", profile.get("name"), exc)
result["open_positions"] = len(open_positions)
```

- [ ] **Step 4: Propagate the open-position count into comparison entries**

```python
"open_positions": live_data["open_positions"],
"active_positions": live_data["open_positions"],
```

- [ ] **Step 5: Run the orchestrator tests again**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_account_orchestrator_profiles.py -v
```

Expected: PASS with cTrader and MetaAPI standalone profiles both producing live card data.

- [ ] **Step 6: Commit the orchestrator changes**

```bash
git add src/services/account_orchestrator.py tests/test_account_orchestrator_profiles.py
git commit -m "DEV-209: make dashboard profile snapshots venue-aware"
```

## Task 4: Replace MetaAPI-Only Portfolio Position Fetching

**Files:**
- Modify: `src/api_portfolio_control.py`
- Test: `tests/test_api_portfolio_control_positions.py`

- [ ] **Step 1: Write the failing portfolio-control tests**

```python
def test_account_positions_use_ctrader_adapter_for_ctrader_profiles(client, fake_supabase, monkeypatch):
    fake_supabase.seed_active_profiles(
        [
            {
                "id": 2,
                "name": "FTMO - TRAIL - 50K",
                "venue": "ctrader",
                "token": "refresh-token",
                "meta_api_account_id": "17093647",
                "selected_for_trading": True,
                "is_active": True,
            }
        ]
    )

    class FakeAdapter:
        def get_open_positions(self):
            return [{"positionId": "321", "tradeSide": "BUY"}]

    monkeypatch.setattr("src.api_portfolio_control.get_profile_adapter", lambda profile, settings=None: FakeAdapter())

    response = client.get("/api/portfolio-control/accounts/FTMO%20-%20TRAIL%20-%2050K/positions")

    assert response.status_code == 200
    assert len(response.json()["broker_positions"]) == 1


def test_account_positions_do_not_require_metaapi_for_ctrader(client, fake_supabase, monkeypatch):
    fake_supabase.seed_active_profiles(
        [
            {
                "id": 2,
                "name": "FTMO - TRAIL - 50K",
                "venue": "ctrader",
                "token": "refresh-token",
                "meta_api_account_id": "17093647",
                "selected_for_trading": True,
                "is_active": True,
            }
        ]
    )

    monkeypatch.setattr(
        "src.api_portfolio_control.MetaApiAdapter",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("MetaApiAdapter should not be used")),
    )
```

- [ ] **Step 2: Run the portfolio-control tests**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_portfolio_control_positions.py -v
```

Expected: FAIL because the endpoint currently instantiates `MetaApiAdapter` directly.

- [ ] **Step 3: Replace direct MetaAPI construction with `get_profile_adapter`**

```python
from src.adapters.execution.router import get_profile_adapter
from src.core.broker_profiles import get_active_profiles

profiles = get_active_profiles()
profile = next((p for p in profiles if p.get("name") == account_name), None)
if profile:
    adapter = get_profile_adapter(profile)
    if hasattr(adapter, "get_open_positions"):
        broker_raw = adapter.get_open_positions() or []
```

- [ ] **Step 4: Normalize cTrader and MetaAPI open-position IDs in the reconciliation loop**

```python
broker_id = str(
    bp.get("id")
    or bp.get("positionId")
    or bp.get("broker_order_id")
    or ""
)
pos_type = str(bp.get("type") or bp.get("tradeSide") or "").upper()
side = "buy" if "BUY" in pos_type else "sell"
```

- [ ] **Step 5: Run the portfolio-control tests again**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_portfolio_control_positions.py -v
```

Expected: PASS with cTrader accounts using the cTrader adapter path.

- [ ] **Step 6: Commit the portfolio-control changes**

```bash
git add src/api_portfolio_control.py tests/test_api_portfolio_control_positions.py
git commit -m "DEV-209: route portfolio positions by broker venue"
```

## Task 5: Full Regression Pass for Multi-Account Visibility and Isolation

**Files:**
- Modify: `src/api_broker_profiles.py`
- Modify: `src/services/account_orchestrator.py`
- Modify: `src/api_portfolio_control.py`
- Modify: `src/core/broker_profiles.py`
- Modify: `src/adapters/execution/router.py`
- Test: `tests/test_api_broker_profiles_activation.py`
- Test: `tests/test_account_orchestrator_profiles.py`
- Test: `tests/test_api_portfolio_control_positions.py`

- [ ] **Step 1: Run the focused regression suite**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest \
  tests/test_api_broker_profiles_activation.py \
  tests/test_account_orchestrator_profiles.py \
  tests/test_api_portfolio_control_positions.py -v
```

Expected: PASS.

- [ ] **Step 2: Run a broader safety pass around existing account/risk views**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. pytest tests/test_api_risk_monitor.py -v
```

Expected: PASS and no regression in selected-profile reporting.

- [ ] **Step 3: Manually verify the approved user flow**

Run:

```bash
source ./venv/bin/activate && PYTHONPATH=. python3 -m uvicorn src.api:app --host 0.0.0.0 --port 8000
```

Then verify in the UI:

- activate `ACG-DEMO-3`
- activate `FTMO - TRAIL - 50K`
- refresh dashboard
- confirm both cards remain visible
- confirm FTMO no longer throws `METAAPI_AUTH_FAILED` in the dashboard data path

- [ ] **Step 4: Commit the verification-ready integration changes**

```bash
git add src/api_broker_profiles.py src/services/account_orchestrator.py src/api_portfolio_control.py src/adapters/execution/router.py \
  src/core/broker_profiles.py \
  tests/test_api_broker_profiles_activation.py tests/test_account_orchestrator_profiles.py tests/test_api_portfolio_control_positions.py
git commit -m "DEV-209: support multi-account activation with ctrader parity"
```
