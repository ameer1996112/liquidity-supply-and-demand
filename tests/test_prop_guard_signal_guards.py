from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import config
import src.core.dynamic_config as dynamic_config_mod

from src.core.guard_rails.prop_guard import check_signal_guards


class _FakeQuery:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.filters: list[tuple[str, str, object]] = []

    def select(self, *_args, **_kwargs):
        return self

    def in_(self, column: str, values):
        self.filters.append(("in", column, tuple(values)))
        return self

    @property
    def not_(self):
        return self

    def is_(self, column: str, value):
        self.filters.append(("not_is", column, value))
        return self

    def order(self, column: str, desc: bool = False):
        self.filters.append(("order", column, desc))
        return self

    def limit(self, value: int):
        self.filters.append(("limit", "__limit__", value))
        return self

    def eq(self, column: str, value):
        self.filters.append(("eq", column, value))
        return self

    def execute(self):
        rows = list(self._rows)
        for op, column, value in self.filters:
            if op == "eq":
                rows = [row for row in rows if row.get(column) == value]
            elif op == "in":
                rows = [row for row in rows if row.get(column) in value]
            elif op == "not_is":
                rows = [row for row in rows if row.get(column) is not None]

        order_ops = [f for f in self.filters if f[0] == "order"]
        if order_ops:
            _, column, desc = order_ops[-1]
            rows = sorted(rows, key=lambda row: row.get(column), reverse=bool(desc))

        limit_ops = [f for f in self.filters if f[0] == "limit"]
        if limit_ops:
            rows = rows[: int(limit_ops[-1][2])]

        return SimpleNamespace(data=rows)


class _FakeSupabase:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.last_query: _FakeQuery | None = None

    def table(self, _name: str) -> _FakeQuery:
        self.last_query = _FakeQuery(self._rows)
        return self.last_query


def _settings(**overrides):
    base = {
        "evaluation_mode": True,
        "evaluation_phase": "phase1",
        "min_rr_ratio": 0.0,
        "max_consecutive_losses": 5,
        "consec_loss_pause_hours": 2.0,
        "consec_loss_min_streak_pct": 1.0,
        "account_balance": 10000.0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _patch_settings(monkeypatch, **overrides):
    """Patch both get_settings and get_dynamic_setting to use test values."""
    s = _settings(**overrides)
    monkeypatch.setattr(config, "get_settings", lambda: s)
    monkeypatch.setattr(
        dynamic_config_mod,
        "get_dynamic_setting",
        lambda key, default=None: getattr(s, key, default),
    )


def test_check_signal_guards_uses_latest_account_trades_for_loss_pause(monkeypatch):
    """Win in the middle of the streak breaks the consecutive count — should allow."""
    now = datetime.now(timezone.utc)
    rows = [
        {
            "broker_profile_id": "acct-1",
            "account_name": "ACG-1",
            "status": "closed",
            "outcome": "loss",
            "pnl_usd": -50.0,
            "exit_time": (now - timedelta(minutes=30)).isoformat(),
        },
        {
            "broker_profile_id": "acct-1",
            "account_name": "ACG-1",
            "status": "closed",
            "outcome": "win",
            "pnl_usd": 35.0,
            "exit_time": (now - timedelta(hours=1)).isoformat(),
        },
        {
            "broker_profile_id": "acct-1",
            "account_name": "ACG-1",
            "status": "closed",
            "outcome": "loss",
            "pnl_usd": -25.0,
            "exit_time": (now - timedelta(hours=2)).isoformat(),
        },
    ]
    sb = _FakeSupabase(rows)
    _patch_settings(monkeypatch, max_consecutive_losses=2)

    allowed, reason = check_signal_guards(
        {"rr_ratio": 2.0, "account_balance": 10000.0},
        sb,
        profile={"id": "acct-1", "name": "ACG-1"},
    )

    assert allowed is True
    assert reason is None
    assert sb.last_query is not None
    assert ("eq", "broker_profile_id", "acct-1") in sb.last_query.filters


def test_circuit_breaker_auto_resumes_after_cooldown(monkeypatch):
    """After cooldown expires, trading should resume even if last N trades are still losses."""
    now = datetime.now(timezone.utc)
    # 5 consecutive losses, but the last one was 3 hours ago (cooldown is 2h)
    rows = [
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -30.0,
         "exit_time": (now - timedelta(hours=3)).isoformat(), "account_name": "ACG-1"},
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -25.0,
         "exit_time": (now - timedelta(hours=4)).isoformat(), "account_name": "ACG-1"},
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -20.0,
         "exit_time": (now - timedelta(hours=5)).isoformat(), "account_name": "ACG-1"},
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -15.0,
         "exit_time": (now - timedelta(hours=6)).isoformat(), "account_name": "ACG-1"},
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -10.0,
         "exit_time": (now - timedelta(hours=7)).isoformat(), "account_name": "ACG-1"},
    ]
    sb = _FakeSupabase(rows)
    _patch_settings(monkeypatch)

    allowed, reason = check_signal_guards(
        {"rr_ratio": 2.0, "account_balance": 10000.0},
        sb,
        profile={"id": "acct-1", "name": "ACG-1"},
    )

    # Cooldown (2h) has passed since last loss (3h ago) → should auto-resume
    assert allowed is True
    assert reason is None


