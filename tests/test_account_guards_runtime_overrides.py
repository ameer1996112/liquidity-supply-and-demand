from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sys
import types


import src.pipeline
_MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "pipeline" / "account_guards.py"
_ACCOUNT_STATE = types.ModuleType("src.pipeline.account_state")
_ACCOUNT_STATE.get_account_daily_pnl = lambda profile: 0.0
_ACCOUNT_STATE.get_account_daily_trade_count = lambda profile: 0
_ACCOUNT_STATE.get_account_weekly_pnl = lambda profile: 0.0
_ACCOUNT_STATE.get_account_monthly_pnl = lambda profile: 0.0
_ACCOUNT_STATE.get_account_positions_from_db = lambda profile: []
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
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_signal_guards", lambda *args, **kwargs: (True, None), raising=False)

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
        lambda account_id: {
            "mtm_guardian_enabled": False,
            "pine_adaptive_enabled": False,
            "pine_max_trades_per_day": 1,
        },
    )
    monkeypatch.setattr(_ACCOUNT_GUARDS, "_get_sb", lambda: None)
    monkeypatch.setattr("src.adapters.redis_queue.get_redis", lambda: SimpleNamespace(get=lambda key: None))
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_daily_trade_count", lambda profile: 1)
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_daily_pnl", lambda profile: 0.0)
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_positions_from_db", lambda profile: [])
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_safety", lambda *args, **kwargs: (True, 1.0, "ok"))
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_signal_guards", lambda *args, **kwargs: (True, None), raising=False)

    result = run_account_guards(
        payload={"symbol": "EURUSD", "side": "buy", "run_mode": "LIVE", "account_balance": 50000},
        profile={"id": "acct-1", "name": "ACG-DEMO-3", "risk_pct": 0.5, "max_positions": 3},
        s=_settings(),
        current_equity_global=50000,
        correlation_manager=None,
    )
    assert result == "Daily trade limit reached (ACG-DEMO-3): 1/1 trades today"


def test_account_override_changes_correlation_limit(monkeypatch):
    monkeypatch.setattr(
        _ACCOUNT_GUARDS,
        "load_account_guard_overrides",
        lambda account_id: {"mtm_guardian_enabled": False, "trinity_max_positions": 1},
    )
    monkeypatch.setattr(_ACCOUNT_GUARDS, "_get_sb", lambda: None)
    monkeypatch.setattr("src.adapters.redis_queue.get_redis", lambda: SimpleNamespace(get=lambda key: None))
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_daily_pnl", lambda profile: 0.0)
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_positions_from_db", lambda profile: [object()])
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_safety", lambda *args, **kwargs: (True, 1.0, "ok"))
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_signal_guards", lambda *args, **kwargs: (True, None), raising=False)

    result = run_account_guards(
        payload={"symbol": "EURUSD", "side": "buy", "run_mode": "LIVE", "account_balance": 50000},
        profile={"id": "acct-1", "name": "ACG-DEMO-3", "risk_pct": 0.5},
        s=_settings(trinity_max_positions=3),
        current_equity_global=50000,
        correlation_manager=None,
    )
    assert result == "Bucket Full (ACG-DEMO-3): 1/1"


def test_evaluation_signal_guards_can_block_account(monkeypatch):
    monkeypatch.setattr(_ACCOUNT_GUARDS, "load_account_guard_overrides", lambda account_id: {})
    monkeypatch.setattr(_ACCOUNT_GUARDS, "_get_sb", lambda: object())
    monkeypatch.setattr("src.adapters.redis_queue.get_redis", lambda: SimpleNamespace(get=lambda key: None))
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_daily_pnl", lambda profile: 0.0)
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_positions_from_db", lambda profile: [])
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_safety", lambda *args, **kwargs: (True, 1.0, "ok"))

    captured = {}

    def _fake_signal_guards(payload, supabase=None, **kwargs):
        captured["payload"] = payload
        captured["supabase"] = supabase
        captured["kwargs"] = kwargs
        return False, "RR ratio 1.00 below minimum 1.5 (phase1)"

    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_signal_guards", _fake_signal_guards, raising=False)

    result = run_account_guards(
        payload={
            "symbol": "EURUSD",
            "side": "buy",
            "run_mode": "LIVE",
            "account_balance": 50000,
            "rr_ratio": 1.0,
        },
        profile={"id": "acct-1", "name": "ACG-DEMO-3", "risk_pct": 0.5, "max_positions": 3, "evaluation_mode": True},
        s=_settings(evaluation_mode=True),
        current_equity_global=50000,
        correlation_manager=None,
    )

    assert result == "SignalGuard (ACG-DEMO-3): RR ratio 1.00 below minimum 1.5 (phase1)"
    assert captured["kwargs"]["profile"]["id"] == "acct-1"


