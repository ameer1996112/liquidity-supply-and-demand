"""
Test suite for prop firm protection features.

Tests:
1. MTM Guardian - Floating PnL tracking
2. Staleness Guard - Webhook latency protection
3. Consistency Analyzer - FTMO 40% rule

Run: pytest tests/test_prop_firm_guards.py -v
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock


class TestMTMGuardian:
    """Test MTM Guardian floating PnL calculations."""

    def test_mtm_calculates_floating_pnl(self):
        """Test that MTM Guardian includes open position losses."""
        from src.services.mtm_guardian import MTMGuardian

        # Mock Supabase client
        mock_supabase = Mock()
        mock_settings = Mock()
        mock_settings.account_balance = 10000.0
        mock_settings.trinity_max_daily_loss_pct = 4.0

        # Mock closed trades: -$300 loss
        mock_supabase.table().select().eq().gte().execute.return_value = Mock(
            data=[
                {"pnl_usd": -100},
                {"pnl_usd": -200},
            ]
        )

        # Mock open positions: -$250 floating loss
        mock_supabase.table().select().in_().execute.return_value = Mock(
            data=[
                {
                    "id": 1,
                    "symbol": "EURUSD",
                    "side": "buy",
                    "entry": 1.1000,
                    "size": 1.0,
                    "filled_entry_price": 1.1000,
                }
            ]
        )

        # Mock current price showing loss
        with patch("src.adapters.market_data.get_current_price", return_value=1.0975):
            mtm = MTMGuardian(mock_supabase, mock_settings)
            equity_data = mtm.get_real_time_equity()

            # Check calculations
            assert equity_data["closed_pnl"] == -300.0
            assert equity_data["floating_pnl"] < 0  # Has floating loss
            assert equity_data["current_equity"] < 9700  # Total equity down

    def test_mtm_triggers_kill_switch_at_threshold(self):
        """Test that MTM Guardian engages kill switch at -4% drawdown."""
        from src.services.mtm_guardian import MTMGuardian

        mock_supabase = Mock()
        mock_settings = Mock()
        mock_settings.account_balance = 10000.0
        mock_settings.trinity_max_daily_loss_pct = 4.0

        # Mock -4.5% loss (should trigger)
        mock_supabase.table().select().eq().gte().execute.return_value = Mock(
            data=[{"pnl_usd": -450}]
        )
        mock_supabase.table().select().in_().execute.return_value = Mock(data=[])

        mtm = MTMGuardian(mock_supabase, mock_settings)
        should_kill, reason = mtm.check_kill_switch()

        assert should_kill is True
        assert "4." in reason  # Should mention the percentage
        assert "MTM Kill Switch" in reason

    def test_mtm_allows_trade_under_threshold(self):
        """Test that MTM Guardian allows trades under -4% threshold."""
        from src.services.mtm_guardian import MTMGuardian

        mock_supabase = Mock()
        mock_settings = Mock()
        mock_settings.account_balance = 10000.0
        mock_settings.trinity_max_daily_loss_pct = 4.0

        # Mock -3% loss (should pass)
        mock_supabase.table().select().eq().gte().execute.return_value = Mock(
            data=[{"pnl_usd": -300}]
        )
        mock_supabase.table().select().in_().execute.return_value = Mock(data=[])

        mtm = MTMGuardian(mock_supabase, mock_settings)
        should_kill, reason = mtm.check_kill_switch()

        assert should_kill is False
        assert "OK" in reason


class TestStalenessGuard:
    """Test Staleness Guard webhook latency protection."""

    def test_staleness_rejects_old_signals(self):
        """Test that signals older than 5 seconds are rejected."""
        from src.core.guard_rails.staleness_guard import StalenessGuard

        guard = StalenessGuard(max_age_seconds=5)

        # Signal from 10 seconds ago
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        payload = {
            "symbol": "EURUSD",
            "entry": 1.1000,
            "bar_time": old_time,
        }

        passed, reason = guard.check(payload)

        assert passed is False
        assert "staleness" in reason.lower()
        assert "10" in reason  # Should mention age

    def test_staleness_accepts_fresh_signals(self):
        """Test that fresh signals (<5s) are accepted."""
        from src.core.guard_rails.staleness_guard import StalenessGuard

        guard = StalenessGuard(max_age_seconds=5)

        # Signal from 2 seconds ago
        fresh_time = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
        payload = {
            "symbol": "EURUSD",
            "entry": 1.1000,
            "bar_time": fresh_time,
        }

        with patch("src.adapters.market_data.get_current_price", return_value=1.1001):
            passed, reason = guard.check(payload)

        assert passed is True

    def test_staleness_rejects_price_deviation(self):
        """Test that signals with >3 pips price movement are rejected."""
        from src.core.guard_rails.staleness_guard import StalenessGuard

        guard = StalenessGuard(max_price_deviation_pips=3.0)

        # Fresh signal but price moved 5 pips
        fresh_time = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
        payload = {
            "symbol": "EURUSD",
            "entry": 1.1000,
            "bar_time": fresh_time,
        }

        # Current price is 5 pips away (0.0005)
        with patch("src.adapters.market_data.get_current_price", return_value=1.1005):
            passed, reason = guard.check(payload)

        assert passed is False
        assert "price deviation" in reason.lower() or "moved" in reason.lower()


class TestConsistencyAnalyzer:
    """Test Consistency Analyzer FTMO 40% rule."""

    def test_consistency_allows_safe_trades(self):
        """Test that trades under 40% limit are allowed."""
        from src.services.consistency_analyzer import ConsistencyAnalyzer

        mock_supabase = Mock()
        mock_settings = Mock()

        # Mock: Total profit $1000, best day $300 (30%)
        mock_supabase.table().select().eq().gte().order().execute.return_value = Mock(
            data=[
                {"pnl_usd": 100, "created_at": "2025-02-01T10:00:00Z"},
                {"pnl_usd": 200, "created_at": "2025-02-02T10:00:00Z"},
                {"pnl_usd": 300, "created_at": "2025-02-03T10:00:00Z"},  # Best day
                {"pnl_usd": 150, "created_at": "2025-02-04T10:00:00Z"},
                {"pnl_usd": 250, "created_at": "2025-02-05T10:00:00Z"},
            ]
        )

        consistency = ConsistencyAnalyzer(mock_supabase, mock_settings)
        breakdown = consistency.get_daily_profit_breakdown()

        assert breakdown["consistency_ok"] is True
        assert breakdown["best_day_pct"] == 30.0  # 300/1000
        assert breakdown["best_day_pct"] < 40.0

    def test_consistency_blocks_violation_trades(self):
        """Test that trades causing >40% best day are blocked."""
        from src.services.consistency_analyzer import ConsistencyAnalyzer

        mock_supabase = Mock()
        mock_settings = Mock()

        # Mock: Total profit $500, today already at $150
        mock_supabase.table().select().eq().gte().order().execute.return_value = Mock(
            data=[
                {"pnl_usd": 100, "created_at": "2025-02-01T10:00:00Z"},
                {"pnl_usd": 200, "created_at": "2025-02-02T10:00:00Z"},
                {"pnl_usd": 150, "created_at": f"{datetime.now(timezone.utc).date()}T10:00:00Z"},  # Today
                {"pnl_usd": 50, "created_at": "2025-02-04T10:00:00Z"},
            ]
        )

        consistency = ConsistencyAnalyzer(mock_supabase, mock_settings)

        # Try to add $100 profit (would make today $250 = 50% of $500)
        allowed, reason, multiplier = consistency.check_trade_consistency_risk(expected_profit=100.0)

        assert allowed is False
        assert "consistency violation" in reason.lower()
        assert multiplier == 0.0

    def test_consistency_reduces_risk_in_warning_zone(self):
        """Test that risk is reduced when approaching 40% limit."""
        from src.services.consistency_analyzer import ConsistencyAnalyzer

        mock_supabase = Mock()
        mock_settings = Mock()

        # Mock: Total profit $1000, today at $350 (35%)
        mock_supabase.table().select().eq().gte().order().execute.return_value = Mock(
            data=[
                {"pnl_usd": 200, "created_at": "2025-02-01T10:00:00Z"},
                {"pnl_usd": 100, "created_at": "2025-02-02T10:00:00Z"},
                {"pnl_usd": 350, "created_at": f"{datetime.now(timezone.utc).date()}T10:00:00Z"},  # Today 35%
                {"pnl_usd": 150, "created_at": "2025-02-04T10:00:00Z"},
                {"pnl_usd": 200, "created_at": "2025-02-05T10:00:00Z"},
            ]
        )

        consistency = ConsistencyAnalyzer(mock_supabase, mock_settings)

        # Try to add $50 profit (would make today 36%)
        allowed, reason, multiplier = consistency.check_trade_consistency_risk(expected_profit=50.0)

        assert allowed is True
        assert multiplier < 1.0  # Risk reduced
        assert ("warning" in reason.lower() or "danger" in reason.lower())


class TestPropFirmIntegration:
    """Integration tests for prop firm tracking."""

    def test_prop_firm_tracker_calculates_metrics(self):
        """Test PropFirmTracker correctly calculates all metrics."""
        from src.services.prop_firm_tracker import PropFirmTracker

        mock_supabase = Mock()
        mock_settings = Mock()
        mock_settings.account_balance = 10000.0
        mock_settings.phase1_max_daily_loss = 500.0
        mock_settings.phase1_max_drawdown_pct = 5.0
        mock_settings.evaluation_mode = True
        mock_settings.evaluation_phase = "phase1"

        # Mock: No snapshots yet (new day)
        mock_supabase.table().select().eq().gte().order().limit().execute.return_value = Mock(data=[])

        # Mock closed PnL: -$300
        mock_supabase.table().select().eq().gte().execute.return_value = Mock(
            data=[{"pnl_usd": -300}]
        )

        # Mock open positions: -$100 floating
        mock_supabase.table().select().in_().execute.return_value = Mock(data=[])

        tracker = PropFirmTracker(mock_supabase, mock_settings)

        # This would be async in real usage
        import asyncio
        metrics = asyncio.run(tracker.get_current_metrics())

        assert metrics.daily_start_balance == 10000.0
        assert metrics.daily_pnl_closed == -300.0
        assert metrics.current_equity == 9700.0
        assert metrics.daily_drawdown_pct == 3.0  # -300/10000
        assert metrics.daily_loss_breach is False  # Under $500 limit
        assert metrics.drawdown_breach is False  # Under 5% limit


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
