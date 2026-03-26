from datetime import timezone
import pytz
from unittest.mock import MagicMock, patch
import asyncio

from src.services.prop_firm_tracker import get_ny_midnight_utc, PropFirmTracker
from src.services.mtm_guardian import MTMGuardian

def test_ny_midnight_utc():
    # Test that get_ny_midnight_utc returns a datetime with 00:00:00 in NY time
    result = get_ny_midnight_utc()
    ny_tz = pytz.timezone("America/New_York")
    ny_time = result.astimezone(ny_tz)
    
    assert ny_time.hour == 0
    assert ny_time.minute == 0
    assert ny_time.second == 0
    assert result.tzinfo == timezone.utc

def test_prop_firm_tracker_drawdown_denominator():
    mock_supabase = MagicMock()
    mock_settings = MagicMock()
    mock_settings.account_balance = 100000.0
    mock_settings.phase1_max_daily_loss = 5000.0
    mock_settings.phase1_max_drawdown_pct = 10.0
    mock_settings.funded_max_daily_loss = 5000.0
    mock_settings.funded_max_drawdown_pct = 10.0
    mock_settings.evaluation_mode = True
    mock_settings.evaluation_phase = "phase1"
    
    tracker = PropFirmTracker(mock_supabase, mock_settings)
    
    # Mock MTMGuardian and database responses
    with patch("src.services.mtm_guardian.MTMGuardian") as mock_mtm:
        mock_mtm_instance = mock_mtm.return_value
        mock_mtm_instance.get_real_time_equity.return_value = {
            "closed_pnl": 0.0,
            "floating_pnl": -5000.0,
            "current_equity": 95000.0
        }
        
        mock_response = MagicMock()
        mock_response.data = [{
            "daily_start_balance": 100000.0,
            "daily_high_water_mark": 100000.0,
            "max_historical_equity": 105000.0
        }]
        
        # Deep mock strategy to avoid mock attribute errors
        mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.limit.return_value.execute.return_value = mock_response
        
        # Test Phase 1
        metrics_phase1 = asyncio.run(tracker.get_current_metrics("test", "phase1"))
        assert metrics_phase1.trailing_drawdown_pct == 5.0
        
        # Test Funded 
        metrics_funded = asyncio.run(tracker.get_current_metrics("test", "funded"))
        assert round(metrics_funded.trailing_drawdown_pct, 2) == 9.52

def test_mtm_guardian_dynamic_jpy():
    mock_supabase = MagicMock()
    mock_settings = MagicMock()
    mock_settings.account_balance = 100000.0
    
    guardian = MTMGuardian(mock_supabase, mock_settings)
    
    mock_response = MagicMock()
    mock_response.data = [{
        "id": 1,
        "symbol": "USDJPY",
        "side": "buy",
        "entry": 150.0,
        "size": 1.0,
        "filled_entry_price": 150.0,
        "sl": 149.0,
        "tp": 151.0,
        "status": "active"
    }]
    
    guardian._apply_account_filter = MagicMock()
    guardian._apply_account_filter.return_value.execute.return_value = mock_response
    
    # Also mock the 'closed' query
    mock_closed_response = MagicMock()
    mock_closed_response.data = []
    
    mock_closed_query = MagicMock()
    mock_closed_query.execute.return_value = mock_closed_response
    
    mock_open_query = MagicMock()
    mock_open_query.execute.return_value = mock_response
    
    guardian._apply_account_filter.side_effect = [mock_closed_query, mock_open_query]
    
    with patch("src.adapters.market_data.get_current_price") as mock_price:
        mock_price.return_value = 149.0
        
        equity = guardian.get_real_time_equity("test")
        
        pnl = equity["floating_pnl"]
        # Expected: -666.67
        assert -667.0 < pnl < -666.0


# ─────────────────────────────────────────────────────────────────
# Phase 2 — Rubric Engine Council Pre-Gate Regressions
# ─────────────────────────────────────────────────────────────────

