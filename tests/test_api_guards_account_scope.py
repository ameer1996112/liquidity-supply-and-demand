from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.api_guards import router


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=True)


def test_global_and_account_guard_sets_are_classified():
    from src.core.guard_rails.guard_registry import get_all_guards

    guards = get_all_guards()
    by_id = {guard.guard_id: guard for guard in guards}

    assert by_id["staleness_guard"].scope == "global"
    assert by_id["daily_loss_limit"].scope == "account"


def test_account_guard_setting_falls_back_to_global_default():
    from src.services.account_guard_settings import get_effective_account_guard_value

    value, source = get_effective_account_guard_value(
        account_id="acct-1",
        setting_key="daily_loss_limit_pct",
        global_default=4,
    )

    assert value == 4
    assert source == "global_default"


def test_account_guard_setting_prefers_account_override():
    from src.services.account_guard_settings import get_effective_account_guard_value

    value, source = get_effective_account_guard_value(
        account_id="acct-1",
        setting_key="daily_loss_limit_pct",
        global_default=4,
        account_overrides={"daily_loss_limit_pct": 2},
    )

    assert value == 2
    assert source == "account"


def test_list_guard_accounts_returns_active_profiles(client, monkeypatch):
    monkeypatch.setattr(
        "src.api_guards.get_active_profiles",
        lambda: [{"id": "acct-1", "name": "ACG-DEMO-2", "run_mode": "LIVE"}],
    )

    response = client.get("/api/v1/guards/accounts")
    assert response.status_code == 200
    assert response.json()["accounts"][0]["id"] == "acct-1"


def test_account_guards_config_filters_to_account_scoped_guards(client, monkeypatch):
    monkeypatch.setattr("src.api_guards._get_rejection_stats", lambda _days=7: {"by_guard": {}, "total_rejections": 0, "total_signals": 0})
    monkeypatch.setattr(
        "src.api_guards.load_account_guard_overrides",
        lambda account_id: {"trinity_max_daily_loss_pct": 2.0} if account_id == "acct-1" else {},
    )

    response = client.get("/api/v1/guards/config/account/acct-1")
    assert response.status_code == 200
    body = response.json()
    assert "capital_protection" in body["groups"]
    returned_ids = {guard["guard_id"] for group in body["groups"].values() for guard in group}
    assert "daily_loss_limit" in returned_ids
    assert "staleness_guard" not in returned_ids


def test_account_guard_thresholds_use_account_overrides(client, monkeypatch):
    monkeypatch.setattr("src.api_guards._get_rejection_stats", lambda _days=7: {"by_guard": {}, "total_rejections": 0, "total_signals": 0})
    monkeypatch.setattr(
        "src.api_guards.load_account_guard_overrides",
        lambda account_id: {"weekly_max_loss_pct": 3.5} if account_id == "acct-1" else {},
    )

    response = client.get("/api/v1/guards/config/account/acct-1")
    assert response.status_code == 200
    body = response.json()
    weekly_guard = next(
        guard
        for group in body["groups"].values()
        for guard in group
        if guard["guard_id"] == "weekly_loss_limit"
    )
    threshold_values = {th["setting_key"]: th["current_value"] for th in weekly_guard["thresholds"]}
    assert threshold_values["weekly_max_loss_pct"] == 3.5


def test_patch_account_guard_does_not_update_global_setting(client, monkeypatch):
    monkeypatch.setattr("src.api_guards.load_account_guard_overrides", lambda account_id: {})
    monkeypatch.setattr(
        "src.api_guards.update_account_guard_override",
        lambda account_id, setting_key, value: {setting_key: value},
    )
    monkeypatch.setattr("src.api_guards.log_event", lambda *args, **kwargs: None)

    response = client.patch(
        "/api/v1/guards/config/account/acct-1/daily_loss_limit",
        json={"value": 2, "change_reason": "test"},
    )
    assert response.status_code == 200
    assert response.json()["guard_id"] == "daily_loss_limit"
    assert response.json()["new_value"] == 2


def test_patch_account_guard_persists_threshold_overrides(client, monkeypatch):
    captured: dict[str, object] = {}
    monkeypatch.setattr("src.api_guards.load_account_guard_overrides", lambda account_id: {})
    monkeypatch.setattr(
        "src.api_guards.update_account_guard_override",
        lambda account_id, setting_key, value: captured.setdefault("settings", {}) or {"noop": True},
    )
    monkeypatch.setattr("src.api_guards.log_event", lambda *args, **kwargs: None)

    def _capture(account_id, setting_key, value):
        captured.setdefault("updates", []).append((account_id, setting_key, value))
        return {setting_key: value}

    monkeypatch.setattr("src.api_guards.update_account_guard_override", _capture)

    response = client.patch(
        "/api/v1/guards/config/account/acct-1/weekly_loss_limit",
        json={
            "value": True,
            "thresholds": {"weekly_max_loss_pct": 3.5},
            "change_reason": "test",
        },
    )
    assert response.status_code == 200
    assert ("acct-1", "enable_weekly_loss_limit", True) in captured["updates"]
    assert ("acct-1", "weekly_max_loss_pct", 3.5) in captured["updates"]