def test_circuit_breaker_consumes_expired_streak_before_counting_new_losses(monkeypatch):
    """After serving cooldown, old losses should not combine with one fresh loss."""
    now = datetime.now(timezone.utc)
    rows = [
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -129.34,
         "exit_time": (now - timedelta(minutes=30)).isoformat(), "account_name": "ACG-DEMO-3"},
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -127.64,
         "exit_time": (now - timedelta(days=3)).isoformat(), "account_name": "ACG-DEMO-3"},
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -127.46,
         "exit_time": (now - timedelta(days=5)).isoformat(), "account_name": "ACG-DEMO-3"},
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -360.05,
         "exit_time": (now - timedelta(days=6)).isoformat(), "account_name": "ACG-DEMO-3"},
        {"broker_profile_id": "acct-1", "outcome": "win", "pnl_usd": 275.35,
         "exit_time": (now - timedelta(days=7)).isoformat(), "account_name": "ACG-DEMO-3"},
    ]
    sb = _FakeSupabase(rows)
    _patch_settings(
        monkeypatch,
        max_consecutive_losses=3,
        consec_loss_pause_hours=4.0,
        consec_loss_min_streak_pct=0.0,
    )

    allowed, reason = check_signal_guards(
        {"rr_ratio": 2.0, "account_balance": 10000.0},
        sb,
        profile={"id": "acct-1", "name": "ACG-DEMO-3"},
    )

    assert allowed is True
    assert reason is None


def test_circuit_breaker_blocks_during_cooldown(monkeypatch):
    """During cooldown period, trading should be blocked."""
    now = datetime.now(timezone.utc)
    # 5 consecutive losses, last one 30 min ago (within 2h cooldown)
    rows = [
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -30.0,
         "exit_time": (now - timedelta(minutes=30)).isoformat(), "account_name": "ACG-1"},
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -25.0,
         "exit_time": (now - timedelta(hours=1)).isoformat(), "account_name": "ACG-1"},
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -20.0,
         "exit_time": (now - timedelta(hours=2)).isoformat(), "account_name": "ACG-1"},
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -15.0,
         "exit_time": (now - timedelta(hours=3)).isoformat(), "account_name": "ACG-1"},
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -10.0,
         "exit_time": (now - timedelta(hours=4)).isoformat(), "account_name": "ACG-1"},
    ]
    sb = _FakeSupabase(rows)
    _patch_settings(monkeypatch)

    allowed, reason = check_signal_guards(
        {"rr_ratio": 2.0, "account_balance": 10000.0},
        sb,
        profile={"id": "acct-1", "name": "ACG-1"},
    )

    assert allowed is False
    assert "Circuit breaker" in reason
    assert "consecutive losses" in reason


def test_circuit_breaker_message_labels_cooldown_separately_from_remaining(monkeypatch):
    """Stored rejection should include reset time, not only stale remaining time."""
    now = datetime.now(timezone.utc)
    rows = [
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -300.0,
         "exit_time": (now - timedelta(minutes=24)).isoformat(), "account_name": "ACG-DEMO-3"},
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -250.0,
         "exit_time": (now - timedelta(minutes=40)).isoformat(), "account_name": "ACG-DEMO-3"},
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -231.0,
         "exit_time": (now - timedelta(minutes=55)).isoformat(), "account_name": "ACG-DEMO-3"},
    ]
    sb = _FakeSupabase(rows)
    _patch_settings(
        monkeypatch,
        max_consecutive_losses=3,
        consec_loss_pause_hours=4.0,
    )

    allowed, reason = check_signal_guards(
        {"rr_ratio": 2.0, "account_balance": 10000.0},
        sb,
        profile={"id": "acct-1", "name": "ACG-DEMO-3"},
    )

    assert allowed is False
    assert reason is not None
    reset_at = datetime.fromisoformat(rows[0]["exit_time"]) + timedelta(hours=4)
    assert "$781 total" in reason
    assert "paused 3.6h remaining" in reason
    assert f"until {reset_at.strftime('%Y-%m-%d %H:%M UTC')}" in reason
    assert "remaining at rejection" in reason
    assert "from last close" in reason
    assert "4.0h cooldown" in reason
    assert "resets after 4.0h" not in reason


def test_circuit_breaker_skips_small_losses(monkeypatch):
    """If cumulative streak loss is below min_streak_pct, don't trigger."""
    now = datetime.now(timezone.utc)
    # 5 consecutive losses but tiny amounts (total $5 on $10k balance = 0.05%, below 1%)
    rows = [
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -1.0,
         "exit_time": (now - timedelta(minutes=10)).isoformat(), "account_name": "ACG-1"},
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -1.0,
         "exit_time": (now - timedelta(minutes=20)).isoformat(), "account_name": "ACG-1"},
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -1.0,
         "exit_time": (now - timedelta(minutes=30)).isoformat(), "account_name": "ACG-1"},
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -1.0,
         "exit_time": (now - timedelta(minutes=40)).isoformat(), "account_name": "ACG-1"},
        {"broker_profile_id": "acct-1", "outcome": "loss", "pnl_usd": -1.0,
         "exit_time": (now - timedelta(minutes=50)).isoformat(), "account_name": "ACG-1"},
    ]
    sb = _FakeSupabase(rows)
    _patch_settings(monkeypatch)

    allowed, reason = check_signal_guards(
        {"rr_ratio": 2.0, "account_balance": 10000.0},
        sb,
        profile={"id": "acct-1", "name": "ACG-1"},
    )

    # $5 total loss on $10k = 0.05% < 1% threshold → should allow
    assert allowed is True
    assert reason is None