def _build_payload_with_composite(composite_target: float) -> dict:
    """
    Build a payload whose rubric composite_score approximates composite_target.
    We achieve this by engineering the 4 input dimensions exactly.
    
    Strategy: use departure_strength to dial in the final score
      departure=dep → d1 = dep*0.30
      return_strength=0 → d2 = 25.0
      premium_discount=1.0, side=buy → d3 = 25.0
      candles_to_return=11 → d4 = 0.0
      composite = dep*0.30 + 50
    
    So for composite=65: dep = (65-50)/0.30 = 50.0
    For composite=70: dep = (70-50)/0.30 = 66.67
    For composite=78: dep = (78-50)/0.30 = 93.33
    """
    dep = (composite_target - 50.0) / 0.30
    return {
        "symbol": "EURUSD",
        "side": "buy",
        "entry": 1.1,
        "sl": 1.09,
        "tp": 1.12,
        "size": 0.1,
        "departure_strength": dep,
        "return_strength": 0.0,
        "premium_discount": 1.0,
        "candles_to_return": 11,  # > 10 → bars_score = 0
        "session": 1,
        "sweep_candle_close": False,
    }


def test_council_pregate_composite_65_skips_council():
    """composite_score=65 → council is NOT called, fallback result returned."""
    from unittest.mock import patch, MagicMock
    from src.ai.trading_council import run_trading_council

    payload = _build_payload_with_composite(65.0)

    # Patch the 9-stage LLM pipeline stages so we can detect if they were called
    with patch("src.ai.trading_council._stage_market_analyst") as mock_stage:
        result = run_trading_council(payload)

    # Council should have been skipped — no LLM stage should fire
    mock_stage.assert_not_called()
    assert result["recommendation"] == "allow"  # fallback always allows
    assert "rubric gate" in result["memo"].lower() or "composite_score" in result["memo"].lower()


def test_council_pregate_composite_70_fires_in_shadow_mode():
    """composite_score=70 → council fires but recommendation is always 'allow' (shadow mode)."""
    from unittest.mock import patch, MagicMock
    from src.ai.trading_council import run_trading_council

    payload = _build_payload_with_composite(71.0)

    # Make the LLM stages return a REJECT decision
    with patch("src.ai.trading_council._stage_market_analyst", return_value="market ok"), \
         patch("src.ai.trading_council._stage_setup_analyst", return_value="setup ok"), \
         patch("src.ai.trading_council._stage_bull_researcher", return_value=("bull ok", "ALLOW")), \
         patch("src.ai.trading_council._stage_bear_researcher", return_value=("bear ok", "REJECT")), \
         patch("src.ai.trading_council._stage_research_manager", return_value="rm ok"), \
         patch("src.ai.trading_council._stage_aggressive_debater", return_value=("allow", "ALLOW")), \
         patch("src.ai.trading_council._stage_conservative_debater", return_value=("block", "REJECT")), \
         patch("src.ai.trading_council._stage_neutral_debater", return_value=("block", "REJECT")), \
         patch("src.ai.trading_council._stage_risk_judge", return_value=("REJECT", 85, "too risky")), \
         patch("src.ai.trading_council._from_cache", return_value=None), \
         patch("src.ai.trading_council._to_cache"):
        result = run_trading_council(payload)

    # Shadow mode: even though judge REJECTs, recommendation must be "allow"
    assert result["recommendation"] == "allow", \
        f"Shadow mode should override REJECT → allow, got: {result['recommendation']!r}"


def test_council_pregate_composite_78_can_block():
    """composite_score=78 → council fires in full mode, can block execution."""
    from unittest.mock import patch, MagicMock
    from src.ai.trading_council import run_trading_council

    payload = _build_payload_with_composite(78.0)

    # Make the LLM stages return a REJECT decision
    with patch("src.ai.trading_council._stage_market_analyst", return_value="market ok"), \
         patch("src.ai.trading_council._stage_setup_analyst", return_value="setup ok"), \
         patch("src.ai.trading_council._stage_bull_researcher", return_value=("bull ok", "ALLOW")), \
         patch("src.ai.trading_council._stage_bear_researcher", return_value=("bear ok", "REJECT")), \
         patch("src.ai.trading_council._stage_research_manager", return_value="rm ok"), \
         patch("src.ai.trading_council._stage_aggressive_debater", return_value=("allow", "ALLOW")), \
         patch("src.ai.trading_council._stage_conservative_debater", return_value=("block", "REJECT")), \
         patch("src.ai.trading_council._stage_neutral_debater", return_value=("block", "REJECT")), \
         patch("src.ai.trading_council._stage_risk_judge", return_value=("REJECT", 85, "too risky")), \
         patch("src.ai.trading_council._from_cache", return_value=None), \
         patch("src.ai.trading_council._to_cache"):
        result = run_trading_council(payload)

    # Full mode: REJECT must translate to "block"
    assert result["recommendation"] == "block", \
        f"Full mode (score>=78) should propagate REJECT as 'block', got: {result['recommendation']!r}"
