import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from src.core.guard_rails.trading_permission_guard import TradingPermissionGuard
from src.worker import _resolve_trading_permission_guard_paths


def _write_permissions(tmp_path, status: str = "TRADE_NORMAL_RISK") -> tuple:
    approved = tmp_path / "approved_candidates.json"
    daily = tmp_path / "daily_trade_permissions.json"
    emergency = tmp_path / "emergency_stop.json"
    approved.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "candidates": {
                    "USDJPY": {
                        "candidate_status": "RESEARCH_APPROVED",
                        "params_hash": "abc123",
                    }
                },
            }
        )
    )
    daily.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "permissions": {
                    "USDJPY": {
                        "status": status,
                        "risk_per_trade_pct": 0.25,
                        "max_trades_today": 1,
                        "session_utc": {"start": 0, "end": 9},
                        "expires_at": "2026-05-05T09:00:00Z",
                        "reasons": ["research approved"],
                    }
                },
            }
        )
    )
    emergency.write_text(json.dumps({"active": False}))
    return approved, daily, emergency


def test_guard_allows_only_explicit_daily_trade_permission(tmp_path) -> None:
    approved, daily, emergency = _write_permissions(tmp_path)
    guard = TradingPermissionGuard(
        approved_candidates_path=approved,
        daily_permissions_path=daily,
        emergency_stop_path=emergency,
        now_provider=lambda: datetime(2026, 5, 5, 8, 0, tzinfo=timezone.utc),
    )

    passed, reason = guard.check({"symbol": "USDJPY", "params_hash": "abc123", "risk_per_trade_pct": 0.2})

    assert passed is True
    assert reason == ""


def test_guard_blocks_watch_only_and_stale_params_hash(tmp_path) -> None:
    approved, daily, emergency = _write_permissions(tmp_path, "WATCH_ONLY")
    guard = TradingPermissionGuard(
        approved_candidates_path=approved,
        daily_permissions_path=daily,
        emergency_stop_path=emergency,
        now_provider=lambda: datetime(2026, 5, 5, 8, 0, tzinfo=timezone.utc),
    )

    passed, reason = guard.check({"symbol": "USDJPY", "params_hash": "wrong", "risk_per_trade_pct": 0.2})

    assert passed is False
    assert "permission_status_not_tradeable" in reason


def test_guard_blocks_excessive_risk_and_outside_session(tmp_path) -> None:
    approved, daily, emergency = _write_permissions(tmp_path)
    guard = TradingPermissionGuard(
        approved_candidates_path=approved,
        daily_permissions_path=daily,
        emergency_stop_path=emergency,
        now_provider=lambda: datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
    )

    passed, reason = guard.check({"symbol": "USDJPY", "params_hash": "abc123", "risk_per_trade_pct": 0.5})

    assert passed is False
    assert "outside_permission_session" in reason


def test_guard_allows_when_optional_approved_candidates_missing(tmp_path) -> None:
    approved, daily, emergency = _write_permissions(tmp_path)
    approved.unlink()
    guard = TradingPermissionGuard(
        approved_candidates_path=approved,
        daily_permissions_path=daily,
        emergency_stop_path=emergency,
        now_provider=lambda: datetime(2026, 5, 5, 8, 0, tzinfo=timezone.utc),
    )

    passed, reason = guard.check({"symbol": "USDJPY", "params_hash": "abc123", "risk_per_trade_pct": 0.2})

    assert passed is True
    assert reason == ""


def test_guard_blocks_when_required_approved_candidates_missing(tmp_path) -> None:
    approved, daily, emergency = _write_permissions(tmp_path)
    approved.unlink()
    guard = TradingPermissionGuard(
        approved_candidates_path=approved,
        daily_permissions_path=daily,
        emergency_stop_path=emergency,
        approved_candidates_required=True,
        now_provider=lambda: datetime(2026, 5, 5, 8, 0, tzinfo=timezone.utc),
    )

    passed, reason = guard.check({"symbol": "USDJPY", "params_hash": "abc123", "risk_per_trade_pct": 0.2})

    assert passed is False
    assert reason == "permission_file_missing:approved_candidates.json"


def test_worker_does_not_require_approved_candidates_just_because_path_is_configured() -> None:
    approved, _, _, required = _resolve_trading_permission_guard_paths(
        SimpleNamespace(
            approved_candidates_file="/app/scripts/optimization_results/approved_candidates.json",
            require_approved_candidates_file=False,
        ),
        default_approved_candidates_path=Path("default-approved.json"),
        default_daily_permissions_path=Path("default-daily.json"),
        default_emergency_stop_path=Path("default-emergency.json"),
    )

    assert approved == "/app/scripts/optimization_results/approved_candidates.json"
    assert required is False


def test_worker_can_explicitly_require_approved_candidates_file() -> None:
    _, _, _, required = _resolve_trading_permission_guard_paths(
        SimpleNamespace(
            approved_candidates_file="/app/scripts/optimization_results/approved_candidates.json",
            require_approved_candidates_file=True,
        ),
        default_approved_candidates_path=Path("default-approved.json"),
        default_daily_permissions_path=Path("default-daily.json"),
        default_emergency_stop_path=Path("default-emergency.json"),
    )

    assert required is True


def test_guard_blocks_when_daily_permissions_missing(tmp_path) -> None:
    approved, daily, emergency = _write_permissions(tmp_path)
    daily.unlink()
    guard = TradingPermissionGuard(
        approved_candidates_path=approved,
        daily_permissions_path=daily,
        emergency_stop_path=emergency,
        now_provider=lambda: datetime(2026, 5, 5, 8, 0, tzinfo=timezone.utc),
    )

    passed, reason = guard.check({"symbol": "USDJPY", "params_hash": "abc123", "risk_per_trade_pct": 0.2})

    assert passed is False
    assert reason == "permission_file_missing:daily_trade_permissions.json"


def test_guard_blocks_when_permissions_empty(tmp_path) -> None:
    approved, daily, emergency = _write_permissions(tmp_path)
    daily.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-05-05T06:00:00Z",
                "account_profile": "alpha_50k_safe",
                "global_decision": "NO_TRADE",
                "permissions": {},
                "blocked": {},
                "watch_only": {},
                "reasons": ["no_research_approved_candidates"],
            }
        )
    )
    guard = TradingPermissionGuard(
        approved_candidates_path=approved,
        daily_permissions_path=daily,
        emergency_stop_path=emergency,
        now_provider=lambda: datetime(2026, 5, 5, 8, 0, tzinfo=timezone.utc),
    )

    passed, reason = guard.check({"symbol": "USDJPY", "params_hash": "abc123", "risk_per_trade_pct": 0.2})

    assert passed is False
    assert reason == "missing_daily_permission"
