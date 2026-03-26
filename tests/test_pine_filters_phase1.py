"""
test_pine_filters_phase1.py — Unit tests for Phase 1 signal vetoes in worker.py

Tests: Sydney session veto, Friday 14:00 UTC cutoff, news proximity veto,
and per-account drawdown veto isolation.
"""

import pytest
from unittest.mock import patch, MagicMock

# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _base_payload(**kwargs):
    """Minimal valid payload, with overrides."""
    p = {
        "symbol": "EURUSD",
        "side": "buy",
        "entry": 1.1000,
        "sl": 1.0950,
        "tp": 1.1100,
        "size": 0.1,
        "score": 80,
        "grade": "A",
        "rr_ratio": 3.0,
    }
    p.update(kwargs)
    return p

def _get_fake_settings():
    class FakeSettings:
        pass
    s = FakeSettings()
    s.max_consecutive_losses = 0
    s.pine_circuit_breaker_losses = 100
    s.min_rr_ratio = 0
    s.pine_max_daily_loss_pct = 5.0
    s.monthly_max_loss_pct = 0.0
    s.weekly_max_loss_pct = 0.0
    s.enable_monthly_loss_limit = False
    s.pine_score_threshold = 0
    s.pine_min_score = 0
    s.pine_min_grade = None
    s.pine_required_grade = "NONE"
    s.pine_require_liq_swept = False
    s.pine_block_dead_zone = False
    s.pine_trading_start_hour = 0
    s.pine_trading_end_hour = 23
    s.pine_min_departure_strength = 0.0
    s.pine_min_return_strength = 0.0
    s.pine_departure_threshold = 0.0
    s.pine_return_threshold = 100.0
    s.account_balance = 100000.0
    s.risk_percent = 1.0
    s.daily_max_loss_pct = 5.0
    s.max_daily_loss_pct = 5.0
    s.mtm_guardian_enabled = False
    s.trinity_max_positions = 3
    s.trinity_correlation_timeout = 5
    return s

# ─────────────────────────────────────────────────────────────────
# Test 1: Sydney session veto
# ─────────────────────────────────────────────────────────────────

def test_sydney_session_veto_blocks_signal():
    """session=0 must be blocked at _validate_pine_filters level."""
    payload = _base_payload(session=0)

    with patch("src.worker.get_settings", return_value=_get_fake_settings()), \
         patch("src.worker._NEWS_FILTER"):
        
        from src.worker import _validate_pine_filters
        result = _validate_pine_filters(payload)

    assert result is not None, "Expected Sydney session veto, got None (no reject)"
    assert "sydney" in result.lower() or "session" in result.lower(), \
        f"Expected 'sydney' or 'session' in rejection: {result!r}"

# ─────────────────────────────────────────────────────────────────
# Test 2: Friday 14:00 UTC cutoff
# ─────────────────────────────────────────────────────────────────

def test_friday_cutoff_blocks_signal():
    """Friday at or after 14:00 UTC must be blocked."""
    import datetime
    fake_friday_14 = datetime.datetime(2026, 3, 27, 14, 0, 0, tzinfo=datetime.timezone.utc)
    payload = _base_payload(session=1)  # Not Sydney

    with patch("src.worker.get_settings", return_value=_get_fake_settings()), \
         patch("src.worker._NEWS_FILTER") as mock_nf:
        mock_nf.is_news_imminent.return_value = False

        from src.worker import _validate_pine_filters
        with patch("src.worker._get_now_utc") as mock_now:
            mock_now.return_value = fake_friday_14
            result = _validate_pine_filters(payload)

    assert result is not None, "Expected Friday cutoff veto, got None (no reject)"
    assert "friday" in result.lower(), f"Expected 'friday' in rejection: {result!r}"

# ─────────────────────────────────────────────────────────────────
# Test 3: News proximity veto
# ─────────────────────────────────────────────────────────────────

def test_news_proximity_veto_blocks_signal():
    """_NEWS_FILTER.is_news_imminent returning True must block the signal."""
    import datetime
    fake_tuesday = datetime.datetime(2026, 3, 24, 10, 0, 0, tzinfo=datetime.timezone.utc)
    payload = _base_payload(session=1, symbol="EURUSD")

    with patch("src.worker.get_settings", return_value=_get_fake_settings()), \
         patch("src.worker._NEWS_FILTER") as mock_nf:
        mock_nf.is_news_imminent.return_value = True  # Simulate news imminent

        from src.worker import _validate_pine_filters
        with patch("src.worker._get_now_utc") as mock_now:
            mock_now.return_value = fake_tuesday
            result = _validate_pine_filters(payload)

    assert result is not None, "Expected news veto, got None (no reject)"
    assert "news" in result.lower(), f"Expected 'news' in rejection: {result!r}"

# ─────────────────────────────────────────────────────────────────
# Test 4: Per-account drawdown veto is account-isolated
# ─────────────────────────────────────────────────────────────────

def test_drawdown_veto_blocks_one_account_not_other():
    """Per-account drawndown veto must block account A but NOT account B."""
    profile_a = {"name": "AccountA", "balance": 10000}
    profile_b = {"name": "AccountB", "balance": 10000}

    payload = _base_payload()
    s = _get_fake_settings()

    with patch("src.worker.supabase", new=MagicMock()), \
         patch("src.worker._get_account_positions_from_db", return_value=[]), \
         patch("src.worker._get_account_daily_pnl") as mock_daily_pnl:

        from src.worker import _run_account_guards

        # Account A: over drawdown threshold
        # We need extreme loss to guarantee Kill Switch trigger safely regardless of balance diffs.
        mock_daily_pnl.return_value = -99999.0
        result_a = _run_account_guards(payload.copy(), profile_a, s, current_equity_global=10000.0)

        # Account B: within limit
        mock_daily_pnl.return_value = -100.0
        result_b = _run_account_guards(payload.copy(), profile_b, s, current_equity_global=10000.0)

    assert result_a is not None, f"Expected account A to be blocked by drawdown veto, got None. (Loss: $510, Limit: $500)"
    assert "kill switch" in result_a.lower() or "drawdown" in result_a.lower() or "loss" in result_a.lower(), \
        f"Expected drawdown mention in: {result_a!r}"
    assert result_b is None, \
        f"Expected account B to pass drawdown check, got: {result_b!r}"