def test_live_eval_blocks_when_consistency_analyzer_crashes(monkeypatch):
    monkeypatch.setattr(
        _ACCOUNT_GUARDS,
        "load_account_guard_overrides",
        lambda account_id: {"mtm_guardian_enabled": False, "pine_adaptive_enabled": False},
    )
    monkeypatch.setattr(_ACCOUNT_GUARDS, "_get_sb", lambda: object())
    monkeypatch.setattr("src.adapters.redis_queue.get_redis", lambda: SimpleNamespace(get=lambda key: None))
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_daily_pnl", lambda profile: 0.0)
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_positions_from_db", lambda profile: [])
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_safety", lambda *args, **kwargs: (True, 1.0, "ok"))
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_signal_guards", lambda *args, **kwargs: (True, None), raising=False)

    class _BrokenConsistency:
        def __init__(self, *args, **kwargs):
            pass

        def check_trade_consistency_risk(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr("src.services.consistency_analyzer.ConsistencyAnalyzer", _BrokenConsistency)

    result = run_account_guards(
        payload={
            "symbol": "EURUSD",
            "side": "buy",
            "run_mode": "LIVE",
            "account_balance": 50000,
            "entry": 1.1,
            "tp": 1.12,
            "size": 1.0,
        },
        profile={
            "id": "acct-1",
            "name": "ACG-DEMO-3",
            "risk_pct": 0.5,
            "max_positions": 3,
            "evaluation_mode": True,
            "consistency_enabled": True,
        },
        s=_settings(evaluation_mode=True, consistency_enabled=True),
        current_equity_global=50000,
        correlation_manager=None,
    )

    assert result == "Consistency dependency unavailable for account ACG-DEMO-3 — blocked for safety"


def test_acg_eval_defaults_to_no_consistency_guard(monkeypatch):
    monkeypatch.setattr(
        _ACCOUNT_GUARDS,
        "load_account_guard_overrides",
        lambda account_id: {"mtm_guardian_enabled": False, "pine_adaptive_enabled": False},
    )
    monkeypatch.setattr(_ACCOUNT_GUARDS, "_get_sb", lambda: object())
    monkeypatch.setattr("src.adapters.redis_queue.get_redis", lambda: SimpleNamespace(get=lambda key: None))
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_daily_pnl", lambda profile: 0.0)
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_positions_from_db", lambda profile: [])
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_safety", lambda *args, **kwargs: (True, 1.0, "ok"))
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_signal_guards", lambda *args, **kwargs: (True, None), raising=False)

    class _UnexpectedConsistency:
        def __init__(self, *args, **kwargs):
            raise AssertionError("ACG accounts should skip the consistency analyzer by default")

    monkeypatch.setattr("src.services.consistency_analyzer.ConsistencyAnalyzer", _UnexpectedConsistency)

    result = run_account_guards(
        payload={
            "symbol": "XAUUSD",
            "side": "buy",
            "run_mode": "LIVE",
            "account_balance": 50000,
            "entry": 4647.12,
            "tp": 4689.04,
            "size": 0.1,
        },
        profile={
            "id": "acct-1",
            "name": "ACG-DEMO-3",
            "risk_pct": 0.5,
            "max_positions": 3,
            "evaluation_mode": True,
            "consistency_enabled": None,
        },
        s=_settings(evaluation_mode=True, consistency_enabled=True),
        current_equity_global=50000,
        correlation_manager=None,
    )

    assert result is None


def test_monthly_loss_limit_uses_account_scoped_pnl(monkeypatch):
    monkeypatch.setattr(
        _ACCOUNT_GUARDS,
        "load_account_guard_overrides",
        lambda account_id: {"mtm_guardian_enabled": False, "pine_adaptive_enabled": False},
    )
    monkeypatch.setattr(_ACCOUNT_GUARDS, "_get_sb", lambda: None)
    monkeypatch.setattr("src.adapters.redis_queue.get_redis", lambda: SimpleNamespace(get=lambda key: None))
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_daily_pnl", lambda profile: 0.0)
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_weekly_pnl", lambda profile: 0.0)
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_positions_from_db", lambda profile: [])
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_safety", lambda *args, **kwargs: (True, 1.0, "ok"))
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_signal_guards", lambda *args, **kwargs: (True, None), raising=False)

    captured = {}

    def _fake_monthly_pnl(profile):
        captured["profile"] = profile
        return -100.0

    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_monthly_pnl", _fake_monthly_pnl)

    result = run_account_guards(
        payload={"symbol": "EURUSD", "side": "buy", "run_mode": "LIVE", "account_balance": 50000},
        profile={"id": "acct-1", "name": "ACG-DEMO-3", "risk_pct": 0.5, "max_positions": 3},
        s=_settings(monthly_max_loss_pct=8.0),
        current_equity_global=50000,
        correlation_manager=None,
    )

    assert result is None
    assert captured["profile"]["id"] == "acct-1"


def test_monthly_loss_limit_blocks_when_account_exceeds_limit(monkeypatch):
    monkeypatch.setattr(
        _ACCOUNT_GUARDS,
        "load_account_guard_overrides",
        lambda account_id: {"mtm_guardian_enabled": False, "pine_adaptive_enabled": False},
    )
    monkeypatch.setattr(_ACCOUNT_GUARDS, "_get_sb", lambda: None)
    monkeypatch.setattr("src.adapters.redis_queue.get_redis", lambda: SimpleNamespace(get=lambda key: None))
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_daily_pnl", lambda profile: 0.0)
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_weekly_pnl", lambda profile: 0.0)
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_monthly_pnl", lambda profile: -4334.24)
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_positions_from_db", lambda profile: [])
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_safety", lambda *args, **kwargs: (True, 1.0, "ok"))
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_signal_guards", lambda *args, **kwargs: (True, None), raising=False)

    result = run_account_guards(
        payload={"symbol": "EURUSD", "side": "buy", "run_mode": "LIVE", "account_balance": 50000},
        profile={"id": "acct-1", "name": "ACG-DEMO-3", "risk_pct": 0.5, "max_positions": 3},
        s=_settings(monthly_max_loss_pct=8.0),
        current_equity_global=50000,
        correlation_manager=None,
    )

    assert result == "Monthly loss limit: $-4334.24 loss this month (limit $-4000.00 = 8% of $50000)"


def test_weekly_loss_limit_blocks_when_account_exceeds_limit(monkeypatch):
    monkeypatch.setattr(
        _ACCOUNT_GUARDS,
        "load_account_guard_overrides",
        lambda account_id: {"mtm_guardian_enabled": False, "pine_adaptive_enabled": False},
    )
    monkeypatch.setattr(_ACCOUNT_GUARDS, "_get_sb", lambda: None)
    monkeypatch.setattr("src.adapters.redis_queue.get_redis", lambda: SimpleNamespace(get=lambda key: None))
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_daily_pnl", lambda profile: 0.0)
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_weekly_pnl", lambda profile: -6000.0)
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_monthly_pnl", lambda profile: 0.0)
    monkeypatch.setattr(_ACCOUNT_GUARDS, "get_account_positions_from_db", lambda profile: [])
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_safety", lambda *args, **kwargs: (True, 1.0, "ok"))
    monkeypatch.setattr(_ACCOUNT_GUARDS, "check_signal_guards", lambda *args, **kwargs: (True, None), raising=False)

    result = run_account_guards(
        payload={"symbol": "EURUSD", "side": "buy", "run_mode": "LIVE", "account_balance": 50000},
        profile={"id": "acct-1", "name": "ACG-DEMO-3", "risk_pct": 0.5, "max_positions": 3},
        s=_settings(weekly_max_loss_pct=10.0),
        current_equity_global=50000,
        correlation_manager=None,
    )

    assert result == "Weekly loss limit: $-6000.00 loss this week (limit $-5000.00 = 10% of $50000)"
