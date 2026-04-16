from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sys
import types


_MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "pipeline" / "account_guards.py"
_PIPELINE_PKG = types.ModuleType("src.pipeline")
_ACCOUNT_STATE = types.ModuleType("src.pipeline.account_state")
_ACCOUNT_STATE.get_account_daily_pnl = lambda profile: 0.0
_ACCOUNT_STATE.get_account_daily_trade_count = lambda profile: 0
_ACCOUNT_STATE.get_account_positions_from_db = lambda profile: []
sys.modules.setdefault("src.pipeline", _PIPELINE_PKG)
sys.modules["src.pipeline.account_state"] = _ACCOUNT_STATE
_SPEC = importlib.util.spec_from_file_location("account_guards_runtime_module", _MODULE_PATH)
_ACCOUNT_GUARDS = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(_ACCOUNT_GUARDS)
run_account_guards = _ACCOUNT_GUARDS.run_account_guards


def _settings(**overrides):
    base = {
        "risk_percent": 0.5,
        "account_balance": 50000.0,
        "mtm_guardian_enabled": True,
        "pine_max_trades_per_day": 2,
        "pine_adaptive_enabled": True,
        "pine_daily_risk_budget_pct": 3.0,
        "trinity_max_positions": 3,
        "consistency_enabled": True,
        "evaluation_mode": False,
        "enable_risk_scaling": True,
        "trinity_max_daily_loss_pct": 4.0,
        "trinity_max_drawdown_pct": 8.0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_account_override_disables_mtm_guardian(monkeypatch):
    monkeypatch.setattr(_ACCOUNT_GUARDS, "load_account_guard_overrides", lambda account_id: {"mtm_guardian_enabled": False})
    monkeypatch.setattr(_ACCOUNT_GUARDS, "_get_sb", lambda: object())
    monkeypatch.setattr("src.adapters.redis_queue.get_redis", lambda: SimpleNamespace(get=lambda key: None))
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_daily_pnl", lambda profile: 0.0)
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_positions_from_db", lambda profile: [])
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_safety", lambda *args, **kwargs: (True, 1.0, "ok"))

    called = {"mtm": 0}

    class _MTM:
        def __init__(self, *args, **kwargs):
            called["mtm"] += 1

        def check_kill_switch(self, **kwargs):
            return False, ""

    monkeypatch.setattr("src.services.mtm_guardian.MTMGuardian", _MTM)

    result = run_account_guards(
        payload={"symbol": "EURUSD", "side": "buy", "run_mode": "LIVE", "account_balance": 50000},
        profile={"id": "acct-1", "name": "ACG-DEMO-3", "risk_pct": 0.5, "max_positions": 3},
        s=_settings(),
        current_equity_global=50000,
        correlation_manager=None,
    )
    assert result is None
    assert called["mtm"] == 0


def test_account_override_blocks_on_static_daily_trade_limit(monkeypatch):
    monkeypatch.setattr(
        _ACCOUNT_GUARDS,
        "load_account_guard_overrides",
        lambda account_id: {"pine_adaptive_enabled": False, "pine_max_trades_per_day": 1},
    )
    monkeypatch.setattr(_ACCOUNT_GUARDS, "_get_sb", lambda: None)
    monkeypatch.setattr("src.adapters.redis_queue.get_redis", lambda: SimpleNamespace(get=lambda key: None))
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_daily_trade_count", lambda profile: 1)
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_daily_pnl", lambda profile: 0.0)
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_positions_from_db", lambda profile: [])
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_safety", lambda *args, **kwargs: (True, 1.0, "ok"))

    result = run_account_guards(
        payload={"symbol": "EURUSD", "side": "buy", "run_mode": "LIVE", "account_balance": 50000},
        profile={"id": "acct-1", "name": "ACG-DEMO-3", "risk_pct": 0.5, "max_positions": 3},
        s=_settings(),
        current_equity_global=50000,
        correlation_manager=None,
    )
    assert result == "Daily trade limit reached (ACG-DEMO-3): 1/1 trades today"


def test_account_override_changes_correlation_limit(monkeypatch):
    monkeypatch.setattr(_ACCOUNT_GUARDS, "load_account_guard_overrides", lambda account_id: {"trinity_max_positions": 1})
    monkeypatch.setattr(_ACCOUNT_GUARDS, "_get_sb", lambda: None)
    monkeypatch.setattr("src.adapters.redis_queue.get_redis", lambda: SimpleNamespace(get=lambda key: None))
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_daily_pnl", lambda profile: 0.0)
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_positions_from_db", lambda profile: [object()])
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_safety", lambda *args, **kwargs: (True, 1.0, "ok"))

    result = run_account_guards(
        payload={"symbol": "EURUSD", "side": "buy", "run_mode": "LIVE", "account_balance": 50000},
        profile={"id": "acct-1", "name": "ACG-DEMO-3", "risk_pct": 0.5},
        s=_settings(trinity_max_positions=3),
        current_equity_global=50000,
        correlation_manager=None,
    )
    assert result == "Bucket Full (ACG-DEMO-3): 1/1"
